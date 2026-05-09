#!/bin/bash
# MAIA Enterprise - Appliance Deployment
# Run: ./deploy.sh [--rebuild]

set -e

echo "========================================="
echo "MAIA Enterprise - Compliance Appliance"
echo "========================================="

# Check environment
if [ ! -f .env ]; then
    echo "[1/5] Creating .env from template..."
    cp .env.example .env
    echo "Please edit .env and set MAIA_API_KEY"
    exit 1
fi

# Validate MAIA_API_KEY is set
source .env
if [ -z "$MAIA_API_KEY" ]; then
    echo "ERROR: MAIA_API_KEY not set in .env"
    exit 1
fi

# Build images if requested
if [ "$1" = "--rebuild" ]; then
    echo "[2/5] Building container images..."
    docker compose build
fi

# Start services
echo "[3/5] Starting services..."
docker compose up -d

# Wait for health
echo "[4/5] Waiting for services..."
sleep 10

# Check status
echo "[5/5] Checking services..."
docker compose ps

echo ""
echo "========================================="
echo "MAIA Enterprise - Running"
echo "========================================="
echo "Dashboard:   http://localhost:3033"
echo "API:        http://localhost:8000"
echo "LoRAX:      http://localhost:8080"
echo "Qdrant:     http://localhost:6333"
echo "Redis:      localhost:6379"
echo ""
echo "To stop:   docker compose down"
echo "To logs:    docker compose logs -f"
echo "To update: ./deploy.sh --rebuild"