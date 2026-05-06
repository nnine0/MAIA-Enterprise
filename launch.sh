#!/bin/bash
# MAIA Kernel Launch Script
# ======================
# Launch the MAIA Speculative Governance Stack with vLLM

set -e

# Configuration
TARGET_MODEL="${TARGET_MODEL:-ibm-granite/granite-4.1-3b}"
DRAFTER_MODEL="${DRAFTER_MODEL:-HuggingFaceTB/nanowhale-100m}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-ibm-granite/granite-embedding-97m}"

NUM_SPECULATIVE="${NUM_SPECULATIVE:-5}"
MAX_LORAS="${MAX_LORAS:-20}"
MAX_LORA_RANK="${MAX_LORA_RANK:-64}"
GPU_UTIL="${GPU_UTIL:-0.90}"
MAX_CONTEXT="${MAX_CONTEXT:-8192}"

echo "=========================================="
echo "  MAIA Kernel Launch"
echo "=========================================="
echo "  Target Model:  $TARGET_MODEL"
echo "  Drafter Model:  $DRAFTER_MODEL" 
echo "  Embedding:      $EMBEDDING_MODEL"
echo "  VRAM:          $(echo "$GPU_UTIL * 100" | bc)%"
echo "  Max LoRAs:     $MAX_LORAS"
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
echo "Test routing:"
echo '  curl -X POST http://localhost:8000/v1/chat/completions \'
echo '    -H "Authorization: Bearer MAIA_LOCAL" \'
echo '    -d "{"
echo '      "model": "ibm-granite/granite-4.1-3b",'
echo '      "messages": [{"role": "user", "content": "Submit bid at 2%"}],'
echo '      "extra_body": {"lora_name": "finance_insurance_adapter"}'
echo '    }"'