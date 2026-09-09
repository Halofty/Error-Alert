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

nohup python -m app.ingest_server >> logs/ingest.out 2>&1 &
nohup python -m app.socket_listener >> logs/listener.out 2>&1 &

sleep 2
echo "배포 완료."
echo "  ingest:   $(pgrep -f app.ingest_server | wc -l) 개 프로세스"
echo "  listener: $(pgrep -f app.socket_listener | wc -l) 개 프로세스"
echo "로그: logs/ingest.log, logs/listener.log (앱 자체 로그) / logs/*.out (stdout/stderr)"
