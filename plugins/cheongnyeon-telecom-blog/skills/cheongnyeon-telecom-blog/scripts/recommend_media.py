#!/usr/bin/env python3
"""Recommend context-relevant media from the 청년통신 archive index.

The recommender scores the same library and arguments in a stable order,
excludes unsafe legacy roles, and reports missing slots as metadata instead of
filling weak matches with unrelated assets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIBRARY = SKILL_ROOT / "assets" / "media-library.json"
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣+·._-]*")
MODEL_RE = re.compile(
    r"(아이폰\s*\d{1,2}|갤럭시\s*[asz]?\s*\d{1,3}|"
    r"s\s*\d{2}|플립\s*\d+|폴드\s*\d+|a\s*\d{2})",
    re.IGNORECASE,
)
STOPWORDS = {
    "광주",
    "휴대폰",
    "핸드폰",
    "청년통신",
    "매장",
    "성지",
    "관련",
    "대한",
    "위한",
    "하는",
    "있는",
    "없는",
    "방법",
    "정보",
    "글",
    "블로그",
}
MODE_ALIASES = {
    "information": "information",
    "info": "information",
    "compare": "information",
    "정보형": "information",
    "설명형": "information",
    "warning": "warning",
    "warn": "warning",
    "경고형": "warning",
    "피해예방형": "warning",
    "authority": "authority",
    "proof": "authority",
    "권위형": "authority",
    "권위 증명형": "authority",
    "draft": "draft",
    "초안": "draft",
}
MODE_TAG_SEQUENCE = {
    "information": (
        ("how-to", "price-comparison"),
        ("price-comparison", "carrier-plan"),
        ("how-to", "device-product"),
        ("carrier-plan", "price-comparison"),
    ),
    "warning": (
        ("contract-warning", "price-comparison"),
        ("contract-warning", "carrier-plan"),
        ("price-comparison", "how-to"),
        ("contract-warning", "brand-proof"),
    ),
    "authority": (
        ("brand-proof",),
        ("brand-proof", "price-comparison"),
        ("price-comparison", "carrier-plan"),
        ("brand-proof", "how-to"),
    ),
    "draft": (
        ("how-to", "price-comparison"),
        ("price-comparison", "carrier-plan"),
        ("brand-proof", "how-to"),
    ),
}
TAG_QUERY_RULES = {
    "brand-proof": (
        "대표",
        "방송",
        "수상",
        "후기",
        "신뢰",
        "경력",
        "매장 소개",
        "운영 철학",
    ),
    "contract-warning": (
        "계약",
        "약정",
        "할부",
        "반납",
        "부가서비스",
        "사기",
        "호갱",
        "피해",
        "불법",
        "폰테크",
    ),
    "price-comparison": (
        "가격",
        "시세",
        "지원금",
        "선택약정",
        "공시지원금",
        "비교",
        "할인",
        "저렴",
        "싸게",
    ),
    "device-product": (
        "아이폰",
        "갤럭시",
        "플립",
        "폴드",
        "키즈폰",
        "효도폰",
        "워치",
        "스펙",
        "기종",
    ),
    "how-to": (
        "방법",
        "설정",
        "초기화",
        "데이터",
        "옮기",
        "고장",
        "서비스센터",
        "해결",
        "검사",
        "재부팅",
    ),
    "carrier-plan": (
        "요금제",
        "통신사",
        "skt",
        "kt",
        "lgu",
        "결합",
        "알뜰폰",
        "자급제",
        "제휴카드",
    ),
    "event-launch": (
        "이벤트",
        "사전예약",
        "출시",
        "선착순",
        "사은품",
        "수능",
        "예약 혜택",
    ),
    "store-contact": (
        "전화",
        "문의",
        "연락처",
        "주소",
        "찾아오",
        "방문 예약",
    ),
}
TAG_LABELS = {
    "brand-proof": "신뢰 근거",
    "contract-warning": "계약 위험",
    "price-comparison": "가격 비교",
    "device-product": "기기·제품",
    "how-to": "설정·해결 방법",
    "carrier-plan": "통신사·요금제",
    "event-launch": "출시·이벤트",
    "store-contact": "매장·연락",
}
BANNED_ROLES = {"map", "og_image", "video_thumbnail", "video", "sticker"}
BANNED_TAGS = {"decorative", "map", "external-card"}
EVENT_TERMS = {
    "이벤트",
    "사전예약",
    "출시",
    "선착순",
    "사은품",
    "수능",
    "예약 혜택",
}
MOTION_TERMS = {
    "설정",
    "옮기",
    "재부팅",
    "과정",
    "순서",
    "방법",
    "상담",
    "개통",
    "시연",
}
TEMPORAL_TAGS = {
    "event-launch",
    "price-comparison",
    "carrier-plan",
    "contract-warning",
    "store-contact",
}


@dataclass(frozen=True)
class Slot:
    index: int
    band: str
    role: str
    preferred_tags: tuple[str, ...]
    insertion: str


@dataclass(frozen=True)
class Score:
    total: int
    semantic: int
    topical: int
    matched_terms: tuple[str, ...]
    matched_tags: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="청년통신 미디어 인덱스에서 문맥에 맞는 사진·GIF를 추천합니다."
    )
    parser.add_argument("--topic", required=True, help="글의 구체적인 주제")
    parser.add_argument("--keyword", required=True, help="메인키워드")
    parser.add_argument(
        "--mode",
        default="information",
        help="information, warning, authority, draft 또는 한국어 별칭",
    )
    parser.add_argument("--count", type=int, default=6, help="필요한 자료 수 (1~10)")
    parser.add_argument(
        "--include-gif",
        action="store_true",
        help="움직임이 설명을 보완할 때 GIF를 후보에 포함",
    )
    parser.add_argument(
        "--long-form",
        action="store_true",
        help="긴 글로 간주하여 GIF를 최대 2개 허용",
    )
    parser.add_argument(
        "--recent-id",
        action="append",
        default=[],
        metavar="ASSET_ID",
        help="최근 원고에서 사용한 자산 ID. 반복 또는 쉼표 구분 가능",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="출력 형식",
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=DEFAULT_LIBRARY,
        help="media-library.json 경로",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        help="시점 민감 자료 판정 기준일 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--max-age-months",
        type=int,
        default=18,
        help="자동 추천에 허용할 출처 최대 경과 개월 수 (기본 18)",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=28,
        help="선택에 필요한 최소 종합 점수",
    )
    return parser.parse_args()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("\u200b", " ")).strip()


def compact(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣+]", "", normalize(value))


def tokenize(value: str) -> tuple[str, ...]:
    output: list[str] = []
    for raw in TOKEN_RE.findall(normalize(value)):
        token = raw.strip("._-")
        if len(token) < 2 or token in STOPWORDS:
            continue
        if token not in output:
            output.append(token)
    return tuple(output)


def parse_recent_ids(values: Iterable[str]) -> set[str]:
    return {
        item.strip().upper()
        for value in values
        for item in value.split(",")
        if item.strip()
    }


def resolve_mode(value: str) -> str:
    key = normalize(value)
    if key not in MODE_ALIASES:
        accepted = ", ".join(("information", "warning", "authority", "draft"))
        raise ValueError(f"지원하지 않는 mode '{value}'입니다: {accepted}")
    return MODE_ALIASES[key]


def build_slots(mode: str, count: int) -> list[Slot]:
    sequences = MODE_TAG_SEQUENCE[mode]
    first_roles = {
        "information": "독자 문제 또는 핵심 기준",
        "warning": "위험 상황",
        "authority": "신뢰 근거",
        "draft": "도입 핵심 맥락",
    }
    slots: list[Slot] = []
    for index in range(count):
        preferred = sequences[index % len(sequences)]
        if index == 0:
            slots.append(
                Slot(
                    index=1,
                    band="intro",
                    role=first_roles[mode],
                    preferred_tags=preferred,
                    insertion="도입 내용 문단 3~8개 뒤에 단일 이미지",
                )
            )
            continue
        slots.append(
            Slot(
                index=index + 1,
                band="body",
                role="본문 맥락 보충",
                preferred_tags=preferred,
                insertion="관련 논거 또는 설명이 끝난 뒤",
            )
        )
    return slots


def infer_query_tags(query: str) -> set[str]:
    text = normalize(query)
    return {
        tag
        for tag, phrases in TAG_QUERY_RULES.items()
        if any(normalize(phrase) in text for phrase in phrases)
    }


def models(value: str) -> set[str]:
    return {compact(match) for match in MODEL_RE.findall(value)}


def source_date(asset: dict[str, Any]) -> date | None:
    dates: list[date] = []
    for source in asset.get("sourcePosts", []):
        raw = str(source.get("publishedAt") or "")
        try:
            dates.append(datetime.fromisoformat(raw).date())
        except (TypeError, ValueError):
            continue
    return max(dates) if dates else None


def parsed_source_date(source: dict[str, Any]) -> date | None:
    raw = str(source.get("publishedAt") or "")
    try:
        return datetime.fromisoformat(raw).date()
    except (TypeError, ValueError):
        return None


def best_context_source(
    asset: dict[str, Any],
    *,
    topic: str,
    keyword: str,
    as_of: date,
    max_age_months: int,
) -> dict[str, Any] | None:
    cutoff = as_of - timedelta(days=max_age_months * 30.4375)
    query_tokens = tokenize(f"{keyword} {topic}")
    keyword_compact = compact(keyword)
    ranked: list[tuple[int, int, dict[str, Any]]] = []

    for source in asset.get("sourcePosts") or []:
        published = parsed_source_date(source)
        if not published or published > as_of or published < cutoff:
            continue
        search = normalize(
            f"{source.get('postTitle') or ''} {source.get('context') or ''}"
        )
        search_compact = compact(search)
        matches = [
            token
            for token in query_tokens
            if token in search
            or (
                len(compact(token)) >= 4
                and compact(token) in search_compact
            )
        ]
        exact_keyword = (
            len(keyword_compact) >= 4 and keyword_compact in search_compact
        )
        if not matches and not exact_keyword:
            continue
        direct_score = len(set(matches)) * 10 + (24 if exact_keyword else 0)
        ranked.append((direct_score, published.toordinal(), source))

    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], -item[1]))
    return ranked[0][2]


def library_as_of(library: dict[str, Any]) -> date:
    # Recency is relative to the publication run, not to the day on which the
    # media index happened to be generated.
    del library
    return date.today()


def source_sort_value(asset: dict[str, Any]) -> int:
    published = source_date(asset)
    return published.toordinal() if published else 0


def is_base_eligible(
    asset: dict[str, Any],
    include_gif: bool,
    recent_ids: set[str],
) -> bool:
    if not asset.get("eligible"):
        return False
    asset_id = str(asset.get("id") or "").upper()
    if not asset_id or asset_id in recent_ids:
        return False
    display_type = str(asset.get("displayType") or "")
    if display_type not in {"image", "gif"}:
        return False
    if display_type == "gif" and not include_gif:
        return False
    roles = set(asset.get("roles") or [])
    tags = set(asset.get("tags") or [])
    if roles & BANNED_ROLES or tags & BANNED_TAGS:
        return False
    return bool(asset.get("localPath") or asset.get("sourceUrl"))


def score_asset(
    asset: dict[str, Any],
    source: dict[str, Any],
    slot: Slot,
    *,
    topic: str,
    keyword: str,
    query_tokens: tuple[str, ...],
    topic_tokens: tuple[str, ...],
    query_tags: set[str],
    query_models: set[str],
    event_intent: bool,
    motion_intent: bool,
    as_of: date,
) -> Score:
    # Score only the selected occurrence's title and neighboring text. The
    # asset-level index merges contexts from every reuse and can cause a photo
    # to look relevant when its actual source occurrence is not.
    search = normalize(
        f"{source.get('postTitle') or ''} {source.get('context') or ''}"
    )
    search_compact = compact(search)
    keyword_norm = normalize(keyword)
    topic_norm = normalize(topic)
    total = 0
    semantic = 0
    topical = 0
    matched_terms: list[str] = []

    for phrase, points in ((keyword_norm, 18), (topic_norm, 12)):
        if len(phrase) >= 2 and phrase in search:
            semantic += points
            total += points
            if phrase == topic_norm:
                topical += points
            matched_terms.append(phrase)
        elif len(compact(phrase)) >= 4 and compact(phrase) in search_compact:
            semantic += points - 4
            total += points - 4
            if phrase == topic_norm:
                topical += points - 4
            matched_terms.append(phrase)

    asset_keywords = set(tokenize(search))
    for token in query_tokens:
        points = 0
        if token in asset_keywords:
            points = 7
        elif token in search:
            points = 4
        elif len(compact(token)) >= 4 and compact(token) in search_compact:
            points = 3
        if points:
            semantic += points
            total += points
            if token in topic_tokens:
                topical += points
            if token not in matched_terms:
                matched_terms.append(token)

    asset_tags = set(asset.get("tags") or [])
    explicit_tag_matches = sorted(asset_tags & query_tags)
    total += 7 * len(explicit_tag_matches)

    structural_matches = [
        tag for tag in slot.preferred_tags if tag in asset_tags
    ]
    if structural_matches:
        total += 14
        total += 4 * (len(structural_matches) - 1)
    if asset.get("preferredBand") == slot.band:
        total += 8
    elif slot.band == "intro" and asset.get("preferredBand") == "closing":
        total -= 5

    published = parsed_source_date(source)
    if published:
        age_days = max(0, (as_of - published).days)
        if age_days <= 550:
            total += 7
        elif age_days <= 1100:
            total += 3
        elif age_days > 1500:
            total -= 3

    total -= min(7, max(0, int(asset.get("reuseCount") or 0) - 1) * 2)
    if int(asset.get("width") or 0) >= 600:
        total += 2

    asset_models = models(search)
    if query_models and asset_models and not (query_models & asset_models):
        total -= 20
    elif query_models & asset_models:
        semantic += 8
        topical += 8
        total += 8

    if "event-launch" in asset_tags and not event_intent:
        total -= 10
    if "store-contact" in asset_tags and "store-contact" not in query_tags:
        total -= 4

    if asset.get("displayType") == "gif":
        if slot.index == 1:
            total -= 30
        elif motion_intent or "how-to" in asset_tags:
            total += 5
        else:
            total -= 6

    return Score(
        total=total,
        semantic=semantic,
        topical=topical,
        matched_terms=tuple(matched_terms[:6]),
        matched_tags=tuple(
            dict.fromkeys((*explicit_tag_matches, *structural_matches))
        ),
    )


def primary_source(asset: dict[str, Any]) -> dict[str, Any]:
    sources = asset.get("sourcePosts") or []
    if not sources:
        return {}
    return max(
        sources,
        key=lambda item: str(item.get("publishedAt") or ""),
    )


def verification(
    asset: dict[str, Any], source: dict[str, Any], as_of: date
) -> tuple[bool, str]:
    published = parsed_source_date(source)
    tags = set(asset.get("tags") or [])
    age_days = (as_of - published).days if published else 9999
    if tags & TEMPORAL_TAGS and age_days > 365:
        return (
            True,
            "가격·정책·이벤트·연락 정보와 이미지 안 날짜·숫자를 현재 기준으로 확인하세요.",
        )
    return (
        False,
        "파일을 직접 열어 실제 장면과 인접 문단의 의미가 일치하는지 확인하세요.",
    )


def asset_result(
    asset: dict[str, Any],
    source: dict[str, Any],
    slot: Slot,
    score: Score,
    keyword: str,
    as_of: date,
) -> dict[str, Any]:
    tags = list(asset.get("tags") or [])
    matched_labels = [
        TAG_LABELS[tag] for tag in score.matched_tags if tag in TAG_LABELS
    ]
    evidence = ", ".join(score.matched_terms[:3]) or "주제 문맥"
    tag_reason = ", ".join(matched_labels[:2]) or "배치 역할"
    requires_verification, note = verification(asset, source, as_of)
    caption_base = keyword.strip() or "청년통신"
    return {
        "slot": slot.index,
        "status": "selected",
        "slotRole": slot.role,
        "insertion": slot.insertion,
        "id": asset.get("id"),
        "type": asset.get("displayType"),
        "score": score.total,
        "semanticScore": score.semantic,
        "topicScore": score.topical,
        "confidence": (
            "strong"
            if score.semantic >= 30
            else "medium"
            if score.semantic >= 16
            else "cautious"
        ),
        "preferredBand": asset.get("preferredBand"),
        "localPath": asset.get("localPath"),
        "sourceUrl": asset.get("sourceUrl"),
        "width": asset.get("width"),
        "height": asset.get("height"),
        "captionDraft": f"{caption_base} · {slot.role} 참고 자료",
        "reason": f"'{evidence}' 문맥과 {tag_reason} 역할이 일치",
        "tags": tags,
        "matchedTerms": list(score.matched_terms),
        "matchedTags": list(score.matched_tags),
        "requiresVerification": requires_verification,
        "verificationNote": note,
        "sourcePost": {
            "title": source.get("postTitle"),
            "url": source.get("postUrl"),
            "publishedAt": source.get("publishedAt"),
            "context": source.get("context"),
        },
    }


def placeholder_result(slot: Slot, min_score: int) -> dict[str, Any]:
    return {
        "slot": slot.index,
        "status": "placeholder",
        "slotRole": slot.role,
        "insertion": slot.insertion,
        "renderInBody": False,
        "reason": (
            f"관련도와 안전 기준(종합 {min_score}점·문맥 8점·주제 6점)을 모두 통과한 "
            "미사용 자료가 없습니다."
        ),
    }


def recommend(
    library: dict[str, Any],
    *,
    topic: str,
    keyword: str,
    mode: str,
    count: int,
    include_gif: bool,
    long_form: bool,
    recent_ids: set[str],
    as_of: date,
    max_age_months: int,
    min_score: int,
) -> dict[str, Any]:
    query = f"{keyword} {topic}"
    query_tokens = tokenize(query)
    topic_tokens = tokenize(topic)
    query_tags = infer_query_tags(query)
    query_models = models(query)
    query_norm = normalize(query)
    event_intent = any(term in query_norm for term in EVENT_TERMS)
    motion_intent = any(term in query_norm for term in MOTION_TERMS)
    gif_limit = 2 if long_form or count >= 8 else 1
    slots = build_slots(mode, count)
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for asset in library.get("assets", []):
        if not is_base_eligible(asset, include_gif, recent_ids):
            continue
        source = best_context_source(
            asset,
            topic=topic,
            keyword=keyword,
            as_of=as_of,
            max_age_months=max_age_months,
        )
        if source:
            candidates.append((asset, source))
    selected_ids: set[str] = set()
    source_counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    gif_count = 0

    for slot in slots:
        ranked: list[tuple[Score, dict[str, Any], dict[str, Any]]] = []
        for asset, source in candidates:
            asset_id = str(asset.get("id") or "")
            if asset_id in selected_ids:
                continue
            if asset.get("displayType") == "gif" and gif_count >= gif_limit:
                continue

            source_id = str(source.get("postLogNo") or "")
            if source_id and source_counts.get(source_id, 0) >= 2:
                continue

            published = parsed_source_date(source)
            asset_tags = set(asset.get("tags") or [])
            if (
                event_intent
                and (
                    "event-launch" not in asset_tags
                    or (
                        published
                        and (as_of - published).days > 450
                    )
                )
            ):
                continue

            asset_score = score_asset(
                asset,
                source,
                slot,
                topic=topic,
                keyword=keyword,
                query_tokens=query_tokens,
                topic_tokens=topic_tokens,
                query_tags=query_tags,
                query_models=query_models,
                event_intent=event_intent,
                motion_intent=motion_intent,
                as_of=as_of,
            )
            if source_id:
                previous_from_source = source_counts.get(source_id, 0)
                if previous_from_source:
                    asset_score = Score(
                        total=asset_score.total - 8 * previous_from_source,
                        semantic=asset_score.semantic,
                        topical=asset_score.topical,
                        matched_terms=asset_score.matched_terms,
                        matched_tags=asset_score.matched_tags,
                    )
            ranked.append((asset_score, asset, source))

        ranked.sort(
            key=lambda item: (
                -item[0].total,
                -item[0].semantic,
                -(
                    parsed_source_date(item[2]).toordinal()
                    if parsed_source_date(item[2])
                    else 0
                ),
                str(item[1].get("id") or ""),
            )
        )
        choice = next(
            (
                (asset_score, asset, source)
                for asset_score, asset, source in ranked
                if (
                    asset_score.total >= min_score
                    and asset_score.semantic >= 8
                    and asset_score.topical >= 6
                )
            ),
            None,
        )
        if choice is None:
            selected.append(placeholder_result(slot, min_score))
            continue

        asset_score, asset, source = choice
        selected_ids.add(str(asset.get("id") or ""))
        source_id = str(source.get("postLogNo") or "")
        if source_id:
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
        if asset.get("displayType") == "gif":
            gif_count += 1
        selected.append(
            asset_result(asset, source, slot, asset_score, keyword, as_of)
        )

    selected_count = sum(item["status"] == "selected" for item in selected)
    placeholder_count = len(selected) - selected_count
    profile = library.get("placementProfile") or {}
    return {
        "schemaVersion": 1,
        "query": {
            "topic": topic,
            "keyword": keyword,
            "mode": mode,
            "count": count,
            "includeGif": include_gif,
            "longForm": long_form or count >= 8,
            "asOf": as_of.isoformat(),
            "maxAgeMonths": max_age_months,
            "recentIds": sorted(recent_ids),
        },
        "library": {
            "version": library.get("version"),
            "blogId": library.get("blogId"),
            "generatedAt": library.get("generatedAt"),
            "postCount": profile.get("postCount"),
            "assetCount": profile.get("assetCount"),
        },
        "rules": {
            "gifLimit": gif_limit if include_gif else 0,
            "sameAssetAllowed": False,
            "maxAssetsPerSourcePost": 2,
            "excludedByDefault": [
                "sticker",
                "map",
                "og_image",
                "video_thumbnail",
                "video",
            ],
            "weakMatchesBecomePlaceholders": True,
            "hardRecencyCutoffMonths": max_age_months,
            "sourceOccurrenceContextRequired": True,
        },
        "summary": {
            "selectedCount": selected_count,
            "placeholderCount": placeholder_count,
            "gifCount": gif_count,
            "excludedRecentCount": len(recent_ids),
        },
        "recommendations": selected,
    }


def markdown(payload: dict[str, Any]) -> str:
    query = payload["query"]
    summary = payload["summary"]
    lines = [
        "# 청년통신 미디어 추천",
        "",
        f"- 주제: {query['topic']}",
        f"- 메인키워드: {query['keyword']}",
        f"- 유형: {query['mode']}",
        (
            f"- 결과: 실제 자료 {summary['selectedCount']}개 · "
            f"GIF {summary['gifCount']}개 · 미디어 누락 "
            f"{summary['placeholderCount']}개"
        ),
        "",
    ]
    for item in payload["recommendations"]:
        lines.extend(
            [
                f"## {item['slot']}. {item['slotRole']}",
                "",
                f"- 배치: {item['insertion']}",
            ]
        )
        if item["status"] == "placeholder":
            lines.extend(
                [
                    f"- 이유: {item['reason']}",
                    "- 발행 본문 처리: 해당 미디어 슬롯 생략",
                    "",
                ]
            )
            continue
        lines.extend(
            [
                f"- 자산: `{item['id']}` · {item['type']} · "
                f"관련도 {item['confidence']} (문맥 {item['semanticScore']}점 · "
                f"주제 {item['topicScore']}점)",
                f"- 로컬 파일: `{item.get('localPath') or '없음'}`",
                f"- 추천 이유: {item['reason']}",
                f"- 확인: {item['verificationNote']}",
            ]
        )
        source = item.get("sourcePost") or {}
        if source.get("title"):
            lines.append(
                f"- 원문 맥락: [{source['title']}]({source.get('url') or ''})"
            )
        if item.get("sourceUrl"):
            lines.extend(
                [
                    "",
                    f"![{item['captionDraft']}]({item['sourceUrl']})",
                ]
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    if not 1 <= args.count <= 10:
        raise SystemExit("--count는 1~10 사이여야 합니다.")
    if args.min_score < 0:
        raise SystemExit("--min-score는 0 이상이어야 합니다.")
    if not 0 <= args.max_age_months <= 120:
        raise SystemExit("--max-age-months는 0~120 사이여야 합니다.")
    if not args.topic.strip() or not args.keyword.strip():
        raise SystemExit("--topic과 --keyword는 빈 문자열일 수 없습니다.")

    try:
        mode = resolve_mode(args.mode)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    library_path = args.library.expanduser().resolve()
    if not library_path.is_file():
        raise SystemExit(f"미디어 인덱스를 찾을 수 없습니다: {library_path}")
    try:
        library = json.loads(library_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"미디어 인덱스를 읽을 수 없습니다: {error}") from error
    if not isinstance(library.get("assets"), list):
        raise SystemExit("미디어 인덱스에 assets 배열이 없습니다.")

    as_of = args.as_of or library_as_of(library)
    payload = recommend(
        library,
        topic=args.topic.strip(),
        keyword=args.keyword.strip(),
        mode=mode,
        count=args.count,
        include_gif=args.include_gif,
        long_form=args.long_form,
        recent_ids=parse_recent_ids(args.recent_id),
        as_of=as_of,
        max_age_months=args.max_age_months,
        min_score=args.min_score,
    )
    if args.format == "markdown":
        sys.stdout.write(markdown(payload))
    else:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
