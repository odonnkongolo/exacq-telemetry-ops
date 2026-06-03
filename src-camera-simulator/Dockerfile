# =============================================================================
# Dockerfile — CCTV IP Camera Simulator
# Base: Ubuntu 22.04 + FFmpeg + Python 3 + MediaMTX v1.9.1
# =============================================================================
FROM ubuntu:22.04

# Prevent interactive prompts during apt-get
ENV DEBIAN_FRONTEND=noninteractive

# ---- 1. System packages ----
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
    python3 python3-pip \
    ffmpeg \
    curl \
    wget \
    net-tools \
    iproute2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# ---- 2. Python dependencies ----
RUN pip3 install --no-cache-dir flask

# ---- 3. Download & install MediaMTX v1.9.1 ----
ARG MEDIAMTX_VERSION=v1.19.0
# Detect architecture at build time (supports amd64 and arm64 for Apple Silicon)
RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
    x86_64)  MTX_ARCH="amd64"   ;; \
    aarch64) MTX_ARCH="arm64v8" ;; \
    *)       echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    wget -q -O /tmp/mediamtx.tar.gz \
    "https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/mediamtx_${MEDIAMTX_VERSION}_linux_${MTX_ARCH}.tar.gz" && \
    tar -xzf /tmp/mediamtx.tar.gz -C /tmp && \
    install -m 755 /tmp/mediamtx /usr/local/bin/mediamtx && \
    rm -rf /tmp/mediamtx*

# ---- 4. Create project directory structure ----
RUN mkdir -p /opt/cctv-simulator/{configs,videos,logs,pids}

# ---- 5. Copy project files ----
WORKDIR /opt/cctv-simulator
COPY camera.mp4          videos/camera.mp4
COPY cameras.conf        configs/cameras.conf
COPY generate_config.py  generate_config.py
COPY start_cameras.sh    start_cameras.sh
COPY stop_cameras.sh     stop_cameras.sh
COPY status.sh           status.sh
COPY onvif_server.py     onvif_server.py
COPY web_gui.py          web_gui.py

RUN chmod +x start_cameras.sh stop_cameras.sh status.sh

# ---- 6. Ports ----
# 5000  = Flask web dashboard
# 8554  = RTSP streams
# 9997  = MediaMTX REST API
EXPOSE 5000 8554 9997

# ---- 7. Entrypoint ----
# Launch the Flask dashboard (users start cameras from the UI)
CMD ["python3", "web_gui.py"]
