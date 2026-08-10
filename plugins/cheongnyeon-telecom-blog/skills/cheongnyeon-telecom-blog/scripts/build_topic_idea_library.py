#!/usr/bin/env python3
"""Build a compact title/topic idea catalog from a public Naver Blog category.

The generated catalog intentionally excludes full article prose. It stores only
short derived metadata needed to choose a topic and title mechanism. All source
brand facts remain blocked from Cheongnyeon Telecom drafts.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup


DEFAULT_BLOG_ID = "sungji_dongtan"
DEFAULT_CATEGORY_NO = "1"
DEFAULT_EXPECTED_COUNT = 188
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


PRIMARY_TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "launch-stock",
        (
            "사전예약",
            "출시",
            "재고",
            "입고",
            "당일 수령",
            "아이폰",
            "갤럭시",
            "프로맥스",
            "플립",
            "폴드",
        ),
    ),
    (
        "fraud-prevention",
        (
            "사기",
            "호갱",
            "호구",
            "폰팔이",
            "속지",
            "강요",
            "절대",
            "반납",
            "보상기변",
            "당하지",
            "주의",
        ),
    ),
    (
        "switching-comparison",
        ("번호이동", "기기변경", "통신사 이동", "갈아타", "이동 vs", "기변"),
    ),
    (
        "plan-contract-explainer",
        (
            "결합할인",
            "가족결합",
            "인터넷결합",
            "요금제",
            "부가서비스",
            "선택약정",
            "공시지원금",
            "할부",
            "위약금",
            "약정",
        ),
    ),
    (
        "faq-aftercare",
        (
            "준비물",
            "영업시간",
            "서비스센터",
            "데이터 이전",
            "유심",
            "명의",
            "미성년",
            "외국인",
            "분실",
            "고장",
            "개통 시간",
            "자급제",
        ),
    ),
    (
        "visit-case-story",
        (
            "사러 오",
            "찾아오",
            "멀리서",
            "서울에서",
            "재방문",
            "방문 후기",
            "고객 후기",
            "소개로",
        ),
    ),
    (
        "price-mechanism",
        (
            "가격",
            "싸게",
            "싼 이유",
            "저렴",
            "제값",
            "마진",
            "수수료",
            "도매",
            "판매량",
            "비싸게",
        ),
    ),
    (
        "store-trust-intro",
        (
            "생활의 달인",
            "누적",
            "한자리",
            "1위",
            "상위",
            "믿을",
            "신뢰",
            "매장의 비밀",
            "진짜 이유",
            "업체",
        ),
    ),
    (
        "purchase-checklist",
        (
            "개통 전",
            "계약 전",
            "확인",
            "기준",
            "체크",
            "놓치는",
            "고르는 법",
            "선택 기준",
            "3가지",
        ),
    ),
    (
        "insider-story",
        (
            "대표",
            "고백",
            "솔직히",
            "철학",
            "업계",
            "창업",
            "운영",
            "장사",
            "말씀드",
        ),
    ),
]


# Lower numbers win when two types have the same number of title signals.
# Specific reader situations beat generic price words because nearly every
# mobile-phone article mentions price somewhere in its body.
TYPE_PRIORITY = {
    "faq-aftercare": 0,
    "switching-comparison": 1,
    "plan-contract-explainer": 2,
    "fraud-prevention": 3,
    "visit-case-story": 4,
    "store-trust-intro": 5,
    "insider-story": 6,
    "purchase-checklist": 7,
    "launch-stock": 8,
    "price-mechanism": 9,
}


ANGLE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("device-launch", ("아이폰", "갤럭시", "플립", "폴드", "프로맥스", "출시", "사전예약")),
    ("switching", ("번호이동", "기기변경", "기변", "통신사 이동")),
    ("bundle-discount", ("결합할인", "가족결합", "인터넷결합", "결합")),
    ("installment", ("할부", "36개월", "48개월", "할부원금")),
    ("rate-plan", ("요금제", "고가 요금제", "선택약정", "공시지원금")),
    ("add-on-service", ("부가서비스", "부가 서비스")),
    ("trade-in", ("중고폰", "반납", "보상기변")),
    ("contract-document", ("계약서", "신청서", "견적서", "계약 전")),
    ("store-selection", ("매장", "성지", "가게", "판매점", "대리점")),
    ("aftercare", ("서비스센터", "고장", "수리", "사후관리", "데이터 이전")),
    ("stock", ("재고", "입고", "당일 수령", "즉시 개통")),
    ("price", ("가격", "싸게", "저렴", "비싸게", "제값", "마진", "도매")),
]


TYPE_LABELS = {
    "launch-stock": "신제품·사전예약·재고형",
    "fraud-prevention": "사기·호갱 피해예방형",
    "switching-comparison": "번호이동·기기변경 비교형",
    "plan-contract-explainer": "요금제·결합·약정 정보형",
    "faq-aftercare": "FAQ·사후관리형",
    "visit-case-story": "고객 방문 이유·사례형",
    "price-mechanism": "가격 구조·저렴한 이유형",
    "store-trust-intro": "업체·신뢰 소개형",
    "purchase-checklist": "구매 기준·체크리스트형",
    "insider-story": "대표 철학·내부자 고백형",
}


ANGLE_LABELS = {
    "device-launch": "신제품 출시와 구매 시점",
    "switching": "번호이동과 기기변경",
    "bundle-discount": "가족·인터넷 결합 할인",
    "installment": "할부 기간과 할부원금",
    "rate-plan": "요금제와 지원금",
    "add-on-service": "부가서비스",
    "trade-in": "중고폰 반납과 보상기변",
    "contract-document": "계약서와 견적서",
    "store-selection": "매장 선택",
    "aftercare": "개통 후 사후관리",
    "stock": "재고와 즉시 개통",
    "price": "가격과 매장 수익 구조",
    "general": "휴대폰 구매 일반",
}


TYPE_AGENDAS = {
    "launch-stock": ["출시·예약 조건", "재고와 수령 시점", "구매 전 확인 항목"],
    "fraud-prevention": ["경계할 말이나 조건", "소비자에게 생기는 손실", "계약 전 중단·확인 행동"],
    "switching-comparison": ["두 방식의 차이", "위약금·결합 할인 같은 예외 비용", "총비용 비교"],
    "plan-contract-explainer": ["제도의 실제 의미", "이익과 예외 조건", "계약서에서 확인할 항목"],
    "faq-aftercare": ["해당 상황의 준비 조건", "진행 중 막히는 지점", "개통·사후관리 행동"],
    "visit-case-story": ["고객이 움직이는 이유", "그 이유를 뒷받침하는 운영 근거", "다른 매장에서도 확인할 기준"],
    "price-mechanism": ["같은 기종 가격이 달라지는 원인", "판매량·마진 등 운영 구조", "동일 조건 비교법"],
    "store-trust-intro": ["광고를 의심하는 독자의 반론", "검증 가능한 운영·신뢰 근거", "매장을 고르는 일반 기준"],
    "purchase-checklist": ["계약 전에 볼 구체 항목", "항목을 놓쳤을 때의 결과", "현장에서 물어볼 질문"],
    "insider-story": ["대표의 이해관계와 관찰", "운영 선택의 이유", "구매자가 적용할 행동"],
}


TYPE_QUESTIONS = {
    "launch-stock": "신제품을 예약하거나 구매하기 전에 무엇을 확인해야 하는가",
    "fraud-prevention": "계약 전에 어떤 위험 신호를 확인해야 하는가",
    "switching-comparison": "번호이동과 기기변경 중 어떤 조건이 실제로 유리한가",
    "plan-contract-explainer": "요금제·결합·약정 조건이 실제로 유리한지 어떻게 확인하는가",
    "faq-aftercare": "해당 상황에서 개통과 사후관리를 위해 무엇을 준비해야 하는가",
    "visit-case-story": "고객이 가까운 곳을 두고도 특정 매장을 찾는 이유는 무엇인가",
    "price-mechanism": "같은 휴대폰 가격이 매장마다 다른 이유는 무엇인가",
    "store-trust-intro": "광고 문구가 아니라 어떤 근거로 매장을 판단할 수 있는가",
    "purchase-checklist": "휴대폰 계약 전에 무엇을 순서대로 확인해야 하는가",
    "insider-story": "대표의 운영 방식이 고객 조건에 어떤 차이를 만드는가",
}


COMPATIBLE_MASTERS = {
    "launch-stock": [],
    "fraud-prevention": ["warning-seller-lines-01"],
    "switching-comparison": ["authority-broadcast-reason-01", "warning-seller-lines-01"],
    "plan-contract-explainer": ["authority-broadcast-reason-01", "warning-seller-lines-01"],
    "faq-aftercare": [],
    "visit-case-story": ["operation-counterargument-01", "authority-broadcast-reason-01"],
    "price-mechanism": ["price-reader-objections-01", "authority-broadcast-reason-01"],
    "store-trust-intro": ["operation-counterargument-01", "authority-broadcast-reason-01"],
    "purchase-checklist": ["warning-seller-lines-01", "authority-broadcast-reason-01"],
    "insider-story": ["operation-counterargument-01", "authority-broadcast-reason-01"],
}


WRITING_MASTER_REGISTRY = {
    "warning-seller-lines-01": {
        "label": "경고·피해예방형",
        "sourceUrl": "https://blog.naver.com/cjdsus4444/223515173954",
        "decorationProfileAvailable": True,
    },
    "price-reader-objections-01": {
        "label": "가격·독자 반론형",
        "sourceUrl": "https://blog.naver.com/cjdsus4444/224139466948",
        "decorationProfileAvailable": True,
    },
    "authority-broadcast-reason-01": {
        "label": "권위·방송·가격 이유형",
        "sourceUrl": "https://blog.naver.com/cjdsus4444/224275775634",
        "decorationProfileAvailable": True,
    },
    "operation-counterargument-01": {
        "label": "반론·운영 근거형",
        "sourceUrl": "https://blog.naver.com/cjdsus4444/223722832688",
        "decorationProfileAvailable": True,
    },
}


def fetch_html(url: str, retries: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - network retry path
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def count_blog_posts(soup: BeautifulSoup) -> int | None:
    for heading in soup.select("h4"):
        match = re.search(r"([\d,]+)개의\s*글", heading.get_text(" ", strip=True))
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def extract_page_posts(html: str, blog_id: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    roots = soup.select("div.post[id^='post_']")
    # A category page wraps each article in ``div.post``. A direct PostView
    # page (used for pinned notices) exposes the same post-view/title/body
    # nodes without that wrapper, so the document itself becomes the root.
    if not roots and soup.select_one("div[id^='post-view']"):
        roots = [soup]
    for root in roots:
        post_view = root.select_one("div[id^='post-view']")
        title_node = root.select_one(".se-title-text") or root.select_one(".htitle .itemSubjectBoldfont")
        date_node = root.select_one(".se_publishDate") or root.select_one("._postAddDate")
        if post_view is None or title_node is None:
            continue

        match = re.search(r"post-view(\d+)", post_view.get("id", ""))
        if not match:
            continue
        log_no = match.group(1)
        title = compact_text(title_node.get_text(" ", strip=True))
        published_at = compact_text(date_node.get_text(" ", strip=True)) if date_node else ""

        body = root.select_one(".se-main-container") or root.select_one(".se-viewer") or post_view
        body_copy = BeautifulSoup(str(body), "html.parser")
        for unwanted in body_copy.select(
            ".se-documentTitle, script, style, .blog2_post_function, .post-btn, .post_footer_contents"
        ):
            unwanted.decompose()
        body_text = compact_text(body_copy.get_text(" ", strip=True))
        results.append(
            {
                "logNo": log_no,
                "sourceUrl": f"https://blog.naver.com/{blog_id}/{log_no}",
                "sourceTitle": title,
                "publishedAt": published_at,
                "analysisText": body_text,
            }
        )
    return results


def extract_notice_log_numbers(soup: BeautifulSoup) -> list[str]:
    log_numbers: list[str] = []
    for link in soup.select("table.blog2_notice a[href*='logNo=']"):
        match = re.search(r"[?&]logNo=(\d+)", link.get("href", ""))
        if match and match.group(1) not in log_numbers:
            log_numbers.append(match.group(1))
    return log_numbers


def infer_primary_type(title: str, body: str) -> str:
    lowered_title = title.lower()
    title_scores = []
    for type_id, terms in PRIMARY_TYPE_RULES:
        score = sum(1 for term in terms if term.lower() in lowered_title)
        title_scores.append((score, -TYPE_PRIORITY[type_id], type_id))
    best_title_score, _, best_title_type = max(title_scores)
    if best_title_score > 0:
        return best_title_type

    # Only use the opening body as a fallback. Count distinct signals instead
    # of raw repetitions so boilerplate price claims cannot dominate a post.
    lowered_opening = body[:1800].lower()
    body_scores = []
    for type_id, terms in PRIMARY_TYPE_RULES:
        score = sum(1 for term in terms if term.lower() in lowered_opening)
        body_scores.append((score, -TYPE_PRIORITY[type_id], type_id))
    best_body_score, _, best_body_type = max(body_scores)
    return best_body_type if best_body_score >= 2 else "purchase-checklist"


def infer_angle(title: str, body: str) -> str:
    combined = f"{title} {body[:4000]}".lower()
    scores = []
    for index, (angle_id, terms) in enumerate(ANGLE_RULES):
        score = sum(5 for term in terms if term.lower() in title.lower()) + sum(
            min(combined.count(term.lower()), 3) for term in terms
        )
        scores.append((score, index, angle_id))
    best_score, _, best_angle = max(scores, key=lambda item: (item[0], -item[1]))
    return best_angle if best_score > 0 else "general"


def infer_title_pattern(title: str) -> tuple[str, str]:
    normalized = compact_text(title)
    has_question = "?" in normalized
    has_number = bool(re.search(r"\d", normalized))
    if re.search(r"(?:개통|계약)\s*전", normalized) and re.search(r"놓치|확인|기준|주의", normalized):
        return "keyword-preopen-missed-criterion", "메인키워드 + 개통·계약 전 + 놓치기 쉬운 구체 기준"
    if has_question and re.search(r"누적|생활의\s*달인|상위|1위|판매량", normalized) and re.search(r"이유|비밀|진짜", normalized):
        return "keyword-question-authority-reason", "메인키워드 질문 + 검증된 권위 근거 + 진짜 이유·비밀"
    if re.search(r"상위|1위|달인|대표", normalized) and re.search(r"싸게|저렴|하는\s*법|알려", normalized):
        return "keyword-authority-benefit-howto", "메인키워드 + 검증된 권위 + 독자가 얻는 구매 이익"
    if has_number and re.search(r"가지|이유|비밀|기준|공통점", normalized):
        return "keyword-numbered-curiosity", "메인키워드 + 검증 가능한 숫자 + 이유·비밀·기준"
    if re.search(r"사기|호갱|호구|절대|주의|멈추|속지|당하지", normalized):
        return "keyword-warning-loss", "메인키워드 + 손실 경고 + 즉시 이해되는 행동"
    if re.search(r"vs|차이|비교|번호이동|기기변경", normalized, re.I):
        return "keyword-choice-comparison", "메인키워드 + 두 선택의 충돌 + 판단 답"
    if has_question and re.search(r"이것|비밀|진짜|왜", normalized):
        return "keyword-question-curiosity", "메인키워드 질문 + 구체적인 궁금증"
    if re.search(r"이유|왜", normalized):
        return "keyword-causal-reason", "메인키워드 + 원인에 대한 분명한 약속"
    if re.search(r"하는\s*법|방법|알려", normalized):
        return "keyword-direct-howto", "메인키워드 + 독자가 바로 얻는 방법"
    return "keyword-specific-promise", "메인키워드 + 구체적인 문제·이익 약속"


def title_signals(title: str) -> list[str]:
    signals: list[str] = []
    checks = [
        ("question", r"\?"),
        ("number", r"\d"),
        ("authority", r"생활의\s*달인|누적|상위|1위|판매량|대표"),
        ("loss", r"손해|사기|호갱|호구|비싸|놓치|절대|주의"),
        ("curiosity", r"비밀|진짜|이것|이유|왜"),
        ("benefit", r"싸게|저렴|하는\s*법|알려|이득"),
        ("time-pressure", r"개통\s*전|계약\s*전|사기\s*전|구매\s*전"),
    ]
    for label, pattern in checks:
        if re.search(pattern, title):
            signals.append(label)
    return signals


def derive_record(raw: dict[str, str]) -> dict[str, object]:
    title = raw["sourceTitle"]
    body = raw.pop("analysisText")
    primary_type = infer_primary_type(title, body)
    angle = infer_angle(title, body)
    pattern_id, pattern_description = infer_title_pattern(title)
    return {
        "id": f"sungji-{raw['logNo']}",
        "sourceUrl": raw["sourceUrl"],
        "sourceTitle": title,
        "publishedAt": raw["publishedAt"],
        "primaryType": primary_type,
        "primaryTypeLabel": TYPE_LABELS[primary_type],
        "secondaryAngle": angle,
        "secondaryAngleLabel": ANGLE_LABELS[angle],
        "titlePatternId": pattern_id,
        "titlePatternDescription": pattern_description,
        "titleHookSignals": title_signals(title),
        "readerQuestion": TYPE_QUESTIONS[primary_type],
        "answerAgenda": TYPE_AGENDAS[primary_type],
        "compatibleWritingMasterIds": COMPATIBLE_MASTERS[primary_type],
        "sourceFactsBlocked": True,
    }


def build_catalog(blog_id: str, category_no: str, expected_count: int, delay: float) -> dict[str, object]:
    base_url = "https://blog.naver.com/PostList.naver"
    first_params = {
        "blogId": blog_id,
        "categoryNo": category_no,
        "from": "postList",
        "parentCategoryNo": "0",
        "currentPage": "1",
    }
    first_url = f"{base_url}?{urllib.parse.urlencode(first_params)}"
    first_html = fetch_html(first_url)
    first_soup = BeautifulSoup(first_html, "html.parser")
    observed_count = count_blog_posts(first_soup) or expected_count
    if expected_count and observed_count != expected_count:
        raise RuntimeError(f"Expected {expected_count} public posts, but Naver currently reports {observed_count}")

    first_posts = extract_page_posts(first_html, blog_id)
    notice_log_numbers = extract_notice_log_numbers(first_soup)
    if not first_posts:
        raise RuntimeError("No posts found on the first category page")
    per_page = len(first_posts)
    page_count = math.ceil(observed_count / per_page)
    raw_posts: list[dict[str, str]] = first_posts
    seen = {post["logNo"] for post in raw_posts}

    for page in range(2, page_count + 1):
        params = dict(first_params)
        params["currentPage"] = str(page)
        html = fetch_html(f"{base_url}?{urllib.parse.urlencode(params)}")
        posts = extract_page_posts(html, blog_id)
        for post in posts:
            if post["logNo"] not in seen:
                seen.add(post["logNo"])
                raw_posts.append(post)
        if delay:
            time.sleep(delay)

    for log_no in notice_log_numbers:
        if log_no in seen:
            continue
        notice_url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
        notice_posts = extract_page_posts(fetch_html(notice_url), blog_id)
        for post in notice_posts:
            if post["logNo"] not in seen:
                seen.add(post["logNo"])
                raw_posts.append(post)
        if delay:
            time.sleep(delay)

    if len(raw_posts) != observed_count:
        raise RuntimeError(f"Collected {len(raw_posts)} unique posts, expected {observed_count}")

    records = [derive_record(dict(post)) for post in raw_posts]
    type_counts = Counter(str(record["primaryType"]) for record in records)
    pattern_counts = Counter(str(record["titlePatternId"]) for record in records)
    return {
        "version": 1,
        "source": {
            "blogId": blog_id,
            "categoryNo": category_no,
            "categoryUrl": f"https://blog.naver.com/PostList.naver?blogId={blog_id}&categoryNo={category_no}&from=postList&parentCategoryNo=0",
            "observedPublicPostCount": observed_count,
            "collectedAt": date.today().isoformat(),
            "usage": "title-topic-ideas-only",
            "factPolicy": "Never copy source names, numbers, prices, testimonials, guarantees, locations, or business claims into Cheongnyeon Telecom content.",
        },
        "summary": {
            "typeCounts": dict(sorted(type_counts.items())),
            "titlePatternCounts": dict(sorted(pattern_counts.items())),
        },
        "writingMasterRegistry": WRITING_MASTER_REGISTRY,
        "articles": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blog-id", default=DEFAULT_BLOG_ID)
    parser.add_argument("--category-no", default=DEFAULT_CATEGORY_NO)
    parser.add_argument("--expected-count", type=int, default=DEFAULT_EXPECTED_COUNT)
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    catalog = build_catalog(args.blog_id, args.category_no, args.expected_count, args.delay)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(catalog['articles'])} article profiles to {output}")
    print(json.dumps(catalog["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
