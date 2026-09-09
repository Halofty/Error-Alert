#!/data/data/com.termux/files/usr/bin/bash
# Termux에서 코드 업데이트할 때 이거 하나만 실행: bash deploy.sh
set -euo pipefail

cd "$(dirname "$0")"

git pull
pip install -r requirements.txt

mkdir -p logs

pkill -f "app.ingest_server" 2>/dev/null || true
pkill -f "app.socket_listener" 2>/dev/null || true
sleep 1

# >> 대신 > — 매 배포마다 새로 씀. 계속 append하면 재배포할 때마다 무한정 커진다.
# (앱 자체 로그는 logging_config.py가 이미 회전시켜서 별도 보관하고, 이 .out은
# setup_logging()이 뜨기도 전에 나는 임포트/문법 에러 같은 걸 잡기 위한 최소한의 안전망이다)
nohup python -m app.ingest_server > logs/ingest.out 2>&1 &
nohup python -m app.socket_listener > logs/listener.out 2>&1 &

sleep 2
echo "배포 완료."
echo "  ingest:   $(pgrep -f app.ingest_server | wc -l) 개 프로세스"
echo "  listener: $(pgrep -f app.socket_listener | wc -l) 개 프로세스"
echo "로그: logs/ingest.log, logs/listener.log (앱 자체 로그) / logs/*.out (stdout/stderr)"
