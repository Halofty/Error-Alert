# Error Alert System

Airflow(Linux PC)의 태스크 실패를 GalaxyBook·Termux 위 서버가 받아 중복을 걸러내고, Slack 채널에 통계·증감이 반영된 대시보드 메시지 하나로 보여주는 개인용 알림 시스템.

- 전체 아키텍처, Slack 색상 제약, 리스크 검토: [Termux 에러 알림 서버](https://claude.ai/code/artifact/6330b030-8bd9-4e94-9f37-04db6389424b)
- 결정 사항·남은 작업: [docs/planning.md](docs/planning.md)
- Airflow 쪽 연결 계약·폴백 경로: [docs/airflow_connection.md](docs/airflow_connection.md)

## 구조

```
app/
├─ adapters/        # AlertChannel 계약 + Slack 구현
├─ ingest.py          # POST /ingest — Airflow → 여기
├─ interactions.py     # Slack 확인/해결 버튼 처리
├─ digest.py, scheduler.py   # 일/주간 다이제스트
├─ ingest_server.py     # 프로세스 ① 진입점 (FastAPI + 다이제스트 스케줄러)
└─ socket_listener.py    # 프로세스 ② 진입점 (Slack Socket Mode)
```

두 프로세스는 같은 SQLite 파일을 공유하며 독립적으로 뜨고 죽는다 — 하나가 죽어도 다른 하나는 영향받지 않는다.

참고 문서는 [docs/](docs/)에 모아뒀다 (`planning.md`, `airflow_connection.md`, `slack_setting.md` + `slack.yaml`). 루트에는 실행에 직접 쓰이는 것만 남겼다 — `README.md`, `requirements*.txt`, `.env.example`, `deploy.sh`, `app/`.

## [사용방법]

전제: GalaxyBook에 Termux 설치, PC와 Tailscale로 연결되어 SSH 접속 가능한 상태.

### 0. 기기 켜지면 SSH 접속 후 이거 하나만 붙여넣기

아래 1~4번(패키지 설치, clone, 의존성 설치, Termux:Boot 등록)을 한 블록으로 묶은 것. `<repo-url>`만 실제 저장소 주소로 바꿔서 그대로 붙여넣으면 된다. 토큰 입력(`.env`)과 실제 기동(`deploy.sh`)은 Slack 앱 설정이 끝난 뒤 손으로 하는 게 맞아서 여기엔 안 넣었다 — 이 블록이 끝나면 아래 "그다음 할 일" 안내가 뜬다.

```bash
cd ~
pkg update -y
pkg install -y python git openssh rust clang termux-api

git clone <repo-url> error-alert
cd error-alert

pip install -r requirements.txt
cp .env.example .env

mkdir -p ~/.termux/boot
cp deploy/termux-boot/ingest.sh ~/.termux/boot/
cp deploy/termux-boot/listener.sh ~/.termux/boot/
chmod +x ~/.termux/boot/*.sh deploy.sh

echo "=== 준비 끝. 그다음 할 일 ==="
echo "1) docs/slack_setting.md대로 Slack 앱 만들고 토큰 발급"
echo "2) nano .env 로 SLACK_BOT_TOKEN / SLACK_APP_TOKEN / SLACK_CHANNEL_ID / ALERT_SERVER_TOKEN 채우기"
echo "3) Termux:Boot, Termux:API 앱을 Termux 본체와 같은 경로(F-Droid/GitHub)로 설치 후 한 번씩 직접 실행해서 권한 허용 (4번 참고)"
echo "4) Android 설정 > 앱 > Termux > 배터리 > 제한 없음으로 변경"
echo "5) bash deploy.sh 로 시작 (README [사용방법] 5번 참고)"
```

`rust`/`clang`은 `pydantic-core`/`aiohttp` 빌드용 예방적 설치라 시간이 좀 걸릴 수 있다 — 아래 1번에 적힌 것과 같은 이유.

### 1. 최초 설정 (Termux, SSH로 접속한 뒤 한 번만)

```bash
pkg install python git openssh
git clone <repo-url> error-alert
cd error-alert
pip install -r requirements.txt
```

`pydantic-settings`(pydantic-core, Rust 확장)나 `aiohttp`(C 확장)가 Termux ARM용 사전 빌드 wheel을 못 찾으면 여기서 실패하거나 오래 걸릴 수 있다. 그럴 땐:

```bash
pkg install rust clang
```

후 다시 `pip install -r requirements.txt`.

### 2. Slack 앱 설정

매니페스트([docs/slack.yaml](docs/slack.yaml))로 앱 생성 → Bot Token·App-Level Token 발급 → 채널 초대 → 폴백 Webhook 활성화까지 전 과정: [docs/slack_setting.md](docs/slack_setting.md)

### 3. 환경변수 채우기

```bash
cp .env.example .env
nano .env   # 또는 vi — SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_CHANNEL_ID, ALERT_SERVER_TOKEN 채우기
```

`.env`는 git이 추적하지 않으므로(`.gitignore`) 이후 `git pull`로 코드가 바뀌어도 그대로 남는다 — 토큰을 다시 넣을 필요는 로테이션할 때뿐이다.

`ALERT_SERVER_PORT`는 기본 `8001`(폰에서 다른 프로젝트가 `8000`을 쓰고 있을 걸 감안해서). 그것마저 겹치면 `.env`에서 이 값만 바꾸면 됨 — 코드 어디도 손댈 필요 없음.

### 4. 상시 구동 설정 (최초 1번)

```bash
pkg install termux-api
mkdir -p ~/.termux/boot
cp deploy/termux-boot/ingest.sh ~/.termux/boot/
cp deploy/termux-boot/listener.sh ~/.termux/boot/
chmod +x ~/.termux/boot/*.sh deploy.sh
```

(`termux-boot`라는 `pkg` 패키지는 없다 — Termux:Boot는 CLI 패키지 없이 앱(APK)만으로 동작한다. `termux-api`만 설치하면 된다.)

두 스크립트 안의 `cd ~/error-alert` 경로를 실제 클론 위치에 맞게 확인한다. 이후:

- **Termux:Boot 앱 설치 — Termux 본체를 설치한 것과 같은 경로로 받는다.** Termux 애드온(Termux:Boot, Termux:API)은 본체와 출처가 다르면 서명이 안 맞아 동작하지 않는다 (Play스토어 Termux는 개발 중단된 구버전이라 애초에 비권장 — F-Droid 또는 GitHub Releases APK 사용):
  - F-Droid로 설치했다면 → F-Droid 앱에서 "Termux:Boot" 검색해 설치
  - GitHub Releases APK로 설치했다면 → https://github.com/termux/termux-boot/releases 에서 **폰과 같은 CPU 아키텍처**의 apk를 받아 설치 (`termux-boot-app.apk`처럼 파일명이 버전·아키텍처별로 다르므로 링크를 고정해두지 않았다 — 페이지에서 직접 확인)

  APK 설치는 Android가 확인 탭을 요구해서 완전히 명령줄만으로는 못 끝낸다. 설치 후 **앱을 한 번 직접 실행해서 권한을 준다** (이후 재부팅마다 두 스크립트가 자동 실행됨).
- `termux-api` 패키지(위에서 이미 설치됨)가 실제로 동작하려면 **Termux:API 앱**도 마찬가지로 같은 경로로 설치해야 한다 — 안 하면 `termux-wake-lock`이 조용히 실패한다.
- Android 설정 → 앱 → Termux → 배터리 → **제한 없음**으로 변경 (Doze로 프로세스가 죽는 걸 최대한 방지)

### 5. 처음 실행 & 확인

재부팅하거나, 지금 바로 켜보려면:

```bash
bash deploy.sh
curl http://localhost:8001/health
```

Slack 채널에 "오늘의 에러 현황" 고정 메시지가 뜨는지는 실제 에러가 한 번 들어와야 생긴다 — 테스트용으로 [docs/airflow_connection.md](docs/airflow_connection.md)의 payload 형식으로 curl 한 번 쳐봐도 된다:

```bash
curl -X POST http://localhost:8001/ingest \
  -H "X-Alert-Token: <ALERT_SERVER_TOKEN 값>" \
  -H "Content-Type: application/json" \
  -d '{"dag_id":"test_dag","task_id":"test_task","error_type":"ManualTest","message":"배포 확인용","occurred_at":"2026-09-09T12:00:00+09:00"}'
```

### 6. 이후 업데이트할 때

PC에서 SSH로 접속해서:

```bash
bash deploy.sh
```

이 한 줄이 `git pull` → 의존성 갱신 → 기존 프로세스 종료 → 재시작까지 다 한다.

### 7. 로그 확인

```bash
tail -f logs/ingest.log      # 앱 자체 로그 (RotatingFileHandler)
tail -f logs/listener.log
tail -f logs/ingest-crash.log    # Termux:Boot 루프가 재시작을 기록한 로그 (최근 500줄만 유지)
tail -f logs/listener-crash.log
```

`*-crash.log`에 재부팅·업데이트와 무관하게 재시작 기록이 계속 쌓인다면, 배터리 최적화 "제한 없음" 설정이 실제로 안 먹혔거나 다시 풀렸다는 신호다 — 4번을 재확인한다.
