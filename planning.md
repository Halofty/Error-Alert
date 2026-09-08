# Error Alert System — Planning

마지막 갱신: 2026-09-09

## 결정된 것

- **스택**: FastAPI + Redis(중복 제거) + SQLite/SQLModel(영속 저장) + Slack Bolt Socket Mode(상호작용). Go 도입은 보류 — 폰(Termux) 환경에서의 리소스 이점은 있지만, 지금 규모에서는 프로세스/스키마 이중화 비용이 이득보다 큼. 실제로 Socket Mode 리스너가 반복적으로 죽는 문제가 로그로 확인되면 그 컴포넌트만 재검토.
- **알림 채널은 어댑터 패턴**(`app/adapters`)으로 추상화. `AlertChannel` Protocol 하나만 구현하면 새 채널 추가. 지금은 Slack만 구현.
- **다이제스트(일/주간)는 채널을 모르는 순수 집계 함수**로 분리(`digest.build_digest`), 채널로의 발송은 fan-out으로 별도 처리. 채널이 늘어나도 집계 로직은 안 바뀜.
- **메시지 참조는 채널별로 독립 저장** — `ChannelMessageRef(fingerprint, channel_name, kind)` 유니크 제약. 한 에러가 여러 채널에 동시에 걸려도 충돌 없음.

## 지금까지 만든 것

| 파일 | 역할 |
|---|---|
| `app/adapters/base.py` | `AlertChannel` 계약, `ErrorEvent`/`DigestReport` |
| `app/adapters/slack.py` | `SlackAdapter` 구현 — 색상 바 + 이모지 델타, 대시보드 chat.update |
| `app/models.py` | `ErrorRecord`, `ChannelMessageRef`(unique 제약 포함) |
| `app/config.py` | `Settings`(pydantic-settings) — 채널별 필수 env 중앙 검증 |
| `app/channels.py` | `BUILDERS` 레지스트리로 활성 채널 조립 + fail-fast 검증 |
| `app/digest.py` | DB 집계 → `DigestReport` → 채널 fan-out, 채널별 실패 격리, sync DB 호출은 executor로 오프로드 |
| `app/scheduler.py` | APScheduler cron (일 00:00 / 주 월 00:05, Asia/Seoul) |

## 남은 작업 (제안 순서)

1. **`app/db.py`** — SQLite 엔진 + `session_factory` 정의(WAL 모드), 테이블 생성(`SQLModel.metadata.create_all`)
2. **`app/dedup.py`** — 지문 계산(`hash(dag_id+task_id+error_type)`), Redis TTL 캐시, `INCR`로 카운터 증가
3. **`app/ingest.py`** — FastAPI 라우터. Airflow → `POST /ingest` → dedup 조회 → 신규/반복 분기 → DB write + 채널 `post_new_error`/`bump_occurrence` + `update_dashboard`
4. **`app/interactions.py`** — Slack Bolt Socket Mode 앱. 확인/해결/스누즈 버튼 → DB 상태 갱신 → 대시보드 재계산(현재 `SlackAdapter.handle_interaction`은 `NotImplementedError`)
5. **`app/main.py`** — FastAPI app 생성, lifespan에서 scheduler 시작/종료 + Socket Mode 리스너 구동, `ingest` 라우터 등록
6. **`.env.example`** — `Settings`가 요구하는 환경변수 목록 문서화
7. **Termux 배포** — Termux:Boot 자동 시작 스크립트, `termux-wake-lock`, 배터리 최적화 예외 등록, 상시 구동 확인

## 보류 중인 결정

- **Discord/Telegram 어댑터** — 구조(계약, 레지스트리, 메시지 참조 테이블)는 준비됨. 실사용 필요가 생기면 어댑터 파일 하나 추가.
- **DAG/심각도별 채널 라우팅 규칙** — `channels.py`에 확장 지점은 확보. 규칙 형태(설정 파일 vs DB)는 미정.
- **폰 밖으로 이전(Tailscale/클라우드)** — 상시 구동 안정성 문제가 실제로 반복되면 재검토.

## 참고

- 초기 아키텍처 설계안(전체 구조도, Slack 색상 제약, 리스크 콜아웃 포함): [Termux 에러 알림 서버](https://claude.ai/code/artifact/6330b030-8bd9-4e94-9f37-04db6389424b)
