"""
MAIA Configuration Settings
"""

# API Settings
API_HOST = "0.0.0.0"
API_PORT = 8000
DASHBOARD_PORT = 3033

# LoRAX Settings  
LORAX_URL = "http://127.0.0.1:8080"
BASE_MODEL_ID = "google/gemma-4-26b-a4b-moe"

# Memory Settings (VRAM in MB)
VRAM_TOTAL_MB = 24576
MAX_RAM_ADAPTERS = 100

# PVI Airlock Settings
DEFAULT_AUDITOR = "citi/pvi-airlock-sr2602"

# SME Pool Settings
SME_VOTES_REQUIRED = 3

# File Paths
DATA_LOGS_DIR = "/tmp/maia_logs"
METADATA_FILE = "/tmp/adapter_metadata.json"

# Domain to adapter mapping
DOMAIN_ADAPTERS = {
    "finance": {
        "actor": "citi/finance-expert-v4",
        "auditor": "citi/pvi-airlock-sr2602"
    },
    "credit": {
        "actor": "citi/credit-expert-v4", 
        "auditor": "citi/pvi-airlock-sr2602"
    },
    "compliance": {
        "actor": "citi/compliance-expert-v4",
        "auditor": "citi/pvi-airlock-sr2602"
    },
    "fraud": {
        "actor": "citi/fraud-aml-expert-v4",
        "auditor": "citi/pvi-airlock-sr2602"
    },
    "logistics": {
        "actor": "logistics/terminal-expert-v4",
        "auditor": "logistics/safety-auditor-v4"
    }
}

# Materiality Keywords
CRITICAL_KEYWORDS = {
    "credit", "wire", "transfer", "contract", "legal", "loan",
    "mortgage", "sanction", "compliance", "fraud", "aml", "kyc",
    "collateral", "escrow", "settlement", "derivative", "exposure"
}

ELEVATED_KEYWORDS = {
    "risk", "limit", "approval", "policy", "audit", "report",
    "client", "account", "exposure", "margin", "guarantee"
}