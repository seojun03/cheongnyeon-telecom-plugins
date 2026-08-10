#!/usr/bin/env python3
"""Strict validator for publication-ready Cheongnyeon Telecom blog articles."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
SPECIAL_SPACES = re.compile(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]")
CONCRETE_TERMS = (
    "할부원금",
    "월 납부액",
    "할부 개월 수",
    "기기 할부금",
    "요금제",
    "유지 기간",
    "부가서비스",
    "반납 조건",
    "결합 할인",
    "견적서",
    "계약서",
    "신청서",
    "기종",
    "용량",
    "통신사",
)
ABSTRACT_TERMS = ("기준", "조건", "판단", "비교", "방향", "전제", "단위", "항목")
FIRST_PERSON = re.compile(r"(?:저는|제가|저희는|저희가|청년통신\s*대표)")
JUDGMENT = re.compile(r"(?:생각합니다|권합니다|권해\s*드립니다|보지\s*않습니다|설명드|판단합니다|중요하게\s*봅니다)")
IMPERATIVE_END = re.compile(
    r"(?:하세요|해\s*보세요|보세요|물어보세요|살펴보세요|요청하세요|확인하십시오|보십시오)[.!?\"'”’)]*$"
)

PRODUCTION_PATTERNS = {
    "photo-placeholder": re.compile(r"\[\s*(?:사진|이미지)(?:\s*\d+)?(?:\s*[:：][^\]]*)?\s*\]"),
    "photo-instruction": re.compile(r"(?:사진|이미지).{0,30}(?:선택해\s*주세요|배치해\s*주세요)"),
    "production-label": re.compile(r"(?m)^\s*(?:상담\s*현장|매장\s*운영|방문\s*후기|관련\s*확인\s*이미지)\s*$"),
    "internal-label": re.compile(r"\b(?:CHECK\s*\d+|FACT-\d+|TEMP-\d+|titlePromise|readerDecision|actionId)\b", re.I),
    "template-placeholder": re.compile(r"(?:\{\{[^{}]+\}\}|<\s*(?:입력|작성|추가)[^>]*>|\[\s*(?:입력|작성|추가)\s*필요[^\]]*\]|\bT(?:ODO|BD)\b)"),
}

UNSUPPORTED_CLAIMS = {
    "lowest-price-claim": re.compile(r"(?:최저가|가장\s*싼|업계\s*최저)"),
    "rank-claim": re.compile(r"(?:지역\s*)?(?:1위|상위\s*\d+(?:\.\d+)?\s*%)"),
    "sales-volume-claim": re.compile(r"(?:판매량|판매\s*실적|누적\s*판매)"),
    "inquiry-volume-claim": re.compile(r"(?:문의량|문의가\s*(?:많|몰리)|상담이\s*(?:많|몰리))"),
    "testimonial-claim": re.compile(r"(?:실제\s*고객|고객\s*후기|고객님이.{0,20}(?:말했|물었|찾아왔))"),
    "broadcast-award-claim": re.compile(r"(?:방송\s*출연|표창|수상|대상\s*수상)"),
    "career-claim": re.compile(r"(?:\d+\s*년\s*(?:차|경력)|경력\s*\d+\s*년)"),
    "competitor-price-claim": re.compile(r"(?:다른|타)\s*매장보다.{0,20}(?:싸|저렴|비싸)"),
    "reservation-benefit-claim": re.compile(r"(?:예약\s*혜택|예약\s*사은품)"),
    "stock-guarantee-claim": re.compile(r"(?:재고\s*보장|즉시\s*개통\s*보장|재고가\s*항상)"),
    "service-guarantee-claim": re.compile(r"(?:서비스|환불|배상).{0,12}(?:보장|100\s*%)"),
}

NUMERIC_CLAIM = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:억\s*)?(?:원|만원|%|퍼센트|대|건|명|회|년|개월)")
SENSITIVE_CONTEXT = re.compile(
    r"(?:가격|할인|지원금|판매|문의|경력|보장|최저|상위|순위|수상|방송|혜택|재고|개통|유지|약정|반납|결합)"
)

KEYWORD_ROLE_PATTERNS = {
    "reader-situation": re.compile(r"(?:앞두|알아보|고민|견적을\s*받|고르|바꾸려|찾고\s*있)"),
    "direct-answer": re.compile(r"(?:답은|핵심은|먼저\s*(?:볼|물어볼)|바로|질문은)"),
    "cause": re.compile(r"(?:달라지|때문|따라|영향|원인|반면|결과)"),
    "document": re.compile(r"(?:계약서|견적서|신청서|서류|기재|적혀)"),
    "speaker-judgment": re.compile(r"(?:저는|제가|저희는|저희가|생각합니다|권합니다|설명드|중요하게\s*봅니다)"),
}

BRAND_PROOF_PATTERNS = {
    "생활의 달인 출연": re.compile(r"생활의\s*달인.{0,50}(?:출연|휴대폰\s*달인)"),
    "연간 8,000대 이상 판매": re.compile(r"(?:연간?|1년에)\s*8,?000대\s*이상\s*판매"),
    "3년간 서비스센터 무상 대행": re.compile(r"구매\s*후\s*3년간.{0,40}서비스센터.{0,20}(?:무상|무료)\s*대행"),
    "사용량 기반 맞춤 요금제 상담": re.compile(r"사용량.{0,20}맞춤형?.{0,10}요금제.{0,10}(?:상담|컨설팅)"),
    "최신 기종 즉시 개통": re.compile(r"최신\s*기종.{0,20}(?:대기\s*없이\s*)?즉시\s*개통"),
}
FIXED_PHONE = re.compile(r"010\s*-\s*8489\s*-\s*4440")
FIXED_RESERVATION = re.compile(r"네이버\s*예약")
EXTERNAL_IDEA_SOURCE_LEAKS = {
    "external-idea-person": re.compile(r"(?:박건|박건희)"),
    "external-idea-brand": re.compile(r"(?:달인폰센터|동탄도매폰센[터타]|도매폰센[터타])"),
    "external-idea-location": re.compile(r"(?:동탄|화성|오산|평택|수원|용인|광교|분당|병점|남양읍|반월동|영천동)"),
    "external-idea-claim": re.compile(
        r"(?:누적\s*12만|12,?000대|상위\s*1\s*%|10년\s*차|7년\s*차|1억\s*배상|대당\s*4만|948화|0507-1319-0786|031-8015-0786)"
    ),
}
BUYER_HOOK_TERMS = re.compile(
    r"(?:기기값|할부원금|할부|월\s*납부액|요금제|요금|청구|계약|부가서비스|반납|지원금|개통|위약금|결합|재고|수리|서비스센터)"
)
BRAND_HOOK_TERMS = re.compile(r"(?:문의|판매량|운영|박리다매|매장\s*확장|표창|수상)")
AI_CLOSING_PATTERNS = {
    "abstract-match-closing": re.compile(
        r"(?:답변|대답|설명|안내|조건|상담\s*내용)(?:과|와)\s*"
        r"(?:서류|계약서|견적서|신청서)(?:가|이|를|을)?\s*"
        r"(?:맞(?:을\s*때|으면|는지|춘\s*뒤)|같(?:을\s*때|으면|은지))"
    ),
    "generic-late-decision-closing": re.compile(r"(?:결정|판단)(?:하셔?도|해도)\s*늦지\s*않습니다"),
}


def normalize_unicode(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = SPECIAL_SPACES.sub(" ", value)
    return ZERO_WIDTH.sub("", value)


def visible_text(value: str) -> str:
    value = normalize_unicode(value)
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"</?(?:p|div|section|article|h[1-6]|blockquote|li|tr|figure|figcaption)\b[^>]*>", "\n\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"(?m)^\s*#{1,6}\s*", "", value)
    value = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"(?:\*\*|__|~~|`)", "", value)
    return normalize_unicode(value)


def compact(value: str) -> str:
    return re.sub(r"\s+", "", visible_text(value))


def reference_role_texts(raw: str, role: str) -> list[str]:
    """Extract visible text from exact reconstruction role elements."""
    pattern = re.compile(
        rf"<(?P<tag>[a-z][\w:-]*)\b(?=[^>]*data-reference-role\s*=\s*[\"']{re.escape(role)}[\"'])[^>]*>.*?</(?P=tag)>",
        flags=re.I | re.S,
    )
    return [re.sub(r"\s+", " ", visible_text(match.group(0))).strip() for match in pattern.finditer(raw)]


def extract_article(raw: str, explicit_title: str | None = None) -> tuple[str, str]:
    raw = normalize_unicode(raw).strip()
    if explicit_title:
        # The generated Naver copy page wraps the article in a UI shell. When
        # validating that final page, inspect only the copy target so the
        # browser title, toolbar, and reference card are not counted as body
        # prose (or as extra keyword occurrences).
        copy_root = re.search(
            r'<main\b[^>]*\bid\s*=\s*["\']naver-copy-root["\'][^>]*>(.*?)</main>',
            raw,
            flags=re.I | re.S,
        )
        body = copy_root.group(1) if copy_root else raw
        return normalize_unicode(explicit_title).strip(), body.strip()

    html_title = re.search(r"<h1\b[^>]*>(.*?)</h1>", raw, flags=re.I | re.S)
    if html_title:
        title = visible_text(html_title.group(1)).strip()
        body = raw[: html_title.start()] + raw[html_title.end() :]
        return title, body.strip()

    markdown_title = re.search(r"(?m)^\s*#\s+(.+?)\s*$", raw)
    if markdown_title:
        title = markdown_title.group(1).strip()
        body = raw[: markdown_title.start()] + raw[markdown_title.end() :]
        return title, body.strip()

    lines = raw.split("\n")
    for index, line in enumerate(lines):
        if line.strip():
            return line.strip(), "\n".join(lines[index + 1 :]).strip()
    return "", ""


def paragraphs(body: str) -> list[str]:
    text = normalize_unicode(body)
    text = re.sub(r"</?(?:p|div|section|article|h[1-6]|blockquote|li)\b[^>]*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    parts = re.split(r"\n\s*\n+", text)
    return [re.sub(r"\s+", " ", visible_text(part)).strip() for part in parts if visible_text(part).strip()]


def keyword_eligible_paragraphs(body: str) -> list[str]:
    """Return prose used for exact-keyword counting, excluding non-body roles."""
    result = normalize_unicode(body)
    result = re.sub(r"<(?:table|figure|figcaption)\b[^>]*>.*?</(?:table|figure|figcaption)>", " ", result, flags=re.I | re.S)
    role_region = re.compile(
        r"<(?P<tag>[a-z][\w:-]*)\b(?=[^>]*data-cheongnyeon-role\s*=\s*[\"'](?:cta|contact|map|source|caption|media|proof)[\"'])[^>]*>.*?</(?P=tag)>",
        flags=re.I | re.S,
    )
    previous = None
    while previous != result:
        previous = result
        result = role_region.sub(" ", result)

    excluded_heading = re.compile(r"^(?:문의|예약|연락처|주소|지도|출처|사진\s*설명|캡션|CTA)(?:\s|$)", re.I)
    explicit_cta = re.compile(r"(?:문의|예약|전화|카카오톡|연락|상담\s*신청).{0,35}(?:주세요|바랍니다|가능합니다|하세요|드립니다)")
    contact_line = re.compile(r"(?:\b0\d{1,2}-\d{3,4}-\d{4}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})")
    eligible: list[str] = []
    for paragraph in paragraphs(result):
        without_heading = re.sub(r"^#{1,6}\s*", "", paragraph).strip()
        proof_hits = sum(bool(pattern.search(without_heading)) for pattern in BRAND_PROOF_PATTERNS.values())
        if proof_hits >= 4:
            continue
        if excluded_heading.search(without_heading):
            continue
        if explicit_cta.search(without_heading):
            continue
        if contact_line.search(without_heading):
            continue
        eligible.append(paragraph)
    return eligible


def add_issue(
    issues: list[dict[str, object]],
    severity: str,
    code: str,
    detail: str,
    paragraph: int | None = None,
) -> None:
    item: dict[str, object] = {"severity": severity, "code": code, "detail": detail}
    if paragraph is not None:
        item["paragraph"] = paragraph
    issues.append(item)


def read_allowed_evidence(paths: Iterable[str], today: date) -> str:
    allowed_blocks: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        text = normalize_unicode(path.read_text(encoding="utf-8"))
        blocks = re.split(r"(?m)(?=^##\s+)", text)
        for block in blocks:
            if not re.search(r"(?m)^-?\s*상태\s*:\s*사용\s*가능\s*$", block):
                continue
            expiry = re.search(r"(?m)^-?\s*(?:종료일|만료일)\s*:\s*(\d{4}-\d{2}-\d{2})", block)
            if expiry:
                try:
                    if datetime.strptime(expiry.group(1), "%Y-%m-%d").date() < today:
                        continue
                except ValueError:
                    continue
            allowed_lines: list[str] = []
            capture = False
            for line in block.splitlines():
                field = re.match(r"^\s*-\s*([^:]+)\s*:\s*(.*)$", line)
                if field:
                    capture = field.group(1).strip() in {"정확한 사실", "사용할 수 있는 표현"}
                    if capture and field.group(2).strip():
                        allowed_lines.append(field.group(2).strip())
                    continue
                if capture and (line.startswith("  ") or line.startswith("\t")) and line.strip():
                    allowed_lines.append(line.strip())
                else:
                    capture = False
            if allowed_lines:
                allowed_blocks.append("\n".join(allowed_lines))
    return normalize_unicode("\n".join(allowed_blocks))


def evidence_contains(evidence: str, claim: str) -> bool:
    return bool(evidence) and compact(claim) in compact(evidence)


def title_answer_count(title: str) -> int | None:
    matches = re.findall(r"(?<!\d)(\d{1,2})\s*(?:가지|개|단계)(?!\d)", normalize_unicode(title))
    if not matches:
        return None
    values = {int(value) for value in matches}
    return values.pop() if len(values) == 1 else -1


def numbered_section_markers(body: str) -> list[tuple[int, int, str]]:
    normalized = normalize_unicode(body)
    pattern = re.compile(r"(?m)^\s*(?:#{1,6}\s*)?(\d{1,2})\s*[.)]\s+(.+?)\s*$")
    markers = [(match.start(), int(match.group(1)), match.group(2)) for match in pattern.finditer(normalized)]
    if markers or not re.search(r"<h[1-6]\b", normalized, flags=re.I):
        return markers

    # Rich Naver-copy drafts use real HTML headings, so their visible text
    # never starts at the beginning of a raw source line. Read the heading
    # elements directly instead of incorrectly reporting that numbered
    # sections are missing.
    heading_pattern = re.compile(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", flags=re.I | re.S)
    html_markers: list[tuple[int, int, str]] = []
    for match in heading_pattern.finditer(normalized):
        heading = visible_text(match.group(1)).strip()
        number_match = re.match(r"(\d{1,2})\s*[.)]\s*(.+)", heading, flags=re.S)
        if number_match:
            html_markers.append((match.start(), int(number_match.group(1)), number_match.group(2).strip()))
    return html_markers


def section_signatures(body: str, markers: list[tuple[int, int, str]]) -> list[tuple[int, bool, bool, int]]:
    signatures: list[tuple[int, bool, bool, int]] = []
    for index, (start, _, heading) in enumerate(markers):
        end = markers[index + 1][0] if index + 1 < len(markers) else len(body)
        section_text = body[start:end]
        section_paragraphs = paragraphs(section_text)
        prose = section_paragraphs[1:] if len(section_paragraphs) > 1 else []
        last = prose[-1] if prose else ""
        sentence_count = len(re.findall(r"[.!?](?:\s|$)", visible_text(section_text)))
        signatures.append((len(prose), "?" in heading, bool(IMPERATIVE_END.search(last)), sentence_count))
    return signatures


def keyword_role_coverage(keyword_paragraphs: list[str]) -> tuple[int, list[str]]:
    candidates = [
        [role for role, pattern in KEYWORD_ROLE_PATTERNS.items() if pattern.search(paragraph)]
        for paragraph in keyword_paragraphs
    ]
    matched_role_to_paragraph: dict[str, int] = {}

    def assign(paragraph_index: int, seen: set[str]) -> bool:
        for role in candidates[paragraph_index]:
            if role in seen:
                continue
            seen.add(role)
            owner = matched_role_to_paragraph.get(role)
            if owner is None or assign(owner, seen):
                matched_role_to_paragraph[role] = paragraph_index
                return True
        return False

    for index in range(len(candidates)):
        assign(index, set())
    missing = [role for role in KEYWORD_ROLE_PATTERNS if role not in matched_role_to_paragraph]
    return len(matched_role_to_paragraph), missing


def validate_article(
    raw: str,
    keyword: str,
    *,
    explicit_title: str | None = None,
    min_chars: int = 1400,
    max_chars: int = 1800,
    evidence: str = "",
    allow_table: bool = False,
    require_fixed_components: bool = False,
) -> dict[str, object]:
    keyword = normalize_unicode(keyword).strip()
    title, body = extract_article(raw, explicit_title)
    title_text = visible_text(title).strip()
    body_text = visible_text(body).strip()
    body_paragraphs = paragraphs(body)
    eligible_paragraphs = keyword_eligible_paragraphs(body)
    issues: list[dict[str, object]] = []

    if not title_text:
        add_issue(issues, "error", "missing-title", "제목을 찾을 수 없습니다.")
    if not body_text:
        add_issue(issues, "error", "missing-body", "본문을 찾을 수 없습니다.")

    closing_text = body_text[int(len(body_text) * 0.65) :]
    for code, pattern in AI_CLOSING_PATTERNS.items():
        match = pattern.search(closing_text)
        if match:
            add_issue(
                issues,
                "error",
                code,
                f"마스터형 구체 마무리로 다시 써야 하는 AI식 압축 결론: {match.group(0)}",
            )

    title_and_body = f"{title_text}\n{body_text}"
    for code, pattern in EXTERNAL_IDEA_SOURCE_LEAKS.items():
        match = pattern.search(title_and_body)
        if match:
            add_issue(issues, "error", code, f"외부 주제·제목 아이디어 출처의 사실·고유명사 사용 금지: {match.group(0)}")

    hook_lines = reference_role_texts(body, "hook-line")
    if len(hook_lines) >= 2:
        buyer_hook_count = sum(bool(BUYER_HOOK_TERMS.search(line)) for line in hook_lines)
        brand_hook_count = sum(bool(BRAND_HOOK_TERMS.search(line)) for line in hook_lines)
        if brand_hook_count >= 2 and buyer_hook_count < 2:
            add_issue(
                issues,
                "error",
                "brand-centric-hook",
                "첫 후킹이 휴대폰 구매자의 기기값·요금·계약 문제가 아니라 매장의 문의·판매·운영 관심사로 구성됐습니다.",
            )

    brand_proof_found = {label: bool(pattern.search(body_text)) for label, pattern in BRAND_PROOF_PATTERNS.items()}
    fixed_phone_found = bool(FIXED_PHONE.search(body_text))
    fixed_reservation_found = bool(FIXED_RESERVATION.search(body_text))
    if require_fixed_components and body_text:
        if not any(brand_proof_found.values()):
            add_issue(issues, "error", "brand-proof-missing", "제목과 가까운 현재 신뢰 근거를 최소 하나 사용해야 합니다.")

        ending_body = body_text[int(len(body_text) * 0.70) :]
        if not fixed_phone_found:
            add_issue(issues, "error", "fixed-phone-missing", "대표 전화 010-8489-4440이 없습니다.")
        elif not FIXED_PHONE.search(ending_body):
            add_issue(issues, "error", "fixed-phone-not-at-end", "대표 전화는 본문 뒤 30%의 고정 마감 블록에 있어야 합니다.")
        if not fixed_reservation_found:
            add_issue(issues, "error", "fixed-reservation-missing", "네이버 예약 안내가 없습니다.")
        elif not FIXED_RESERVATION.search(ending_body):
            add_issue(issues, "error", "fixed-reservation-not-at-end", "네이버 예약은 본문 뒤 30%의 고정 마감 블록에 있어야 합니다.")

    total_chars = len(re.sub(r"\s+", "", title_text + body_text))
    if total_chars < min_chars:
        add_issue(issues, "error", "article-too-short", f"공백 제외 {total_chars}자; 최소 {min_chars}자")
    if total_chars > max_chars:
        add_issue(issues, "error", "article-too-long", f"공백 제외 {total_chars}자; 최대 {max_chars}자")

    title_keyword_count = title_text.count(keyword)
    body_keyword_count = sum(paragraph.count(keyword) for paragraph in eligible_paragraphs)
    if title_keyword_count != 1:
        add_issue(issues, "error", "title-keyword-count", f"제목의 정확 키워드 {title_keyword_count}회; 1회 필요")
    if body_keyword_count != 5:
        add_issue(issues, "error", "body-keyword-count", f"본문의 정확 키워드 {body_keyword_count}회; 5회 필요")

    keyword_indexes: list[int] = []
    keyword_paragraph_texts: list[str] = []
    for index, paragraph in enumerate(eligible_paragraphs):
        count = paragraph.count(keyword)
        if count:
            keyword_indexes.append(index)
            keyword_paragraph_texts.append(paragraph)
        if count > 1:
            add_issue(issues, "error", "keyword-repeat-in-paragraph", f"한 문단에 정확 키워드 {count}회", index + 1)

    for left, right in zip(keyword_indexes, keyword_indexes[1:]):
        if right - left == 1:
            add_issue(issues, "error", "adjacent-keyword-paragraphs", "정확 키워드가 들어간 문단이 연속합니다.", right + 1)
    if len(keyword_indexes) == 5 and eligible_paragraphs:
        if keyword_indexes[0] / len(eligible_paragraphs) > 0.35 or keyword_indexes[-1] / len(eligible_paragraphs) < 0.65:
            add_issue(issues, "error", "keyword-distribution", "정확 키워드를 도입·중간·후반에 분산해야 합니다.")
        coverage, missing_roles = keyword_role_coverage(keyword_paragraph_texts)
        if coverage < 5:
            add_issue(
                issues,
                "error",
                "keyword-role-coverage",
                f"서로 다른 정보 역할 {coverage}/5개; 부족: {', '.join(missing_roles)}",
            )

    expected_sections = title_answer_count(title_text)
    markers = numbered_section_markers(body)
    section_numbers = [number for _, number, _ in markers]
    if expected_sections == -1:
        add_issue(issues, "error", "ambiguous-title-count", "제목에 서로 다른 답 개수가 함께 들어 있습니다.")
    elif expected_sections is not None:
        if section_numbers != list(range(1, expected_sections + 1)):
            add_issue(
                issues,
                "error",
                "title-section-count",
                f"제목은 {expected_sections}개를 약속하지만 번호 절은 {section_numbers or '없음'}입니다.",
            )

    if "이것" in title_text:
        intro = " ".join(body_paragraphs[:2])
        if not any(term in intro for term in CONCRETE_TERMS):
            add_issue(issues, "error", "this-not-revealed", "제목의 '이것'을 도입 첫 두 문단에서 구체 명사로 공개해야 합니다.")

    if not FIRST_PERSON.search(body_text):
        add_issue(issues, "error", "speaker-missing", "청년통신 대표의 1인칭 화자가 본문에 없습니다.")
    elif not JUDGMENT.search(body_text):
        add_issue(issues, "warning", "speaker-judgment-weak", "1인칭 소개는 있으나 대표의 판단이나 입장이 약합니다.")

    for code, pattern in PRODUCTION_PATTERNS.items():
        match = pattern.search(body)
        if match:
            add_issue(issues, "error", code, visible_text(match.group(0))[:120])

    table_present = bool(re.search(r"(?m)^\s*\|.+\|\s*$", body) and re.search(r"(?m)^\s*\|?\s*:?-{3,}", body)) or bool(re.search(r"<table\b", body, re.I))
    if table_present and not allow_table:
        add_issue(issues, "error", "table-present", "엄격 기본 모드에서는 표를 본문에 넣지 않습니다.")
    if re.search(r"(?m)^\s*(?:#{1,6}\s*)?(?:요약|한눈에\s*정리|정리표)\s*$", body):
        add_issue(issues, "error", "summary-repeat-signal", "본문을 되풀이하는 요약 블록 가능성이 있습니다.")

    for index, paragraph in enumerate(body_paragraphs):
        abstract_hits = sum(paragraph.count(term) for term in ABSTRACT_TERMS)
        if abstract_hits >= 4 and not any(term in paragraph for term in CONCRETE_TERMS):
            add_issue(issues, "warning", "abstract-chain", paragraph[:120], index + 1)

    imperative_count = sum(bool(IMPERATIVE_END.search(sentence.strip())) for sentence in re.split(r"(?<=[.!?])\s+", body_text))
    if imperative_count >= 5:
        add_issue(issues, "warning", "instruction-heavy", f"지시형 종결 {imperative_count}개; 원인과 결과 설명을 늘려야 합니다.")

    for code, pattern in UNSUPPORTED_CLAIMS.items():
        for match in pattern.finditer(body_text):
            claim = match.group(0)
            if not evidence_contains(evidence, claim):
                add_issue(issues, "error", code, f"사용 가능한 근거 없음: {claim[:100]}")

    for match in NUMERIC_CLAIM.finditer(body_text):
        claim = match.group(0)
        unit_is_money_or_rate = bool(re.search(r"(?:원|만원|%)\s*$", claim))
        context = body_text[max(0, match.start() - 35) : min(len(body_text), match.end() + 35)]
        if (unit_is_money_or_rate or SENSITIVE_CONTEXT.search(context)) and not evidence_contains(evidence, claim):
            add_issue(issues, "error", "unsupported-numeric-claim", f"사용 가능한 근거 없음: {claim}")

    errors = sum(issue["severity"] == "error" for issue in issues)
    warnings = sum(issue["severity"] == "warning" for issue in issues)
    status = "fail" if errors else "warning" if warnings else "pass"
    return {
        "status": status,
        "metrics": {
            "nonWhitespaceChars": total_chars,
            "titleKeywordCount": title_keyword_count,
            "bodyKeywordCount": body_keyword_count,
            "paragraphCount": len(body_paragraphs),
            "keywordEligibleParagraphCount": len(eligible_paragraphs),
            "numberedSectionCount": len(markers),
            "brandProofCount": sum(brand_proof_found.values()),
            "fixedProofCount": sum(brand_proof_found.values()),
            "fixedPhoneFound": fixed_phone_found,
            "fixedReservationFound": fixed_reservation_found,
            "hookLineCount": len(hook_lines),
            "errors": errors,
            "warnings": warnings,
        },
        "issues": issues,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="제목과 본문이 들어 있는 UTF-8 Markdown/HTML/텍스트 파일")
    parser.add_argument("--keyword", required=True, help="정확히 셀 메인키워드")
    parser.add_argument("--title", help="파일에 제목이 없을 때 별도로 지정할 제목")
    parser.add_argument("--min-chars", type=int, default=1400)
    parser.add_argument("--max-chars", type=int, default=1800)
    parser.add_argument("--evidence", action="append", default=[], help="사용 가능 사실 레코드 파일; 여러 번 지정 가능")
    parser.add_argument("--allow-table", action="store_true", help="실제 비교값 표를 허용하되 의미 중복은 사람이 검수")
    parser.add_argument("--skip-fixed-components", action="store_true", help="신뢰 근거와 고정 연락·예약 검사만 생략")
    parser.add_argument("--json", action="store_true", help="프로그램용 JSON 출력")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    try:
        raw = input_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"입력 파일을 읽을 수 없습니다: {exc}", file=sys.stderr)
        return 2

    evidence = read_allowed_evidence(args.evidence, date.today())
    result = validate_article(
        raw,
        args.keyword,
        explicit_title=args.title,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        evidence=evidence,
        allow_table=args.allow_table,
        require_fixed_components=not args.skip_fixed_components,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        metrics = result["metrics"]
        print(f"status: {result['status']}")
        print(f"공백 제외 글자 수: {metrics['nonWhitespaceChars']}")
        print(f"제목 정확 키워드: {metrics['titleKeywordCount']}회")
        print(f"본문 정확 키워드: {metrics['bodyKeywordCount']}회")
        print(f"번호 절: {metrics['numberedSectionCount']}개")
        for issue in result["issues"]:
            location = f" (문단 {issue['paragraph']})" if "paragraph" in issue else ""
            print(f"[{issue['severity'].upper()}] {issue['code']}{location}: {issue['detail']}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
