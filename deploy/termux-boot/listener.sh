#!/data/data/com.termux/files/usr/bin/bash
# ~/.termux/boot/listener.sh 로 복사해서 사용 (Termux:Boot이 재부팅 시 자동 실행)
termux-wake-lock

cd ~/error-alert   # 실제 클론 경로에 맞게 수정

# 부팅 직후 WiFi/모바일 데이터가 아직 안 붙었을 수 있어 최대 60초 대기.
# curl/ping 설치 여부와 무관하게 동작하도록 bash 내장 /dev/tcp로 확인.
# socket_listener는 시작 시 Slack auth.test를 호출하므로(app/socket_listener.py의
# create_app()) 네트워크 없이 뜨면 바로 실패한다 — 여기서 기다려 첫 시도부터
# 성공할 확률을 높인다. 그래도 실패하면 앱 내부 재시도 루프가 이어서 처리한다.
for i in $(seq 1 30); do
    (echo > /dev/tcp/1.1.1.1/443) 2>/dev/null && break
    sleep 2
done

mkdir -p logs
CRASH_LOG=logs/listener-crash.log

while true; do
    python -m app.socket_listener
    echo "$(date) socket_listener 종료됨 — 2초 후 재시작" >> "$CRASH_LOG"
    # append만 하면 무한정 커지므로 최근 500줄로 제한
    tail -n 500 "$CRASH_LOG" > "$CRASH_LOG.tmp" && mv "$CRASH_LOG.tmp" "$CRASH_LOG"
    sleep 2
done
