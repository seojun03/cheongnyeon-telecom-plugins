#!/usr/bin/env python3
"""Validate the public marketplace and plugin distribution."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "cheongnyeon-telecom-blog"
MARKETPLACE_NAME = "cheongnyeon-telecom"
PLUGIN_ROOT = ROOT / "plugins" / PLUGIN_NAME
MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_json(path: Path) -> dict:
    require(path.is_file(), f"필수 파일이 없습니다: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest() -> str:
    manifest = load_json(MANIFEST)
    require(manifest.get("name") == PLUGIN_NAME, "plugin.json name 불일치")
    require(PLUGIN_ROOT.name == PLUGIN_NAME, "플러그인 폴더 이름 불일치")
    version = manifest.get("version", "")
    require(bool(SEMVER.fullmatch(version)), "plugin.json version이 SemVer가 아닙니다")
    require(bool(manifest.get("description")), "plugin.json description 누락")
    require(bool(manifest.get("author", {}).get("name")), "plugin.json author.name 누락")
    interface = manifest.get("interface", {})
    for field in ("displayName", "shortDescription", "longDescription", "developerName", "category", "capabilities"):
        require(bool(interface.get(field)), f"plugin.json interface.{field} 누락")
    prompts = interface.get("defaultPrompt", [])
    require(len(prompts) <= 3, "defaultPrompt는 3개 이하여야 합니다")
    require(all(len(prompt) <= 128 for prompt in prompts), "defaultPrompt는 128자 이하여야 합니다")
    require(manifest.get("skills") == "./skills/", "skills 경로가 ./skills/가 아닙니다")
    return version


def validate_marketplace() -> None:
    marketplace = load_json(MARKETPLACE)
    require(marketplace.get("name") == MARKETPLACE_NAME, "marketplace 이름 불일치")
    entries = [entry for entry in marketplace.get("plugins", []) if entry.get("name") == PLUGIN_NAME]
    require(len(entries) == 1, "마켓플레이스 플러그인 항목은 정확히 하나여야 합니다")
    entry = entries[0]
    require(entry.get("source") == {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"}, "마켓플레이스 source 불일치")
    require(entry.get("policy", {}).get("installation") == "AVAILABLE", "installation 정책 불일치")
    require(entry.get("policy", {}).get("authentication") == "ON_INSTALL", "authentication 정책 불일치")
    require(entry.get("category") == "Productivity", "category 불일치")


def validate_tree() -> None:
    require((PLUGIN_ROOT / "skills" / PLUGIN_NAME / "SKILL.md").is_file(), "SKILL.md 누락")
    require((ROOT / "install-macos.sh").is_file(), "macOS 설치기 누락")
    require((ROOT / "install-windows.ps1").is_file(), "Windows 설치기 누락")
    forbidden = []
    long_paths = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT)
        if path.name == ".DS_Store" or path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}:
            forbidden.append(str(relative))
        if len(str(relative)) > 220:
            long_paths.append(str(relative))
    require(not forbidden, "배포 금지 캐시 파일: " + ", ".join(forbidden))
    require(not long_paths, "Windows 안전 길이 220자를 넘는 경로: " + ", ".join(long_paths))


def validate_installers() -> None:
    for path in (ROOT / "install-macos.sh", ROOT / "install-windows.ps1"):
        text = path.read_text(encoding="utf-8")
        require("seojun03/cheongnyeon-telecom-plugins" in text, f"{path.name} 저장소 상수 누락")
        require(MARKETPLACE_NAME in text, f"{path.name} 마켓플레이스 상수 누락")
        require(PLUGIN_NAME in text, f"{path.name} 플러그인 상수 누락")
        require("marketplace" in text and "add" in text, f"{path.name} 마켓플레이스 등록 누락")
        require("plugin" in text and "add" in text, f"{path.name} 플러그인 설치 누락")


def main() -> int:
    version = validate_manifest()
    validate_marketplace()
    validate_tree()
    validate_installers()
    print(f"배포 검증 통과: {PLUGIN_NAME} {version}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"배포 검증 실패: {exc}", file=sys.stderr)
        raise SystemExit(1)
