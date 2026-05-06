#!/bin/bash
# MAIA Enterprise Quad-Node Deployment
# ======================================
# Slices 24GB GPU into 4 isolated governance nodes.
#
# Hardware Efficiency:
#   Total VRAM: 24GB
#   Per Node: 5.4GB (23% = 0.23)
#   System: 2.2GB KV cache
#   Total: 24.2GB (leaves buffer)
#
# Economic Case for Mid-Market:
#   1 GPU = 4 compliance domains
#   No dedicated hardware per department

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
GPU_MEMORY_UTIL=${GPU_MEMORY_UTIL:-0.23}
NODES=("estimating" "legal" "safety" "logistics")
PORTS=(8001 8002 8003 8004)

# Functions
usage() {
    echo "Usage: $0 {start|stop|status|logs|restart}"
    echo ""
    echo "Commands:"
    echo "  start   - Start quad-node cluster"
    echo "  stop   - Stop all nodes"
    echo "  status - Show node status"
    echo "  logs   - Tail logs for node"
    echo "  restart - Restart cluster"
}

start_nodes() {
    log_info "Starting MAIA Quad-Node Cluster..."
    
    # Docker Compose deployment
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d
        log_info "Nodes started via docker-compose"
    else
        # Manual process start
        for i in "${!NODES[@]}"; do
            node=${NODES[$i]}
            port=${PORTS[$i]}
            
            log_info "Starting $node node on port $port..."
            
            NODE_ID=$node NODE_PORT=$port GPU_MEMORY_UTIL=$GPU_MEMORY_UTIL \
                python3 server.py &
            
            echo $! > /tmp/maia_${node}.pid
        done
        
        log_info "All nodes started"
    fi
    
    echo ""
    echo "Endpoints:"
    echo "  Estimating: http://localhost:8001"
    echo "  Legal:     http://localhost:8002"
    echo "  Safety:   http://localhost:8003"
    echo "  Logistics: http://localhost:8004"
    echo ""
    echo "Dashboard: http://localhost:3033"
}

stop_nodes() {
    log_info "Stopping MAIA Quad-Node Cluster..."
    
    if command -v docker-compose &> /dev/null; then
        docker-compose down
    else
        for node in "${NODES[@]}"; do
            pidfile="/tmp/maia_${node}.pid"
            if [ -f "$pidfile" ]; then
                kill $(cat "$pidfile") 2>/dev/null || true
                rm -f "$pidfile"
            fi
        done
    fi
    
    log_info "All nodes stopped"
}

node_status() {
    echo "MAIA Quad-Node Status:"
    echo ""
    
    for i in "${!NODES[@]}"; do
        node=${NODES[$i]}
        port=${PORTS[$i]}
        
        if curl -s "http://localhost:$port/health" &> /dev/null; then
            echo -e "  ${GREEN}●${NC} $node (port $port)"
        else
            echo -e "  ${RED}○${NC} $node (port $port)"
        fi
    done
}

show_logs() {
    node=${1:-estimating}
    tail -f logs/maia_${node}.log 2>/dev/null || \
        echo "No logs found for $node"
}

case "${1:-start}" in
    start)
        start_nodes
        ;;
    stop)
        stop_nodes
        ;;
    status)
        node_status
        ;;
    logs)
        show_logs "$2"
        ;;
    restart)
        stop_nodes
        sleep 2
        start_nodes
        ;;
    *)
        usage
        exit 1
        ;;
esac