#!/usr/bin/env python3
"""Validate reference-bound Cheongnyeon HTML decoration."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROFILES = SKILL_DIR / "assets" / "reference-decoration-profiles.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="HTML file")
    parser.add_argument("--profile", required=True, help="master reference id")
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def article_fragment(raw: str) -> str:
    match = re.search(r"<article\b[^>]*>.*?</article>", raw, flags=re.I | re.S)
    if not match:
        raise ValueError("copy target <article> was not found")
    return match.group(0)


def attr_values(fragment: str, attribute: str) -> list[str]:
    pattern = re.compile(rf"\b{re.escape(attribute)}\s*=\s*([\"'])(.*?)\1", flags=re.I | re.S)
    return [match.group(2) for match in pattern.finditer(fragment)]


def image_sources(fragment: str) -> list[str]:
    sources: list[str] = []
    for tag in re.findall(r"<img\b[^>]*>", fragment, flags=re.I | re.S):
        values = attr_values(tag, "data-reference-source-url") or attr_values(tag, "src")
        if values:
            sources.append(html.unescape(values[0]))
    return sources


def is_ordered_subsequence(actual: list[str], expected: list[str]) -> bool:
    cursor = 0
    for value in actual:
        if cursor < len(expected) and value == expected[cursor]:
            cursor += 1
    return cursor == len(expected)


def visible_text(fragment: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", fragment, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return unicodedata.normalize("NFKC", html.unescape(value))


def paragraph_fragments(fragment: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"<(p|h[1-6])\b([^>]*)>(.*?)</\1>", flags=re.I | re.S)
    return [(match.group(2), match.group(3)) for match in pattern.finditer(fragment)]


class DirectArticleParagraphParser(HTMLParser):
    """Collect only direct-child body paragraphs and their gap boundaries."""

    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_article = False
        self.depth = 0
        self.current_attrs: dict[str, str] | None = None
        self.current_text: list[str] = []
        self.events: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if not self.in_article:
            if tag == "article":
                self.in_article = True
                self.depth = 0
            return

        if self.depth == 0:
            if tag == "p":
                self.current_attrs = {key.lower(): value or "" for key, value in attrs}
                self.current_text = []
            else:
                self.events.append(("boundary", ""))

        if self.current_attrs is not None and tag == "br":
            self.current_text.append("\n")

        if tag not in self.VOID_TAGS:
            self.depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self.in_article and self.current_attrs is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self.in_article:
            return
        if tag == "article" and self.depth == 0:
            self.in_article = False
            return
        if tag in self.VOID_TAGS:
            return

        self.depth = max(0, self.depth - 1)
        if tag == "p" and self.depth == 0 and self.current_attrs is not None:
            is_gap = (
                "data-preview-gap" in self.current_attrs
                or "data-naver-gap" in self.current_attrs
            )
            text = unicodedata.normalize("NFKC", "".join(self.current_text))
            self.events.append(("gap" if is_gap else "paragraph", text))
            self.current_attrs = None
            self.current_text = []


def estimated_mobile_line_count(text: str, characters_per_line: float) -> int:
    units = 0.0
    for char in " ".join(text.split()):
        if char.isspace():
            units += 0.45
        elif ord(char) < 128:
            units += 0.58
        else:
            units += 1.0
    return max(1, int((units + characters_per_line - 0.001) // characters_per_line))


def direct_body_group_metrics(
    fragment: str,
    characters_per_line: float,
) -> dict[str, object]:
    parser = DirectArticleParagraphParser()
    parser.feed(fragment)

    groups: list[dict[str, object]] = []
    current: list[tuple[str, int]] = []

    def flush() -> None:
        if not current:
            return
        groups.append(
            {
                "paragraphs": len(current),
                "estimatedMobileLines": sum(lines for _, lines in current),
                "text": " / ".join(text for text, _ in current),
            }
        )
        current.clear()

    for kind, text in parser.events:
        if kind != "paragraph":
            flush()
            continue
        clean = text.replace("\u2060", "").replace("\u200b", "").strip()
        if not clean:
            flush()
            continue
        current.append((clean, estimated_mobile_line_count(clean, characters_per_line)))
    flush()

    return {
        "groupCount": len(groups),
        "maxConsecutiveParagraphs": max((int(group["paragraphs"]) for group in groups), default=0),
        "maxEstimatedMobileLines": max((int(group["estimatedMobileLines"]) for group in groups), default=0),
        "groups": groups,
    }


def validate(raw: str, profile: dict[str, object]) -> dict[str, object]:
    fragment = article_fragment(raw)
    contract = profile.get("renderContract")
    if not isinstance(contract, dict):
        raise ValueError("selected profile has no renderContract")

    issues: list[str] = []
    roles = Counter(attr_values(fragment, "data-reference-role"))
    required_roles = contract.get("requiredRoleCounts", {})
    if isinstance(required_roles, dict):
        for role, expected in required_roles.items():
            actual = roles.get(str(role), 0)
            if actual != int(expected):
                issues.append(f"role {role}: {actual}, expected {expected}")

    ordered_roles = contract.get("requiredOrderedRoles", [])
    role_sequence = attr_values(fragment, "data-reference-role")
    if isinstance(ordered_roles, list):
        expected_sequence = [str(value) for value in ordered_roles]
        if expected_sequence and not is_ordered_subsequence(role_sequence, expected_sequence):
            issues.append(
                "reference role order mismatch: "
                f"actual {role_sequence}, expected subsequence {expected_sequence}"
            )

    media_slots = profile.get("mediaSlots", [])
    expected_media: list[str] = []
    if isinstance(media_slots, list):
        for slot in media_slots:
            if not isinstance(slot, dict):
                issues.append("invalid media slot entry")
                continue
            source = slot.get("sourceUrl")
            if not isinstance(source, str) or not source:
                issues.append("media slot sourceUrl is missing")
            elif not source.startswith("https://"):
                issues.append("media slot sourceUrl must use HTTPS")
            else:
                expected_media.append(source)

    media_sources = image_sources(fragment)
    if contract.get("requireExactMediaSources") is True and media_sources != expected_media:
        issues.append(f"image sources do not match the master: {media_sources}")

    colors = {value.lower() for value in re.findall(r"#[0-9a-fA-F]{6}", fragment)}
    required_colors = contract.get("requiredColors", [])
    if isinstance(required_colors, list):
        for color in required_colors:
            if str(color).lower() not in colors:
                issues.append(f"missing required color {color}")

    paragraphs = paragraph_fragments(fragment)
    centered = sum("text-align:center" in attrs.replace(" ", "").lower() for attrs, _ in paragraphs)
    center_ratio = centered / len(paragraphs) if paragraphs else 0.0
    minimum_center = float(contract.get("minimumCenterRatio", 0.0))
    if center_ratio < minimum_center:
        issues.append(f"center ratio {center_ratio:.3f}, minimum {minimum_center:.3f}")

    table_rows = [
        len(re.findall(r"<tr\b", table, flags=re.I))
        for table in re.findall(r"<table\b[^>]*>.*?</table>", fragment, flags=re.I | re.S)
    ]
    expected_rows = contract.get("tableRowCounts", [])
    if isinstance(expected_rows, list) and table_rows != [int(value) for value in expected_rows]:
        issues.append(f"table rows {table_rows}, expected {expected_rows}")

    underline_tags = re.findall(r"<u\b[^>]*>", fragment, flags=re.I | re.S)
    underline_roles = Counter(
        role
        for tag in underline_tags
        for role in attr_values(tag, "data-reference-underline-role")
    )
    required_underline_roles = contract.get("requiredUnderlineRoleCounts", {})
    if isinstance(required_underline_roles, dict):
        for role, expected in required_underline_roles.items():
            actual = underline_roles.get(str(role), 0)
            if actual != int(expected):
                issues.append(f"underline role {role}: {actual}, expected {expected}")
    expected_underline_count = int(contract.get("requiredUnderlineCount", 0))
    if len(underline_tags) != expected_underline_count:
        issues.append(
            f"underline count {len(underline_tags)}, expected {expected_underline_count}"
        )
    if len(underline_roles) == 0 and underline_tags:
        issues.append("unregistered underline found")
    if sum(underline_roles.values()) != len(underline_tags):
        issues.append("every underline must have exactly one reference underline role")
    if re.search(r"text-decoration\s*:", fragment, flags=re.I):
        issues.append("text-decoration CSS found; use role-bound <u> elements")
    if re.search(r"\bse-[a-z0-9_-]+", fragment, flags=re.I):
        issues.append("Naver internal se-* class found")

    dash_only = 0
    empty = 0
    for attrs, inner in paragraphs:
        text = visible_text(inner).replace("\u2060", "").replace("\u200b", "").strip()
        if re.fullmatch(r"[-ㅡ—–]+", text):
            dash_only += 1
        if not text and "data-preview-gap" not in attrs and "data-naver-gap" not in attrs:
            empty += 1
    if dash_only:
        issues.append(f"dash-only paragraphs {dash_only}")
    if empty:
        issues.append(f"empty paragraphs {empty}")

    characters_per_line = float(contract.get("estimatedMobileCharactersPerLine", 24.0))
    body_group_metrics = direct_body_group_metrics(fragment, characters_per_line)
    max_body_paragraphs = int(contract.get("maxConsecutiveDirectBodyParagraphs", 0))
    if (
        max_body_paragraphs > 0
        and int(body_group_metrics["maxConsecutiveParagraphs"]) > max_body_paragraphs
    ):
        issues.append(
            "body paragraph cadence exceeds limit: "
            f"{body_group_metrics['maxConsecutiveParagraphs']} consecutive paragraphs, "
            f"maximum {max_body_paragraphs}"
        )
    max_mobile_lines = int(contract.get("maxEstimatedMobileLinesPerBodyGroup", 0))
    min_mobile_lines = int(contract.get("minEstimatedMobileLinesPerBodyGroup", 0))
    if min_mobile_lines > 0:
        underfilled_groups = [
            group
            for group in body_group_metrics["groups"]
            if int(group["estimatedMobileLines"]) < min_mobile_lines
        ]
        if underfilled_groups:
            sample = str(underfilled_groups[0]["text"])
            issues.append(
                "mobile body cadence is too short: "
                f"{len(underfilled_groups)} group(s) under {min_mobile_lines} lines; "
                f"first: {sample[:120]}"
            )
    if max_mobile_lines > 0:
        overflowing_groups = [
            group
            for group in body_group_metrics["groups"]
            if int(group["estimatedMobileLines"]) > max_mobile_lines
        ]
        if overflowing_groups:
            sample = str(overflowing_groups[0]["text"])
            issues.append(
                "mobile body cadence exceeds limit: "
                f"{len(overflowing_groups)} group(s) over {max_mobile_lines} lines; "
                f"first: {sample[:120]}"
            )

    nested_header_highlight = re.search(
        r"<td\b(?=[^>]*(?:#28e1ff|background[^>]*28e1ff))[^>]*>(?:(?!</td>).)*?<(?:span|strong)\b[^>]*background",
        fragment,
        flags=re.I | re.S,
    )
    if nested_header_highlight:
        issues.append("nested table-header highlight found")

    return {
        "status": "pass" if not issues else "fail",
        "metrics": {
            "roles": dict(roles),
            "colors": sorted(colors),
            "centerRatio": round(center_ratio, 3),
            "tableRowCounts": table_rows,
            "paragraphCount": len(paragraphs),
            "referenceRoleSequence": role_sequence,
            "imageSources": media_sources,
            "underlineRoles": dict(underline_roles),
            "underlineCount": len(underline_tags),
            "bodyGroupCount": body_group_metrics["groupCount"],
            "maxConsecutiveBodyParagraphs": body_group_metrics["maxConsecutiveParagraphs"],
            "minRequiredEstimatedMobileLinesPerBodyGroup": min_mobile_lines,
            "maxEstimatedMobileLinesPerBodyGroup": body_group_metrics["maxEstimatedMobileLines"],
        },
        "issues": issues,
    }


def main() -> int:
    args = parse_args()
    try:
        raw = args.input.read_text(encoding="utf-8")
        profiles = json.loads(args.profiles.read_text(encoding="utf-8"))
        profile = profiles["profiles"][args.profile]
        result = validate(raw, profile)
    except (OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"validation setup failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status: {result['status']}")
        for key, value in result["metrics"].items():
            print(f"{key}: {value}")
        for issue in result["issues"]:
            print(f"[ERROR] {issue}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
