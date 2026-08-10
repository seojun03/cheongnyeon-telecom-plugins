#!/bin/bash
set -euo pipefail

REPOSITORY_SOURCE="${CHEONGNYEON_REPOSITORY_SOURCE:-seojun03/cheongnyeon-telecom-plugins}"
REPOSITORY_REF="${CHEONGNYEON_REPOSITORY_REF:-main}"
MARKETPLACE_NAME="cheongnyeon-telecom"
PLUGIN_NAME="cheongnyeon-telecom-blog"
PLUGIN_SELECTOR="$PLUGIN_NAME@$MARKETPLACE_NAME"
AUTO_UPDATE_LABEL="com.cheongnyeon.telecom.plugin-updater"
EDITABLE_ROOT="${CHEONGNYEON_EDITABLE_ROOT:-$HOME/CheongnyeonTelecomPlugin}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"

log() {
  printf '[청년통신 편집용 설치] %s\n' "$1"
}

fail() {
  printf '[청년통신 편집용 설치 오류] %s\n' "$1" >&2
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

disable_auto_update() {
  local launch_agents_dir plist_path disabled_path user_id
  launch_agents_dir="${CHEONGNYEON_LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
  plist_path="$launch_agents_dir/$AUTO_UPDATE_LABEL.plist"
  user_id="$(id -u)"
  /bin/launchctl bootout "gui/$user_id/$AUTO_UPDATE_LABEL" >/dev/null 2>&1 || true
  /bin/launchctl bootout "gui/$user_id" "$plist_path" >/dev/null 2>&1 || true
  if [ -f "$plist_path" ]; then
    disabled_path="$plist_path.disabled"
    [ ! -e "$disabled_path" ] || disabled_path="$disabled_path.$(date -u +%Y%m%d%H%M%S)"
    mv "$plist_path" "$disabled_path"
  fi
  log "중앙 자동 업데이트를 해제했습니다."
}

download_editable_copy() {
  local temp_dir archive_path source_root archive_url
  if [ -e "$EDITABLE_ROOT" ]; then
    [ -f "$EDITABLE_ROOT/.agents/plugins/marketplace.json" ] || \
      fail "기존 폴더가 편집용 플러그인 구조가 아닙니다: $EDITABLE_ROOT"
    [ -f "$EDITABLE_ROOT/plugins/$PLUGIN_NAME/skills/$PLUGIN_NAME/SKILL.md" ] || \
      fail "기존 폴더에서 SKILL.md를 찾지 못했습니다: $EDITABLE_ROOT"
    log "기존 로컬 수정본을 보존하고 다시 연결합니다."
    return 0
  fi

  temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/cheongnyeon-editable.XXXXXX")"
  archive_path="$temp_dir/plugin.zip"
  archive_url="https://codeload.github.com/$REPOSITORY_SOURCE/zip/$REPOSITORY_REF?cachebust=$(date +%s)"
  log "자동 업데이트와 분리된 로컬 수정본을 다운로드합니다."
  curl -fL --retry 3 --connect-timeout 20 "$archive_url" -o "$archive_path"
  ditto -x -k "$archive_path" "$temp_dir/unpacked"
  source_root="$(find "$temp_dir/unpacked" -mindepth 1 -maxdepth 1 -type d -print -quit)"
  [ -n "$source_root" ] || fail "다운로드 압축에서 플러그인 폴더를 찾지 못했습니다."
  mkdir -p "$(dirname "$EDITABLE_ROOT")"
  mv "$source_root" "$EDITABLE_ROOT"
  find "$temp_dir" -type f -delete 2>/dev/null || true
  find "$temp_dir" -depth -type d -empty -delete 2>/dev/null || true
}

create_desktop_shortcut() {
  local desktop_dir shortcut_path apply_script
  [ "${CHEONGNYEON_SKIP_DESKTOP_SHORTCUT:-0}" != "1" ] || return 0
  desktop_dir="$HOME/Desktop"
  [ -d "$desktop_dir" ] || return 0
  shortcut_path="$desktop_dir/청년통신_플러그인_내수정적용.command"
  apply_script="$EDITABLE_ROOT/scripts/apply-local-edits-macos.sh"
  {
    printf '#!/bin/bash\n'
    printf '/bin/bash %q\n' "$apply_script"
    printf 'STATUS=$?\n'
    printf "read -r -p 'Enter를 누르면 닫힙니다.'\n"
    printf 'exit "$STATUS"\n'
  } > "$shortcut_path"
  chmod 700 "$shortcut_path" "$apply_script"
}

disable_auto_update

BASE_INSTALLER_URL="https://raw.githubusercontent.com/$REPOSITORY_SOURCE/$REPOSITORY_REF/install-macos.sh?cachebust=$(date +%s)"
CHEONGNYEON_DISABLE_AUTO_UPDATE=1 \
CHEONGNYEON_NO_LAUNCH=1 \
/bin/bash -c "$(curl -fsSL --retry 3 --connect-timeout 20 "$BASE_INSTALLER_URL")"

download_editable_copy
chmod 700 "$EDITABLE_ROOT/scripts/apply-local-edits-macos.sh"
mkdir -p "$CODEX_HOME_DIR"
export CODEX_HOME="$CODEX_HOME_DIR"
CODEX_BIN="$(find_codex || true)"
[ -n "$CODEX_BIN" ] || fail "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다."

"$CODEX_BIN" plugin remove "$PLUGIN_SELECTOR" --json >/dev/null 2>&1 || true
"$CODEX_BIN" plugin marketplace remove "$MARKETPLACE_NAME" --json >/dev/null 2>&1 || true
"$CODEX_BIN" plugin marketplace add "$EDITABLE_ROOT" --json >/dev/null
"$CODEX_BIN" plugin add "$PLUGIN_SELECTOR" --json >/dev/null

PLUGIN_LIST="$("$CODEX_BIN" plugin list --json)"
printf '%s' "$PLUGIN_LIST" | awk -v selector="$PLUGIN_SELECTOR" '
  index($0, "\"pluginId\"") && index($0, selector) { found = 1 }
  found && index($0, "\"sourceType\"") && index($0, "\"local\"") { ok = 1; exit }
  END { exit ok ? 0 : 1 }
' || fail "설치된 플러그인이 로컬 수정본에 연결되지 않았습니다."
[ -w "$EDITABLE_ROOT/plugins/$PLUGIN_NAME/skills/$PLUGIN_NAME/SKILL.md" ] || \
  fail "설치된 SKILL.md에 쓰기 권한이 없습니다."

create_desktop_shortcut
if [ "${CHEONGNYEON_NO_LAUNCH:-0}" != "1" ]; then
  if [ -d /Applications/ChatGPT.app ]; then
    open -a /Applications/ChatGPT.app
  elif [ -d /Applications/Codex.app ]; then
    open -a /Applications/Codex.app
  fi
fi

log "설치 완료: 이 PC는 중앙 자동 업데이트를 받지 않습니다."
log "수정 파일: $EDITABLE_ROOT/plugins/$PLUGIN_NAME/skills/$PLUGIN_NAME/SKILL.md"
log "수정 후 바탕화면의 '청년통신_플러그인_내수정적용.command'를 실행하세요."
