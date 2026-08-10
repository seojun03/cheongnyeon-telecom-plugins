#!/bin/bash
set -euo pipefail

REPOSITORY_SOURCE="${CHEONGNYEON_REPOSITORY_SOURCE:-seojun03/cheongnyeon-telecom-plugins}"
REPOSITORY_REF="${CHEONGNYEON_REPOSITORY_REF:-main}"
MARKETPLACE_NAME="cheongnyeon-telecom"
PLUGIN_NAME="cheongnyeon-telecom-blog"
PLUGIN_SELECTOR="$PLUGIN_NAME@$MARKETPLACE_NAME"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
MANIFEST_URL="https://raw.githubusercontent.com/$REPOSITORY_SOURCE/$REPOSITORY_REF/plugins/$PLUGIN_NAME/.codex-plugin/plugin.json"

log() {
  printf '[청년통신 자동 업데이트] %s\n' "$1"
}

fail() {
  printf '[청년통신 자동 업데이트 오류] %s\n' "$1" >&2
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

installed_version() {
  "$CODEX_BIN" plugin list --json 2>/dev/null | awk -v selector="$PLUGIN_SELECTOR" '
    index($0, "\"pluginId\"") && index($0, selector) { found = 1; next }
    found && index($0, "\"version\"") {
      line = $0
      sub(/^.*\"version\"[[:space:]]*:[[:space:]]*\"/, "", line)
      sub(/\".*$/, "", line)
      print line
      exit
    }
  '
}

mkdir -p "$CODEX_HOME_DIR"
CODEX_BIN="$(find_codex || true)"
[ -n "$CODEX_BIN" ] || fail "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다."

REMOTE_MANIFEST="$(curl -fsSL --retry 3 --connect-timeout 20 "$MANIFEST_URL")" || \
  fail "GitHub에서 최신 버전 정보를 가져오지 못했습니다."
REMOTE_VERSION="$(printf '%s\n' "$REMOTE_MANIFEST" | sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
[ -n "$REMOTE_VERSION" ] || fail "최신 플러그인 버전을 읽지 못했습니다."

CURRENT_VERSION="$(installed_version || true)"
if [ "$CURRENT_VERSION" = "$REMOTE_VERSION" ]; then
  log "최신 버전입니다: $REMOTE_VERSION"
  exit 0
fi

log "업데이트를 시작합니다: ${CURRENT_VERSION:-미설치} → $REMOTE_VERSION"
CODEX_HOME="$CODEX_HOME_DIR" \
CHEONGNYEON_CODEX_BIN="$CODEX_BIN" \
CHEONGNYEON_REPOSITORY_SOURCE="$REPOSITORY_SOURCE" \
CHEONGNYEON_REPOSITORY_REF="$REPOSITORY_REF" \
CHEONGNYEON_SKIP_APP_INSTALL=1 \
CHEONGNYEON_NO_LAUNCH=1 \
CHEONGNYEON_SKIP_AUTO_UPDATE_SETUP=1 \
/bin/bash -c "$(curl -fsSL --retry 3 --connect-timeout 20 "https://raw.githubusercontent.com/$REPOSITORY_SOURCE/$REPOSITORY_REF/install-macos.sh")"

UPDATED_VERSION="$(installed_version || true)"
[ "$UPDATED_VERSION" = "$REMOTE_VERSION" ] || \
  fail "업데이트 후 버전이 일치하지 않습니다. 현재: ${UPDATED_VERSION:-없음}, 최신: $REMOTE_VERSION"

log "업데이트 완료: $UPDATED_VERSION"
if [ "${CHEONGNYEON_NO_NOTIFICATION:-0}" != "1" ] && command -v osascript >/dev/null 2>&1; then
  osascript -e 'display notification "ChatGPT 앱을 다시 열면 최신 버전이 적용됩니다." with title "청년통신 플러그인 업데이트 완료"' >/dev/null 2>&1 || true
fi
