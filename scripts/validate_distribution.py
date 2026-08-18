#!/usr/bin/env python3
"""Validate the public marketplace and plugin distribution."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


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
    required_files = (
        PLUGIN_ROOT / "skills" / PLUGIN_NAME / "SKILL.md",
        ROOT / "install-macos.sh",
        ROOT / "install-windows.ps1",
        ROOT / "install-editable-macos.sh",
        ROOT / "install-editable-windows.ps1",
        ROOT / "INSTALL-WINDOWS.cmd",
        ROOT / "install-from-download-windows.ps1",
        ROOT / "scripts" / "update-macos.sh",
        ROOT / "scripts" / "update-windows.ps1",
        ROOT / "scripts" / "apply-local-edits-macos.sh",
        ROOT / "scripts" / "apply-local-edits-windows.ps1",
        ROOT / "scripts" / "publish-update.sh",
        ROOT / "AUTHOR_UPDATE.md",
    )
    for path in required_files:
        require(path.is_file(), f"필수 파일이 없습니다: {path.relative_to(ROOT)}")
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
        require("6시간마다" in text, f"{path.name} 자동 업데이트 안내 누락")
    require("StartInterval" in (ROOT / "install-macos.sh").read_text(encoding="utf-8"), "macOS LaunchAgent 누락")
    require("Register-ScheduledTask" in (ROOT / "install-windows.ps1").read_text(encoding="utf-8"), "Windows 예약 작업 누락")
    windows_installer = (ROOT / "install-windows.ps1").read_text(encoding="utf-8")
    require("Test-WingetPackageInstalled" in windows_installer, "Windows 기설치 패키지 감지 누락")
    require("-1978335189" in windows_installer, "winget 최신 버전 반환값 처리 누락")
    require("플러그인 설치는 계속합니다" in windows_installer, "ChatGPT 앱 실패 시 플러그인 계속 처리 누락")

    editable_installers = (
        ROOT / "install-editable-macos.sh",
        ROOT / "install-editable-windows.ps1",
    )
    for path in editable_installers:
        text = path.read_text(encoding="utf-8")
        require("CHEONGNYEON_EDITABLE_ROOT" in text, f"{path.name} 편집 폴더 설정 누락")
        require("CHEONGNYEON_DISABLE_AUTO_UPDATE" in text, f"{path.name} 자동 업데이트 차단 누락")
        require("sourceType" in text and "local" in text, f"{path.name} 로컬 소스 검증 누락")
        require("apply-local-edits" in text, f"{path.name} 로컬 수정 적용기 연결 누락")

    mac_editable = (ROOT / "install-editable-macos.sh").read_text(encoding="utf-8")
    windows_editable = (ROOT / "install-editable-windows.ps1").read_text(encoding="utf-8")
    require("launchctl bootout" in mac_editable, "macOS 편집용 설치기의 자동 업데이트 해제 누락")
    require("Unregister-ScheduledTask" in windows_editable, "Windows 편집용 설치기의 자동 업데이트 해제 누락")
    require("CHEONGNYEON_SKIP_APP_INSTALL" in windows_editable, "Windows 편집용 설치기의 ChatGPT 앱 변경 차단 누락")

    download_installer = (ROOT / "install-from-download-windows.ps1").read_text(encoding="utf-8")
    require("Test-PluginTree" in download_installer, "Windows ZIP 설치기의 로컬 파일 검증 누락")
    require("sourceType" in download_installer and "local" in download_installer, "Windows ZIP 설치기의 로컬 연결 검증 누락")
    require("Get-AppxPackage" in download_installer, "Windows ZIP 설치기의 ChatGPT 앱 감지 누락")
    require("Install-WingetPackage" not in download_installer and "winget.exe" not in download_installer, "Windows ZIP 설치기가 winget을 실행할 수 있습니다")
    require("Invoke-WebRequest" not in download_installer and "Invoke-RestMethod" not in download_installer, "Windows ZIP 설치기는 네트워크를 사용하면 안 됩니다")

    for path in (
        ROOT / "install-windows.ps1",
        ROOT / "install-editable-windows.ps1",
        ROOT / "scripts" / "update-windows.ps1",
        ROOT / "scripts" / "apply-local-edits-windows.ps1",
    ):
        text = path.read_text(encoding="utf-8")
        require('ChatGPT|OpenAI|Codex' in text, f"{path.name} 통합 ChatGPT 앱 감지 누락")

    for path in (
        ROOT / "scripts" / "apply-local-edits-macos.sh",
        ROOT / "scripts" / "apply-local-edits-windows.ps1",
    ):
        text = path.read_text(encoding="utf-8")
        require("codex.local" in text, f"{path.name} 로컬 캐시버스터 누락")
        require("sourceType" in text and "local" in text, f"{path.name} 로컬 연결 검증 누락")


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
