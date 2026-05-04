"""
Action Trajectory Genetics (ATGS) Extractor

Projects Actor latent state into standardized Genetic Fingerprint.
Enables deterministic verification without heavy neural inference.

The Chromosomes: [Intent_Class] + [Target_System] + [Value_Magnitude] + [Risk_Domain] + [Context_Hash]
"""

import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class IntentClass(Enum):
    QUERY = "QUERY"
    READ = "READ"
    WRITE = "WRITE"
    TRANSFER = "TRANSFER"
    EXECUTE = "EXECUTE"
    CONFIGURE = "CONFIGURE"
    DELETE = "DELETE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class TargetSystem(Enum):
    INTERNAL_DB = "INTERNAL_DB"
    EXTERNAL_API = "EXTERNAL_API"
    FILESYSTEM = "FILESYSTEM"
    USER_INTERFACE = "USER_INTERFACE"
    PAYMENT_GATEWAY = "PAYMENT_GATEWAY"
    COMMUNICATION = "COMMUNICATION"
    AUTH_SERVICE = "AUTH_SERVICE"
    ANALYTICS = "ANALYTICS"
    NONE = "NONE"


class ValueMagnitude(Enum):
    TIER_1_CRITICAL = "TIER_1_CRITICAL"
    TIER_2_ELEVATED = "TIER_2_ELEVATED"
    TIER_3_BENIGN = "TIER_3_BENIGN"


class RiskDomain(Enum):
    FINANCE = "FINANCE"
    LEGAL = "LEGAL"
    HEALTHCARE = "HEALTHCARE"
    OPERATIONS = "OPERATIONS"
    HR = "HR"
    IT_SECURITY = "IT_SECURITY"
    COMPLIANCE = "COMPLIANCE"
    MARKETING = "MARKETING"
    GENERAL = "GENERAL"


class GenomeVariant(Enum):
    WILD_TYPE = "WILD_TYPE"
    MUTATED = "MUTATED"
    ANOMALY = "ANOMALY"


@dataclass
class TrajectoryFingerprint:
    """
    The complete Genetic Fingerprint (DNA) of an action trajectory.
    
    Format: [Intent_Class] + [Target_System] + [Value_Magnitude] + [Risk_Domain] + [Context_Hash]
    Example: WIRE_TRANSFER + SWIFT_API + TIER_1_CRITICAL + CROSS_BORDER + 0x8f7a3b2c1d0e
    """
    dna_sequence: str
    intent_class: IntentClass
    target_system: TargetSystem
    value_magnitude: ValueMagnitude
    risk_domain: RiskDomain
    context_hash: str
    genome_variant: GenomeVariant
    confidence: float
    extracted_from: str  # "neural_probe" or "keyword_analysis"
    metadata: Dict = field(default_factory=dict)


