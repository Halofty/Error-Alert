#!/data/data/com.termux/files/usr/bin/bash
# ~/.termux/boot/listener.sh 로 복사해서 사용 (Termux:Boot이 재부팅 시 자동 실행)
termux-wake-lock

cd ~/error-alert   # 실제 클론 경로에 맞게 수정

while true; do
    python -m app.socket_listener
    echo "$(date) socket_listener 종료됨 — 2초 후 재시작" >> logs/listener-crash.log
    sleep 2
done
