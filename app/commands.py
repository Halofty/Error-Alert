from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session

from app.queries import format_error_list, query_errors

DEFAULT_LIMIT = 30

USAGE = (
    "사용법 (시각은 UTC 기준, 기본 30개까지 표시):\n"
    "`/errors` — 미해결 목록\n"
    "`/errors all` — 전체 목록 (해결된 것 포함)\n"
    "`/errors 2026-09-09` — 해당 날짜, 미해결만\n"
    "`/errors all 2026-09-09` — 해당 날짜, 전체\n"
    "`/errors 2026-09-09T10:00 2026-09-09T18:00` — 두 시각 사이, 미해결만\n"
    "아무 위치에나 `limit=50` 을 추가하면 표시 개수 조정"
)


def handle_errors_command(text: str, session: Session) -> str:
    """토큰을 세 종류로 나눠서 파싱한다: 'all'/'전체' 키워드(상태 필터),
    'limit=N'(표시 개수, 기본 30), 나머지(날짜 파라미터 — 0개: 필터 없음,
    1개: 그 날짜, 2개: 두 시각 사이 범위)."""
    show_all = False
    limit = DEFAULT_LIMIT
    date_tokens: list[str] = []

    for tok in text.split():
        low = tok.lower()
        if low in ("all", "전체"):
            show_all = True
        elif low.startswith("limit="):
            try:
                limit = int(tok.split("=", 1)[1])
                if limit <= 0:
                    raise ValueError
            except ValueError:
                return f"limit 값이 잘못됐습니다 (양의 정수).\n\n{USAGE}"
        else:
            date_tokens.append(tok)

    scope = "전체" if show_all else "미해결"

    if len(date_tokens) == 0:
        records = query_errors(session, unresolved_only=not show_all)
        return format_error_list(records, f"{scope} 에러", limit)

    if len(date_tokens) == 1:
        try:
            day = datetime.strptime(date_tokens[0], "%Y-%m-%d")
        except ValueError:
            return f"날짜 형식이 잘못됐습니다 (`YYYY-MM-DD`).\n\n{USAGE}"
        records = query_errors(session, unresolved_only=not show_all, start=day, end=day + timedelta(days=1))
        return format_error_list(records, f"{date_tokens[0]} {scope} 에러", limit)

    if len(date_tokens) == 2:
        try:
            start = datetime.strptime(date_tokens[0], "%Y-%m-%dT%H:%M")
            end = datetime.strptime(date_tokens[1], "%Y-%m-%dT%H:%M")
        except ValueError:
            return f"시각 형식이 잘못됐습니다 (`YYYY-MM-DDTHH:MM`).\n\n{USAGE}"
        if start >= end:
            return "시작 시각이 끝 시각보다 앞서야 합니다."
        records = query_errors(session, unresolved_only=not show_all, start=start, end=end)
        return format_error_list(records, f"{date_tokens[0]} ~ {date_tokens[1]} {scope} 에러", limit)

    return f"날짜 파라미터는 0~2개까지만 지원합니다.\n\n{USAGE}"