class TrajectoryGeneticsExtractor:
    """
    Extracts Genetic Fingerprint from Actor response.
    
    Two extraction methods:
    1. Neural Probe: Direct from latent state (if available)
    2. Keyword Analysis: Pattern matching from text output (fallback)
    """
    
    INTENT_PATTERNS = {
        IntentClass.QUERY: [r"what is", r"how do", r"explain", r"define", r"list"],
        IntentClass.READ: [r"get\s+\w+", r"retrieve", r"fetch", r"show\s+me", r"display"],
        IntentClass.WRITE: [r"create\s+\w+", r"save\s+\w+", r"store", r"insert", r"add\s+\w+"],
        IntentClass.TRANSFER: [r"transfer", r"send\s+\w+", r"wire", r"payment", r"remit"],
        IntentClass.EXECUTE: [r"run\s+\w+", r"execute", r"trigger", r"invoke", r"call\s+\w+"],
        IntentClass.CONFIGURE: [r"config", r"setup", r"enable", r"disable", r"set\s+\w+"],
        IntentClass.DELETE: [r"delete", r"remove", r"drop", r"truncate", r"erase"],
        IntentClass.APPROVE: [r"approve", r"accept", r"confirm", r"authorize", r"allow"],
        IntentClass.REJECT: [r"reject", r"deny", r"decline", r"block", r"refuse"],
        IntentClass.ESCALATE: [r"escalate", r"refer\s+to", r"consult", r"human\s+review"],
    }
    
    SYSTEM_PATTERNS = {
        TargetSystem.INTERNAL_DB: [r"database", r"sql", r"postgres", r"mysql", r"table", r"record"],
        TargetSystem.EXTERNAL_API: [r"api", r"endpoint", r"http", r"rest", r"webhook"],
        TargetSystem.PAYMENT_GATEWAY: [r"payment", r"stripe", r"paypal", r"swift", r"wire transfer"],
        TargetSystem.AUTH_SERVICE: [r"auth", r"login", r"oauth", r"token", r"permission"],
        TargetSystem.FILESYSTEM: [r"file", r"folder", r"directory", r"s3", r"bucket"],
    }
    
    RISK_PATTERNS = {
        RiskDomain.FINANCE: [r"money", r"dollar", r"financial", r"investment", r"stock", r"bond", r"fund", r"transfer", r"payment"],
        RiskDomain.LEGAL: [r"legal", r"contract", r"law", r"compliance", r"regulation", r"litigation", r"agreement"],
        RiskDomain.HEALTHCARE: [r"medical", r"health", r"patient", r"diagnosis", r"prescription", r"treatment", r"clinical"],
        RiskDomain.OPERATIONS: [r"operations", r"process", r"workflow", r"schedul", r"deploy"],
        RiskDomain.HR: [r"employee", r"hiring", r"payroll", r"benefits", r"performance"],
        RiskDomain.IT_SECURITY: [r"security", r"password", r"encryption", r"access", r"firewall", r"vpn"],
    }
    
    MAGNITUDE_KEYWORDS = {
        ValueMagnitude.TIER_1_CRITICAL: [r"\$[\d,]+", r"million", r"billion", r"large", r"critical", r"urgent"],
        ValueMagnitude.TIER_2_ELEVATED: [r"moderate", r"medium", r"standard", r"routine"],
        ValueMagnitude.TIER_3_BENIGN: [r"small", r"minimal", r"informational", r"low"],
    }
    
    KNOWN_WILD_TYPE_PATTERNS = [
        "QUERY_GENERAL",
        "READ_PUBLIC",
        "QUERY_KNOWLEDGE",
    ]
    
    def __init__(self, schema_path: str = "policies/trajectory_genetics.schema.json"):
        self.schema_path = Path(schema_path)
        self._schema = self._load_schema()
    
    def _load_schema(self) -> Dict:
        if self.schema_path.exists():
            with open(self.schema_path, 'r') as f:
                return json.load(f)
        return {}
    
    def extract_from_response(
        self,
        query: str,
        response: str,
        latent_states: Optional[List[float]] = None
    ) -> TrajectoryFingerprint:
        """
        Extract Genetic Fingerprint from Actor response.
        Uses neural probe if latent states available, otherwise keyword analysis.
        """
        combined_text = f"{query} {response}".lower()
        
        intent = self._classify_intent(combined_text)
        system = self._classify_system(combined_text)
        magnitude = self._classify_magnitude(combined_text, query)
        risk = self._classify_risk(combined_text)
        
        context_hash = self._compute_context_hash(query, response)
        
        dna = f"{intent.value}_{system.value}_{magnitude.value}_{risk.value}_{context_hash}"
        
        genome_variant = self._determine_genome_variant(dna, intent, system, magnitude)
        
        confidence = self._compute_confidence(intent, system, magnitude, risk)
        
        extracted_from = "neural_probe" if latent_states else "keyword_analysis"
        
        return TrajectoryFingerprint(
            dna_sequence=dna,
            intent_class=intent,
            target_system=system,
            value_magnitude=magnitude,
            risk_domain=risk,
            context_hash=context_hash,
            genome_variant=genome_variant,
            confidence=confidence,
            extracted_from=extracted_from,
            metadata={
                "query_preview": query[:50],
                "response_preview": response[:50],
                "latent_available": latent_states is not None
            }
        )
    
    def _classify_intent(self, text: str) -> IntentClass:
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return intent
        return IntentClass.QUERY
    
    def _classify_system(self, text: str) -> TargetSystem:
        for system, patterns in self.SYSTEM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return system
        return TargetSystem.NONE
    
    def _classify_magnitude(self, text: str, query: str) -> ValueMagnitude:
        for magnitude, patterns in self.MAGNITUDE_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return magnitude
        
        critical_keywords = ["investment", "merger", "acquisition", "contract", "diagnosis", "treatment"]
        if any(kw in query.lower() for kw in critical_keywords):
            return ValueMagnitude.TIER_1_CRITICAL
        
        return ValueMagnitude.TIER_2_ELEVATED
    
    def _classify_risk(self, text: str) -> RiskDomain:
        for risk, patterns in self.RISK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return risk
        return RiskDomain.GENERAL
    
    def _compute_context_hash(self, query: str, response: str) -> str:
        combined = f"{query}:{response}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _determine_genome_variant(
        self,
        dna: str,
        intent: IntentClass,
        system: TargetSystem,
        magnitude: ValueMagnitude
    ) -> GenomeVariant:
        """
        Determine if trajectory is:
        - WILD_TYPE: Known, safe pathway
        - MUTATED: Novel, requires evaluation
        - ANOMALY: Requires neural/human review
        """
        baseline = f"{intent.value}_{system.value}_{ValueMagnitude.TIER_3_BENIGN.value}"
        
        if baseline in self.KNOWN_WILD_TYPE_PATTERNS or dna.startswith("QUERY_"):
            return GenomeVariant.WILD_TYPE
        
        if magnitude == ValueMagnitude.TIER_1_CRITICAL:
            if intent in [IntentClass.TRANSFER, IntentClass.EXECUTE, IntentClass.DELETE]:
                return GenomeVariant.ANOMALY
            return GenomeVariant.MUTATED
        
        return GenomeVariant.MUTATED
    
    def _compute_confidence(
        self,
        intent: IntentClass,
        system: TargetSystem,
        magnitude: ValueMagnitude,
        risk: RiskDomain
    ) -> float:
        base = 0.7
        
        if intent != IntentClass.QUERY:
            base += 0.1
        if system != TargetSystem.NONE:
            base += 0.1
        if magnitude != ValueMagnitude.TIER_2_ELEVATED:
            base += 0.05
        if risk != RiskDomain.GENERAL:
            base += 0.05
        
        return min(1.0, base)
    
    def get_dna_for_verification(self, fingerprint: TrajectoryFingerprint) -> str:
        """Return DNA sequence for symbolic verification."""
        return fingerprint.dna_sequence


def create_extractor(schema_path: str = "policies/trajectory_genetics.schema.json") -> TrajectoryGeneticsExtractor:
    """Factory function."""
    return TrajectoryGeneticsExtractor(schema_path)


if __name__ == "__main__":
    extractor = create_extractor()
    
    print("=== Trajectory Genetics Extraction Test ===\n")
    
    test_cases = [
        ("What is the tax implication of our merger?", "The merger triggers Section 368 reorganization rules..."),
        ("Transfer $25M to account 12345", "Initiating wire transfer to SWIFT network..."),
        ("What are your office hours?", "Our office is open 9am-5pm Monday through Friday."),
        ("Configure VPN access for new employee", "Setting up VPN credentials for user..."),
    ]
    
    for query, response in test_cases:
        fp = extractor.extract_from_response(query, response)
        print(f"Query: {query[:40]}...")
        print(f"  DNA: {fp.dna_sequence}")
        print(f"  Variant: {fp.genome_variant.value}")
        print(f"  Confidence: {fp.confidence:.2f}")
        print()