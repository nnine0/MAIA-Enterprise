"""
Configuration module for MAIA project.
Centralizes constants, URLs, and settings.
"""

import os
from typing import List

# Model and Inference
BASE_MODEL_ID = "Nanbeige/Nanbeige4-3B-Thinking-2511"
LORAX_URL = os.getenv("LORAX_URL", "http://lorax:80")
EMBEDDINGS_URL = os.getenv("EMBEDDINGS_URL", "http://embeddings:6000")
OCR_URL = os.getenv("OCR_URL", "http://ocr:5000")
QDRANT_URL = os.getenv("QDRANT_URL", "http://vector-db:6333")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# API Keys
MAIA_API_KEY = os.getenv("MAIA_API_KEY", "default-key")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Experts and Sectors
EXPERT_LIST: List[str] = [
    "real_estate_leasing", "manufacturing", "professional_services",
    "government", "health_care", "finance_insurance", "retail_trade",
    "wholesale_trade", "information", "general", "trivium"
]

# Training Configs
DEFAULT_ADAPTER_NAME = "adapter_math"
DEFAULT_DATASET_PATH = "gsm8k"
DEFAULT_EXPERT_DATA_PATH = "maiadeen_law.json"
DEFAULT_OVERSAMPLE_FACTOR = 20
DEFAULT_OUTPUT_DIR = "./council"

# LoRA Config
LORA_R = 32
LORA_ALPHA = 64
LORA_DROPOUT = 0.05

# Training Args
NUM_TRAIN_EPOCHS = 1
PER_DEVICE_TRAIN_BATCH_SIZE = 1
GRADIENT_ACCUMULATION_STEPS = 16
LEARNING_RATE = 2e-4

# Evaluation
EVALUATION_THRESHOLD = 7  # Average score threshold

# Paths
ADAPTERS_DIR = "/adapters"
DATA_LOGS_DIR = "/data_logs"
METADATA_FILE = "/adapters/adapter_metadata.json"

# Other
MAX_CONTEXT_LENGTH = 2000  # For summarization
PAD_TOKEN = "<|pad|>"  # Pad token for tokenizer