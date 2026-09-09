# Error Alert System — Planning

마지막 갱신: 2026-09-09

## 결정된 것

- **스택**: FastAPI + SQLite/SQLModel(영속 저장 + 중복 제거) + Slack Bolt Socket Mode(상호작용). Go 도입은 보류.
- **Redis는 사용하지 않음.** 지문 중복 체크·발생 횟수 증가는 SQLite로 충분한 규모(개인 프로젝트, 저빈도 쓰기). "Redis 재도입 트리거" 참고.
- **알림 채널은 어댑터 패턴**(`app/adapters`)으로 추상화. `AlertChannel` Protocol 하나만 구현하면 새 채널 추가. 지금은 Slack만 구현.
- **다이제스트(일/주간)는 채널을 모르는 순수 집계 함수**로 분리(`digest.build_digest`), 채널로의 발송은 fan-out으로 별도 처리.
- **메시지 참조는 채널별로 독립 저장** — `ChannelMessageRef(fingerprint, channel_name, kind)` 유니크 제약.
- **ingest와 Slack Socket Mode 리스너는 별도 OS 프로세스로 분리.** 같은 코드베이스, 같은 SQLite 파일을 공유(WAL 모드 + busy_timeout)하는 구조 — 마이크로서비스는 아님. 목적은 장애 격리(리스너 버그가 ingest까지 끌고 내려가지 않게, Android가 프로세스를 죽여도 한쪽만 재시작).
- **`AlertChannel.upsert_error` 하나로 통합** — 원래 `post_new_error`/`bump_occurrence` 두 메서드였는데, `interactions.py`를 만들면서 "반복 발생"과 "상태 변경(확인/해결)" 둘 다 같은 종류의 갱신(메시지를 최신 상태로 다시 그리기)이라는 게 드러남. 특히 기존 `bump_occurrence`는 메시지 전체를 컨텍스트 블록 하나로 덮어써서 원본 내용·버튼이 사라지는 버그가 있었음 — 통합하면서 같이 고침. `handle_interaction`도 실제로는 쓰이지 않아(상호작용은 각 채널의 리스너가 직접 받아 `interactions.py`를 호출) 계약에서 제거.

## 지금까지 만든 것

