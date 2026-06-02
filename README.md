# 📹 Exacq Camera Simulator & Telemetry Stack

This repository contains the Infrastructure as Code (IaC) to deploy a localized camera simulator alongside an enterprise-grade monitoring stack (**Prometheus**, **cAdvisor**, and **Grafana**). 

This environment allows us to generate active video streams for Exacq environments while actively monitoring the hardware footprint (CPU, Memory, Network) of the simulation engine in real-time.

---

## ⚙️ Prerequisites
Before deploying, ensure your local machine has the following installed:
* 🐳 [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Running in the background)
* 🌍 [Terraform CLI](https://developer.hashicorp.com/terraform/downloads)

---

## 🚀 Quick Start Guide

### 1️⃣ Clone the Repository
Pull the latest infrastructure code to your local machine and navigate into the directory.
```bash
git clone <insert-your-repo-url-here>
cd <your-repo-folder-name>
```

### 2️⃣ Initialize Terraform
This command downloads the necessary Docker providers and prepares the local backend state. You only need to run this once.
```bash
terraform init
```

### 3️⃣ Deploy the Infrastructure
This command will automatically provision the Docker network, pull the required images, map the volume sensors, and launch the full 5-container stack.
```bash
terraform apply -auto-approve
```

---

## 💻 Accessing the Dashboards
Once the deployment completes (usually under 15 seconds), the telemetry pipeline is fully operational. You can access the UI command centers via your local browser:

*   📊 **Grafana (Main Dashboard)**: [http://localhost:3000](http://localhost:3000)
    *   **Default Login**: `admin` / `admin` (You will be prompted to change this on first login).
    *   **Navigation**: Go to *Dashboards > cAdvisor exporter* to view live CPU, Memory, and Network traffic for the simulator and Nginx router.

*   📈 **Prometheus (Raw Database)**: [http://localhost:9090](http://localhost:9090)

*   📡 **cAdvisor (Raw Sensors)**: [http://localhost:8080](http://localhost:8080)

---

## 🗑️ Teardown
To completely destroy the environment and wipe the containers from your machine, run:
```bash
terraform destroy -auto-approve
```

---

## 👨‍💻 Maintainers

**Odon Nkongolo** — *Lead Infrastructure Automation Engineer*