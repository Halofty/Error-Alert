# Slack 앱 설정

마지막 갱신: 2026-09-09

이 문서를 끝까지 따라가면 `.env`에 채울 값 4개(`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`, 그리고 [airflow_connection.md](airflow_connection.md)용 폴백 Webhook URL)를 전부 얻는다.

앱 자체의 권한·기능 설정은 손으로 하나씩 누르는 대신 매니페스트([slack.yaml](slack.yaml))로 한 번에 만든다.

## 1. 매니페스트로 앱 생성

1. https://api.slack.com/apps → **Create New App**
2. **From an app manifest** 선택
3. 앱을 만들 워크스페이스 선택
4. YAML 탭에서 [slack.yaml](slack.yaml) 내용을 그대로 붙여넣기
5. **Next** → 요약 확인(Bot Token Scopes: `chat:write`, `pins:write`, `incoming-webhook`, `commands` / Socket Mode: On / Interactivity: On / Slash Commands: `/errors`) → **Create**

이 한 번으로 아래가 전부 설정된다:
- Bot User 생성 (`error-alert`)
- Bot Token Scopes 4개
- Socket Mode 활성화
- Interactivity 활성화 (Request URL 없이 — 소켓으로 받으므로)
- `/errors` 슬래시 커맨드 등록

## 2. 워크스페이스에 설치 → Bot Token 발급

1. 왼쪽 메뉴 **Install App** → **Install to Workspace** → 권한 확인 후 **Allow**
2. 같은 페이지(또는 **OAuth & Permissions**)에 표시되는 **Bot User OAuth Token**(`xoxb-`로 시작)을 복사 → `.env`의 `SLACK_BOT_TOKEN`

## 3. Socket Mode용 App-Level Token 발급

매니페스트로는 여기까지 안 된다 — App-Level Token은 보안상 콘솔에서 직접 눌러서 발급해야 한다.

1. 왼쪽 메뉴 **Basic Information** → 아래쪽 **App-Level Tokens** → **Generate Token and Scopes**
2. 토큰 이름 아무거나(예: `socket-mode`) 입력 → Scope에 `connections:write` 추가 → **Generate**
3. 발급된 토큰(`xapp-`로 시작)을 복사 → `.env`의 `SLACK_APP_TOKEN`

## 4. 채널에 봇 초대 + 채널 ID 확인

1. 알림 받을 Slack 채널에서 `/invite @error-alert`
2. 채널 이름 클릭 → 맨 아래 **채널 ID 복사**(또는 채널 링크의 마지막 세그먼트, `C`로 시작하는 문자열) → `.env`의 `SLACK_CHANNEL_ID`

## 5. 폴백용 Incoming Webhook 활성화

[airflow_connection.md](airflow_connection.md)의 폴백 경로(서버가 죽어있을 때 Airflow가 직접 쏘는 용도)에 쓰는 것으로, 위 Bot Token과는 별개의 값이다.

1. 왼쪽 메뉴 **Incoming Webhooks** → 토글 **On**
2. 아래 **Add New Webhook to Workspace** → 4번에서 초대한 채널 선택 → **Allow**
3. 생성된 Webhook URL(`https://hooks.slack.com/services/...`) 복사 → Airflow `Variable` `slack_fallback_webhook`에 저장 (Termux 서버가 아니라 Airflow 쪽 값이다)

## 6. `.env` 채우기

Termux(또는 로컬 테스트 환경)에서 `.env.example`을 복사한 뒤 위에서 모은 값을 채운다.

| 값 | 어디서 얻었나 | `.env` 키 |
|---|---|---|
| `xoxb-...` | 2단계 | `SLACK_BOT_TOKEN` |
| `xapp-...` | 3단계 | `SLACK_APP_TOKEN` |
| `C...` | 4단계 | `SLACK_CHANNEL_ID` |
| `https://hooks.slack.com/...` | 5단계 | (Airflow `Variable`, 이 서버의 `.env`가 아님) |

## 7. 확인

[README.md](../README.md#사용방법)의 [사용방법] 5번(curl로 `/ingest` 호출)을 실행해서 채널에 실제로 메시지가 뜨는지, 대시보드가 갱신되는지 확인한다. 확인/해결 버튼도 눌러서 상태 전이가 반영되는지 본다.
