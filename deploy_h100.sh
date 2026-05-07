#!/bin/bash
# MAIA H100 Neural Refinery - Deployment Script
# ==========================================
# Deploys the production stack on H100 GPU node
#
# Usage: ./deploy_h100.sh [start|stop|status|logs|clean]
#
# Requires: NVIDIA H100 (80GB), docker-compose, nvidia-docker2

set -e

COMPOSE_FILE="docker-compose.h100.yml"
IMAGE_NAME="maia-enterprise"
NETWORK="maia-internal"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_gpu() {
    log_info "Checking NVIDIA H100..."
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    else
        log_error "nvidia-smi not found. Install NVIDIA drivers."
        exit 1
    fi
}

check_docker() {
    log_info "Checking Docker..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found."
        exit 1
    fi
    if ! docker compose version &> /dev/null; then
        log_error "docker-compose not found."
        exit 1
    fi
}

start() {
    log_info "Starting MAIA H100 Neural Refinery..."
    
    check_gpu
    check_docker
    
    # Create necessary directories
    mkdir -p logs/{lorax,airlock,gateway,kafka,redis,dashboard}
    mkdir -p adapters
    mkdir -p configs/materiality
    mkdir -p certs
    
    # Load environment
    if [ -f .env ]; then
        log_info "Loading environment from .env"
        source .env
    else
        log_warn "No .env found, using defaults"
    fi
    
    # Pull base images
    log_info "Pulling base images..."
    docker pull ghcr.io/predibase/lorax:latest || true
    docker pull confluentinc/cp-kafka:7.5.0 || true
    docker pull redis:7-alpine || true
    
    # Build custom images
    log_info "Building custom images..."
    docker compose -f $COMPOSE_FILE build
    
    # Start stack
    log_info "Starting services..."
    docker compose -f $COMPOSE_FILE up -d
    
    # Wait for healthy
    sleep 10
    
    log_info "Waiting for services to be healthy..."
    for service in lorax-kernel pvi-airlock maia-gateway kafka redis; do
        local status=$(docker compose -f $COMPOSE_FILE ps $service --format "{{.Health}}" 2>/dev/null || echo "starting")
        echo "  $service: $status"
    done
    
    log_info "Deployment complete!"
    echo ""
    echo "Services:"
    echo "  Gateway:   https://localhost (port 443)"
    echo "  LoRAX:     http://localhost:8080"
    echo "  Dashboard: http://localhost:3034"
    echo "  Kafka:     localhost:9092"
    echo "  Redis:     localhost:6379"
    echo ""
    echo "Test: curl -k https://localhost/api/v1/vetted-action \\"
    echo '  -H "X-MAIA-Key: your_key_here" \\'
    echo '  -H "Content-Type: application/json" \\'
    echo '  -d '"'"'{"context":{"sector":"finance","role":"loan_officer","materiality_target":"tier_2"},"instruction":"test"}'"'"''
}

stop() {
    log_info "Stopping MAIA H100 Neural Refinery..."
    docker compose -f $COMPOSE_FILE down
    log_info "Stopped."
}

status() {
    log_info "Service Status:"
    docker compose -f $COMPOSE_FILE ps
}

logs() {
    SERVICE=${1:-}
    if [ -n "$SERVICE" ]; then
        docker compose -f $COMPOSE_FILE logs -f $SERVICE
    else
        docker compose -f $COMPOSE_FILE logs -f
    fi
}

clean() {
    log_warn "Cleaning up..."
    docker compose -f $COMPOSE_FILE down -v --remove-orphans
    docker system prune -f
    log_info "Cleaned."
}

case "${1:-start}" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    logs) logs "${2:-}" ;;
    clean) clean ;;
    *) echo "Usage: $0 {start|stop|status|logs|clean}"; exit 1 ;;
esac