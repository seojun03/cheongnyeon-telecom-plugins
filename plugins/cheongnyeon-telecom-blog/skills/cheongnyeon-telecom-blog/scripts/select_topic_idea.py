#!/usr/bin/env python3
"""Select fresh title/topic references without loading external article prose."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY = SKILL_DIR / "references" / "topic-idea-library.json"
DEFAULT_STATE = SKILL_DIR / "state" / "recent-articles.json"


def stable_number(*parts: str) -> int:
    payload = "\u241f".join(parts).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest(), 16)


def date_score(value: str) -> int:
    digits = [part for part in value.replace("년", ".").replace("월", ".").replace("일", ".").split(".") if part.strip().isdigit()]
    if len(digits) < 3:
        return 0
    year, month, day = (int(part.strip()) for part in digits[:3])
    return year * 10_000 + month * 100 + day


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def recent_dimensions(state: dict[str, object]) -> tuple[set[str], set[str], set[str], set[str]]:
    entries = state.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    idea_types = {str(entry.get("ideaType")) for entry in entries if isinstance(entry, dict) and entry.get("ideaType")}
    patterns = {str(entry.get("titlePatternId")) for entry in entries if isinstance(entry, dict) and entry.get("titlePatternId")}
    urls = {str(entry.get("ideaReferenceUrl")) for entry in entries if isinstance(entry, dict) and entry.get("ideaReferenceUrl")}
    masters = {
        str(entry.get("writingMasterId") or entry.get("type"))
        for entry in entries
        if isinstance(entry, dict) and (entry.get("writingMasterId") or entry.get("type"))
    }
    return idea_types, patterns, urls, masters


def choose_master(
    options: list[str],
    registry: dict[str, object],
    recent_masters: set[str],
    selected_masters: set[str],
    keyword: str,
    seed: str,
    article_id: str,
) -> str:
    usable = [master_id for master_id in options if master_id in registry]
    if not usable:
        raise ValueError(f"No registered writing master for {article_id}")
    return max(
        usable,
        key=lambda master_id: (
            master_id not in recent_masters,
            master_id not in selected_masters,
            stable_number(keyword, seed, article_id, master_id),
        ),
    )


def select_ideas(
    library: dict[str, object],
    state: dict[str, object],
    keyword: str,
    *,
    count: int = 1,
    seed: str = "",
) -> list[dict[str, object]]:
    articles = library.get("articles", [])
    registry = library.get("writingMasterRegistry", {})
    if not isinstance(articles, list) or not isinstance(registry, dict):
        raise ValueError("Malformed topic idea library")
    eligible = [
        article
        for article in articles
        if isinstance(article, dict)
        and article.get("sourceFactsBlocked") is True
        and any(master_id in registry for master_id in article.get("compatibleWritingMasterIds", []))
    ]
    if not eligible:
        raise ValueError("No eligible topic idea profiles")

    recent_types, recent_patterns, recent_urls, recent_masters = recent_dimensions(state)
    fresh_urls = [article for article in eligible if str(article.get("sourceUrl")) not in recent_urls]
    pool = fresh_urls or eligible
    selected: list[dict[str, object]] = []
    selected_article_ids: set[str] = set()
    selected_types: set[str] = set()
    selected_patterns: set[str] = set()
    selected_masters: set[str] = set()
    seed = seed or date.today().isoformat()

    for slot in range(min(count, len(pool))):
        remaining = [article for article in pool if str(article.get("id")) not in selected_article_ids]
        article = max(
            remaining,
            key=lambda item: (
                str(item.get("primaryType")) not in recent_types,
                str(item.get("primaryType")) not in selected_types,
                str(item.get("titlePatternId")) not in recent_patterns,
                str(item.get("titlePatternId")) not in selected_patterns,
                min(len(item.get("titleHookSignals", [])), 4),
                date_score(str(item.get("publishedAt", ""))),
                stable_number(keyword, seed, str(slot), str(item.get("id"))),
            ),
        )
        master_id = choose_master(
            [str(value) for value in article.get("compatibleWritingMasterIds", [])],
            registry,
            recent_masters,
            selected_masters,
            keyword,
            seed,
            str(article.get("id")),
        )
        master = registry[master_id]
        selected.append(
            {
                "ideaReferenceId": article["id"],
                "ideaReferenceTitle": article["sourceTitle"],
                "ideaReferenceUrl": article["sourceUrl"],
                "ideaType": article["primaryType"],
                "ideaTypeLabel": article["primaryTypeLabel"],
                "secondaryAngle": article["secondaryAngle"],
                "titlePatternId": article["titlePatternId"],
                "titlePatternDescription": article["titlePatternDescription"],
                "readerQuestion": article["readerQuestion"],
                "answerAgenda": article["answerAgenda"],
                "writingMasterId": master_id,
                "writingMasterLabel": master["label"],
                "writingReferenceUrl": master["sourceUrl"],
                "factPolicy": "Use only Cheongnyeon Telecom evidence; never transfer facts from the idea reference.",
            }
        )
        selected_types.add(str(article["primaryType"]))
        selected_patterns.add(str(article["titlePatternId"]))
        selected_masters.add(master_id)
        selected_article_ids.add(str(article["id"]))
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--count", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--seed", default="")
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selections = select_ideas(
        load_json(args.library),
        load_json(args.state),
        args.keyword.strip(),
        count=args.count,
        seed=args.seed,
    )
    print(json.dumps({"keyword": args.keyword.strip(), "selections": selections}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
