#!/bin/bash
# =============================================================================
# start_cameras.sh — Start the CCTV camera simulator
# =============================================================================

INSTALL_DIR="/opt/cctv-simulator"
CONFIG_FILE="$INSTALL_DIR/configs/mediamtx.yml"
CAMERAS_CONF="$INSTALL_DIR/configs/cameras.conf"
PID_FILE="$INSTALL_DIR/pids/mediamtx.pid"
LOG_DIR="$INSTALL_DIR/logs"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

mkdir -p "$LOG_DIR" "$INSTALL_DIR/pids"

# --- Load config ---
CAMERA_COUNT=10
VIDEO_FILE="$INSTALL_DIR/videos/camera.mp4"
RTSP_PORT=8554
API_PORT=9997
[[ -f "$CAMERAS_CONF" ]] && source "$CAMERAS_CONF"

# --- Get host IP ---
HOST_IP=$(ip route get 8.8.8.8 2>/dev/null | awk '{print $7; exit}')
[[ -z "$HOST_IP" ]] && HOST_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         CCTV IP Camera Simulator                     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# --- Check / create video file ---
if [[ ! -f "$VIDEO_FILE" ]]; then
    warn "No video found at $VIDEO_FILE"
    warn "Generating test pattern (60s loop)..."
    mkdir -p "$INSTALL_DIR/videos"
    ffmpeg -y \
        -f lavfi -i "testsrc2=size=1280x720:rate=25" \
        -f lavfi -i "sine=frequency=0:sample_rate=48000" \
        -c:v libx264 -preset ultrafast -crf 28 -t 60 \
        -c:a aac -b:a 64k \
        "$VIDEO_FILE" -loglevel error
    log "Test pattern created: $VIDEO_FILE"
fi
log "Video source : $VIDEO_FILE"

# --- Generate config ---
log "Generating config for $CAMERA_COUNT cameras..."
RTSP_PORT=$RTSP_PORT API_PORT=$API_PORT \
    python3 "$INSTALL_DIR/generate_config.py" \
    "$CAMERA_COUNT" "$VIDEO_FILE" "$INSTALL_DIR/configs"

# --- Stop any existing instance ---
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        warn "Stopping existing MediaMTX (PID $OLD_PID)..."
        kill "$OLD_PID" && sleep 1
    fi
    rm -f "$PID_FILE"
fi
# Also catch any stray mediamtx processes
pkill -x mediamtx 2>/dev/null; sleep 0.5

# --- Start MediaMTX ---
log "Starting MediaMTX..."
mediamtx "$CONFIG_FILE" >> "$LOG_DIR/mediamtx.log" 2>&1 &
MTX_PID=$!
echo $MTX_PID > "$PID_FILE"
sleep 2

if ! kill -0 $MTX_PID 2>/dev/null; then
    echo -e "${RED}[x]${NC} MediaMTX failed. Last log:"
    tail -5 "$LOG_DIR/mediamtx.log"
    exit 1
fi
log "MediaMTX started (PID: $MTX_PID)"

# --- Start ONVIF if enabled ---
if [[ -f "$INSTALL_DIR/.onvif_enabled" ]]; then
    log "Starting ONVIF discovery server..."
    python3 "$INSTALL_DIR/onvif_server.py" \
        --cameras "$CAMERA_COUNT" \
        --host "$HOST_IP" \
        --rtsp-port "$RTSP_PORT" \
        >> "$LOG_DIR/onvif.log" 2>&1 &
    echo $! > "$INSTALL_DIR/pids/onvif.pid"
    log "ONVIF server started"
fi

# --- Summary ---
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✓ $CAMERA_COUNT cameras ready!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${CYAN}Host IP   :${NC} $HOST_IP"
echo -e "  ${CYAN}RTSP Port :${NC} $RTSP_PORT"
echo ""
echo -e "  ${CYAN}RTSP stream URLs:${NC}"
for i in $(seq 1 $(( CAMERA_COUNT < 5 ? CAMERA_COUNT : 5 ))); do
    echo -e "  ${YELLOW}  rtsp://$HOST_IP:$RTSP_PORT/cam${i}${NC}"
done
[[ $CAMERA_COUNT -gt 5 ]] && echo -e "  ${YELLOW}  ... up to cam${CAMERA_COUNT}${NC}"
echo ""
echo -e "  ${CYAN}Test stream:${NC}"
echo -e "  ${YELLOW}  ffplay rtsp://$HOST_IP:$RTSP_PORT/cam1${NC}"
echo ""
echo -e "  ${CYAN}Exacq / NVR — add as Generic RTSP:${NC}"
echo -e "    IP    : $HOST_IP"
echo -e "    Port  : $RTSP_PORT"
echo -e "    Path  : /cam1  (change per camera)"
echo ""
echo -e "  ${CYAN}API:${NC} http://$HOST_IP:$API_PORT/v3/paths/list"
echo ""
