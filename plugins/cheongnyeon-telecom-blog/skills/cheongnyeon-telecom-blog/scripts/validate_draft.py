#!/usr/bin/env python3
"""Validate publication-facing Cheongnyeon Telecom blog copy."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path


PLACEHOLDER_PATTERNS = {
    "visible-photo-placeholder": re.compile(r"\[\s*(?:사진|이미지)\s*\d*\s*:[^\]]+\]"),
    "photo-selection-instruction": re.compile(r"(?:사진|이미지).{0,30}선택해\s*주세요"),
    "related-image-placeholder": re.compile(r"관련\s*확인\s*이미지"),
    "missing-brand-placeholder": re.compile(r"\[\s*브랜드\s*정보\s*입력\s*필요\s*\]"),
    "media-null-placeholder": re.compile(r"(?:assetId|data-cheongnyeon-media)\s*[:=]\s*[\"']?(?:null|placeholder)"),
}

INTERNAL_PATTERNS = {
    "check-label": re.compile(r"\bCHECK\s*0?\d+\b", re.IGNORECASE),
    "internal-json-key": re.compile(
        r"\b(?:titlePromise|readerDecision|selectedFlow|referenceProfile|actionId|closingJob|reasoningMoves)\b"
    ),
}

AI_SIGNAL_PATTERNS = {
    "outline-leakage": re.compile(r"(?:첫|두|세)\s*번째\s*(?:점검|기준)은.{0,50}(?:일입니다|과정입니다)"),
    "mixed-metaphor": re.compile(r"(?:세\s*(?:답|기준|칸).{0,50}(?:방향을\s*가리|완성됩|채워|모여))"),
    "abstract-completion": re.compile(r"세\s*(?:기준|답|조건).{0,30}완성(?:됩|된|되었)"),
    "conclusion-recap": re.compile(r"(?:이|위)\s*세\s*(?:질문|가지|기준).{0,60}(?:확인|비교|보시면|됩니다)"),
    "seo-damage-example": re.compile(r"[가-힣]+\s+휴대폰\s+성지\s+전에"),
}

ABSTRACT_TERMS = (
    "기준",
    "조건",
    "판단",
    "기록",
    "방향",
    "전제",
    "대조",
    "항목",
)


def visible_text(raw: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"</?(?:p|div|section|article|h[1-6]|blockquote|tr|li|figure|figcaption)\b[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text).replace("\xa0", " ")


def remove_html_region_with_attribute(raw: str, attribute_pattern: str) -> str:
    pattern = re.compile(
        rf"<(?P<tag>[a-z][\w:-]*)\b(?=[^>]*{attribute_pattern})[^>]*>.*?</(?P=tag)>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    previous = None
    result = raw
    while result != previous:
        previous = result
        result = pattern.sub(" ", result)
    return result


def keyword_eligible_body(raw: str) -> str:
    """Return prose only: no title, headings, boxes, media, table, contact or CTA."""
    result = re.sub(r"<h[1-6]\b[^>]*>.*?</h[1-6]>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
    result = re.sub(r"<table\b[^>]*>.*?</table>", " ", result, flags=re.IGNORECASE | re.DOTALL)
    result = re.sub(r"<figure\b[^>]*>.*?</figure>", " ", result, flags=re.IGNORECASE | re.DOTALL)
    result = remove_html_region_with_attribute(
        result,
        r"data-cheongnyeon-box\s*=\s*[\"'][^\"']+[\"']",
    )
    result = remove_html_region_with_attribute(
        result,
        r"(?:data-cheongnyeon-closing\s*=\s*[\"']cta[\"']|data-cheongnyeon-closing-role\s*=\s*[\"']action[\"'])",
    )
    text = visible_text(result)
    # Markdown title/headings are not publication prose either.
    text = re.sub(r"(?m)^\s*#{1,6}\s+.*$", " ", text)
    return text


def title_keyword_count(raw: str, keyword: str) -> int:
    headings = re.findall(r"<h1\b[^>]*>(.*?)</h1>", raw, flags=re.IGNORECASE | re.DOTALL)
    if headings:
        return sum(visible_text(heading).count(keyword) for heading in headings)
    markdown_title = re.search(r"(?m)^\s*#\s+(.+)$", raw)
    return markdown_title.group(1).count(keyword) if markdown_title else 0


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def add_issue(issues: list[dict[str, str]], severity: str, code: str, detail: str) -> None:
    issues.append({"severity": severity, "code": code, "detail": detail})


def validate(
    raw: str,
    keyword: str | None,
    max_chars: int,
    min_keyword: int,
    max_keyword: int,
) -> dict[str, object]:
    text = visible_text(raw)
    issues: list[dict[str, str]] = []

    length = len(compact(text))
    if length > max_chars:
        add_issue(issues, "error", "body-too-long", f"공백 제외 {length}자; 상한 {max_chars}자")

    for code, pattern in PLACEHOLDER_PATTERNS.items():
        match = pattern.search(text)
        if match:
            add_issue(issues, "error", code, match.group(0)[:120])

    for code, pattern in INTERNAL_PATTERNS.items():
        match = pattern.search(text)
        if match:
            add_issue(issues, "error", code, match.group(0)[:120])

    if re.search(r"(?m)^\s*방문\s*후기\s*$\n\s*방문\s*후기\s*$", text):
        add_issue(issues, "error", "duplicate-production-label", "방문 후기 라벨이 연속으로 반복됨")

    for code, pattern in AI_SIGNAL_PATTERNS.items():
        match = pattern.search(text)
        if match:
            add_issue(issues, "warning", code, match.group(0)[:120])

    units = [
        re.sub(r"\s+", " ", part).strip()
        for part in re.split(r"(?<=[.!?。！？])\s+|\n+", text)
        if re.sub(r"\s+", " ", part).strip()
    ]
    normalized = [re.sub(r"[^0-9A-Za-z가-힣]", "", unit) for unit in units]
    duplicates = [value for value, count in Counter(normalized).items() if count > 1 and len(value) >= 12]
    if duplicates:
        add_issue(issues, "warning", "exact-meaning-block-repeat", f"동일 문장 후보 {len(duplicates)}개")

    abstract_heavy = []
    for unit in units:
        hits = sum(unit.count(term) for term in ABSTRACT_TERMS)
        if hits >= 4:
            abstract_heavy.append(unit[:120])
    if abstract_heavy:
        add_issue(issues, "warning", "abstract-chain", abstract_heavy[0])

    can_count = text.count("수 있습니다") + text.count("수 있는데")
    if can_count >= 5:
        add_issue(issues, "warning", "uniform-hedging", f"'수 있습니다' 계열 {can_count}회")

    section_markers = list(
        re.finditer(r"(?m)^\s*(?:#{1,6}\s*)?(\d+)[.)]\s+.+$", text)
    )
    if len(section_markers) >= 3:
        section_sizes = []
        for index, marker in enumerate(section_markers):
            end = section_markers[index + 1].start() if index + 1 < len(section_markers) else len(text)
            section_text = text[marker.end():end].strip()
            blocks = [block for block in re.split(r"\n+", section_text) if block.strip()]
            if (
                index == len(section_markers) - 1
                and blocks
                and re.search(r"(?:상담|문의|예약|결정하기\s*전)", blocks[-1])
            ):
                blocks = blocks[:-1]
            section_sizes.append(len(blocks))
        baseline = section_sizes[0]
        if (
            baseline >= 2
            and section_sizes[1] == baseline
            and all(size >= baseline for size in section_sizes[2:3])
        ):
            add_issue(
                issues,
                "warning",
                "section-symmetry",
                f"첫 3개 번호 절이 각각 최소 {baseline}개의 같은 문단 골격을 가질 가능성",
            )

    keyword_count = 0
    keyword_title_count = 0
    if keyword:
        keyword_text = keyword_eligible_body(raw)
        keyword_count = keyword_text.count(keyword)
        keyword_title_count = title_keyword_count(raw, keyword)
        if keyword_title_count not in (0, 1):
            add_issue(
                issues,
                "error",
                "title-keyword-count",
                f"제목의 '{keyword}' {keyword_title_count}회; 제목이 포함된 원고는 정확히 1회여야 함",
            )
        if keyword_count < min_keyword:
            add_issue(issues, "error", "keyword-underuse", f"본문의 '{keyword}' {keyword_count}회; 최소 {min_keyword}회")
        if keyword_count > max_keyword:
            add_issue(issues, "error", "keyword-overuse", f"본문의 '{keyword}' {keyword_count}회; 최대 {max_keyword}회")
        paragraphs = [
            re.sub(r"\s+", " ", paragraph).strip()
            for paragraph in re.split(r"\n+", keyword_text)
            if paragraph.strip()
        ]
        keyword_paragraphs = [
            (index, paragraph)
            for index, paragraph in enumerate(paragraphs)
            if keyword in paragraph
        ]
        repeated = next(
            (paragraph for _, paragraph in keyword_paragraphs if paragraph.count(keyword) > 1),
            None,
        )
        adjacent = any(
            right[0] - left[0] <= 1
            for left, right in zip(keyword_paragraphs, keyword_paragraphs[1:])
        )
        if repeated or adjacent:
            add_issue(
                issues,
                "error",
                "keyword-cluster",
                (repeated or "키워드 문단이 연속됨")[:120],
            )
        leading = [
            paragraph
            for _, paragraph in keyword_paragraphs
            if re.match(rf"^(?:[\"'“]\s*)?(?:실제\s+)?{re.escape(keyword)}", paragraph)
        ]
        if len(leading) > 1:
            add_issue(
                issues,
                "error",
                "keyword-forced-lead",
                f"정확 키워드로 시작하는 문단 {len(leading)}개",
            )
        noun_stack = re.search(
            rf"{re.escape(keyword)}\s+(?:상담|조건|견적|선택|비교|기준)(?:은|는|이|가|을|를|의|에서|에도|부터|까지|\s|[,.!?])",
            keyword_text,
        )
        if noun_stack:
            add_issue(issues, "error", "keyword-noun-stack", noun_stack.group(0)[:120])
        keyword_head = keyword.split()[-1]
        if re.search(r"(?:계약|개통|가입|구매|교체|번호이동)$", keyword_head):
            subject_mismatch = re.search(
                rf"(?:(?:서비스센터|수리|사후\s*지원).{{0,45}}(?:염두에\s+둔|받아야\s+하는|필요한)\s+{re.escape(keyword)}|(?:원하는\s+기종|기종을\s+(?:바로|곧바로)?\s*받아야).{{0,35}}\s+{re.escape(keyword)}|(?:기기\s*대금|통신요금|금액).{{0,45}}구분되지\s+않은\s+{re.escape(keyword)})",
                keyword_text,
            )
            if subject_mismatch:
                add_issue(
                    issues,
                    "error",
                    "keyword-semantic-mismatch",
                    subject_mismatch.group(0)[:120],
                )
        filler = re.search(
            rf"(?:실제\s+{re.escape(keyword)}\s+(?:상담|현장)|{re.escape(keyword)}(?:을|를)?\s+알아볼\s+때\s+질문을\s+미리|{re.escape(keyword)}.{{0,80}}앞의\s+기준을\s+같은\s+순서)",
            keyword_text,
        )
        if filler:
            add_issue(issues, "error", "keyword-filler-frame", filler.group(0)[:120])
        if keyword_count >= min_keyword and keyword_paragraphs:
            first_ratio = keyword_paragraphs[0][0] / max(len(paragraphs), 1)
            last_ratio = keyword_paragraphs[-1][0] / max(len(paragraphs), 1)
            if first_ratio > 0.45 or last_ratio < 0.55:
                add_issue(
                    issues,
                    "error",
                    "keyword-distribution",
                    "정확 키워드를 도입·본문·후반에 나누어 배치해야 함",
                )

    errors = sum(issue["severity"] == "error" for issue in issues)
    warnings = sum(issue["severity"] == "warning" for issue in issues)
    status = "fail" if errors else "warning" if warnings else "pass"
    return {
        "status": status,
        "metrics": {
            "nonWhitespaceChars": length,
            "titleKeywordCount": keyword_title_count,
            "bodyKeywordCount": keyword_count,
            "keywordCount": keyword_title_count + keyword_count,
        },
        "issues": issues,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="원고 파일 경로 또는 stdin의 '-'")
    parser.add_argument("--keyword", help="메인키워드 exact form")
    parser.add_argument("--max-chars", type=int, default=2000)
    parser.add_argument("--min-keyword", type=int, default=5, help="본문 exact keyword 최소 횟수")
    parser.add_argument("--max-keyword", type=int, default=6, help="본문 exact keyword 최대 횟수")
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.input == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.input).read_text(encoding="utf-8")

    result = validate(
        raw,
        args.keyword,
        args.max_chars,
        args.min_keyword,
        args.max_keyword,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status: {result['status']}")
        print(f"non-whitespace chars: {result['metrics']['nonWhitespaceChars']}")
        if args.keyword:
            print(f"title keyword count: {result['metrics']['titleKeywordCount']}")
            print(f"body keyword count: {result['metrics']['bodyKeywordCount']}")
        for issue in result["issues"]:
            print(f"- {issue['severity']}: {issue['code']} — {issue['detail']}")

    if result["status"] == "fail":
        return 1
    if result["status"] == "warning":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
