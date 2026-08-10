#!/bin/bash
set -euo pipefail

REPOSITORY_SOURCE="${CHEONGNYEON_REPOSITORY_SOURCE:-seojun03/cheongnyeon-telecom-plugins}"
REPOSITORY_REF="${CHEONGNYEON_REPOSITORY_REF:-main}"
MARKETPLACE_NAME="cheongnyeon-telecom"
PLUGIN_NAME="cheongnyeon-telecom-blog"
LEGACY_MARKETPLACE_NAME="cheongnyeon-telecom-share"
CHATGPT_DMG_URL="https://persistent.oaistatic.com/codex-app-prod/Codex.dmg"
OPENAI_TEAM_ID="2DC432GLL2"
AUTO_UPDATE_LABEL="com.cheongnyeon.telecom.plugin-updater"
AUTO_UPDATE_INTERVAL_SECONDS=21600
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"

log() {
  printf '[청년통신 설치] %s\n' "$1"
}

fail() {
  printf '[청년통신 설치 오류] %s\n' "$1" >&2
  exit 1
}

is_openai_app() {
  local app_path="$1"
  local team_id
  [ -d "$app_path" ] || return 1
  team_id="$(codesign -dv --verbose=4 "$app_path" 2>&1 | sed -n 's/^TeamIdentifier=//p' | head -n 1)"
  [ "$team_id" = "$OPENAI_TEAM_ID" ]
}

