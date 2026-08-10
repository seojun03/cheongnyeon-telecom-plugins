from __future__ import annotations

import os
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "build_naver_copy_page.py"


def load_builder_module():
    spec = importlib.util.spec_from_file_location("cheongnyeon_build_naver_copy_page", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("빌더 모듈을 불러올 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildNaverCopyPageTests(unittest.TestCase):
    def test_windows_page_uses_ctrl_v_and_output_override(self) -> None:
        module = load_builder_module()
        page = module.build_page(
            "Windows 테스트",
            "<article><p>본문</p></article>",
            "",
            "선택한 대표 레퍼런스",
            platform_name="nt",
        )
        self.assertIn("버튼 클릭 → Ctrl+V", page)
        self.assertIn("복사 완료 · B·U 확인 후 Ctrl+V", page)
        self.assertNotIn("버튼 클릭 → ⌘V", page)

        with tempfile.TemporaryDirectory() as temp_dir:
            requested_output = Path(temp_dir) / "Windows Desktop"
            previous_override = os.environ.get("CHEONGNYEON_OUTPUT_DIR")
            try:
                os.environ["CHEONGNYEON_OUTPUT_DIR"] = str(requested_output)
                self.assertEqual(
                    module.default_output_dir(platform_name="nt"),
                    requested_output.resolve(),
                )
            finally:
                if previous_override is None:
                    os.environ.pop("CHEONGNYEON_OUTPUT_DIR", None)
                else:
                    os.environ["CHEONGNYEON_OUTPUT_DIR"] = previous_override

    def test_wraps_article_and_keeps_naver_copy_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "article.html"
            output = root / "result.html"
            fragment.write_text(
                '<article data-master-reference-id="warning-seller-lines-01">'
                '<p data-preview-gap="true" aria-hidden="true">&#8288;</p>'
                '<p>첫 번째 문장입니다. 두 번째 문장입니다.</p>'
                '<p><u data-reference-underline-role="hook-line">핵심</u></p>'
                '<img data-reference-source-url="https://example.com/image.jpg" src="local.jpg">'
                '</article>',
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--title",
                    "광주 휴대폰 테스트",
                    "--article-html",
                    str(fragment),
                    "--reference-url",
                    "https://blog.naver.com/cjdsus4444/223515173954",
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.stdout.strip(), str(output.resolve()))
            html = output.read_text(encoding="utf-8")
            self.assertIn("네이버용 HTML 복사", html)
            self.assertIn("ClipboardItem", html)
            self.assertIn("https://example.com/image.jpg", html)
            self.assertIn("data-master-reference-id=\"warning-seller-lines-01\"", html)
            self.assertIn("\\u2060", html)
            self.assertIn("첫 번째 문장입니다. 두 번째 문장입니다.", html)
            self.assertNotIn("첫 번째 문장입니다.<br", html)

    def test_output_override_uses_requested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requested_output = root / "recipient-desktop"
            fragment = root / "article.html"
            fragment.write_text("<article><p>공유 환경 테스트</p></article>", encoding="utf-8")
            env = os.environ.copy()
            env["CHEONGNYEON_OUTPUT_DIR"] = str(requested_output)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--title",
                    "공유 환경 테스트",
                    "--article-html",
                    str(fragment),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            output = Path(result.stdout.strip())
            self.assertEqual(output.parent, requested_output.resolve())
            self.assertTrue(output.is_file())

    def test_uses_reference_blog_image_without_local_files(self) -> None:
        source_url = "https://postfiles.pstatic.net/reference-image.jpg?type=w580"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "article.html"
            output = root / "result.html"
            fragment.write_text(
                '<article data-master-reference-id="authority-broadcast-reason-01">'
                f'<img data-reference-source-url="{source_url}" src="/missing/local/image.png">'
                "</article>",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--title",
                    "이미지 공유 테스트",
                    "--article-html",
                    str(fragment),
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            rendered = output.read_text(encoding="utf-8")
            self.assertIn(f'src="{source_url}"', rendered)
            self.assertIn(f'data-reference-source-url="{source_url}"', rendered)
            self.assertIn('referrerpolicy="no-referrer"', rendered)
            self.assertNotIn("/missing/local/image.png", rendered)
            self.assertFalse((root / "청년통신_레퍼런스사진").exists())


if __name__ == "__main__":
    unittest.main()
