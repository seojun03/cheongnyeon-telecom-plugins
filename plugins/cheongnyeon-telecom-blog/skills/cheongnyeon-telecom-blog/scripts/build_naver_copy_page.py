#!/usr/bin/env python3
"""Wrap a reference-styled article fragment in a Naver-copy preview page."""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path


OUTPUT_DIR_ENV = "CHEONGNYEON_OUTPUT_DIR"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True, help="Article title.")
    parser.add_argument(
        "--article-html",
        required=True,
        type=Path,
        help="UTF-8 file containing exactly one fully styled <article>.",
    )
    parser.add_argument("--reference-url", default="", help="Master reference URL.")
    parser.add_argument("--reference-label", default="선택한 대표 레퍼런스", help="Reference label.")
    parser.add_argument("--output", type=Path, help="Output HTML path. Defaults to Desktop.")
    return parser.parse_args()


def slugify(title: str) -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣]+", "_", title, flags=re.UNICODE).strip("_")
    return value[:90] or "원고"


def windows_desktop_dir() -> Path:
    """Resolve the current Windows user's configured Desktop directory."""

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "Desktop")
        return Path(os.path.expandvars(str(value))).expanduser()
    except (ImportError, OSError):
        pass

    for variable in ("OneDrive", "USERPROFILE"):
        root = os.environ.get(variable, "").strip()
        if root:
            return Path(root).expanduser() / "Desktop"
    return Path.home() / "Desktop"