find_embedded_codex() {
  local app_path="$1"
  find "$app_path/Contents" -type f -name codex -perm -111 -print 2>/dev/null | head -n 1
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
    if is_openai_app "$app_path"; then
      candidate="$(find_embedded_codex "$app_path")"
      if [ -n "$candidate" ] && "$candidate" plugin --help >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

cleanup_installer() {
  if [ -n "${INSTALL_MOUNT_DIR:-}" ] && [ -d "$INSTALL_MOUNT_DIR" ]; then
    hdiutil detach "$INSTALL_MOUNT_DIR" >/dev/null 2>&1 || true
  fi
  if [ -n "${INSTALL_TEMP_DIR:-}" ] && [ -d "$INSTALL_TEMP_DIR" ]; then
    rm -rf "$INSTALL_TEMP_DIR"
  fi
}

install_chatgpt_app() {
  local dmg_path app_source
  [ "${CHEONGNYEON_SKIP_APP_INSTALL:-0}" != "1" ] || return 0
  if is_openai_app /Applications/ChatGPT.app || is_openai_app /Applications/Codex.app; then
    return 0
  fi
  command -v curl >/dev/null 2>&1 || fail "curl을 찾을 수 없습니다."
  INSTALL_TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/cheongnyeon-chatgpt.XXXXXX")"
  INSTALL_MOUNT_DIR="$INSTALL_TEMP_DIR/mount"
  dmg_path="$INSTALL_TEMP_DIR/ChatGPT.dmg"
  mkdir -p "$INSTALL_MOUNT_DIR"
  trap cleanup_installer EXIT
  log "공식 ChatGPT 앱을 다운로드합니다."
  curl -fL --retry 3 --connect-timeout 20 "$CHATGPT_DMG_URL" -o "$dmg_path"
  hdiutil attach "$dmg_path" -nobrowse -readonly -mountpoint "$INSTALL_MOUNT_DIR" >/dev/null
  app_source="$(find "$INSTALL_MOUNT_DIR" -maxdepth 2 -type d \( -name 'ChatGPT.app' -o -name 'Codex.app' \) -print -quit)"
  [ -n "$app_source" ] || fail "다운로드한 이미지에서 ChatGPT 앱을 찾지 못했습니다."
  is_openai_app "$app_source" || fail "다운로드한 앱의 OpenAI 서명을 확인하지 못했습니다."
  ditto "$app_source" "/Applications/$(basename "$app_source")" 2>/dev/null || \
    fail "앱을 /Applications에 복사하지 못했습니다. 관리자 권한이 있는 계정에서 다시 실행하세요."
  cleanup_installer
  INSTALL_TEMP_DIR=""
  INSTALL_MOUNT_DIR=""
  trap - EXIT
}

install_auto_update() {
  local updater_root launch_agents_dir bootstrap_path plist_path log_path user_id
  [ "${CHEONGNYEON_DISABLE_AUTO_UPDATE:-0}" != "1" ] || {
    log "자동 업데이트 등록을 건너뜁니다."
    return 0
  }
  [ "${CHEONGNYEON_SKIP_AUTO_UPDATE_SETUP:-0}" != "1" ] || return 0

  updater_root="${CHEONGNYEON_AUTO_UPDATE_ROOT:-$HOME/Library/Application Support/CheongnyeonTelecom}"
  launch_agents_dir="${CHEONGNYEON_LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
  bootstrap_path="$updater_root/run-update.sh"
  plist_path="$launch_agents_dir/$AUTO_UPDATE_LABEL.plist"
  log_path="$updater_root/plugin-update.log"
  mkdir -p "$updater_root" "$launch_agents_dir"

  {
    printf '#!/bin/bash\n'
    printf 'set -euo pipefail\n'
    printf 'export CODEX_HOME=%q\n' "$CODEX_HOME_DIR"
    printf 'export CHEONGNYEON_CODEX_BIN=%q\n' "$CODEX_BIN"
    printf 'export CHEONGNYEON_REPOSITORY_SOURCE=%q\n' "$REPOSITORY_SOURCE"
    printf 'export CHEONGNYEON_REPOSITORY_REF=%q\n' "$REPOSITORY_REF"
    printf '/bin/bash -c "$(/usr/bin/curl -fsSL --retry 3 --connect-timeout 20 %q)"\n' \
      "https://raw.githubusercontent.com/$REPOSITORY_SOURCE/$REPOSITORY_REF/scripts/update-macos.sh"
  } > "$bootstrap_path"
  chmod 700 "$bootstrap_path"

  /usr/bin/plutil -create xml1 "$plist_path"
  /usr/bin/plutil -insert Label -string "$AUTO_UPDATE_LABEL" "$plist_path"
  /usr/bin/plutil -insert ProgramArguments -xml '<array/>' "$plist_path"
  /usr/bin/plutil -insert ProgramArguments.0 -string /bin/bash "$plist_path"
  /usr/bin/plutil -insert ProgramArguments.1 -string "$bootstrap_path" "$plist_path"
  /usr/bin/plutil -insert RunAtLoad -bool true "$plist_path"
  /usr/bin/plutil -insert StartInterval -integer "$AUTO_UPDATE_INTERVAL_SECONDS" "$plist_path"
  /usr/bin/plutil -insert StandardOutPath -string "$log_path" "$plist_path"
  /usr/bin/plutil -insert StandardErrorPath -string "$log_path" "$plist_path"
  /usr/bin/plutil -insert ProcessType -string Background "$plist_path"
  /usr/bin/plutil -lint "$plist_path" >/dev/null

  if [ "${CHEONGNYEON_SKIP_SCHEDULER_ACTIVATION:-0}" != "1" ]; then
    user_id="$(id -u)"
    /bin/launchctl bootout "gui/$user_id" "$plist_path" >/dev/null 2>&1 || true
    if ! /bin/launchctl bootstrap "gui/$user_id" "$plist_path" >/dev/null 2>&1; then
      log "자동 업데이트 파일은 등록했습니다. 다음 로그인부터 자동 실행됩니다."
      return 0
    fi
  fi
  log "자동 업데이트를 등록했습니다: 로그인 시 및 6시간마다 확인"
}

install_chatgpt_app
mkdir -p "$CODEX_HOME_DIR"
export CODEX_HOME="$CODEX_HOME_DIR"
CODEX_BIN="$(find_codex || true)"
[ -n "$CODEX_BIN" ] || fail "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다. ChatGPT 앱을 한 번 실행한 뒤 다시 시도하세요."

log "기존 청년통신 플러그인 연결을 정리합니다."
"$CODEX_BIN" plugin remove "$PLUGIN_NAME@$LEGACY_MARKETPLACE_NAME" --json >/dev/null 2>&1 || true
"$CODEX_BIN" plugin marketplace remove "$LEGACY_MARKETPLACE_NAME" --json >/dev/null 2>&1 || true
"$CODEX_BIN" plugin remove "$PLUGIN_NAME@$MARKETPLACE_NAME" --json >/dev/null 2>&1 || true
"$CODEX_BIN" plugin marketplace remove "$MARKETPLACE_NAME" --json >/dev/null 2>&1 || true

log "공개 GitHub 마켓플레이스를 등록합니다."
"$CODEX_BIN" plugin marketplace add "$REPOSITORY_SOURCE" --ref "$REPOSITORY_REF" --json >/dev/null
log "청년통신 블로그 플러그인을 설치합니다."
"$CODEX_BIN" plugin add "$PLUGIN_NAME@$MARKETPLACE_NAME" --json >/dev/null

PLUGIN_LIST="$("$CODEX_BIN" plugin list --json)"
printf '%s' "$PLUGIN_LIST" | grep -Eq '"pluginId"[[:space:]]*:[[:space:]]*"cheongnyeon-telecom-blog@cheongnyeon-telecom"' || \
  fail "설치 후 플러그인을 찾지 못했습니다."
printf '%s' "$PLUGIN_LIST" | grep -Eq '"enabled"[[:space:]]*:[[:space:]]*true' || \
  fail "설치 후 플러그인 활성 상태를 확인하지 못했습니다."

install_auto_update

if [ "${CHEONGNYEON_NO_LAUNCH:-0}" != "1" ]; then
  if [ -d /Applications/ChatGPT.app ]; then
    open -a /Applications/ChatGPT.app
  elif [ -d /Applications/Codex.app ]; then
    open -a /Applications/Codex.app
  fi
fi

log "설치 완료: ChatGPT 앱에서 '청년통신 블로그 글을 자동모드로 작성해줘'라고 입력하세요."
