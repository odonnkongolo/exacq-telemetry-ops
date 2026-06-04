# Enterprise CCTV Telemetry & GitOps Platform

An end-to-end GitOps platform designed to deploy, monitor, and manage a containerized CCTV RTSP stream simulator on edge infrastructure. This project demonstrates Senior-level Platform Engineering principles, including Infrastructure as Code (IaC), DevSecOps pipelines, and cost-optimized cloud deployments.

## 🏗️ Architecture Overview

This platform provisions immutable AWS edge infrastructure via Terraform and deploys a lightweight Kubernetes (K3s) cluster to orchestrate application and observability payloads. 

### Core Technology Stack
* **Cloud Provider:** AWS (EC2 `t3.micro` - strict Free Tier compliance)
* **Infrastructure as Code:** Terraform (with S3 backend remote state & DynamoDB/S3 lock-files)
* **Container Orchestration:** Kubernetes (K3s)
* **CI/CD & Automation:** GitHub Actions (GitOps workflow)
* **DevSecOps:** Trivy (Container vulnerability scanning)
* **Observability:** Prometheus & Grafana (Configured for low-memory edge environments)
* **Application Layer:** Python-based RTSP Camera Simulator (MediaMTX)

## 🔄 The DevSecOps Pipeline

The deployment lifecycle is entirely automated via GitHub Actions, enforcing strict CI/CD gates before infrastructure is modified.

1. **Security Gate (`trivy-scan`):** On every push, the container image is built locally in the CI runner and scanned for `CRITICAL` and `HIGH` CVEs at the OS and library level.
2. **Infrastructure Gate (`terraform-deploy`):** Upon passing security, the runner authenticates securely with AWS, initializes the Terraform S3 backend, acquires the state lock, and executes `terraform apply`.
3. **Application Bootstrap:** The EC2 `user_data` script installs K3s and dynamically applies the Kubernetes manifests directly from the repository.

## 🛠️ SRE & Platform Engineering Highlights

### 1. Ephemeral Cost Optimization (The "Kill Switch")
To ensure absolute zero-cost overhead when the environment is not actively monitored, a discrete `workflow_dispatch` GitHub Action was engineered. This allows administrators to trigger a `terraform destroy` directly from the GitHub UI, gracefully tearing down all AWS resources while preserving the infrastructure state in S3.

### 2. S3 State Locking & Concurrency Control
Terraform state is managed remotely in an AWS S3 bucket with native lock-file configurations. This prevents race conditions and corrupted states if multiple pipeline runs are triggered simultaneously.

### 3. Resource Constrained Edge Deployments
The deployment was heavily optimized to run within the strict 1GB RAM limits of an AWS `t3.micro` instance. Trade-offs were made to consolidate the control plane and data plane into a single lightweight K3s footprint, highlighting adaptability to edge-compute constraints.

## 🚀 Quick Start Guide

**1. Infrastructure Provisioning**
Pushing code to the `main` branch automatically triggers the master DevSecOps pipeline. 

**2. Accessing the Environment**
Once deployed, extract the public IP from the GitHub Actions Terraform log output. 
* **CCTV Simulator:** Accessible via standard RTSP protocols on the configured port.

**3. Teardown**
Navigate to the GitHub Actions tab, select `🛑 Destroy Cloud Infrastructure`, and execute the manual run to terminate all billable AWS resources.

---
*Engineered for scale, security, and absolute automation - Odon Nkongolo*