#!/bin/bash

# Exit immediately if any command fails (Standard DevOps safety measure)
set -e 

echo "🚀 Initiating Enterprise CCTV Simulator Deployment..."

# 1. Create the cluster (The '|| true' prevents it from failing if the cluster already exists)
echo "🧠 Provisioning Control Plane..."
k3d cluster create exacq-cluster || true

# 2. Inject the Configuration
echo "⚙️ Injecting Camera Configurations..."
kubectl create configmap camera-config --from-file=./src-camera-simulator/cameras.conf --dry-run=client -o yaml | kubectl apply -f -

# 3. Build and Airlift the Image
echo "📦 Compiling Simulator Image..."
docker build -t cctv-simulator:latest ./src-camera-simulator
echo "✈️ Airlifting image into Kubernetes storage..."
k3d image import cctv-simulator:latest -c exacq-cluster

# 4. Apply the Blueprint Manifests
echo "🏗️ Applying Infrastructure State..."
kubectl apply -f ./env-kubernetes/prometheus-manifest.yaml
kubectl apply -f ./env-kubernetes/simulator-deployment.yaml
kubectl apply -f ./env-kubernetes/simulator-service.yaml

# 5. Expose the Simulator via a Local Port Forward (The "Production Proxy")
echo "🔗 Establishing Background Port-Forward Tunnel..."
# 1. Kill any existing tunnels so we don't get an "Address already in use" error
pkill -f "kubectl port-forward service/camera-simulator-service" || true

# 2. Start the tunnel in the background (&) and send all text output to the void (/dev/null)
kubectl port-forward service/camera-simulator-service 8080:5000 > /dev/null 2>&1 &

echo "================================================="
echo "✅ DEPLOYMENT SUCCESSFUL: Stack is live!"
echo "🌐 The tunnel was automatically opened in the background."
echo "👉 Open your browser to: http://localhost:8080"
echo "🔴 If the tunnel is not open, run: kubectl port-forward service/camera-simulator-service 8080:5000"
echo "================================================="