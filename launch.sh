#!/bin/bash
# MAIA Kernel Launch Script - Gemma 4 Version
# ============================================
# Launch the MAIA Speculative Governance Stack with vLLM

set -e

# Configuration - Gemma 4 E4B
TARGET_MODEL="${TARGET_MODEL:-google/gemma-4-E4B-it}"
DRAFTER_MODEL="${DRAFTER_MODEL:-google/gemma-4-E4B-it-assistant}"

NUM_SPECULATIVE="${NUM_SPECULATIVE:-16}"
MAX_LORAS="${MAX_LORAS:-10}"
MAX_LORA_RANK="${MAX_LORA_RANK:-64}"
GPU_UTIL="${GPU_UTIL:-0.95}"
MAX_CONTEXT="${MAX_CONTEXT:-32768}"

echo "=========================================="
echo "  MAIA Kernel Launch (Gemma 4)"
echo "=========================================="
echo "  Target Model:  $TARGET_MODEL"
echo "  Drafter Model: $DRAFTER_MODEL"
echo "  VRAM:         $(echo "$GPU_UTIL * 100" | bc)%"
echo "  Max LoRAs:    $MAX_LORAS"
echo "  Thinking:    Enabled"
echo "=========================================="
echo ""

# Check for vLLM
if ! command -v vllm &> /dev/null; then
    echo "ERROR: vLLM not installed. Install with:"
    echo "  pip install vllm"
    exit 1
fi

# Launch command
echo "Launching MAIA Kernel..."
echo ""

vllm serve "$TARGET_MODEL" \
    --speculative-model "$DRAFTER_MODEL" \
    --num-speculative-tokens "$NUM_SPECULATIVE" \
    --enable-thinking \
    --enable-lora \
    --max-loras "$MAX_LORAS" \
    --max-lora-rank "$MAX_LORA_RANK" \
    --gpu-memory-utilization "$GPU_UTIL" \
    --max-model-len "$MAX_CONTEXT" \
    --trust-remote-code \
    --host 0.0.0.0 \
    --port 8000

echo ""
echo "MAIA Kernel running at http://localhost:8000"
echo ""
echo "Testing with thinking prompt:"
echo '  curl -X POST http://localhost:8000/v1/chat/completions \'
echo '    -H "Authorization: Bearer MAIA" \'
echo '    -d "{\"model\": \"google/gemma-4-E4B-it\",'
echo '       \"messages\": [{\"role\": \"user\", \"content\": \"...\"}]}"'