| 파일 | 역할 |
|---|---|
| `app/adapters/base.py` | `AlertChannel` 계약(`upsert_error`/`update_dashboard`/`post_digest`), `ErrorEvent`/`DigestReport` |
| `app/adapters/slack.py` | `SlackAdapter` — 상태별 색상 바(open/acked/resolved) + 이모지 델타, 대시보드 chat.update |
| `app/models.py` | `ErrorRecord`, `ChannelMessageRef`(unique 제약 포함) |
| `app/config.py` | `Settings`(pydantic-settings) + `get_settings()` 캐시. 채널별 필수 env 중앙 검증 |
| `app/channels.py` | `BUILDERS` 레지스트리로 활성 채널 조립 + fail-fast 검증 |
| `app/db.py` | SQLite 엔진, WAL + busy_timeout 설정, `get_session`/`get_db`(FastAPI dependency) |
| `app/refs.py` | `ChannelMessageRef` 조회/upsert 헬퍼 (`get_ref`/`save_ref`) |
| `app/stats.py` | 오늘 총계 집계(`today_totals`) + 대시보드 갱신(`refresh_dashboard`) |
| `app/dedup.py` | 지문 계산 + SQLite 기반 신규/반복 판별(`record_error`) — Redis 없음 |
| `app/ingest.py` | `POST /ingest` 라우터. `X-Alert-Token` 인증 → dedup → 채널 `upsert_error` → 신규일 때만 대시보드 갱신 |
| `app/interactions.py` | 확인/해결 버튼 액션 처리 — DB 상태 변경 → 메시지 재작성 → (해결 시에만) 대시보드 갱신 |
| `app/queries.py` | `query_errors(unresolved_only, start, end)` 하나로 상태·기간 조합 조회 + 목록 포맷팅 (순수 함수, Slack 비의존) |
| `app/commands.py` | `/errors` 파싱 — `all`(상태), 날짜 0/1/2개(기간), `limit=N`(개수, 기본 30)을 순서 무관하게 분리 |
| `app/digest.py` | DB 집계 → `DigestReport` → 채널 fan-out, 실패 격리, executor 오프로드 |
| `app/scheduler.py` | APScheduler cron (일 00:00 / 주 월 00:05, Asia/Seoul) |
| `app/logging_config.py` | `RotatingFileHandler` 설정 |
| `app/ingest_server.py` | 프로세스 ① 진입점 — FastAPI app, lifespan에서 DB 초기화 + scheduler 구동, `GET /health` |
| `app/socket_listener.py` | 프로세스 ② 진입점 — Slack Bolt Socket Mode, 재연결 백오프 포함 |
| `.env.example` | 필요한 환경변수 목록 |
| `deploy.sh` | 업데이트 스크립트 — git pull + 의존성 갱신 + 프로세스 재시작을 한 번에 |
| `deploy/termux-boot/*.sh` | Termux:Boot 템플릿 — 재부팅 시 자동 시작 + 크래시 시 재시작 루프 |
| `README.md` | 프로젝트 개요 + [사용방법](../README.md#사용방법)(최초 설정~업데이트 전 과정) |
| `tests/` | `dedup`/`interactions`/`stats` 유닛 테스트 13개 (`FakeChannel`로 Slack 없이 검증), `conftest.py`에 SQLite 세션 픽스처 |
| `pytest.ini`, `requirements-dev.txt` | 테스트 실행 설정 (`asyncio_mode=auto`) + 개발용 의존성(pytest, pytest-asyncio) |

## 검증 완료

- `pytest` 28개 전부 통과 (dedup 신규/반복/TTL만료/재발/지문충돌, interactions 확인/해결/중복클릭/알수없는액션/메시지재사용, stats 집계+대시보드 ref 재사용, `/errors` 커맨드 날짜 0·1·2개 분기+`all`+`limit=`+조합+잘못된 입력, ingest 시각 타임존 정규화).
- `/errors` 슬래시 커맨드 구현 완료 — `slack.yaml`에 선언, `socket_listener.py`에 핸들러 연결. 토큰을 세 종류로 분리해서 순서 무관하게 파싱: 상태 필터(`all`/`전체` 없으면 미해결만), 날짜(0개: 필터 없음, 1개: `YYYY-MM-DD`, 2개: `YYYY-MM-DDTHH:MM` 두 개로 범위), `limit=N`(표시 개수, 기본 30). 응답은 ephemeral(본인에게만 보임)이라 채널이 지저분해지지 않음.
- **버그 수정**: `ingest.py`의 `IngestPayload.occurred_at`이 Airflow가 보낸 타임존 오프셋(`+09:00` 등)을 그대로 저장하고 있어서, `today_totals`/`build_digest`/`/errors`가 쓰는 `datetime.utcnow()` 기준 naive 비교와 어긋날 수 있는 지점이었음. `/errors`를 만들면서 발견해서, ingest 시점에 항상 naive UTC로 정규화하도록 고침.
- FastAPI 앱을 채널 없이(더미) 띄워 `/health` → `/ingest`(신규, `is_new=True, count=1`) → `/ingest`(반복, `is_new=False, count=2`) → 잘못된 토큰(`401`)까지 실제 요청으로 확인 — DB 초기화·dedup·인증이 맞물려 도는 것까지 검증됨. 로컬 `.venv`에 개발 의존성 설치되어 있어 `pytest` 바로 재실행 가능(둘 다 `.gitignore` 대상이라 커밋 안 됨).
- 아직 검증 안 된 것: 실제 Slack API 호출(토큰 필요), Socket Mode 연결, Termux 환경 자체(ARM 의존성 설치 여부).

## 남은 작업

1. ~~Slack 앱 설정~~ — 절차 문서화 완료: [slack_setting.md](slack_setting.md) (매니페스트: [slack.yaml](slack.yaml)). 실제로 콘솔에서 앱 생성 + 토큰 발급 + `.env` 채우기는 남음.
2. **실제 Termux 배포 수행** — README.md [사용방법] 절차대로 GitHub push → Termux에서 clone → `.env` 채우기 → Termux:Boot 등록 → `bash deploy.sh`.
3. **실채널 동작 확인** — 토큰 채운 뒤 README 5번 curl 예시로 실제 Slack 채널에 메시지·대시보드가 뜨는지, 확인/해결 버튼 클릭이 반영되는지 확인. (더미 채널 기준 파이프라인 자체는 검증 완료 — 위 "검증 완료" 참고)
4. **Airflow 쪽 콜백 실제 배치** — `airflow_connection.md`의 `alert_on_failure`를 실제 DAG `default_args`에 연결.

## Redis 재도입 트리거

지금은 제거하지만, 아래 상황이 실제로 발생하면 다시 검토한다. (ingest/socket listener 프로세스 분리는 트리거에서 제외 — SQLite WAL + busy_timeout으로 충분함을 확인했음.)

1. **폰 → 클라우드 이전 + 다중 워커/인스턴스로 ingest를 수평 확장할 때** — 여러 워커가 SQLite 파일 하나에 고빈도로 동시 쓰기를 하게 되면 단일 writer 직렬화가 병목이 됨.
2. **Discord/Telegram 등 채널이 늘어 발송을 producer/consumer 큐로 분리해야 할 때** — 느린 채널 하나가 다른 채널/ingest를 막지 않게 Redis Streams로 비동기 분리.
3. **실제 flood(무한 재시도 루프 등)로 데이터 기반 rate limiting이 필요해질 때** — `INCR`+`EXPIRE` sliding window가 필요한 시점.
4. **실시간 웹 대시보드(SSE/WebSocket)를 붙일 때** — Pub/Sub으로 "새 이벤트 발생"을 브로드캐스트해야 폴링 없이 push 가능.

## 보류 중인 결정

- **Discord/Telegram 어댑터** — 구조(계약, 레지스트리, 메시지 참조 테이블)는 준비됨. 실사용 필요가 생기면 어댑터 파일 하나 추가.
- **DAG/심각도별 채널 라우팅 규칙** — `channels.py`에 확장 지점은 확보. 규칙 형태(설정 파일 vs DB)는 미정.

## 참고

- 초기 아키텍처 설계안(전체 구조도, Slack 색상 제약, 리스크 콜아웃 포함): [Termux 에러 알림 서버](https://claude.ai/code/artifact/6330b030-8bd9-4e94-9f37-04db6389424b)
- Airflow → 서버 연결 계약, 인증, 서버 다운 시 폴백 경로: [airflow_connection.md](airflow_connection.md)
- Slack 앱 생성·토큰 발급 절차: [slack_setting.md](slack_setting.md) (매니페스트: [slack.yaml](slack.yaml))
