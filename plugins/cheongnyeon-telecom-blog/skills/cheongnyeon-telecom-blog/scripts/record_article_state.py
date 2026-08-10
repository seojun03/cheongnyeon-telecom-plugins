#!/usr/bin/env python3
"""Record one completed article and retain only the newest three records."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE = SKILL_DIR / "state" / "recent-articles.json"


def record(state: dict[str, object], entry: dict[str, str]) -> dict[str, object]:
    max_entries = int(state.get("maxEntries", 3))
    current = state.get("entries", [])
    entries = [item for item in current if isinstance(item, dict)] if isinstance(current, list) else []
    identity = (entry["title"], entry["ideaReferenceUrl"], entry["writingMasterId"])
    entries = [
        item
        for item in entries
        if (str(item.get("title")), str(item.get("ideaReferenceUrl")), str(item.get("writingMasterId") or item.get("type")))
        != identity
    ]
    entries.insert(0, entry)
    return {"maxEntries": max_entries, "entries": entries[:max_entries]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--title", required=True)
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--idea-reference-id", required=True)
    parser.add_argument("--idea-reference-title", required=True)
    parser.add_argument("--idea-reference-url", required=True)
    parser.add_argument("--idea-type", required=True)
    parser.add_argument("--title-pattern-id", required=True)
    parser.add_argument("--writing-master-id", required=True)
    parser.add_argument("--writing-reference-url", required=True)
    parser.add_argument("--written-at", default=date.today().isoformat())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else {"maxEntries": 3, "entries": []}
    entry = {
        "title": args.title.strip(),
        "mainKeyword": args.keyword.strip(),
        "ideaReferenceId": args.idea_reference_id,
        "ideaReferenceTitle": args.idea_reference_title,
        "ideaReferenceUrl": args.idea_reference_url,
        "ideaType": args.idea_type,
        "titlePatternId": args.title_pattern_id,
        "writingMasterId": args.writing_master_id,
        "writingReferenceUrl": args.writing_reference_url,
        "writtenAt": args.written_at,
    }
    updated = record(state, entry)
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(updated, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
