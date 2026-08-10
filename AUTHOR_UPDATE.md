# 사용자님용 플러그인 업데이트 방법

## 가장 간단한 방법

로컬 스킬 `/Users/seojun/.codex/skills/cheongnyeon-telecom-blog`을 수정한 뒤 바탕화면의 `청년통신_플러그인_업데이트.command`를 더블클릭합니다.

터미널에서 실행하려면 아래 한 줄을 사용합니다.

```bash
cd "/Users/seojun/Documents/서준 AI/인코어/cheongnyeon-telecom-plugins" && ./scripts/publish-update.sh
```

이 명령은 다음 작업을 순서대로 처리합니다.

1. 로컬 스킬을 공개 플러그인 폴더에 동기화합니다.
2. 플러그인 버전의 Codex 캐시버스터를 자동으로 변경합니다.
3. 플러그인·배포 구조 검증과 전체 회귀 테스트를 실행합니다.
4. 임시 배포 분기와 PR을 자동으로 만듭니다.
5. Windows·macOS GitHub Actions가 통과한 경우에만 `main`으로 자동 병합합니다.
6. `main` 재검증 후 새 GitHub 릴리스를 생성합니다.

테스트나 GitHub Actions가 실패하면 `main`에 병합하지 않고 임시 분기를 정리한 뒤 오류를 보여줍니다. 따라서 상대방에게 실패한 버전이 자동 배포되지 않습니다.

## 다른 원본 스킬 폴더를 배포할 때

```bash
./scripts/publish-update.sh "/절대/경로/cheongnyeon-telecom-blog"
```

원본 폴더에는 `SKILL.md`가 있어야 합니다.

## 상대방에게 반영되는 시점

상대방 컴퓨터는 로그인할 때와 6시간마다 GitHub의 플러그인 버전을 확인합니다. 새 버전이면 자동으로 재설치하고 완료 알림을 표시합니다. 이미 ChatGPT 앱이 실행 중이었다면 앱을 다시 열 때 최신 지침이 확실하게 적용됩니다.
