#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
PLUGIN_ROOT="$REPO_ROOT/plugins/cheongnyeon-telecom-blog"
DESTINATION_SKILL="$PLUGIN_ROOT/skills/cheongnyeon-telecom-blog"
SOURCE_SKILL="${1:-$HOME/.codex/skills/cheongnyeon-telecom-blog}"
EXPECTED_REMOTE="https://github.com/seojun03/cheongnyeon-telecom-plugins.git"
CACHEBUSTER_HELPER="${CHEONGNYEON_CACHEBUSTER_HELPER:-/Users/seojun/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py}"
PLUGIN_VALIDATOR="${CHEONGNYEON_PLUGIN_VALIDATOR:-/Users/seojun/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py}"
PUBLISH_BRANCH="publish/cheongnyeon-$(date -u +%Y%m%d%H%M%S)"
PUBLISH_STARTED=0
PR_NUMBER=""

fail() {
  printf '[배포 오류] %s\n' "$1" >&2
  exit 1
}

log() {
  printf '[청년통신 배포] %s\n' "$1"
}

cleanup_failed_publish() {
  local status=$?
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "$PUBLISH_STARTED" = "1" ]; then
    log "실패한 임시 배포 분기를 정리합니다. 원본 스킬은 변경하지 않습니다."
    if [ -n "$PR_NUMBER" ]; then
      gh pr close "$PR_NUMBER" --repo seojun03/cheongnyeon-telecom-plugins --delete-branch >/dev/null 2>&1 || true
    fi
    git -C "$REPO_ROOT" restore --staged --worktree -- "$PLUGIN_ROOT" >/dev/null 2>&1 || true
    git -C "$REPO_ROOT" clean -fd -- "$PLUGIN_ROOT" >/dev/null 2>&1 || true
    git -C "$REPO_ROOT" switch main >/dev/null 2>&1 || true
    git -C "$REPO_ROOT" branch -D "$PUBLISH_BRANCH" >/dev/null 2>&1 || true
  fi
  exit "$status"
}

wait_for_actions() {
  local sha="$1"
  local run_id=""
  for _ in $(seq 1 60); do
    run_id="$(gh run list --repo seojun03/cheongnyeon-telecom-plugins --workflow ci.yml --commit "$sha" --limit 1 --json databaseId --jq '.[0].databaseId // empty')"
    [ -z "$run_id" ] || break
    sleep 2
  done
  [ -n "$run_id" ] || fail "GitHub Actions 실행을 찾지 못했습니다."
  gh run watch "$run_id" --repo seojun03/cheongnyeon-telecom-plugins --exit-status
}

trap cleanup_failed_publish EXIT

command -v git >/dev/null 2>&1 || fail "git이 필요합니다."
command -v gh >/dev/null 2>&1 || fail "GitHub CLI(gh)가 필요합니다."
command -v python3 >/dev/null 2>&1 || fail "python3가 필요합니다."
command -v rsync >/dev/null 2>&1 || fail "rsync가 필요합니다."
[ -f "$SOURCE_SKILL/SKILL.md" ] || fail "원본 스킬을 찾지 못했습니다: $SOURCE_SKILL"
[ -f "$CACHEBUSTER_HELPER" ] || fail "plugin-creator 버전 갱신 도구를 찾지 못했습니다: $CACHEBUSTER_HELPER"
[ -f "$PLUGIN_VALIDATOR" ] || fail "plugin-creator 검증 도구를 찾지 못했습니다: $PLUGIN_VALIDATOR"
[ "$(git -C "$REPO_ROOT" rev-parse --show-toplevel)" = "$REPO_ROOT" ] || fail "공개 저장소 루트 확인에 실패했습니다."
[ "$(git -C "$REPO_ROOT" remote get-url origin)" = "$EXPECTED_REMOTE" ] || fail "예상한 GitHub 저장소가 아닙니다."
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "저장소에 아직 커밋하지 않은 변경이 있습니다. 먼저 정리하세요."
gh auth status >/dev/null 2>&1 || fail "GitHub CLI 로그인이 필요합니다."
git -C "$REPO_ROOT" fetch origin main --quiet
[ "$(git -C "$REPO_ROOT" branch --show-current)" = "main" ] || fail "main 분기에서 실행해주세요."
[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$(git -C "$REPO_ROOT" rev-parse origin/main)" ] || fail "로컬 main과 GitHub main이 다릅니다. git pull 후 다시 실행해주세요."
git -C "$REPO_ROOT" switch -c "$PUBLISH_BRANCH" >/dev/null
PUBLISH_STARTED=1

log "로컬 스킬을 공개 플러그인에 동기화합니다."
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'state/recent-articles.json' \
  "$SOURCE_SKILL/" "$DESTINATION_SKILL/"
find "$DESTINATION_SKILL" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
find "$DESTINATION_SKILL" -type d -name '__pycache__' -empty -delete

if [ -z "$(git -C "$REPO_ROOT" status --porcelain -- "$DESTINATION_SKILL")" ]; then
  log "배포할 스킬 변경이 없습니다."
  git -C "$REPO_ROOT" switch main >/dev/null
  git -C "$REPO_ROOT" branch -d "$PUBLISH_BRANCH" >/dev/null
  PUBLISH_STARTED=0
  exit 0
fi

python3 "$CACHEBUSTER_HELPER" "$PLUGIN_ROOT"
VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$PLUGIN_ROOT/.codex-plugin/plugin.json")"
log "새 플러그인 버전: $VERSION"
git -C "$REPO_ROOT" add "$PLUGIN_ROOT"
git -C "$REPO_ROOT" diff --cached --check
git -C "$REPO_ROOT" commit -m "Publish Cheongnyeon Telecom plugin $VERSION"

python3 "$REPO_ROOT/scripts/validate_distribution.py"
python3 "$PLUGIN_VALIDATOR" "$PLUGIN_ROOT"
(
  cd "$DESTINATION_SKILL"
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
)

SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
git -C "$REPO_ROOT" push --set-upstream origin "$PUBLISH_BRANCH"
PR_URL="$(gh pr create \
  --repo seojun03/cheongnyeon-telecom-plugins \
  --base main \
  --head "$PUBLISH_BRANCH" \
  --title "Publish Cheongnyeon Telecom plugin $VERSION" \
  --body "자동 배포 검증용 PR입니다. macOS와 Windows 검증이 통과한 뒤 자동 병합합니다.")"
PR_NUMBER="$(gh pr view "$PR_URL" --repo seojun03/cheongnyeon-telecom-plugins --json number --jq .number)"
wait_for_actions "$SHA"
gh pr merge "$PR_NUMBER" --repo seojun03/cheongnyeon-telecom-plugins --merge --delete-branch

git -C "$REPO_ROOT" switch main >/dev/null
git -C "$REPO_ROOT" pull --ff-only origin main
git -C "$REPO_ROOT" branch -d "$PUBLISH_BRANCH" >/dev/null 2>&1 || true
PUBLISH_STARTED=0
SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
wait_for_actions "$SHA"

TAG="v$VERSION"
gh release create "$TAG" \
  "$REPO_ROOT/install-windows.ps1" \
  "$REPO_ROOT/install-macos.sh" \
  --repo seojun03/cheongnyeon-telecom-plugins \
  --target "$SHA" \
  --title "청년통신 블로그 플러그인 $VERSION" \
  --notes "청년통신 블로그 플러그인 자동 배포 버전 $VERSION입니다. Windows와 macOS 교차 플랫폼 검증을 통과했습니다."

log "배포 완료: https://github.com/seojun03/cheongnyeon-telecom-plugins/releases/tag/$TAG"
trap - EXIT
