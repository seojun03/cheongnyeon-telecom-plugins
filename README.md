# 청년통신 Codex 플러그인

청년통신 방식의 네이버 블로그 원고와 복사용 HTML을 만드는 공개 Codex 플러그인 저장소입니다.

## 어떤 설치 방식을 고르면 되나요?

| 용도 | 자동 업데이트 | 사용자가 지침 수정 | 설치 방법 |
| --- | --- | --- | --- |
| 일반 배포용 | 켜짐 | 업데이트 때 덮어써질 수 있음 | 기존 한 줄 설치 |
| 사용자 자유 수정용 | 꺼짐 | 가능 | GitHub ZIP 다운로드 후 설치 파일 실행 |

상대방이 자기 방식으로 플러그인 지침을 계속 수정하게 하려면 **사용자 자유 수정용**을 설치하세요.

## 사용자 자유 수정용 · 자동 업데이트 없음

이 설치 방식은 GitHub의 새 버전을 자동으로 받지 않습니다. 플러그인 전체를 사용자의 일반 폴더에 복사하고 로컬 플러그인으로 연결하므로, 중앙 업데이트가 사용자의 수정을 덮어쓰지 않습니다. 같은 설치 명령을 다시 실행해도 기존 로컬 수정본을 보존합니다.

### Windows 편집용 ZIP 설치 (권장)

PowerShell 명령을 입력하지 않아도 됩니다. 아래 ZIP을 내려받아 설치 파일만 실행하세요.

