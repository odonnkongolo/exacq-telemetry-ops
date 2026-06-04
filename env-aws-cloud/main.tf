terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # --- TELL TERRAFORM TO USE THE CLOUD VAULT ---
  backend "s3" {
    bucket         = "exacq-tf-state-odon-2026"
    key            = "exacq-telemetry/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}

# 1. The Cloud Provider
provider "aws" {
  region = "eu-west-1" # Dublin (Closest to Belfast for lowest latency)
}

# 2. The Cloud Firewall (Security Group)
resource "aws_security_group" "cctv_sg" {
  name        = "cctv_simulator_sg"
  description = "Allow Web and SSH traffic"

  # Allow HTTP traffic to the Flask Web UI
  ingress {
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] 
  }
  # Allow Grafana Telemetry Dashboard
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow RTSP Video Streaming traffic
  ingress {
    from_port   = 8554
    to_port     = 8554
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow standard web traffic
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow SSH traffic so we can debug
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow all outbound traffic (so the server can download packages)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 3. Find the latest Ubuntu OS automatically
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Official Canonical Ubuntu

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# 4. The Virtual Server (100% Free Tier Eligible)
resource "aws_instance" "cctv_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.cctv_sg.id]

# ---> ADD THIS BLOCK TO CLAIM 20GB OF FREE TIER STORAGE <---
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

# 5. The Bootstrap Automation (Runs once on boot)
  user_data = <<-EOF
              #!/bin/bash
              
              # --- 1. PREVENT MEMORY CRASH (CREATE 2GB SWAP) ---
              fallocate -l 2G /swapfile
              chmod 600 /swapfile
              mkswap /swapfile
              swapon /swapfile

              # --- 2. Install Docker and Git ---
              apt-get update
              apt-get install -y docker.io git

              # --- 3. Install the k3s Orchestrator ---
              curl -sfL https://get.k3s.io | sh -
              sleep 15 # Wait for cluster to wake up

              # --- 4. Clone your specific repository ---
              git clone https://github.com/odonnkongolo/exacq-telemetry-ops.git /opt/exacq
              cd /opt/exacq

              # --- 5. Build the Simulator Image on the server ---
              docker build -t cctv-simulator:latest ./src-camera-simulator
              
              # --- 6. Import the image into k3s internal storage ---
              docker save cctv-simulator:latest > cctv.tar
              k3s ctr images import cctv.tar

              # --- 7. Apply the configuration and manifests ---
              export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
              kubectl create configmap camera-config --from-file=./src-camera-simulator/cameras.conf
              kubectl apply -f ./env-kubernetes/simulator-deployment.yaml
              kubectl apply -f ./env-kubernetes/simulator-service.yaml
              kubectl apply -f ./env-kubernetes/observability/prometheus.yaml  # -----  Prometheus (Observability Feature File) installed
              kubectl apply -f ./env-kubernetes/observability/grafana.yml      # -----  Grafana (Observability Feature File) installed
              EOF

  tags = {
    Name = "Enterprise-CCTV-Cluster"
  }
}

# 6. Output the Public IP address to your terminal
output "simulator_live_url" {
  value       = "http://${aws_instance.cctv_server.public_ip}:5000"
  description = "Click this link in ~3 minutes to see your live cloud app!"
}
