#!/bin/bash
# MAIA One-Click Deployment
# ========================
# Bootstrap script for MAIA-Node
#
# Usage:
#   curl -sSL get.maia.ai | bash -s -- --license-key=XXXX-XXXX
#   or
#   ./deploy_maia.sh --license-key=XXXX-XXXX
#
# Options:
#   --license-key     Required license key
#   --gpu-model       GPU model (h100, a100, rtx4090, rtx3090) [default: auto]
#   --sector         Default sector (finance, healthcare, legal, construction) [default: finance]
#   --air-gapped     Enable air-gapped mode [default: false]
#   --admin-email    Admin email for notifications
#   --domain        Custom domain (optional)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Defaults
GPU_MODEL="auto"
SECTOR="finance"
AIR_GAPPED=false
ADMIN_EMAIL=""
DOMAIN=""
REGISTRY_URL="https://registry.maia.ai"
K3S_VERSION="v1.28.4+k3s1"
MAIA_VERSION="latest"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --license-key)
            LICENSE_KEY="$2"
            shift 2
            ;;
        --gpu-model)
            GPU_MODEL="$2"
            shift 2
            ;;
        --sector)
            SECTOR="$2"
            shift 2
            ;;
        --air-gapped)
            AIR_GAPPED=true
            shift
            ;;
        --admin-email)
            ADMIN_EMAIL="$2"
            shift 2
            ;;
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate
if [[ -z "$LICENSE_KEY" ]]; then
    log_error "--license-key is required"
    echo "Usage: $0 --license-key=XXXX-XXXX [--gpu-model=h100] [--sector=finance]"
    exit 1
fi

log_info "MAIA One-Click Deployment"
echo "================================"

# Check root
if [ "$EUID" -ne 0 ]; then
    log_error "Run as root: sudo $0 ..."
    exit 1
fi

# Step 1: Check GPU
log_step "Detecting GPU..."
detect_gpu() {
    if nvidia-smi &>/dev/null; then
        local gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
        case $gpu in
            *H100*) echo "h100" ;;
            *A100*) echo "a100" ;;
            *4090*) echo "rtx4090" ;;
            *3090*) echo "rtx3090" ;;
            *) echo "auto" ;;
        esac
    else
        echo "none"
    fi
}

DETECTED_GPU=$(detect_gpu)
if [ "$DETECTED_GPU" = "none" ]; then
    log_warn "No NVIDIA GPU detected. MAIA requires GPU for inference."
    log_warn "Install NVIDIA drivers: https://docs.nvidia.com/cuda/getting-started-guide.html"
fi

if [ "$GPU_MODEL" = "auto" ]; then
    GPU_MODEL=$DETECTED_GPU
fi
log_info "Using GPU model: $GPU_MODEL"

# Step 2: Check prerequisites
log_step "Checking prerequisites..."

check_command() {
    command -v $1 &>/dev/null || { log_error "$1 not found"; return 1; }
}

check_command curl || exit 1
check_command docker || { log_error "Docker not found. Install: https://docs.docker.com/engine/install/"; exit 1; }

# Check NVIDIA Docker
if [ "$DETECTED_GPU" != "none" ]; then
    if ! nvidia-container-toolkit &>/dev/null; then
        log_warn "Installing NVIDIA Container Toolkit..."
        distribution=$(. /etc/os-release 2>/dev/null && echo "$ID")
        case $distribution in
            ubuntu)
                curl -sSL https://nvidia.github.io/nvidia-container-runtime/gpgkey | sudo apt-key add -
                echo "deb https://nvidia.github.io/nvidia-container-runtime/ubuntu focal runtime" | sudo tee /etc/apt/sources.list.d/nvidia-container-runtime.list
                sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
                ;;
        esac
    fi
fi

# Step 3: Install K3s
log_step "Installing K3s..."

if ! command -v k3s &>/dev/null; then
    log_info "Installing K3s $K3S_VERSION..."
    curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=$K3S_VERSION sh -
    
    # Wait for K3s
    sleep 5
fi

# Configure K3s for GPU
if [ "$DETECTED_GPU" != "none" ]; then
    log_info "Configuring K3s for GPU..."
    
    # Enable nvidia-device-plugin
    kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml 2>/dev/null || true
fi

# Step 4: Deploy MAIA
log_step "Deploying MAIA..."

# Create namespace
kubectl create namespace maia --dry-run=client -o yaml | kubectl apply -f -

# Deploy via helm or kubectl
MAIA_VALUES=$(cat <<EOF
licenseKey: $LICENSE_KEY
sector: $SECTOR
gpu:
  model: $GPU_MODEL
  available: $([ "$DETECTED_GPU" != "none" ] && echo "true" || echo "false")
registry:
  url: $REGISTRY_URL
airGapped: $AIR_GAPPED
admin:
  email: $ADMIN_EMAIL
domain: $DOMAIN
EOF
)

# Apply MAIA deployment
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: maia
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: maia-config
  namespace: maia
data:
  sector: "$SECTOR"
  gpu-model: "$GPU_MODEL"
  license-key: "${LICENSE_KEY:0:4}****${LICENSE_KEY:-4}"
  air-gapped: "$AIR_GAPPED"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: maia-kernel
  namespace: maia
spec:
  replicas: 1
  selector:
    matchLabels:
      app: maia-kernel
  template:
    metadata:
      labels:
        app: maia-kernel
    spec:
      containers:
      - name: kernel
        image: maiaai/maia-kernel:latest
        ports:
        - containerPort: 8000
        env:
        - name: LICENSE_KEY
          value: "$LICENSE_KEY"
        - name: SECTOR
          value: "$SECTOR"
        - name: GPU_MODEL
          value: "$GPU_MODEL"
        - name: REGISTRY_URL
          value: "$REGISTRY_URL"
        resources:
          limits:
            nvidia.com/gpu: 1
          requests:
            cpu: "4"
            memory: 16Gi
---
apiVersion: v1
kind: Service
metadata:
  name: maia-service
  namespace: maia
spec:
  selector:
    app: maia-kernel
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
EOF

# Step 5: Wait for deployment
log_step "Waiting for MAIA to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/maia-kernel -n maia 2>/dev/null || true

# Step 6: Get status
log_step "Deployment complete!"

echo ""
log_info "MAIA is deployed!"
echo ""

# Get endpoints
INTERNAL_IP=$(hostname -I | awk '{print $1}')
LB_IP=$(kubectl get svc maia-service -n maia -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "$INTERNAL_IP")

echo "================================"
echo "Endpoints:"
echo "  API:        http://$LB_IP:8000"
echo "  Dashboard: http://$LB_IP:3033"
echo "  Health:    http://$LB_IP:8000/health"
echo ""

if [ "$DOMAIN" ]; then
    echo "Custom domain: https://$DOMAIN"
    echo ""
fi

echo "Installation complete!"
echo "License: ${LICENSE_KEY:0:4}****${LICENSE_KEY:-4}"
echo "Sector: $SECTOR"
echo "GPU: $GPU_MODEL"
echo ""

# Verify
log_info "Verifying deployment..."
if kubectl get pods -n maia | grep -q Running; then
    log_info "All pods running!"
    kubectl get pods -n maia
else
    log_warn "Some pods may still be starting..."
    kubectl get pods -n maia
fi