**[Windows 편집용 플러그인 ZIP 다운로드](https://github.com/seojun03/cheongnyeon-telecom-plugins/archive/refs/heads/main.zip)**

1. [공식 ChatGPT Windows 앱](https://chatgpt.com/download/)을 설치하거나 최신 버전으로 업데이트합니다.
2. ChatGPT 앱을 완전히 종료합니다.
3. 위 링크에서 받은 `cheongnyeon-telecom-plugins-main.zip`을 마우스 오른쪽 버튼으로 눌러 **모두 압축 풀기**를 선택합니다.
4. 압축을 푼 폴더 안의 `INSTALL-WINDOWS.cmd`를 더블클릭합니다. 관리자 권한은 필요하지 않습니다.
5. 검은 창에 `INSTALLATION COMPLETE`가 표시되면 아무 키나 눌러 닫습니다.
6. ChatGPT 앱을 다시 열고 **새 작업**에서 청년통신 플러그인을 사용합니다.

이 방식은 ChatGPT 앱과 Git을 변경하지 않습니다. 플러그인 명령을 실행할 Codex CLI가 없으면 OpenAI 공식 Windows standalone 설치기로 추가하고, 글 작성에 필요한 Python이 없으면 `winget`으로 설치합니다. ZIP 안의 플러그인은 `%USERPROFILE%\CheongnyeonTelecomPlugin`에 복사하고 로컬 편집본으로 연결하므로 중앙 자동 업데이트를 받지 않습니다.

### Windows 편집용 PowerShell 설치 (대체 방법)

공식 ChatGPT Windows 앱을 먼저 설치하고 완전히 종료한 뒤, PowerShell에 아래 한 줄을 붙여넣으세요. 편집용 설치기는 기존 ChatGPT 앱을 설치·업그레이드하지 않고 플러그인만 설치합니다.

```powershell
irm https://raw.githubusercontent.com/seojun03/cheongnyeon-telecom-plugins/main/install-editable-windows.ps1 | iex
```

### macOS 편집용 한 줄 설치

터미널에 아래 한 줄을 붙여넣으세요.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/seojun03/cheongnyeon-telecom-plugins/main/install-editable-macos.sh)"
```

설치 후 지침 파일 위치는 다음과 같습니다.

- Windows: `%USERPROFILE%\CheongnyeonTelecomPlugin\plugins\cheongnyeon-telecom-blog\skills\cheongnyeon-telecom-blog\SKILL.md`
- macOS: `~/CheongnyeonTelecomPlugin/plugins/cheongnyeon-telecom-blog/skills/cheongnyeon-telecom-blog/SKILL.md`

`SKILL.md`와 글 작성 규칙이 담긴 `references`, `templates`, 콘텐츠용 `scripts`도 수정할 수 있습니다. 단, 설치 재시도 시 오류 수정을 받기 위해 유지보수 파일 `scripts/apply-local-edits-windows.ps1`만 최신 정상본으로 교체됩니다. 글 작성 방식은 이 파일이 아니라 `SKILL.md`와 `references`에서 바꾸면 됩니다. 수정 후 바탕화면의 아래 파일을 한 번 실행하고 ChatGPT에서 새 작업을 여세요.

- Windows ZIP 설치: `Cheongnyeon_Plugin_Apply_My_Edits.cmd`
- Windows PowerShell 설치: `청년통신_플러그인_내수정적용.cmd`
- macOS: `청년통신_플러그인_내수정적용.command`

이 로컬 수정본은 제작자의 새 버전을 자동으로 합치지 않습니다. 나중에 제작자 최신판으로 완전히 교체하려면 로컬 폴더를 별도로 백업한 뒤 삭제하고 편집용 설치 명령을 다시 실행해야 합니다.

## Windows 한 줄 설치

Windows에서 **PowerShell**을 열고 아래 한 줄을 그대로 붙여넣으세요.

```powershell
irm https://raw.githubusercontent.com/seojun03/cheongnyeon-telecom-plugins/main/install-windows.ps1 | iex
```

설치기는 ChatGPT Windows 앱, Git, Python을 확인하고 필요한 경우 `winget`으로 설치합니다. 플러그인용 Codex CLI가 없으면 OpenAI 공식 Windows standalone 설치기를 우선 사용하고, 실패할 때만 npm 방식으로 재시도합니다. ChatGPT 앱의 보호된 내부 `Codex.exe`는 설치 명령에 사용하지 않습니다. 설치가 끝나면 ChatGPT 앱을 열고 `청년통신 블로그 글을 자동모드로 작성해줘`라고 입력하면 됩니다.

## macOS 한 줄 설치

터미널을 열고 아래 한 줄을 그대로 붙여넣으세요.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/seojun03/cheongnyeon-telecom-plugins/main/install-macos.sh)"
```

## 자동 업데이트

위 한 줄 설치기를 실행하면 자동 업데이트까지 함께 등록됩니다.

- Windows: 사용자 로그인 시와 6시간마다 예약 작업이 확인합니다.
- macOS: 사용자 로그인 시와 6시간마다 LaunchAgent가 확인합니다.
- GitHub의 플러그인 버전이 달라진 경우에만 재설치합니다.
- 업데이트 중에 ChatGPT 앱이 열려 있었다면 앱을 다시 열어야 최신 지침이 확실하게 적용됩니다.

기존 사용자는 위의 한 줄 설치 명령을 **딱 한 번만 다시 실행**하면 이후부터 자동 업데이트를 받습니다.

플러그인 제작자의 업데이트 배포 방법은 [AUTHOR_UPDATE.md](AUTHOR_UPDATE.md)에 있습니다.

## 모델 안내

모든 모델과 추론 수준에서 작업을 실행합니다. 현재 모델이 GPT-5.6 Sol High 이상이 아닌 것으로 명확히 확인될 때만 아래 안내를 한 번 표시하고, 작업은 중단하지 않습니다.

> 참고: 글 퀄리티를 위해 GPT-5.6 Sol High 이상 모델을 사용해주시면 좋습니다. 현재 모델에서도 작업은 계속 진행합니다.

모델 정보를 확인할 수 없으면 낮은 모델이라고 추측하지 않고 경고 없이 진행합니다.

## 자동모드 첫 입력

자동모드를 실행했는데 메인키워드를 아직 입력하지 않았다면 플러그인은 처음에 아래 한 문장만 요청합니다.

> 메인키워드를 입력해 주세요.

메인키워드를 받으면 주제·제목·마스터·추가 사실·이미지를 사전 질문으로 묻지 않고 제목, 본문, 꾸미기, 네이버용 HTML까지 자동으로 진행합니다. 자동모드 요청과 메인키워드를 한 번에 입력했다면 키워드를 다시 묻지 않습니다.

## 직접 설치 또는 업데이트

```bash
codex plugin marketplace add seojun03/cheongnyeon-telecom-plugins --ref main
codex plugin add cheongnyeon-telecom-blog@cheongnyeon-telecom
```

자동 업데이트를 꺼두었거나 즉시 업데이트가 필요할 때는 다음 명령을 수동으로 사용할 수 있습니다.

```bash
codex plugin marketplace upgrade cheongnyeon-telecom
codex plugin remove cheongnyeon-telecom-blog@cheongnyeon-telecom
codex plugin add cheongnyeon-telecom-blog@cheongnyeon-telecom
```

## 검증 범위

GitHub Actions가 macOS와 Windows에서 다음을 자동 확인합니다.

- 플러그인 및 마켓플레이스 매니페스트
- 금지된 캐시 파일과 Windows 경로 길이
- 블로그 작성기·검증기 전체 테스트
- Windows의 `Ctrl+V` 안내와 바탕화면 출력
- 공개 Git 저장소를 통한 Codex 마켓플레이스 등록 및 플러그인 설치
- GitHub ZIP 압축 해제본의 `INSTALL-WINDOWS.cmd`용 로컬 설치
- 공개 `v0.1.0` 구버전에서 최신 버전으로의 자동 업데이트
- macOS·Windows 편집용 설치가 기존 자동 업데이트를 해제하는지 확인
- 로컬 `SKILL.md` 수정 후 재적용한 내용이 설치 캐시에 반영되는지 확인

## 공개 범위

이 저장소에는 플러그인의 스킬 지침, 검증 스크립트, 템플릿, 사실 자료와 레퍼런스 미디어가 포함됩니다. 별도의 오픈소스 라이선스는 부여하지 않았습니다.
