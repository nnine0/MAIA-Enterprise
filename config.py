"""
MAIA Configuration Settings
==========================
Central configuration for Circuit Breaker governance system.
"""

import os
from dotenv import load_dotenv
load_dotenv()

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "3033"))

LORAX_URL = os.getenv("LORAX_URL", "http://127.0.0.1:8080")
LORAX_API_KEY = os.getenv("LORAX_API_KEY", "not-needed")  # Local inference - typically not required

# Base model - uses LoRAX API which handles chat templates automatically
# No manual prompt templates needed - the API applies model-specific templates
# To change: update this and redeploy the lorax service
BASE_MODEL_ID = os.getenv("BASE_MODEL_ID", "google/gemma-4-26b-a4b-it")

MAIA_API_KEY = os.getenv("MAIA_API_KEY")
if MAIA_API_KEY is None:
    raise ValueError("MAIA_API_KEY environment variable must be set. Copy .env.example to .env and configure.")

# Validate key format (minimum entropy check)
if len(MAIA_API_KEY) < 16:
    raise ValueError("MAIA_API_KEY must be at least 16 characters for adequate entropy")
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

VRAM_TOTAL_MB = int(os.getenv("VRAM_TOTAL_MB", "24576"))
MAX_RAM_ADAPTERS = int(os.getenv("MAX_RAM_ADAPTERS", "100"))

DEFAULT_AUDITOR = os.getenv("DEFAULT_AUDITOR", "pvi_airlock_sr2602")
SME_VOTES_REQUIRED = int(os.getenv("SME_VOTES_REQUIRED", "3"))

DATA_LOGS_DIR = os.getenv("DATA_LOGS_DIR", "/tmp/maia_logs")
METADATA_FILE = os.getenv("METADATA_FILE", "/tmp/adapter_metadata.json")

MAX_CONTEXT_LENGTH = int(os.getenv("MAX_CONTEXT_LENGTH", "32768"))

EXPERT_LIST = [
    "real_estate_leasing", "manufacturing", "professional_services",
    "government", "health_care", "finance_insurance", "retail_trade",
    "wholesale_trade", "information", "general", "trivium"
]

EMBEDDINGS_URL = os.getenv("EMBEDDINGS_URL", "http://127.0.0.1:6000")

# Adapter registry is the single source of truth for all adapter paths.
# See app/core/adapter_loader.py and adapters/registry.json
# DOMAIN_ADAPTERS has been removed — use the registry instead:

CRITICAL_KEYWORDS = {
    "credit", "wire", "transfer", "contract", "legal", "loan",
    "mortgage", "sanction", "compliance", "fraud", "aml", "kyc",
    "collateral", "escrow", "settlement", "derivative", "exposure"
}

ELEVATED_KEYWORDS = {
    "risk", "limit", "approval", "policy", "audit", "report",
    "client", "account", "exposure", "margin", "guarantee"
}

DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.4"))
ROUTING_TEMPERATURE = float(os.getenv("ROUTING_TEMPERATURE", "0.1"))
VALIDATION_TEMPERATURE = float(os.getenv("VALIDATION_TEMPERATURE", "0.1"))

ADAPTER_TEMPERATURES = {
    "default": 0.4,
    "creative": 0.7,
    "precise": 0.1,
    "routing": 0.1,
}

# Gemma 4 sampling best practices
TARGET_TEMPERATURE = 1.0
TARGET_TOP_P = 0.95
TARGET_TOP_K = 64

MODEL_CAPABILITIES = {
    "context_window": 256000,
    "supported_modalities": ["text", "image"],
    "thinking_mode": True,
    "function_calling": True,
    "multilingual": True,
    "languages": 140,
}