#!/bin/bash
# =============================================================================
# stop_cameras.sh
# =============================================================================
INSTALL_DIR="/opt/cctv-simulator"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo ""
for pidfile in "$INSTALL_DIR/pids/"*.pid; do
    [[ -f "$pidfile" ]] || continue
    PID=$(cat "$pidfile")
    NAME=$(basename "$pidfile" .pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo -e "${GREEN}[+]${NC} Stopped $NAME (PID $PID)"
    else
        echo -e "${YELLOW}[!]${NC} $NAME was not running"
    fi
    rm -f "$pidfile"
done

# Clean up any on-demand FFmpeg streams
pkill -f "rtsp://127.0.0.1" 2>/dev/null && echo -e "${GREEN}[+]${NC} Cleaned up FFmpeg streams"
pkill -x mediamtx 2>/dev/null

echo "Stopped."
echo ""
