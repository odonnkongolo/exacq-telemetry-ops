#!/bin/bash
# =============================================================================
# status.sh
# =============================================================================
INSTALL_DIR="/opt/cctv-simulator"
CAMERAS_CONF="$INSTALL_DIR/configs/cameras.conf"
[[ -f "$CAMERAS_CONF" ]] && source "$CAMERAS_CONF"
RTSP_PORT=${RTSP_PORT:-8554}
API_PORT=${API_PORT:-9997}
HOST_IP=$(ip route get 8.8.8.8 2>/dev/null | awk '{print $7; exit}')

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        CCTV Simulator Status                 ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# MediaMTX
PID_FILE="$INSTALL_DIR/pids/mediamtx.pid"
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
    echo -e "  MediaMTX     : ${GREEN}● RUNNING${NC} (PID $(cat $PID_FILE))"
else
    echo -e "  MediaMTX     : ${RED}○ STOPPED${NC}"
fi

# ONVIF
OPID="$INSTALL_DIR/pids/onvif.pid"
if [[ -f "$OPID" ]] && kill -0 "$(cat $OPID)" 2>/dev/null; then
    echo -e "  ONVIF Server : ${GREEN}● RUNNING${NC} (PID $(cat $OPID))"
else
    echo -e "  ONVIF Server : ${YELLOW}○ not running${NC}"
fi

# Port check
if ss -tlnp 2>/dev/null | grep -q ":${RTSP_PORT}"; then
    echo -e "  Port $RTSP_PORT   : ${GREEN}● LISTENING${NC}"
else
    echo -e "  Port $RTSP_PORT   : ${RED}○ not listening${NC}"
fi

# Active FFmpeg processes
FFMPEG_COUNT=$(pgrep -c -f "rtsp://127.0.0.1" 2>/dev/null || echo 0)
echo -e "  FFmpeg procs : ${CYAN}${FFMPEG_COUNT} active stream(s)${NC}"

# API query
echo ""
echo -e "  ${CYAN}Active connections (via API):${NC}"
RESULT=$(curl -s "http://127.0.0.1:${API_PORT}/v3/paths/list" 2>/dev/null)
if [[ -n "$RESULT" ]]; then
    echo "$RESULT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    items = data.get('items', [])
    active = [p for p in items if p.get('readers')]
    if not active:
        print('  No NVR connections (streams start on demand when NVR connects)')
    else:
        for p in active:
            print(f'  ✓ /{p[\"name\"]}  — {len(p.get(\"readers\",[]))} viewer(s)')
except Exception as e:
    print(f'  (parse error: {e})')
" 2>/dev/null
else
    echo "  (MediaMTX not running)"
fi

echo ""
echo -e "  ${CYAN}Host IP :${NC} $HOST_IP"
echo -e "  ${CYAN}RTSP    :${NC} rtsp://$HOST_IP:$RTSP_PORT/cam1"
echo -e "  ${CYAN}API     :${NC} http://$HOST_IP:$API_PORT/v3/paths/list"
echo ""
