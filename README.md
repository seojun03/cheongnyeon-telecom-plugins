# 청년통신 Codex 플러그인

청년통신 방식의 네이버 블로그 원고와 복사용 HTML을 만드는 공개 Codex 플러그인 저장소입니다.

## Windows 한 줄 설치

Windows에서 **PowerShell**을 열고 아래 한 줄을 그대로 붙여넣으세요.

```powershell
irm https://raw.githubusercontent.com/seojun03/cheongnyeon-telecom-plugins/main/install-windows.ps1 | iex
```

설치기는 ChatGPT Windows 앱, Git, Python을 확인하고 없으면 `winget`으로 설치한 뒤 플러그인을 설치합니다. 설치가 끝나면 ChatGPT 앱을 열고 `청년통신 블로그 글을 자동모드로 작성해줘`라고 입력하면 됩니다.

## macOS 한 줄 설치

터미널을 열고 아래 한 줄을 그대로 붙여넣으세요.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/seojun03/cheongnyeon-telecom-plugins/main/install-macos.sh)"
```

## 모델 안내

모든 모델과 추론 수준에서 작업을 실행합니다. 현재 모델이 GPT-5.6 Sol High 이상이 아닌 것으로 명확히 확인될 때만 아래 안내를 한 번 표시하고, 작업은 중단하지 않습니다.

> 참고: 글 퀄리티를 위해 GPT-5.6 Sol High 이상 모델을 사용해주시면 좋습니다. 현재 모델에서도 작업은 계속 진행합니다.

모델 정보를 확인할 수 없으면 낮은 모델이라고 추측하지 않고 경고 없이 진행합니다.

## 직접 설치 또는 업데이트

```bash
codex plugin marketplace add seojun03/cheongnyeon-telecom-plugins --ref main
codex plugin add cheongnyeon-telecom-blog@cheongnyeon-telecom
```

업데이트할 때는 다음 명령을 사용합니다.

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

## 공개 범위

이 저장소에는 플러그인의 스킬 지침, 검증 스크립트, 템플릿, 사실 자료와 레퍼런스 미디어가 포함됩니다. 별도의 오픈소스 라이선스는 부여하지 않았습니다.
