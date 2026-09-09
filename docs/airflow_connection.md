# Airflow ↔ Error Alert 연결

마지막 갱신: 2026-09-09

Airflow(Linux PC)가 알림 서버(GalaxyBook·Termux)로 에러를 보내는 경로와, 서버가 죽어있을 때 알림이 완전히 끊기지 않게 하는 폴백 경로를 정의한다.

## 1. 네트워크 경로

- Airflow와 Termux가 같은 LAN이면 Termux의 로컬 IP로 직접 접근.
- 같은 LAN이 아니면(외부 네트워크, 다른 장소) Tailscale 사설망을 통해 접근 — 포트포워딩/공인 IP는 쓰지 않는다(초기 설계안 참고).
- 엔드포인트: `POST http://<termux-host>:8000/ingest`

## 2. 정상 경로 — `on_failure_callback` → `/ingest`

### 요청 형식

```
POST /ingest
Content-Type: application/json
X-Alert-Token: <공유 시크릿>
```

```json
{
  "dag_id": "daily_etl_sync",
  "task_id": "extract_orders",
  "error_type": "OperationalError",
  "message": "connection to server at \"warehouse-db\" ... timeout expired",
  "occurred_at": "2026-09-09T14:32:00+09:00",
  "log_url": "http://airflow.local/log?dag_id=...&task_id=..."
}
```

지문(fingerprint)은 Airflow가 계산하지 않는다 — 서버가 `dag_id+task_id+error_type`으로 내부에서 계산한다(`app/dedup.py`). Airflow는 원시 정보만 보낸다.

### 인증

`X-Alert-Token` 헤더를 서버가 검증한다(`secrets.compare_digest`). 토큰 값은 Airflow `Variable`(`alert_server_token`)과 서버 `.env`(`ALERT_SERVER_TOKEN`)에 동일하게 저장 — Slack Bot Token과는 별개의 값이다.

### 콜백 구현 (Airflow DAG 쪽)

```python
import requests
from airflow.models import Variable

ALERT_SERVER_URL = "http://<termux-host>:8000/ingest"
ALERT_TOKEN = Variable.get("alert_server_token")
SLACK_FALLBACK_WEBHOOK = Variable.get("slack_fallback_webhook")


def alert_on_failure(context):
    payload = {
        "dag_id": context["dag"].dag_id,
        "task_id": context["task_instance"].task_id,
        "error_type": type(context.get("exception")).__name__ if context.get("exception") else "Unknown",
        "message": str(context.get("exception", ""))[:500],
        "occurred_at": context["ts"],
        "log_url": context["task_instance"].log_url,
    }

    try:
        resp = requests.post(
            ALERT_SERVER_URL,
            json=payload,
            headers={"X-Alert-Token": ALERT_TOKEN},
            timeout=5,
        )
        resp.raise_for_status()
        return
    except Exception:
        pass  # 서버 무응답/타임아웃/5xx 등 — 폴백으로 진행

    _send_fallback(payload)
```

각 DAG의 `default_args`에 `"on_failure_callback": alert_on_failure`로 등록한다.

**타임아웃은 5초로 짧게 고정한다.** 콜백이 오래 걸리면 Airflow 스케줄러 자체에 영향을 준다 — 재시도 없이 한 번 시도하고 바로 폴백으로 넘어간다. DAG 자체가 재시도(retry)되면 콜백도 다시 호출되므로, 일시적인 네트워크 문제에 대한 재시도는 DAG 레벨에서 이미 어느 정도 확보된다.

## 3. 폴백 경로 — 서버가 응답하지 않을 때

`/ingest` 호출이 실패(타임아웃, 연결 거부, 5xx)하면 알림 서버를 완전히 거치지 않고 Slack Incoming Webhook으로 직접 보낸다.

```python
def _send_fallback(payload: dict) -> None:
    text = (
        f":red_circle: [폴백] {payload['dag_id']}.{payload['task_id']} 실패\n"
        f"```{payload['message']}```\n"
        f"<{payload['log_url']}|로그 보기>"
    )
    try:
        requests.post(SLACK_FALLBACK_WEBHOOK, json={"text": text}, timeout=5)
    except Exception:
        pass  # 이것마저 실패하면 Airflow 자체 로그(태스크 로그)에만 남는다 — 감수한다
```

### 폴백 경로의 한계 (의도적으로 감수하는 부분)

- **중복 제거 없음** — 같은 에러가 반복돼도 서버가 죽어있는 동안은 매번 새 메시지가 올라간다.
- **통계에 반영 안 됨** — 대시보드 총계·다이제스트는 서버가 자체 DB에 쓴 것만 집계한다. 폴백으로 나간 메시지는 서버가 모르는 이벤트라 통계에서 빠진다.
- **상호작용 버튼 없음** — 단순 텍스트 메시지. 확인/해결 버튼은 서버가 만드는 기능이라 폴백에는 없다.
- 이 세 가지는 "알림이 아예 안 오는 것"보다 낫다는 전제로 감수하는 트레이드오프다. 서버가 복구되면 그 이후 이벤트부터 정상 경로로 돌아온다.

### `slack_fallback_webhook`은 별도로 발급한다

알림 서버의 Slack Bot Token(Socket Mode, `chat.postMessage` 등 API 권한)과는 별개로, Slack 앱 설정에서 Incoming Webhook을 하나 더 활성화해 그 URL을 Airflow `Variable`에 저장한다. 알림 서버가 완전히 macOS/Termux 프로세스째로 죽어도 이 Webhook 자체는 Slack 쪽에 이미 등록되어 있어 영향받지 않는다.

## 4. `/health`와의 관계

`/health`는 Airflow가 매 실패 콜백마다 먼저 찔러보는 용도가 아니다(그 사이에 서버가 죽으면 레이스 컨디션이 생긴다). 대신:

- 콜백은 위처럼 `/ingest`를 바로 시도하고 실패 시 즉시 폴백한다.
- `/health`는 **서버 쪽 자기 점검용**이다 — 예를 들어 별도 모니터링(간단한 크론이나 외부 uptime 체크)이 주기적으로 `/health`를 찔러 서버가 오래 죽어있으면 별도로 알려주는 용도로 나중에 붙인다.

## 필요한 값 정리

| 이름 | 위치 | 용도 |
|---|---|---|
| `alert_server_token` | Airflow Variable | `/ingest` 인증 헤더 |
| `ALERT_SERVER_TOKEN` | 알림 서버 `.env` | 위와 동일 값, 서버 측 검증용 |
| `slack_fallback_webhook` | Airflow Variable | 서버 다운 시 직접 발송용 Slack Incoming Webhook URL |
