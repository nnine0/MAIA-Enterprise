#!/bin/bash
# MAIA-Enterprise Quad-Node Deployment Script
# ================================
# Launches four isolated vLLM instances, one per department.
# Each node has physical process isolation for auditability.
# Uses Gemma 4 E4B with speculative decoding.
#
# Usage: ./deploy_quad_node.sh [start|stop|status|restart]
#
# VRAM Allocation (24GB total):
#   Node 1-4: 5.4 GB each (23% GPU utilization)
#   System: 2.2 GB for KV cache / buffers
#   TOTAL: 24.2 GB

set -e

# Configuration
export BASE_MODEL=${BASE_MODEL:-"google/gemma-4-2b-it"}
export DRAFTER_MODEL=${DRAFTER_MODEL:-"google/gemma-4-2b-it"}
export GPU_MEMORY_UTIL=${GPU_MEMORY_UTIL:-0.23}
export MAX_MODEL_LEN=${MAX_MODEL_LEN:-32768}
export TENSOR_PARALLEL_SIZE=${TENSOR_PARALLEL_SIZE:-1}
export ENFORCE_EAGER=${ENFORCE_EAGER:-1}

# Node ports
PORT_ESTIMATING=8001
PORT_LEGAL=8002
PORT_SAFETY=8003
PORT_LOGISTICS=8004

# LoRA module paths (relative to this script)
LORA_DIR=${MAIA_LORA_DIR:-"/maia/loras"}
ADAPTER_DIR=${MAIA_ADAPTER_DIR:-"adapters"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

check_vllm() {
    command -v vllm &> /dev/null || { log_error "vllm not found. Install: pip install vllm"; exit 1; }
}

check_model() {
    if [ ! -d "$ADAPTER_DIR" ]; then
        log_error "Adapter directory not found: $ADAPTER_DIR"
        log_error "Run from project root or set MAIA_ADAPTER_DIR"
        exit 1
    fi
}

start_node() {
    local node_name=$1
    local port=$2
    local lora_module=$3
    local lora_path=$4

    log_info "Starting $node_name node on port $port..."

    # Build vllm command
    local cmd="vllm serve $BASE_MODEL"
    cmd+=" --port $port"
    cmd+=" --speculative-model $DRAFTER_MODEL"
    cmd+=" --enable-lora"

    if [ -n "$lora_module" ] && [ -n "$lora_path" ]; then
        cmd+=" --lora-modules $lora_module=$lora_path"
    fi

    cmd+=" --gpu-memory-utilization $GPU_MEMORY_UTIL"
    cmd+=" --max-model-len $MAX_MODEL_LEN"
    cmd+=" --tensor-parallel-size $TENSOR_PARALLEL_SIZE"
    cmd+=" --enforce-eager $ENFORCE_EAGER"

    # Add node name to process list for management
    local pidfile="/tmp/maia_${node_name}.pid"

    # Start in background
    eval $cmd &
    echo $! > "$pidfile"

    # Wait for health check
    local max_wait=30
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -s "http://localhost:$port/health" &> /dev/null 2>&1; then
            log_info "$node_name node ready on port $port"
            return 0
        fi
        sleep 1
        ((waited++))
    done

    log_warn "$node_name node started but health check pending (port $port)"
    return 1
}

stop_node() {
    local node_name=$1
    local pidfile="/tmp/maia_${node_name}.pid"

    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping $node_name node (PID $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 2
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$pidfile"
    fi
}

status_node() {
    local node_name=$1
    local port=$2
    local pidfile="/tmp/maia_${node_name}.pid"

    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "  ${GREEN}●${NC} $node_name (PID $pid) - Port $port"
        else
            echo -e "  ${RED}○${NC} $node_name (stale PID $pid)"
        fi
    else
        echo -e "  ${RED}○${NC} $node_name (not running)"
    fi
}

case "${1:-start}" in
    start)
        check_vllm
        check_model

        log_info "Starting MAIA Quad-Node Cluster..."
        log_info "Base model: $BASE_MODEL"
        log_info "VRAM per node: $(echo "$GPU_MEMORY_UTIL * 24" | bc)GB"

        # Node 1: Estimating (Financial Guardrails)
        start_node "estimating" $PORT_ESTIMATING "estimating_lora" \
            "$ADAPTER_DIR/estimating_lora"

        # Node 2: Legal/FAR
        start_node "legal" $PORT_LEGAL "legal_lora" \
            "$ADAPTER_DIR/legal_lora"

        # Node 3: Site Safety (OSHA)
        start_node "safety" $PORT_SAFETY "safety_lora" \
            "$ADAPTER_DIR/safety_lora"

        # Node 4: Logistics
        start_node "logistics" $PORT_LOGISTICS "logistics_lora" \
            "$ADAPTER_DIR/logistics_lora"

        log_info "Quad-Node cluster started successfully"
        echo ""
        echo "Endpoints:"
        echo "  Estimating: http://localhost:$PORT_ESTIMATING"
        echo "  Legal:    http://localhost:$PORT_LEGAL"
        echo "  Safety:  http://localhost:$PORT_SAFETY"
        echo "  Logistics: http://localhost:$PORT_LOGISTICS"
        echo ""
        echo "Health checks:"
        echo "  curl http://localhost:$PORT_ESTIMATING/health"
        ;;

    stop)
        log_info "Stopping MAIA Quad-Node Cluster..."
        stop_node "estimating"
        stop_node "legal"
        stop_node "safety"
        stop_node "logistics"
        log_info "All nodes stopped"
        ;;

    restart)
        $0 stop
        sleep 2
        $0 start
        ;;

    status)
        echo "MAIA Quad-Node Status:"
        status_node "estimating" $PORT_ESTIMATING
        status_node "legal" $PORT_LEGAL
        status_node "safety" $PORT_SAFETY
        status_node "logistics" $PORT_LOGISTICS
        ;;

    logs)
        node_name=${2:-estimating}
        pidfile="/tmp/maia_${node_name}.pid"
        if [ -f "$pidfile" ]; then
            tail -f "/proc/$(cat $pidfile)/fd/1"
        else
            log_error "Node $node_name not running"
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|status|restart|logs [node]}"
        echo ""
        echo "Commands:"
        echo "  start   - Start all four nodes"
        echo "  stop   - Stop all nodes"
        echo "  status - Show node status"
        echo "  restart - Restart cluster"
        echo "  logs   - Tail logs for a node (default: estimating)"
        exit 1
        ;;
esac