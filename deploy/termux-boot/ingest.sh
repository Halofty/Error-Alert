#!/data/data/com.termux/files/usr/bin/bash
# ~/.termux/boot/ingest.sh 로 복사해서 사용 (Termux:Boot이 재부팅 시 자동 실행)
termux-wake-lock

cd ~/error-alert   # 실제 클론 경로에 맞게 수정

# 부팅 직후 WiFi/모바일 데이터가 아직 안 붙었을 수 있어 최대 60초 대기.
# curl/ping 설치 여부와 무관하게 동작하도록 bash 내장 /dev/tcp로 확인.
# (ingest_server 자체는 네트워크 없이도 뜨지만, 뜨자마자 오는 요청이 전부
# Slack 호출에서 실패하는 걸 줄이려고 여기서도 같이 기다린다.)
for i in $(seq 1 30); do
    (echo > /dev/tcp/1.1.1.1/443) 2>/dev/null && break
    sleep 2
done

mkdir -p logs
CRASH_LOG=logs/ingest-crash.log

while true; do
    python -m app.ingest_server
    echo "$(date) ingest_server 종료됨 — 2초 후 재시작" >> "$CRASH_LOG"
    # append만 하면 무한정 커지므로 최근 500줄로 제한
    tail -n 500 "$CRASH_LOG" > "$CRASH_LOG.tmp" && mv "$CRASH_LOG.tmp" "$CRASH_LOG"
    sleep 2
done
