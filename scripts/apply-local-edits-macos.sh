#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
PLUGIN_NAME="cheongnyeon-telecom-blog"
MARKETPLACE_NAME="cheongnyeon-telecom"
PLUGIN_SELECTOR="$PLUGIN_NAME@$MARKETPLACE_NAME"
PLUGIN_ROOT="$REPO_ROOT/plugins/$PLUGIN_NAME"
MANIFEST="$PLUGIN_ROOT/.codex-plugin/plugin.json"
SKILL_FILE="$PLUGIN_ROOT/skills/$PLUGIN_NAME/SKILL.md"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"

log() {
  printf '[청년통신 로컬 수정 적용] %s\n' "$1"
}

fail() {
  printf '[청년통신 로컬 수정 오류] %s\n' "$1" >&2
  exit 1
}

find_codex() {
  local candidate=""
  local app_path
  if [ -n "${CHEONGNYEON_CODEX_BIN:-}" ] && [ -x "$CHEONGNYEON_CODEX_BIN" ]; then
    printf '%s\n' "$CHEONGNYEON_CODEX_BIN"
    return 0
  fi
  if command -v codex >/dev/null 2>&1; then
    candidate="$(command -v codex)"
    if "$candidate" plugin --help >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi
  for app_path in /Applications/ChatGPT.app /Applications/Codex.app "$HOME/Applications/ChatGPT.app" "$HOME/Applications/Codex.app"; do
    [ -d "$app_path/Contents" ] || continue
    candidate="$(find "$app_path/Contents" -type f -name codex -perm -111 -print 2>/dev/null | head -n 1)"
    if [ -n "$candidate" ] && "$candidate" plugin --help >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

[ -f "$MANIFEST" ] || fail "플러그인 매니페스트를 찾지 못했습니다: $MANIFEST"
[ -f "$SKILL_FILE" ] || fail "수정할 SKILL.md를 찾지 못했습니다: $SKILL_FILE"
[ -w "$SKILL_FILE" ] || fail "SKILL.md에 쓰기 권한이 없습니다."
command -v plutil >/dev/null 2>&1 || fail "plutil을 찾지 못했습니다."
mkdir -p "$CODEX_HOME_DIR"
export CODEX_HOME="$CODEX_HOME_DIR"
CODEX_BIN="$(find_codex || true)"
[ -n "$CODEX_BIN" ] || fail "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다."

OLD_VERSION="$(/usr/bin/plutil -extract version raw -o - "$MANIFEST")"
BASE_VERSION="${OLD_VERSION%%+*}"
CACHEBUSTER="$(date -u +%Y%m%d%H%M%S)"
NEW_VERSION="$BASE_VERSION+codex.local.$CACHEBUSTER"
/usr/bin/plutil -replace version -string "$NEW_VERSION" "$MANIFEST"

log "로컬 지침을 재설치합니다: $NEW_VERSION"
"$CODEX_BIN" plugin add "$PLUGIN_SELECTOR" --json >/dev/null

PLUGIN_LIST="$("$CODEX_BIN" plugin list --json)"
printf '%s' "$PLUGIN_LIST" | grep -Fq "\"version\": \"$NEW_VERSION\"" || \
  fail "수정한 버전의 재설치를 확인하지 못했습니다."
printf '%s' "$PLUGIN_LIST" | awk -v selector="$PLUGIN_SELECTOR" '
  index($0, "\"pluginId\"") && index($0, selector) { found = 1 }
  found && index($0, "\"sourceType\"") && index($0, "\"local\"") { ok = 1; exit }
  END { exit ok ? 0 : 1 }
' || fail "로컬 편집본이 아닌 마켓플레이스에 연결되어 있습니다. 편집용 설치기를 다시 실행하세요."

log "적용 완료: ChatGPT에서 새 작업을 열어 테스트하세요."
log "수정 파일: $SKILL_FILE"