def default_output_dir(platform_name: str | None = None) -> Path:
    override = os.environ.get(OUTPUT_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if (platform_name or os.name) == "nt":
        return windows_desktop_dir()
    return Path.home() / "Desktop"


def paste_shortcut(platform_name: str | None = None) -> str:
    return "Ctrl+V" if (platform_name or os.name) == "nt" else "⌘V"


def output_path(title: str, requested: Path | None) -> Path:
    if requested is not None:
        return requested.expanduser().resolve()
    base = default_output_dir() / f"청년통신_{slugify(title)}.html"
    candidate = base
    index = 2
    while candidate.exists():
        candidate = base.with_name(f"{base.stem}_{index}{base.suffix}")
        index += 1
    return candidate


def article_fragment(raw: str) -> str:
    matches = re.findall(r"<article\b[^>]*>.*?</article>", raw, flags=re.IGNORECASE | re.DOTALL)
    if len(matches) != 1:
        raise ValueError("--article-html에는 <article> 하나만 있어야 합니다.")
    return matches[0].strip()


def use_reference_source_urls(article: str) -> str:
    """Use each registered Naver source URL for both preview and rich copy."""

    def rewrite(match: re.Match[str]) -> str:
        tag = match.group(0)
        source_match = re.search(
            r"\bdata-reference-source-url\s*=\s*([\"'])(?P<value>.*?)\1",
            tag,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not source_match:
            return tag
        source_url = html.unescape(source_match.group("value")).strip()
        if not source_url.startswith("https://"):
            raise ValueError("레퍼런스 이미지는 HTTPS 원본 URL이어야 합니다.")
        escaped_src = html.escape(source_url, quote=True)
        if re.search(r"\bsrc\s*=", tag, flags=re.IGNORECASE):
            tag = re.sub(
                r"\bsrc\s*=\s*([\"']).*?\1",
                f'src="{escaped_src}"',
                tag,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
        else:
            tag = re.sub(r"\s*/?>$", lambda ending: f' src="{escaped_src}"{ending.group(0)}', tag)
        if not re.search(r"\breferrerpolicy\s*=", tag, flags=re.IGNORECASE):
            tag = re.sub(
                r"\s*/?>$",
                lambda ending: f' referrerpolicy="no-referrer"{ending.group(0)}',
                tag,
            )
        return tag

    return re.sub(r"<img\b[^>]*>", rewrite, article, flags=re.IGNORECASE | re.DOTALL)


def build_page(
    title: str,
    article: str,
    reference_url: str,
    reference_label: str,
    platform_name: str | None = None,
) -> str:
    escaped_title = html.escape(title, quote=True)
    escaped_label = html.escape(reference_label, quote=True)
    escaped_url = html.escape(reference_url, quote=True)
    escaped_shortcut = html.escape(paste_shortcut(platform_name), quote=True)
    reference_line = (
        f'<a href="{escaped_url}" target="_blank" rel="noreferrer">{escaped_label}</a>'
        if reference_url
        else escaped_label
    )
    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>{escaped_title} · 청년통신 네이버용 HTML</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin:0; padding:132px 16px 48px; background:#ffffff; color:#3f4847; font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif; }}
    .copy-toolbar {{ position:fixed; z-index:20; top:0; left:0; right:0; display:flex; align-items:center; justify-content:center; gap:18px; padding:16px 20px; background:rgba(255,255,255,.97); border-bottom:1px solid #dce3e6; box-shadow:0 8px 24px rgba(25,42,52,.08); backdrop-filter:blur(12px); }}
    .copy-toolbar__text {{ min-width:0; }}
    .copy-toolbar__title {{ margin:0; font-size:15px; line-height:1.4; color:#202827; font-weight:800; }}
    .copy-toolbar__help {{ margin:3px 0 0; font-size:12px; line-height:1.45; color:#697573; }}
    .copy-button {{ flex:0 0 auto; min-width:190px; padding:14px 20px; border:0; border-radius:10px; background:#22cce7; color:#102325; font-size:15px; font-weight:900; cursor:pointer; box-shadow:0 8px 18px rgba(34,204,231,.24); }}
    .copy-button:hover {{ background:#16bdd7; }}
    .copy-button:focus-visible {{ outline:3px solid #101513; outline-offset:3px; }}
    .copy-button[data-state="done"] {{ background:#18a96b; color:#fff; }}
    .copy-button[data-state="error"] {{ background:#e53b48; color:#fff; }}
    #copy-status {{ position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }}
    .reference-card {{ width:100%; max-width:580px; margin:0 auto 18px; padding:16px 18px; border:1px solid #d9e1e3; border-radius:12px; background:#fff; box-shadow:0 6px 18px rgba(25,42,52,.05); }}
    .reference-card p {{ margin:0; font-size:12px; line-height:1.65; color:#66716f; }}
    .reference-card strong {{ color:#26302f; }}
    .reference-card a {{ color:#087f95; font-weight:800; text-decoration:none; }}
    #naver-copy-root {{ width:100%; }}
    @media (max-width:640px) {{
      body {{ padding:144px 0 0; background:#fff; }}
      .copy-toolbar {{ align-items:stretch; gap:10px; padding:12px; flex-direction:column; }}
      .copy-toolbar__text {{ text-align:center; }}
      .copy-toolbar__help {{ font-size:11px; }}
      .copy-button {{ width:100%; min-width:0; padding:12px 16px; }}
      .reference-card {{ margin:0; border-width:0 0 1px; border-radius:0; box-shadow:none; }}
    }}
  </style>
</head>
<body>
  <header class="copy-toolbar">
    <div class="copy-toolbar__text">
      <p class="copy-toolbar__title">청년통신 네이버 블로그 원고</p>
      <p class="copy-toolbar__help">네이버 본문에서 B·U가 켜져 있으면 먼저 끄기 → 버튼 클릭 → {escaped_shortcut}</p>
    </div>
    <button class="copy-button" id="copy-for-naver" type="button">네이버용 HTML 복사</button>
    <span id="copy-status" role="status" aria-live="polite"></span>
  </header>
  <aside class="reference-card" aria-label="레퍼런스 안내">
    <p><strong>참고한 대표글</strong> · {reference_line}</p>
    <p>이 안내 영역은 네이버 복사 대상에 포함되지 않습니다.</p>
  </aside>
  <main id="naver-copy-root">{article}</main>
  <script>
    (() => {{
      const button = document.getElementById('copy-for-naver');
      const root = document.getElementById('naver-copy-root');
      const status = document.getElementById('copy-status');
      function setState(state, message) {{
        button.dataset.state = state;
        button.textContent = message;
        status.textContent = message;
        window.setTimeout(() => {{ button.dataset.state = ''; button.textContent = '네이버용 HTML 복사'; }}, 2600);
      }}
      function prepareNaverCopyRoot() {{
        const copyRoot = root.cloneNode(true);
        copyRoot.removeAttribute('id');
        copyRoot.querySelectorAll('img[data-reference-source-url]').forEach((image) => {{
          image.setAttribute('src', image.getAttribute('data-reference-source-url'));
          image.setAttribute('referrerpolicy', 'no-referrer');
          image.removeAttribute('data-reference-source-url');
        }});
        copyRoot.querySelectorAll('p[data-preview-gap="true"]').forEach((spacer) => {{
          spacer.removeAttribute('aria-hidden');
          spacer.removeAttribute('data-preview-gap');
          spacer.setAttribute('data-naver-gap', 'true');
          spacer.setAttribute('style', 'margin:0;text-align:center;font-size:15px;line-height:1.8;color:transparent;');
          spacer.textContent = '\\u2060';
        }});
        copyRoot.querySelectorAll('*').forEach((element) => {{
          element.removeAttribute('aria-hidden');
          element.style.removeProperty('text-decoration');
          element.style.removeProperty('text-decoration-line');
          // Do not let a preview/container background become a text
          // highlight when SmartEditor converts the pasted fragment.
          if (!element.style.backgroundColor && !element.style.background) {{
            element.style.backgroundColor = 'transparent';
          }}
        }});
        // SmartEditor can inherit the destination toolbar's B/U state when
        // rich HTML is pasted. Wrap ordinary text runs with their intended
        // weight/decoration so an accidentally active B or U button cannot
        // spread formatting across the whole article. Strong and underline
        // runs are left untouched because they are deliberate master styles.
        const textWalker = document.createTreeWalker(copyRoot, NodeFilter.SHOW_TEXT);
        const textNodes = [];
        let textNode = textWalker.nextNode();
        while (textNode) {{ textNodes.push(textNode); textNode = textWalker.nextNode(); }}
        textNodes.forEach((node) => {{
          if (!(node.nodeValue || '').trim()) return;
          const parent = node.parentElement;
          if (!parent || parent.closest('strong,b,u')) return;
          let weight = '400';
          let styleParent = parent;
          while (styleParent && styleParent !== copyRoot) {{
            if (styleParent.style?.fontWeight) {{ weight = styleParent.style.fontWeight; break; }}
            styleParent = styleParent.parentElement;
          }}
          let background = 'transparent';
          let backgroundParent = parent;
          while (backgroundParent && backgroundParent !== copyRoot) {{
            if (backgroundParent.style?.backgroundColor) {{ background = backgroundParent.style.backgroundColor; break; }}
            backgroundParent = backgroundParent.parentElement;
          }}
          const run = document.createElement('span');
          run.style.fontWeight = weight;
          run.style.textDecoration = 'none';
          run.style.backgroundColor = background;
          parent.insertBefore(run, node);
          run.appendChild(node);
        }});
        copyRoot.querySelectorAll('p,div,span').forEach((element) => {{
          const text = (element.textContent || '').replaceAll('\\u00a0', '').trim();
          if (/^[-ㅡ—–]+$/u.test(text) && element.children.length === 0) element.remove();
        }});
        return copyRoot;
      }}
      function copyRenderedSelection(copyRoot) {{
        copyRoot.style.position = 'fixed'; copyRoot.style.left = '-100000px'; copyRoot.style.top = '0'; copyRoot.style.width = '580px';
        document.body.appendChild(copyRoot);
        const selection = window.getSelection(); const range = document.createRange();
        range.selectNodeContents(copyRoot); selection.removeAllRanges(); selection.addRange(range);
        const copied = document.execCommand('copy'); selection.removeAllRanges(); copyRoot.remove(); return copied;
      }}
      button.addEventListener('click', async () => {{
        const copyRoot = prepareNaverCopyRoot();
        const htmlValue = copyRoot.innerHTML.trim();
        const plainValue = root.innerText.replaceAll('\\u00a0','').replaceAll('\\u2060','').replace(/^\\s*[-ㅡ—–]+\\s*$/gmu,'').replace(/\\n{{3,}}/g,'\\n\\n').trim();
        try {{
          if (navigator.clipboard?.write && window.ClipboardItem) {{
            await navigator.clipboard.write([new ClipboardItem({{'text/html':new Blob([htmlValue],{{type:'text/html'}}),'text/plain':new Blob([plainValue],{{type:'text/plain'}})}})]);
          }} else if (!copyRenderedSelection(copyRoot)) throw new Error('rich-copy-unavailable');
          setState('done','복사 완료 · B·U 확인 후 {escaped_shortcut}');
        }} catch (error) {{
          try {{ if (!copyRenderedSelection(prepareNaverCopyRoot())) throw error; setState('done','복사 완료 · B·U 확인 후 {escaped_shortcut}'); }}
          catch {{ setState('error','복사 차단됨 · 브라우저 권한 확인'); }}
        }}
      }});
      window.__cheongnyeonCopyPreview = () => {{ const prepared = prepareNaverCopyRoot(); return {{ html:prepared.innerHTML, plain:prepared.innerText, underlineNodes:prepared.querySelectorAll('u,[data-reference-underline-role]').length, gapNodes:prepared.querySelectorAll('[data-naver-gap="true"]').length, tables:prepared.querySelectorAll('table').length }}; }};
    }})();
  </script>
</body>
</html>
'''


def main() -> int:
    args = parse_args()
    try:
        article = article_fragment(args.article_html.read_text(encoding="utf-8"))
        article = use_reference_source_urls(article)
        target = output_path(args.title, args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            build_page(args.title, article, args.reference_url, args.reference_label),
            encoding="utf-8",
        )
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"HTML 저장 실패: {exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
