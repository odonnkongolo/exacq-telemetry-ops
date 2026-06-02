#!/bin/bash
# =============================================================================
# CCTV IP Camera Simulator - Setup Script (Optimized)
# Tested on Ubuntu 25 / MediaMTX v1.9.1
# =============================================================================

set -e

MEDIAMTX_VERSION="v1.9.1"
INSTALL_DIR="/opt/cctv-simulator"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        CCTV IP Camera Simulator - Setup              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

[[ $EUID -ne 0 ]] && { echo -e "${RED}[x]${NC} Run as root: sudo bash setup.sh"; exit 1; }

# --- Install FFmpeg ---
log "Installing FFmpeg..."
apt-get update -qq
apt-get install -y ffmpeg curl wget python3 net-tools iproute2
log "FFmpeg installed: $(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f1-3)"

# --- Install MediaMTX ---
log "Installing MediaMTX ${MEDIAMTX_VERSION}..."
ARCH=$(uname -m)
case $ARCH in
  x86_64)  MTX_ARCH="amd64" ;;
  aarch64) MTX_ARCH="arm64v8" ;;
  armv7l)  MTX_ARCH="armv7" ;;
  *) echo -e "${RED}[x]${NC} Unsupported arch: $ARCH"; exit 1 ;;
esac

MTX_URL="https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/mediamtx_${MEDIAMTX_VERSION}_linux_${MTX_ARCH}.tar.gz"
TMP_DIR=$(mktemp -d)
wget -q --show-progress -O "${TMP_DIR}/mediamtx.tar.gz" "$MTX_URL"
tar -xzf "${TMP_DIR}/mediamtx.tar.gz" -C "${TMP_DIR}"
install -m 755 "${TMP_DIR}/mediamtx" /usr/local/bin/mediamtx
rm -rf "$TMP_DIR"
log "MediaMTX installed: $(mediamtx --version 2>&1 | head -1)"

# --- Create directory structure ---
log "Creating directories..."
mkdir -p "$INSTALL_DIR"/{configs,videos,logs,pids}

# Create local empty videos folder in the current execution folder for staging
WORKING_DIR="$(pwd)"
mkdir -p "$WORKING_DIR/videos"
chmod 777 "$WORKING_DIR/videos"
log "Created local empty staging folder: $WORKING_DIR/videos/"

# Apply broad permissions to the global installation videos directory to avoid write conflicts
chmod -R 777 "$INSTALL_DIR/videos"
log "Created global storage folder: $INSTALL_DIR/videos/"

# --- Copy scripts ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for f in start_cameras.sh stop_cameras.sh status.sh generate_config.sh; do
    [[ -f "$SCRIPT_DIR/$f" ]] && cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/" && chmod +x "$INSTALL_DIR/$f"
done
[[ -f "$SCRIPT_DIR/onvif_server.py" ]] && cp "$SCRIPT_DIR/onvif_server.py" "$INSTALL_DIR/"
[[ -f "$SCRIPT_DIR/cameras.conf" ]]    && cp "$SCRIPT_DIR/cameras.conf" "$INSTALL_DIR/configs/"

# --- Optional ONVIF ---
echo ""
read -p "Install ONVIF support (NVR auto-discovery)? [y/N] " -n 1 -r; echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if ! command -v node &>/dev/null; then
        log "Installing Node.js..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
    fi
    log "Node.js $(node --version) ready"
    touch "$INSTALL_DIR/.onvif_enabled"
    log "ONVIF enabled"
fi

# --- Systemd service ---
cat > /etc/systemd/system/cctv-simulator.service << 'EOF'
[Unit]
Description=CCTV IP Camera Simulator
After=network.target

[Service]
Type=forking
ExecStart=/opt/cctv-simulator/start_cameras.sh
ExecStop=/opt/cctv-simulator/stop_cameras.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
log "Systemd service registered"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
info "1. Copy your MP4:  cp yourfile.mp4 $WORKING_DIR/videos/camera.mp4"
info "2. Run auto-start: sudo bash step-2-simulator-auto-start.sh"
echo ""