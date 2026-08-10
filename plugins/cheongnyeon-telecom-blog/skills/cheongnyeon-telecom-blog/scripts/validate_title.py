#!/usr/bin/env python3
"""Validate a Cheongnyeon Telecom title before article generation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_article import compact, evidence_contains, normalize_unicode, read_allowed_evidence


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY = SKILL_DIR / "references" / "topic-idea-library.json"
DEFAULT_EVIDENCE = [
    SKILL_DIR / "references" / "brand_facts.md",
    SKILL_DIR / "references" / "temporary_information.md",
]

SOURCE_LEAKS = {
    "source-person": re.compile(r"(?:박건|박건희)"),
    "source-brand": re.compile(r"(?:달인폰센터|동탄도매폰센[터타]|도매폰센[터타])"),
    "source-location": re.compile(r"(?:동탄|화성|오산|평택|수원|용인|광교|분당|병점|남양읍|반월동|영천동)"),
    "source-number": re.compile(r"(?:누적\s*12만|12,?000대|상위\s*1\s*%|10년\s*차|7년\s*차|1억\s*배상|대당\s*4만|948화|0507-1319-0786|031-8015-0786)"),
}
VAGUE_PATTERNS = {
    "vague-proof": re.compile(r"확인할\s*근거"),
    "vague-consultation": re.compile(r"상담\s*과정을?\s*먼저\s*볼\s*이유"),
    "vague-price-priority": re.compile(r"가격보다.{0,12}먼저\s*볼\s*이유"),
    "vague-suspicion": re.compile(r"싼\s*곳이\s*의심될\s*때"),
    "brand-centric-inquiry": re.compile(r"(?:하루\s*\d[\d,]*\s*건\s*)?문의(?:가|량|의)?.{0,16}(?:남는|많은|몰리는|핵심|이유)"),
    "brand-centric-operation": re.compile(r"(?:문의.{0,12})?핵심은\s*운영|운영(?:을|이|의)?.{0,12}(?:핵심|진짜\s*이유)"),
}
CONCRETE_HOOK = re.compile(
    r"(?:사기|호구|호갱|계약|개통|할부|반납|요금제|부가서비스|시세표|수익구조|수수료|"
    r"단통법|공시지원금|위약금|번호이동|기기변경|생활의\s*달인|판매량|8,?000대|3년|"
    r"서비스센터|즉시\s*개통|후회|손해|절대|멈추|공통점|진짜\s*이유|비밀|\d+가지)"
)
NUMERIC_CLAIM = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:억\s*)?(?:원|만원|%|퍼센트|대|건|명|회|화|년|개월)")
STRONG_CLAIM = re.compile(
    r"(?:최저가|업계\s*최저|상위\s*\d+(?:\.\d+)?\s*%|전국\s*1위|광주.{0,12}1위|"
    r"판매량\s*1위|생활의\s*달인|SBS|100\s*%|무상\s*대행|즉시\s*개통|15\s*%)"
)


def add_issue(issues: list[dict[str, str]], severity: str, code: str, detail: str) -> None:
    issues.append({"severity": severity, "code": code, "detail": detail})


def validate_title(
    title: str,
    keyword: str,
    *,
    evidence: str,
    library: dict[str, object] | None = None,
    idea_reference_id: str = "",
    pattern_id: str = "",
) -> dict[str, object]:
    title = normalize_unicode(title).strip()
    keyword = normalize_unicode(keyword).strip()
    issues: list[dict[str, str]] = []
    compact_length = len(re.sub(r"\s+", "", title))
    keyword_count = title.count(keyword)

    if keyword_count != 1:
        add_issue(issues, "error", "title-keyword-count", f"정확 키워드 {keyword_count}회; 1회 필요")
    elif not title.lstrip("[공지] ").startswith(keyword):
        add_issue(issues, "error", "keyword-not-front", "메인키워드를 제목 첫부분에 배치해야 합니다.")

    if compact_length > 50:
        add_issue(issues, "error", "title-too-long", f"공백 제외 {compact_length}자; 50자 초과")
    elif compact_length > 40:
        add_issue(issues, "warning", "title-long", f"공백 제외 {compact_length}자; 자연스럽게 줄일 수 있는지 확인")
    if compact_length < 14:
        add_issue(issues, "warning", "title-short", f"공백 제외 {compact_length}자; 클릭 이유가 약할 수 있습니다.")

    for code, pattern in SOURCE_LEAKS.items():
        match = pattern.search(title)
        if match:
            add_issue(issues, "error", code, f"외부 아이디어 출처의 사실·고유명사 사용 금지: {match.group(0)}")
    for code, pattern in VAGUE_PATTERNS.items():
        match = pattern.search(title)
        if match:
            add_issue(issues, "error", code, f"구매자가 바로 이해할 구체 답으로 교체: {match.group(0)}")

    remainder = title.replace(keyword, "", 1)
    if not CONCRETE_HOOK.search(remainder):
        add_issue(issues, "error", "concrete-hook-missing", "키워드 뒤에 손실·질문·구체 조건·검증된 근거 중 하나가 필요합니다.")

    checked: set[str] = set()
    for pattern, code in ((NUMERIC_CLAIM, "unsupported-title-number"), (STRONG_CLAIM, "unsupported-title-claim")):
        for match in pattern.finditer(title):
            claim = match.group(0)
            normalized_claim = compact(claim)
            if normalized_claim in checked:
                continue
            checked.add(normalized_claim)
            if not evidence_contains(evidence, claim):
                add_issue(issues, "error", code, f"사용 가능한 청년통신 근거 없음: {claim}")

    selected_profile: dict[str, object] | None = None
    if library is not None and (idea_reference_id or pattern_id):
        articles = library.get("articles", [])
        if isinstance(articles, list) and idea_reference_id:
            selected_profile = next(
                (article for article in articles if isinstance(article, dict) and article.get("id") == idea_reference_id),
                None,
            )
            if selected_profile is None:
                add_issue(issues, "error", "idea-reference-missing", idea_reference_id)
        if selected_profile is not None and pattern_id and selected_profile.get("titlePatternId") != pattern_id:
            add_issue(
                issues,
                "error",
                "pattern-reference-mismatch",
                f"선택 글 패턴 {selected_profile.get('titlePatternId')}와 요청 패턴 {pattern_id}가 다릅니다.",
            )

    errors = sum(issue["severity"] == "error" for issue in issues)
    warnings = sum(issue["severity"] == "warning" for issue in issues)
    return {
        "status": "fail" if errors else "warning" if warnings else "pass",
        "metrics": {
            "nonWhitespaceChars": compact_length,
            "keywordCount": keyword_count,
            "errors": errors,
            "warnings": warnings,
        },
        "issues": issues,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--evidence", action="append", type=Path, default=[])
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--idea-reference-id", default="")
    parser.add_argument("--pattern-id", default="")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence_paths = args.evidence or DEFAULT_EVIDENCE
    evidence = read_allowed_evidence([str(path) for path in evidence_paths], date.today())
    library = json.loads(args.library.read_text(encoding="utf-8")) if args.library.exists() else None
    result = validate_title(
        args.title,
        args.keyword,
        evidence=evidence,
        library=library,
        idea_reference_id=args.idea_reference_id,
        pattern_id=args.pattern_id,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status: {result['status']}")
        print(f"공백 제외 제목 길이: {result['metrics']['nonWhitespaceChars']}")
        for issue in result["issues"]:
            print(f"[{issue['severity'].upper()}] {issue['code']}: {issue['detail']}")
    return 0 if result["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
