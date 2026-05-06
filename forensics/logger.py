"""
MAIA Forensics Logger
================
SR 26-02 compliant forensic logging.

Tracks:
- <|think|> block (reasoning trajectory)
- Tool ID executed
- Timestamp
- Policy violations intercepted
- Latent hash for forensic traceability
"""

import json
import sqlite3
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import os


class AuditLevel(Enum):
    TIER_1_CRITICAL = 1
    TIER_2_ELEVATED = 2
    TIER_3_BENIGN = 3


class ViolationType(Enum):
    PII_LEAK = "PII_LEAK"
    STRUCTURING = "STRUCTURING"
    OFAC_VIOLATION = "OFAC_VIOLATION"
    BIAS_PROXY = "BIAS_PROXY"
    UNAUTHORIZED_TOOL = "UNAUTHORIZED_TOOL"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    DHITL_REQUIRED = "DHITL_REQUIRED"
    NONE = "NONE"


@dataclass
class ForensicRecord:
    """Single forensic record for SR 26-02 compliance"""
    record_id: str
    timestamp: str
    query: str
    thinking_block: str
    tool_id: Optional[str]
    tool_intent_detected: bool
    policy_id: str
    tier: int
    violations_detected: List[str]
    violation_count: int
    latent_hash: str
    governance_passed: bool
    dhitl_required: bool
    response_denied: bool = False
    blocked_reason: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


