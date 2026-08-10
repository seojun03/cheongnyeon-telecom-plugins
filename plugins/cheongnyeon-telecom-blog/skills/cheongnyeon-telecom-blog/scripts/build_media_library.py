#!/usr/bin/env python3
"""Build a compact, searchable media library from a Naver Blog archive.

The archive is produced by scripts/extract_naver_blog_media.py.  This builder
does not guess image meaning from filenames alone: it joins every asset to the
post title, its surrounding SmartEditor components, its original placement,
and its reuse history.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag


SEOUL = ZoneInfo("Asia/Seoul")
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣+·._-]{1,}")
MODEL_RE = re.compile(
    r"(?:아이폰\s*\d{1,2}|갤럭시\s*[A-Za-z]?\s*\d{1,3}|"
    r"[SZ]\s*\d{1,3}|플립\s*\d+|폴드\s*\d+|A\s*\d{2}|SE\s*\d)",
    re.IGNORECASE,
)
STOPWORDS = {
    "관련",
    "대한",
    "위한",
    "있는",
    "없는",
    "하는",
    "합니다",
    "됩니다",
    "입니다",
    "그리고",
    "하지만",
    "때문에",
    "이렇게",
    "저렇게",
    "그렇게",
    "사진",
    "이미지",
    "자료",
    "청년통신",
    "광주",
    "휴대폰",
    "핸드폰",
    "매장",
    "성지",
    "알려",
    "드립니다",
    "보세요",
    "있습니다",
    "같습니다",
}

TAG_RULES: dict[str, tuple[str, ...]] = {
    "brand-proof": (
        "청년통신",
        "대표",
        "생활의 달인",
        "방송",
        "수상",
        "방문 후기",
        "고객 후기",
        "매장 사진",
        "직영점",
    ),
    "contract-warning": (
        "계약",
        "할부",
        "약정",
        "반납",
        "부가서비스",
        "고액 요금제",
        "사기",
        "호갱",
        "피해",
        "가개통",
        "폰테크",
        "보이스피싱",
    ),
    "price-comparison": (
        "가격",
        "시세",
        "지원금",
        "공시지원금",
        "선택약정",
        "비교",
        "총액",
        "할인",
        "저렴",
    ),
    "device-product": (
        "아이폰",
        "갤럭시",
        "플립",
        "폴드",
        "스마트폰",
        "키즈폰",
        "효도폰",
        "워치",
        "스펙",
        "출시",
        "사전예약",
    ),
    "how-to": (
        "방법",
        "설정",
        "초기화",
        "옮기는",
        "데이터 이동",
        "카카오톡",
        "배터리",
        "고장",
        "서비스센터",
        "검사",
        "해결",
    ),
    "carrier-plan": (
        "요금제",
        "통신사",
        "SKT",
        "KT",
        "LGU",
        "엘지유플러스",
        "결합",
        "제휴카드",
        "알뜰통신사",
        "자급제",
    ),
    "event-launch": (
        "이벤트",
        "선착순",
        "사전예약",
        "출시",
        "수능",
        "사은품",
        "할인",
        "예약",
    ),
    "store-contact": (
        "대표 전화",
        "문의",
        "연락처",
        "예약 후 방문",
        "주소",
        "지도",
        "찾아오",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive",
        type=Path,
        help="Extracted archive root. Defaults to the newest Desktop archive.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--public",
        action="store_true",
        help="Remove machine-local paths from the generated JSON.",
    )
    return parser.parse_args()


def find_archive(explicit: Path | None) -> Path:
    if explicit:
        root = explicit.expanduser().resolve()
        if not (root / "manifests" / "assets.csv").is_file():
            raise FileNotFoundError(f"Invalid archive: {root}")
        return root

    desktop = Path.home() / "Desktop"
    candidates = sorted(
        (
            path
            for path in desktop.glob("cjdsus4444_블로그_전체자료_*")
            if path.is_dir() and (path / "manifests" / "assets.csv").is_file()
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No cjdsus4444 archive was found on Desktop")
    return candidates[0].resolve()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def split_pipe(value: str) -> list[str]:
    return [part.strip() for part in value.split(" | ") if part.strip()]


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u200b", " ")).strip()


def truncate(value: str, limit: int) -> str:
    value = compact_text(value)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def tokens(value: str) -> list[str]:
    result: list[str] = []
    for token in TOKEN_RE.findall(value):
        cleaned = token.strip("._-").lower()
        if len(cleaned) < 2 or cleaned in STOPWORDS:
            continue
        if cleaned.isdigit() and len(cleaned) < 2:
            continue
        result.append(cleaned)
    for match in MODEL_RE.findall(value):
        model = re.sub(r"\s+", "", match).lower()
        if model and model not in result:
            result.append(model)
    return result


def position_band(component_index: int, component_count: int) -> str:
    if component_count <= 0:
        return "body"
    ratio = component_index / component_count
    if ratio <= 0.25:
        return "intro"
    if ratio >= 0.78:
        return "closing"
    return "body"


def url_key(value: str) -> str:
    value = value.replace("&amp;", "&").replace("\\/", "/").strip("\"' <>")
    if not value.startswith(("http://", "https://")):
        return value
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    query = parsed.query
    if host in {
        "mblogthumb-phinf.pstatic.net",
        "blogthumb-phinf.pstatic.net",
        "blogthumb.pstatic.net",
        "postfiles.pstatic.net",
        "blogfiles.pstatic.net",
    }:
        host = "blogfiles.pstatic.net"
        query = ""
    return urlunsplit(("https", host, parsed.path, query, ""))


def component_contexts(
    content_path: Path,
) -> tuple[list[str], list[str], dict[str, list[int]]]:
    soup = BeautifulSoup(content_path.read_text(encoding="utf-8"), "lxml")
    components = soup.select(".se-component")
    component_indexes = {id(component): index for index, component in enumerate(components)}
    texts: list[str] = []
    kinds: list[str] = []
    for component in components:
        text = compact_text(component.get_text(" ", strip=False))
        texts.append(text)
        classes = list(component.get("class", []))
        kind = next(
            (
                class_name.removeprefix("se-")
                for class_name in classes
                if class_name.startswith("se-") and class_name != "se-component"
            ),
            "component",
        )
        kinds.append(kind)
    media_components: dict[str, list[int]] = defaultdict(list)
    for anchor in soup.select(
        'a[data-linktype="img"][data-linkdata], '
        'a[data-linktype="sticker"][data-linkdata]'
    ):
        try:
            link_data = json.loads(str(anchor.get("data-linkdata") or "{}"))
        except json.JSONDecodeError:
            continue
        source = str(
            link_data.get("src")
            or link_data.get("originalUrl")
            or link_data.get("url")
            or ""
        )
        component = anchor.find_parent(
            lambda tag: isinstance(tag, Tag)
            and tag.name == "div"
            and "se-component" in tag.get("class", [])
        )
        if source and isinstance(component, Tag):
            index = component_indexes.get(id(component))
            if index is not None:
                media_components[url_key(source)].append(index)
    return texts, kinds, media_components


def nearby_text(component_texts: list[str], component_index: int) -> str:
    if not component_texts:
        return ""
    center = max(0, min(len(component_texts) - 1, component_index - 1))
    selected: list[str] = []
    for index in range(max(0, center - 2), min(len(component_texts), center + 2)):
        text = component_texts[index]
        if text and text not in selected:
            selected.append(text)
    return truncate(" / ".join(selected), 520)


def classify_tags(searchable: str, roles: set[str]) -> list[str]:
    lowered = searchable.lower()
    tags = [
        tag
        for tag, phrases in TAG_RULES.items()
        if any(phrase.lower() in lowered for phrase in phrases)
    ]
    if "sticker" in roles:
        tags.append("decorative")
    if "map" in roles:
        tags.append("map")
    if "og_image" in roles:
        tags.append("external-card")
    return sorted(set(tags))


def display_type(kind: str, roles: set[str], frame_count: int) -> str:
    if "sticker" in roles:
        return "sticker"
    if kind == "gifs" and frame_count > 1:
        return "gif"
    if kind == "videos":
        return "video"
    return "image"


def eligibility(kind: str, roles: set[str]) -> tuple[bool, str]:
    if kind not in {"images", "gifs"}:
        return False, "video-or-attachment"
    if roles and roles <= {"map"}:
        return False, "map"
    if roles and roles <= {"og_image", "video_thumbnail"}:
        return False, "external-or-video-thumbnail"
    return True, ""


def main() -> int:
    args = parse_args()
    archive = find_archive(args.archive)
    manifests = archive / "manifests"
    assets_rows = read_csv(manifests / "assets.csv")
    occurrence_rows = read_csv(manifests / "occurrences.csv")
    post_rows = read_csv(manifests / "posts.csv")
    posts = {row["log_no"]: row for row in post_rows}

    component_cache: dict[
        str, tuple[list[str], list[str], dict[str, list[int]]]
    ] = {}
    for log_no in posts:
        path = archive / "html" / "content" / f"{log_no}.html"
        component_cache[log_no] = component_contexts(path)

    occurrences_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    roles_by_asset: dict[str, set[str]] = defaultdict(set)
    media_counts_by_post: Counter[str] = Counter(
        row["post_log_no"] for row in occurrence_rows if row.get("asset_id")
    )
    first_component_by_post: dict[str, int] = {}
    role_counts: Counter[str] = Counter()
    band_counts: Counter[str] = Counter()
    media_component_offsets: Counter[tuple[str, str]] = Counter()

    for row in occurrence_rows:
        asset_id = row.get("asset_id", "")
        if not asset_id:
            continue
        log_no = row["post_log_no"]
        component_texts, component_kinds, media_components = component_cache.get(
            log_no, ([], [], {})
        )
        matched_indexes = media_components.get(
            url_key(row.get("raw_url") or row.get("normalized_url") or ""),
            [],
        )
        offset_key = (
            log_no,
            url_key(row.get("raw_url") or row.get("normalized_url") or ""),
        )
        offset = media_component_offsets[offset_key]
        matched_index = (
            matched_indexes[min(offset, len(matched_indexes) - 1)]
            if matched_indexes
            else None
        )
        if matched_indexes:
            media_component_offsets[offset_key] += 1
        component_index = (
            matched_index + 1
            if matched_index is not None
            else int(row.get("component_index") or 0)
        )
        component_count = len(component_texts)
        media_order = int(row.get("order") or 0)
        fallback_count = media_counts_by_post.get(log_no, 1)
        band = (
            position_band(component_index, component_count)
            if component_index
            else position_band(media_order, fallback_count)
        )
        context = (
            nearby_text(component_texts, component_index)
            if component_index
            else ""
        )
        component_kind = (
            component_kinds[component_index - 1]
            if 0 < component_index <= len(component_kinds)
            else row.get("component_type", "")
        )
        post = posts.get(log_no, {})
        occurrences_by_asset[asset_id].append(
            {
                "postLogNo": log_no,
                "postTitle": post.get("title", row.get("post_title", "")),
                "postUrl": post.get("post_url", row.get("post_url", "")),
                "publishedAt": post.get("published_at", ""),
                "category": post.get("category_name", ""),
                "order": int(row.get("order") or 0),
                "componentIndex": component_index,
                "componentCount": component_count,
                "componentType": component_kind,
                "band": band,
                "context": context,
            }
        )
        role = row.get("role", "")
        if role:
            roles_by_asset[asset_id].add(role)
        role_counts[role] += 1
        band_counts[band] += 1
        if component_index:
            first_component_by_post[log_no] = min(
                component_index,
                first_component_by_post.get(log_no, component_index),
            )

    library_assets: list[dict[str, Any]] = []
    for row in assets_rows:
        asset_id = row["asset_id"]
        asset_occurrences = occurrences_by_asset.get(asset_id, [])
        roles = roles_by_asset.get(asset_id, set())
        source_urls = split_pipe(row.get("source_urls", ""))
        local_path = archive / row["relative_path"]
        frame_count = int(row.get("frame_count") or 1)
        searchable_parts = [
            row.get("original_name", ""),
            *(item["postTitle"] for item in asset_occurrences),
            *(item["context"] for item in asset_occurrences),
        ]
        searchable = compact_text(" ".join(searchable_parts))
        tags = classify_tags(searchable, roles)

        weighted_tokens: Counter[str] = Counter()
        for item in asset_occurrences:
            weighted_tokens.update(tokens(item["postTitle"]) * 3)
            weighted_tokens.update(tokens(item["context"]))
        weighted_tokens.update(tokens(row.get("original_name", "")) * 2)
        keywords = [
            token
            for token, _ in weighted_tokens.most_common(36)
            if token not in STOPWORDS
        ]
        bands = Counter(item["band"] for item in asset_occurrences)
        preferred_band = bands.most_common(1)[0][0] if bands else "body"
        eligible, excluded_reason = eligibility(row["kind"], roles)
        entry: dict[str, Any] = {
            "id": asset_id,
            "kind": row["kind"],
            "displayType": display_type(row["kind"], roles, frame_count),
            "originalName": row.get("original_name", ""),
            "extension": row.get("extension", ""),
            "width": int(row.get("width") or 0),
            "height": int(row.get("height") or 0),
            "frameCount": frame_count,
            "animated": row.get("animated", "").lower() == "true",
            "byteSize": int(row.get("byte_size") or 0),
            "sourceUrl": source_urls[0] if source_urls else "",
            "roles": sorted(role for role in roles if role),
            "tags": tags,
            "keywords": keywords,
            "searchText": truncate(searchable.lower(), 1500),
            "preferredBand": preferred_band,
            "placementBands": dict(sorted(bands.items())),
            "reuseCount": len(split_pipe(row.get("used_in_posts", ""))),
            "occurrenceCount": int(row.get("occurrence_count") or 0),
            "eligible": eligible,
            "excludedReason": excluded_reason,
            "sourcePosts": asset_occurrences[:6],
        }
        if not args.public:
            entry["localPath"] = str(local_path)
        library_assets.append(entry)

    eligible_count = sum(1 for item in library_assets if item["eligible"])
    media_values = list(media_counts_by_post.values())
    first_values = list(first_component_by_post.values())
    placement_profile = {
        "postCount": len(post_rows),
        "assetCount": len(library_assets),
        "eligibleAssetCount": eligible_count,
        "occurrenceCount": len(occurrence_rows),
        "mediaPerPost": {
            "mean": round(statistics.mean(media_values), 2) if media_values else 0,
            "median": statistics.median(media_values) if media_values else 0,
            "minimum": min(media_values) if media_values else 0,
            "maximum": max(media_values) if media_values else 0,
        },
        "firstMediaComponent": {
            "mean": round(statistics.mean(first_values), 2) if first_values else 0,
            "median": statistics.median(first_values) if first_values else 0,
        },
        "roleCounts": dict(sorted(role_counts.items())),
        "placementBands": dict(sorted(band_counts.items())),
    }
    payload = {
        "version": 1,
        "generatedAt": datetime.now(SEOUL).isoformat(timespec="seconds"),
        "blogId": "cjdsus4444",
        "blogUrl": "https://blog.naver.com/cjdsus4444",
        "placementProfile": placement_profile,
        "assets": library_assets,
    }
    if not args.public:
        payload["archiveRoot"] = str(archive)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "assets": len(library_assets),
                "eligible": eligible_count,
                "bytes": args.output.stat().st_size,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
