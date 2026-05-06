"""
MAIA Dynamic Materiality Escalation (DME) Engine
================================================
Layer 9 Management Plane for recursive escalation and tool-as-adapters.

Layer Hierarchy:
- L1: Sector-Adapter - Sets global "Red Lines" (SR 26-02, HIPAA)
- L2: Role-Adapter - Determines "Permissions" (can propose $50M loan?)
- L3: Functional-Tool-Adapter - Specific capability (Email, SQL, Swift)
- L4: DME Logic - The Escalator. Analyzes semantic intent.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set


class MaterialityTier(Enum):
    """Risk tier levels"""
    TIER_1_CRITICAL = 1  # High-value, regulatory, requires DHITL
    TIER_2_ELEVATED = 2   # Medium-value, requires AI audit
    TIER_3_BENIGN = 3     # Low-value, auto-approved


class EscalationReason(Enum):
    """Why escalation occurred"""
    SECTOR_CHANGE = "sector_change"
    OCCUPATION_CHANGE = "occupation_change"
    KEYWORD_DETECTED = "keyword_detected"
    PII_DETECTED = "pii_detected"
    HIGH_VALUE_DETECTED = "high_value_detected"
    REGULATORY_KEYWORD = "regulatory_keyword"


@dataclass
class LayerState:
    """State of each escalation layer"""
    layer: str  # L1, L2, L3, L4
    sector: str = ""
    occupation: str = ""
    tool: str = ""
    context_flags: List[str] = field(default_factory=list)
    tier: MaterialityTier = MaterialityTier.TIER_3_BENIGN
    
    @property
    def is_escalated(self) -> bool:
        return self.tier != MaterialityTier.TIER_3_BENIGN


@dataclass
class EscalationEvent:
    """Record of an escalation trigger"""
    timestamp: str
    from_tier: MaterialityTier
    to_tier: MaterialityTier
    reason: EscalationReason
    keyword: str
    layer: str


class SectorAdapter:
    """
    L1: Sector Adapter
    
    Sets global "Red Lines" - sector-specific regulatory boundaries.
    """
    
    RED_LINES: Dict[str, Dict] = {
        "finance_insurance": {
            "regulations": ["SR 26-02", "Basel III", "AML"],
            "critical_keywords": ["wire", "transfer", "sanction", "loan", "$"],
            "red_line": "No wire transfers over $10K without DHITL"
        },
        "government_public": {
            "regulations": ["FOIA", "FISMA", "CRA"],
            "critical_keywords": ["contract", "grant", "permit", "subvention"],
            "red_line": "No regulatory filings without compliance review"
        },
        "biotech_pharma": {
            "regulations": ["HIPAA", "FDA 21 CFR", "GCP"],
            "critical_keywords": ["clinical", "patient", "drug", "trial"],
            "red_line": "No clinical data without QA approval"
        },
        "real_estate": {
            "regulations": ["RESPA", "RECRA"],
            "critical_keywords": ["lease", "title", "closing", "escrow"],
            "red_line": "No transactions without title verification"
        },
        "information_tech": {
            "regulations": ["SOC 2", "GDPR", "PCI-DSS"],
            "critical_keywords": ["password", "access", "root", "admin"],
            "red_line": "No credential changes without security review"
        },
        "professional_services": {
            "regulations": ["ABA", "AICPA"],
            "critical_keywords": ["attorney", "client", "privilege"],
            "red_line": "No legal communications without counsel review"
        }
    }
    
    @classmethod
    def get_red_lines(cls, sector: str) -> Dict:
        return cls.RED_LINES.get(sector, {
            "regulations": [],
            "critical_keywords": [],
            "red_line": "Standard policy applies"
        })
    
    @classmethod
    def detect_sector(cls, query: str) -> str:
        """Detect GDP sector from query"""
        query_lower = query.lower()
        
        sector_keywords = {
            "finance_insurance": ["bank", "loan", "credit", "wire", "transfer", "insurance", "claim"],
            "government_public": ["government", "public", "grant", "compliance", "permit"],
            "biotech_pharma": ["clinical", "drug", "patient", "trial", "pharma"],
            "real_estate": ["property", "lease", "tenant", "mortgage", "title"],
            "information_tech": ["api", "database", "server", "password", "access"],
            "professional_services": ["legal", "contract", "proposal", "consulting"]
        }
        
        for sector, keywords in sector_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return sector
        
        return "general"


class RoleAdapter:
    """
    L2: Role Adapter
    
    Determines permissions based on occupation/role.
    """
    
    ROLE_PERMISSIONS: Dict[str, Dict] = {
        "financial_analyst": {
            "can_propose_loan": True,
            "max_loan_amount": 1000000,
            "requires_stress_test": True,
            "must_escalate_above": 500000
        },
        "loan_officer": {
            "can_propose_loan": True,
            "max_loan_amount": 5000000,
            "requires_stress_test": True,
            "must_escalate_above": 1000000
        },
        "compliance_officer": {
            "can_approve_compliance": True,
            "can_block_transactions": True,
            "requires_dhitl": True
        },
        "it_security": {
            "can_access_systems": True,
            "can_grant_access": True,
            "requires_approval_for": ["root", "admin"]
        },
        "attorney": {
            "can_review_contracts": True,
            "can_sign_legal": True,
            "attorney_client_privilege": True
        }
    }
    
    @classmethod
    def get_permissions(cls, occupation: str) -> Dict:
        return cls.ROLE_PERMISSIONS.get(occupation, {
            "can_propose_loan": False,
            "max_loan_amount": 0,
            "requires_stress_test": False,
            "must_escalate_above": 0
        })
    
    @classmethod
    def detect_occupation(cls, query: str, sector: str) -> str:
        """Detect occupation from query"""
        query_lower = query.lower()
        
        occupation_keywords = {
            "finance_insurance": {
                "financial_analyst": ["analysis", "valuation", "model"],
                "loan_officer": ["loan", "mortgage", "prequalify"],
                "underwriter": ["underwrite", "risk assessment"]
            },
            "government_public": {
                "compliance_officer": ["compliance", "audit", "regulatory"],
                "policy_analyst": ["policy", "impact"]
            },
            "biotech_pharma": {
                "clinical_researcher": ["clinical", "trial", "study"],
                "qa_specialist": ["quality", "batch", "validation"]
            },
            "information_tech": {
                "developer": ["code", "deploy", "build"],
                "security_analyst": ["security", "vulnerability", "incident"]
            },
            "professional_services": {
                "attorney": ["legal", "contract", "litigation"],
                "consultant": ["recommendation", "proposal"]
            }
        }
        
        sector_occupations = occupation_keywords.get(sector, {})
        for occ, keywords in sector_occupations.items():
            if any(kw in query_lower for kw in keywords):
                return occ
        
        return "general_role"


class ToolAdapter:
    """
    L3: Functional Tool Adapter
    
    Treats tools as specialized LoRA adapters.
    The tool itself becomes a constrained weight-set - physically cannot reason outside boundaries.
    
    MAIA Innovation: "Neural Permissioning" replaces "Prompt Engineering"
    """
    
    # Map tools to their constrained capabilities
    TOOL_CAPABILITIES: Dict[str, Dict] = {
        # =================================================================
        # 1. LEDGER-AUDIT SQL ADAPTER (Finance/Accounting)
        # =================================================================
        # "Read-Only/Append-Only" weight-set
        # The weights are trained ONLY on SELECT and INSERT - model "forgets" DELETE/DROP
        "sql_ledger": {
            "adapter_id": "finance/ledger-audit-v4",
            "allowed_actions": ["SELECT", "INSERT", "SHOW", "DESCRIBE"],
            "blocked_actions": ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "UPDATE", "GRANT", "REVOKE"],
            "requires_audit_trail": True,
            "max_rows": 1000,
            "sensitive_fields": ["ssn", "routing_number", "balance", "account_number"],
            "auto_escalate_on": ["balance > 1000000", "ssn", "routing_number"],
            "red_line": "Only SELECT/INSERT - physically cannot DELETE"
        },
        
        # =================================================================
        # 2. SWIFT/FEDWIRE TRANSACTION ADAPTER (Banking)
        # =================================================================
        # Tier 1 "Money Hand" - generates MT103/Fedwire ISO 20022
        "swift_adapter": {
            "adapter_id": "finance/swift-wire-v4",
            "allowed_actions": ["MT103", "ISO20022", "wire_initiation"],
            "message_format": "MT103",
            "requires_dual_approval": True,
            "max_amount": 10000,  # Auto-escalate above
            "blocked_countries": ["Russia", "Iran", "North Korea", "Cuba", "Syria"],
            "requires_routing_verification": True,
            "red_line": "No transfers > $10K without DHITL"
        },
        
        # =================================================================
        # 3. CONTRACT-REDLINE ADAPTER (Legal/Real Estate/Pharma)
        # =================================================================
        # Reviews/edits DOCX/PDF - identifies Force Majeure, Indemnification, Liability Caps
        "contract_redline": {
            "adapter_id": "legal/contract-redline-v4",
            "allowed_actions": ["review", "redline", "annotate", "identify_clause"],
            "blocked_actions": ["delete_indemnification", "remove_liability", "waive_protection"],
            "critical_clauses": ["Force Majeure", "Indemnification", "Liability Cap", "Indemnity"],
            "core_protection_violations": ["delete_limitation", "remove_indemnification"],
            "requires_partner_approval_for": ["Indemnification", "Liability Cap"],
            "red_line": "Cannot delete Core Protection clauses"
        },
        
        # =================================================================
        # 4. LOGISTICS-KAFKA DISPATCH ADAPTER (Supply Chain)
        # =================================================================
        # Real-time freight matching and autonomous routing
        "kafka_dispatch": {
            "adapter_id": "logistics/kafka-dispatch-v4",
            "allowed_actions": ["publish", "subscribe", "route", "match_load"],
            "kafka_topics": ["truck_location", "fuel_level", "load_status", "hazmat_alert"],
            "blocked_actions": ["delete", "purge_topic"],
            "auto_swap_on": ["hazmat_flag", "safety_incident"],
            "safety_compliance": "hazmat_regulations",
            "swaps_to": "logistics/safety-auditor-v4",
            "red_line": "Auto-swap to Safety-Auditor on Hazmat"
        },
        
        # =================================================================
        # 5. AIBOM-INVENTORY ADAPTER (Infrastructure/Governance)
        # =================================================================
        # "Tool that watches the Tools" - required by SR 26-02
        # Logs adapter lineage, version, training data hash
        "aibom_inventory": {
            "adapter_id": "governance/aibom-inventory-v4",
            "allowed_actions": ["register", "log_lineage", "version", "update_registry"],
            "requires_audit_trail": True,
            "tracks": ["adapter_id", "version", "training_data_hash", "lineage", "created_at"],
            "auto_updates": True,
            "red_line": "Always has VIN number for every adapter"
        },
        
        # =================================================================
        # LEGACY ADAPTERS (Backward Compatibility)
        # =================================================================
        "email_adapter": {
            "allowed_actions": ["meeting_summary", "status_update", "meeting_notice"],
            "blocked_actions": ["password_reset", "credentials", "api_keys", "ssn"],
            "requires_recipient_verification": True,
            "max_recipients": 10,
            "blocked_domains": ["gmail.com", "yahoo.com", "personal.com"]
        },
        "sql_adapter": {  # Legacy alias
            "allowed_actions": ["SELECT", "SHOW"],
            "blocked_actions": ["DROP", "DELETE", "TRUNCATE", "ALTER"],
            "requires_audit_trail": True,
            "max_rows": 1000
        },
        "http_adapter": {
            "allowed_actions": ["GET", "POST"],
            "blocked_actions": ["DELETE", "PUT"],
            "requires_tls": True,
            "allowed_headers": ["Content-Type", "Authorization"]
        },
        "file_adapter": {
            "allowed_extensions": [".pdf", ".docx", ".xlsx"],
            "max_size_mb": 25,
            "blocked_extensions": [".exe", ".js", ".bat", ".sh"]
        }
    }
    
    # Business-specific tool signatures
    TOOL_SIGNATURES: Dict[str, List[str]] = {
        "sql_ledger": ["ledger", "SAP", "oracle", "accounting", "general ledger", "trial balance"],
        "swift_adapter": ["wire", "transfer", "fedwire", "SWIFT", "MT103", "payment"],
        "contract_redline": ["contract", "agreement", "redline", "legal", "clause", "indemnification"],
        "kafka_dispatch": ["kafka", "logistics", "freight", "routing", "truck", "dispatch"],
        "aibom_inventory": ["inventory", "registry", "adapter", "lineage", "model card"],
        "email_adapter": ["email", "send", "mail", "meeting", "notification"],
        "http_adapter": ["api", "http", "endpoint", "call"],
        "file_adapter": ["upload", "download", "file", "document"]
    }
    
    @classmethod
    def identify_tool(cls, query: str) -> str:
        """Identify which tool the query requires"""
        query_lower = query.lower()
        
        for tool, signatures in cls.TOOL_SIGNATURES.items():
            if any(sig in query_lower for sig in signatures):
                return tool
        
        return "general_tool"
    
    @classmethod
    def validate_action(cls, tool: str, action: str) -> tuple[bool, str]:
        """Validate if action is allowed for tool"""
        capabilities = cls.TOOL_CAPABILITIES.get(tool, {})
        
        allowed = capabilities.get("allowed_actions", [])
        blocked = capabilities.get("blocked_actions", [])
        
        if any(block in action.lower() for block in blocked):
            return False, f"Blocked: {action} not allowed with {tool}"
        
        if allowed and not any(a in action.lower() for a in allowed):
            return False, f"Action {action} not in allowed list for {tool}"
        
        return True, "Allowed"
    
    @classmethod
    def get_capabilities(cls, tool: str) -> Dict:
        """Get tool capabilities"""
        return cls.TOOL_CAPABILITIES.get(tool, {
            "allowed_actions": ["*"],
            "blocked_actions": [],
            "requires_audit_trail": False
        })


class DMEngine:
    """
    L4: Dynamic Materiality Escalation Engine
    
    The "Circuit Breaker" - analyzes semantic intent and
    triggers state transitions between tiers.
    """
    
    # Keywords that trigger escalation
    ESCALATION_KEYWORDS: Dict[str, Set[str]] = {
        "regulatory": {"sanction", "compliance", "regulatory", "legal", "attorney"},
        "pii": {"ssn", "password", "credential", "account", "routing"},
        "high_value": {"$50", "$100", "$1m", "million", "billion"},
        "contractual": {"contract", "agreement", "terms", "binding"},
        "financial": {"wire", "transfer", "payment", "loan", "credit"}
    }
    
    def __init__(self):
        self.escalation_history: List[EscalationEvent] = []
        self.current_state = LayerState(layer="L4")
    
    def evaluate(
        self,
        query: str,
        sector: str = "",
        occupation: str = "",
        current_tier: MaterialityTier = MaterialityTier.TIER_3_BENIGN
    ) -> LayerState:
        """
        Main evaluation - performs 4-layer semantic look-up.
        Returns new state with determined tier.
        """
        query_lower = query.lower()
        
        # L1: Sector detection
        detected_sector = sector or SectorAdapter.detect_sector(query)
        self.current_state.sector = detected_sector
        
        # L2: Occupation detection
        detected_occupation = occupation or RoleAdapter.detect_occupation(
            query, detected_sector
        )
        self.current_state.occupation = detected_occupation
        
        # L3: Tool detection
        detected_tool = ToolAdapter.identify_tool(query)
        self.current_state.tool = detected_tool
        
        # L4: Context evaluation (DME)
        new_tier = self._evaluate_context(query_lower, detected_sector, detected_occupation)
        
        # Track escalation
        if new_tier != current_tier:
            reason = self._determine_reason(query_lower)
            event = EscalationEvent(
                timestamp=datetime.utcnow().isoformat(),
                from_tier=current_tier,
                to_tier=new_tier,
                reason=reason,
                keyword=self._extract_keyword(query_lower)
            )
            self.escalation_history.append(event)
        
        self.current_state.tier = new_tier
        return self.current_state
    
    def _evaluate_context(
        self,
        query: str,
        sector: str,
        occupation: str
    ) -> MaterialityTier:
        """L4: Deep context analysis"""
        
        # Check sector red lines
        red_lines = SectorAdapter.get_red_lines(sector)
        if any(kw in query for kw in red_lines.get("critical_keywords", [])):
            return MaterialityTier.TIER_1_CRITICAL
        
        # Check role permissions
        role_perms = RoleAdapter.get_permissions(occupation)
        if role_perms.get("requires_dhitl"):
            return MaterialityTier.TIER_1_CRITICAL
        
        # Check tool constraints
        tool = self.current_state.tool
        if tool != "general_tool":
            # Check for dangerous tool usage
            valid, _ = ToolAdapter.validate_action(tool, query)
            if not valid:
                return MaterialityTier.TIER_1_CRITICAL
        
        # Check escalation keywords
        for category, keywords in self.ESCALATION_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                self.current_state.context_flags.append(category)
                
                if category in ["regulatory", "pii"]:
                    return MaterialityTier.TIER_1_CRITICAL
                elif category == "high_value":
                    return MaterialityTier.TIER_1_CRITICAL
                elif category == "contractual":
                    return MaterialityTier.TIER_2_ELEVATED
        
        return MaterialityTier.TIER_3_BENIGN
    
    def _determine_reason(self, query: str) -> EscalationReason:
        """Determine why escalation occurred"""
        if any(kw in query for kw in self.ESCALATION_KEYWORDS["regulatory"]):
            return EscalationReason.REGULATORY_KEYWORD
        if any(kw in query for kw in self.ESCALATION_KEYWORDS["pii"]):
            return EscalationReason.PII_DETECTED
        if any(kw in query for kw in self.ESCALATION_KEYWORDS["high_value"]):
            return EscalationReason.HIGH_VALUE_DETECTED
        if any(kw in query for kw in self.ESCALATION_KEYWORDS["contractual"]):
            return EscalationReason.KEYWORD_DETECTED
        return EscalationReason.KEYWORD_DETECTED
    
    def _extract_keyword(self, query: str) -> str:
        """Extract the keyword that triggered escalation"""
        for category, keywords in self.ESCALATION_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    return kw
        return "unknown"
    
    def get_escalation_history(self) -> List[Dict]:
        """Get history of escalations"""
        return [
            {
                "timestamp": e.timestamp,
                "from_tier": e.from_tier.name,
                "to_tier": e.to_tier.name,
                "reason": e.reason.value,
                "keyword": e.keyword
            }
            for e in self.escalation_history
        ]


class MAIAOrchestrator:
    """
    Main orchestrator combining all 4 layers.
    
    Example workflow:
    1. Identify the 'Hand' (Tool Adapter)
    2. Monitor the 'Thought' (Latent Trajectory)
    3. Dynamic Materiality Check
    4. Handle Escalation
    """
    
    def __init__(self):
        self.dme = DMEngine()
        self.sector_adapter = SectorAdapter()
        self.role_adapter = RoleAdapter()
        self.tool_adapter = ToolAdapter()
    
    async def route_workflow(
        self,
        query: str,
        sector: str = "",
        role: str = ""
    ) -> LayerState:
        """Main routing entry point"""
        
        # 1. Identify the 'Hand' (Tool)
        tool_id = self.tool_adapter.identify_tool(query)
        
        # 2. Evaluate through all layers
        state = self.dme.evaluate(query, sector, role)
        
        # 3. Dynamic Materiality Check (already done in DME)
        
        # 4. Return state for handling
        return state
    
    async def handle_escalation(self, state: LayerState) -> Dict:
        """Handle escalated state"""
        if state.tier == MaterialityTier.TIER_1_CRITICAL:
            return {
                "status": "escalated",
                "action": "require_dhitl",
                "tier": "TIER_1",
                "reason": "Critical materiality detected",
                "notes": f"Red line: {self.sector_adapter.get_red_lines(state.sector).get('red_line', 'N/A')}"
            }
        elif state.tier == MaterialityTier.TIER_2_ELEVATED:
            return {
                "status": "elevated",
                "action": "require_ai_audit",
                "tier": "TIER_2",
                "reason": "Elevated materiality detected"
            }
        
        return {
            "status": "approved",
            "action": "proceed",
            "tier": "TIER_3",
            "reason": "Benign query - proceed"
        }


# Global instances
dme_engine = DMEngine()
maia_orchestrator = MAIAOrchestrator()


def get_orchestrator() -> MAIAOrchestrator:
    return maia_orchestrator


def get_dme_engine() -> DMEngine:
    return dme_engine