class ForensicsLogger:
    """
    SR 26-02 compliant forensic logger.
    
    Stores:
    - Reasoning trajectory (<|think|> block)
    - Tool ID executed
    - Latent hash (forensic proof)
    - Policy violations intercepted
    """
    
    def __init__(self, db_path: str = "forensics/maia_audit.db"):
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()
    
    def _ensure_dir(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _init_db(self):
        """Initialize SQLite schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                record_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                query TEXT NOT NULL,
                thinking_block TEXT,
                tool_id TEXT,
                tool_intent_detected INTEGER,
                policy_id TEXT,
                tier INTEGER,
                violations_detected TEXT,
                violation_count INTEGER,
                latent_hash TEXT,
                governance_passed INTEGER,
                dhitl_required INTEGER,
                response_denied INTEGER DEFAULT 0,
                blocked_reason TEXT,
                session_id TEXT,
                user_id TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_logs(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_id ON audit_logs(tool_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_policy_id ON audit_logs(policy_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_latent_hash ON audit_logs(latent_hash)
        """)
        
        conn.commit()
        conn.close()
    
    def _generate_latent_hash(
        self,
        query: str,
        thinking_block: str,
        tool_id: Optional[str],
        violations: List[str]
    ) -> str:
        """Generate forensic latent hash"""
        data = f"{query}:{thinking_block}:{tool_id}:{','.join(sorted(violations))}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def log(
        self,
        query: str,
        thinking_block: str,
        tool_id: Optional[str],
        tool_intent_detected: bool,
        policy_id: str,
        tier: int,
        violations: List[str],
        governance_passed: bool,
        dhitl_required: bool = False,
        response_denied: bool = False,
        blocked_reason: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Log a forensic record.
        
        Returns the latent_hash for audit verification.
        """
        record_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Generate latent hash
        latent_hash = self._generate_latent_hash(
            query, thinking_block, tool_id, violations
        )
        
        # Convert violations list to JSON string
        violations_json = json.dumps(violations)
        
        # Truncate thinking block for storage (first 2000 chars)
        thinking_block_short = thinking_block[:2000] if thinking_block else ""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO audit_logs (
                record_id, timestamp, query, thinking_block, tool_id,
                tool_intent_detected, policy_id, tier, violations_detected,
                violation_count, latent_hash, governance_passed, dhitl_required,
                response_denied, blocked_reason, session_id, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record_id, timestamp, query, thinking_block_short, tool_id,
            1 if tool_intent_detected else 0, policy_id, tier, violations_json,
            len(violations), latent_hash, 1 if governance_passed else 0, 1 if dhitl_required else 0,
            1 if response_denied else 0, blocked_reason, session_id, user_id
        ))
        
        conn.commit()
        conn.close()
        
        return latent_hash
    
    def query_logs(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        tool_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Query audit logs with filters"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        if tool_id:
            query += " AND tool_id = ?"
            params.append(tool_id)
        
        if policy_id:
            query += " AND policy_id = ?"
            params.append(policy_id)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_violation_stats(self) -> Dict:
        """Get violation statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                SUM(violation_count) as total_violations,
                SUM(CASE WHEN violation_count > 0 THEN 1 ELSE 0 END) as records_with_violations,
                SUM(CASE WHEN response_denied = 1 THEN 1 ELSE 0 END) as denied_responses,
                SUM(CASE WHEN tier = 1 THEN 1 ELSE 0 END) as tier1_critical,
                SUM(CASE WHEN tier = 2 THEN 1 ELSE 0 END) as tier2_elevated,
                SUM(CASE WHEN tier = 3 THEN 1 ELSE 0 END) as tier3_benign
            FROM audit_logs
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            "total_records": row[0] or 0,
            "total_violations": row[1] or 0,
            "records_with_violations": row[2] or 0,
            "denied_responses": row[3] or 0,
            "tier1_critical": row[4] or 0,
            "tier2_elevated": row[5] or 0,
            "tier3_benign": row[6] or 0
        }
    
    def export_parquet(self, output_path: str) -> str:
        """Export logs to Parquet format for audit"""
        try:
            import pandas as pd
            
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query("SELECT * FROM audit_logs ORDER BY timestamp", conn)
            conn.close()
            
            df.to_parquet(output_path, index=False)
            return output_path
        except ImportError:
            # Fallback to JSON
            return self.export_json(output_path.replace('.parquet', '.json'))
    
    def export_json(self, output_path: str = "forensics/audit_export.json") -> str:
        """Export logs to JSON for auditor"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp")
        rows = cursor.fetchall()
        conn.close()
        
        records = [dict(row) for row in rows]
        
        with open(output_path, 'w') as f:
            json.dump(records, f, indent=2)
        
        return output_path


# Global logger instance
_logger: Optional[ForensicsLogger] = None


def get_logger(db_path: str = "forensics/maia_audit.db") -> ForensicsLogger:
    """Get global forensics logger"""
    global _logger
    if _logger is None:
        _logger = ForensicsLogger(db_path)
    return _logger


if __name__ == "__main__":
    # Demo logging
    logger = get_logger()
    
    print("=== MAIA Forensics Logger ===\n")
    
    # Log some test records
    test_cases = [
        {
            "query": "Transfer $75k to Russia",
            "thinking_block": "I need to process this wire. [CALL_TOOL:FINANCIAL_WIRE_V1]",
            "tool_id": "FINANCIAL_WIRE_V1",
            "tool_intent_detected": True,
            "policy_id": "sr_26_02_banking",
            "tier": 1,
            "violations": ["OFAC_VIOLATION"],
            "governance_passed": False,
            "dhitl_required": True,
            "response_denied": True,
            "blocked_reason": "OFAC sanctions hit"
        },
        {
            "query": "Send email with SSN",
            "thinking_block": "Sending email with client details. [CALL_TOOL:GOVERNED_SMTP_V1]",
            "tool_id": "GOVERNED_SMTP_V1",
            "tool_intent_detected": True,
            "policy_id": "pii_redaction",
            "tier": 1,
            "violations": ["PII_LEAK"],
            "governance_passed": False,
            "dhitl_required": True,
            "response_denied": True,
            "blocked_reason": "PII pattern detected"
        },
        {
            "query": "Query sales data",
            "thinking_block": "Running analytics query. [CALL_TOOL:SQL_AUDITOR_V1]",
            "tool_id": "SQL_AUDITOR_V1",
            "tool_intent_detected": True,
            "policy_id": "readonly_sql",
            "tier": 2,
            "violations": [],
            "governance_passed": True,
            "dhitl_required": False,
            "response_denied": False
        }
    ]
    
    for tc in test_cases:
        latent_hash = logger.log(**tc)
        print(f"Logged: {tc['query'][:30]}...")
        print(f"  Latent Hash: {latent_hash}")
        print()
    
    # Show stats
    stats = logger.get_violation_stats()
    print("=== Violation Statistics ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")