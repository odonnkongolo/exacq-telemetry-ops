#!/usr/bin/env python3
# =============================================================================
# generate_config.py — Generates mediamtx.yml for N camera streams
# Compatible with MediaMTX v1.9.1+
#
# Usage: python3 generate_config.py [camera_count] [video_file] [output_dir]
# =============================================================================

import sys
import os
from datetime import datetime

camera_count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
video_file   = sys.argv[2] if len(sys.argv) > 2 else "/opt/cctv-simulator/videos/camera.mp4"
output_dir   = sys.argv[3] if len(sys.argv) > 3 else "/opt/cctv-simulator/configs"
rtsp_port    = os.environ.get("RTSP_PORT", "8554")
api_port     = os.environ.get("API_PORT",  "9997")

os.makedirs(output_dir, exist_ok=True)
config_file = os.path.join(output_dir, "mediamtx.yml")

# Build the FFmpeg on-demand command
ffmpeg_cmd = (
    f"ffmpeg -re -stream_loop -1 -i {video_file} "
    f"-c:v copy -c:a aac "
    f"-f rtsp -rtsp_transport tcp "
    f"rtsp://127.0.0.1:{rtsp_port}/$MTX_PATH"
)

lines = []
lines.append(f"# CCTV Simulator — generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
lines.append(f"# Cameras: {camera_count}  |  Video: {video_file}")
lines.append("")
lines.append("logLevel: warn")
lines.append("")
lines.append("rtsp: yes")
lines.append(f"rtspAddress: :{rtsp_port}")
lines.append("")
lines.append("rtmp: no")
lines.append("hls: no")
lines.append("")
lines.append("api: yes")
lines.append(f"apiAddress: :{api_port}")
lines.append("")
lines.append("paths:")

for i in range(1, camera_count + 1):
    lines.append(f"  cam{i}:")
    lines.append(f"    runOnDemand: {ffmpeg_cmd}")
    lines.append(f"    runOnDemandRestart: yes")

config_text = "\n".join(lines) + "\n"

with open(config_file, "w") as f:
    f.write(config_text)

print(f"Config written: {config_file}")
print(f"  Cameras : {camera_count}")
print(f"  RTSP    : rtsp://HOST_IP:{rtsp_port}/cam1 ... cam{camera_count}")
print(f"  API     : http://HOST_IP:{api_port}/v3/paths/list")
