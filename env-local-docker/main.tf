terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0.1"
    }
  }
}

provider "docker" {
  host = "unix:///var/run/docker.sock"
}

# --- Resources ---

# Use the existing image we built previously
data "docker_image" "web_image" {
  name = "cctv-simulator-web:latest"
}

# Pull the Nginx image
resource "docker_image" "nginx_image" {
  name = "nginx:1.27-alpine"
}

# Create a custom Docker network so containers can communicate by name
resource "docker_network" "cctv_net" {
  name = "cctv-simulator-net"
}

# Flask Web / Simulator Container
resource "docker_container" "web" {
  name    = "cctv-simulator"
  image   = data.docker_image.web_image.name
  restart = "unless-stopped"

  networks_advanced {
    name    = docker_network.cctv_net.name
    aliases = ["web"]
  }

  # RTSP Streams
  ports {
    internal = 8554
    external = 8554
    protocol = "tcp"
  }
  ports {
    internal = 8554
    external = 8554
    protocol = "udp"
  }

  # MediaMTX REST API
  ports {
    internal = 9997
    external = 9997
    protocol = "tcp"
  }

  volumes {
    host_path      = "/Users/ojayodon/Developer/cctv-simulator/test-video-tokyo-walking.mp4"
    container_path = "/opt/cctv-simulator/videos/camera.mp4"
    read_only      = true
  }
}

# Nginx Reverse Proxy Container
resource "docker_container" "nginx" {
  name    = "cctv-nginx"
  image   = docker_image.nginx_image.name
  restart = "unless-stopped"

  networks_advanced {
    name = docker_network.cctv_net.name
  }

  ports {
    internal = 80
    external = 5050
    protocol = "tcp"
  }

  volumes {
    host_path      = "/Users/ojayodon/Developer/cctv-simulator/nginx.conf"
    container_path = "/etc/nginx/nginx.conf"
    read_only      = true
  }

  # Ensure the web container starts first
  depends_on = [docker_container.web]
}

# --- Observability Stack ---

resource "docker_image" "prometheus_image" {
  name = "prom/prometheus:latest"
}

resource "docker_image" "grafana_image" {
  name = "grafana/grafana:latest"
}

resource "docker_image" "cadvisor_image" {
  name = "gcr.io/cadvisor/cadvisor:v0.47.0"
}

# Prometheus Container
resource "docker_container" "prometheus" {
  name    = "prometheus"
  image   = docker_image.prometheus_image.name
  restart = "unless-stopped"

  networks_advanced {
    name    = docker_network.cctv_net.name
    aliases = ["prometheus"]
  }

  ports {
    internal = 9090
    external = 9090
    protocol = "tcp"
  }

  volumes {
    host_path      = "/Users/ojayodon/Developer/cctv-simulator/monitoring/prometheus.yml"
    container_path = "/etc/prometheus/prometheus.yml"
    read_only      = true
  }
}

# Grafana Container
resource "docker_container" "grafana" {
  name    = "grafana"
  image   = docker_image.grafana_image.name
  restart = "unless-stopped"

  networks_advanced {
    name    = docker_network.cctv_net.name
    aliases = ["grafana"]
  }

  ports {
    internal = 3000
    external = 3000
    protocol = "tcp"
  }
}

# cAdvisor Container
resource "docker_container" "cadvisor" {
  name       = "cadvisor"
  image      = docker_image.cadvisor_image.name
  restart    = "unless-stopped"
  privileged = true

  networks_advanced {
    name    = docker_network.cctv_net.name
    aliases = ["cadvisor"]
  }

  ports {
    internal = 8080
    external = 8080
    protocol = "tcp"
  }

  volumes {
    host_path      = "/"
    container_path = "/rootfs"
    read_only      = true
  }
  volumes {
    host_path      = "/var/run"
    container_path = "/var/run"
    read_only      = true
  }
  volumes {
    host_path      = "/sys"
    container_path = "/sys"
    read_only      = true
  }
}
