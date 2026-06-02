#!/bin/bash

# ==============================================================================
# CCTV IP Camera Simulator Automation Script (Smart Video Detection)
# ==============================================================================

echo "====================================================="
echo "      CCTV IP Camera Simulator Setup Wizard          "
echo "====================================================="
echo ""

# 1. Determine base directories dynamically
if [ -f "./generate_config.py" ]; then
    BASE_DIR=$(pwd)
else
    BASE_DIR="/opt/cctv-simulator"
fi

CONFIG_DIR="$BASE_DIR/configs"
mkdir -p "$CONFIG_DIR"
mkdir -p "$BASE_DIR/videos"

# 2. Automatically detect any MP4 file in the videos folder
VIDEO_PATH=$(ls "$BASE_DIR/videos/"*.mp4 2>/dev/null | head -n 1)

if [ -z "$VIDEO_PATH" ]; then
    echo "[!] No MP4 video file found in $BASE_DIR/videos/"
    echo "    Generating a default 720p color test pattern video..."
    VIDEO_PATH="$BASE_DIR/videos/camera.mp4"
    ffmpeg -f lavfi -i testsrc2=size=1280x720:rate=25 -f lavfi -i sine=frequency=0 -c:v libx264 -preset ultrafast -t 60 -c:a aac "$VIDEO_PATH" > /dev/null 2>&1
else
    echo "[i] Detected video template source: $(basename "$VIDEO_PATH")"
fi

# 3. Check for generate_config.py
if [ ! -f "$BASE_DIR/generate_config.py" ]; then
    echo "Error: Cannot find 'generate_config.py' in $BASE_DIR."
    exit 1
fi

# 4. Ask for the number of cameras
read -p "How many cameras do you need to simulate? " CAM_COUNT

if ! [[ "$CAM_COUNT" =~ ^[0-9]+$ ]]; then
    echo "Error: Please enter a valid number."
    exit 1
fi

# 5. Install Prerequisites (FFmpeg)
echo -e "\n[+] Step 1: Installing prerequisites (FFmpeg)..."
apt update -y > /dev/null 2>&1
apt install -y ffmpeg > /dev/null 2>&1
echo "    FFmpeg installation complete."

# 6. Generate Configuration
echo -e "\n[+] Step 2: Generating configuration for $CAM_COUNT cameras..."
python3 "$BASE_DIR/generate_config.py" "$CAM_COUNT" "$VIDEO_PATH" "$CONFIG_DIR"

# 7. Optimize for Large Camera Counts (50+)
if [ "$CAM_COUNT" -ge 50 ]; then
    echo "    50+ cameras detected. Optimizing configuration to 'runOnInit' mode..."
    sed -i 's/runOnDemand:/runOnInit:/g; s/runOnDemandRestart/runOnInitRestart/g' "$CONFIG_DIR/mediamtx.yml"
    echo "    Optimization complete. Streams will pre-start."
else
    echo "    Using default 'runOnDemand' mode (saves CPU at idle)."
fi

# 8. Verify and Locate MediaMTX Binary
if command -v mediamtx &> /dev/null; then
    MEDIAMTX_CMD="mediamtx"
elif [ -f "./mediamtx" ]; then
    MEDIAMTX_CMD="./mediamtx"
elif [ -f "/opt/cctv-simulator/mediamtx" ]; then
    MEDIAMTX_CMD="/opt/cctv-simulator/mediamtx"
else
    echo -e "\n[!] Error: 'mediamtx' command not found."
    exit 1
fi

# 9. Start MediaMTX Service
echo -e "\n[+] Step 3: Starting the RTSP server using ($MEDIAMTX_CMD)..."
pkill mediamtx 2>/dev/null
pkill -f ffmpeg 2>/dev/null

# Start MediaMTX in the background
$MEDIAMTX_CMD "$CONFIG_DIR/mediamtx.yml" &
sleep 2

# Verify port 8554 is listening
if ss -tlnp | grep -q 8554; then
    echo -e "\n====================================================="
    echo " SUCCESS: Simulator is running!"
    echo "====================================================="
    
    # Extract native WSL IP address safely
    LOCAL_IP=$(ip addr show eth0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | head -n 1)
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP=$(ip addr show | grep 'inet ' | grep -v 127.0.0.1 | awk '{print $2}' | cut -d/ -f1 | head -n 1)
    fi
    
    echo "You can now add your cameras to exacqVision or your NVR."
    echo "Device Type: RTSP"
    echo "Username/Password: Leave blank"
    echo ""
    echo "Stream URLs to add:"
    echo "  rtsp://$LOCAL_IP:8554/cam1"
    if [ "$CAM_COUNT" -gt 1 ]; then
        echo "  ..."
        echo "  rtsp://$LOCAL_IP:8554/cam$CAM_COUNT"
    fi
    echo ""
    echo "To test locally on this machine, run: ffplay rtsp://127.0.0.1:8554/cam1"
    echo "====================================================="
else
    echo "Error: MediaMTX failed to start. Port 8554 is not listening."
fi