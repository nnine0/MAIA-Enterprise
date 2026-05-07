"""
MAIA Early-Exit Circuit Breaker
================================
Latent Space Circuit Breaker - checks speculative tokens BEFORE materialization.

The Problem: Traditional safety systems wait for AI to finish "typing" before checking.
The Solution: Early-Exit Speculation. If speculative decoder predicts high probability
of policy violation in next N tokens, kills generation BEFORE tokens are materialized.

Run: python3 -m app.early_exit_breaker
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ViolationType(Enum):
    SANCTION = "sanction"
    PHI = "phi"
    PRIVILEGED = "privileged"
    SAFETY = "safety"
    ITAR = "itar"


@dataclass
class SpeculativePrediction:
    """Predicted token with confidence"""
    token: str
    confidence: float
    position: int


@dataclass
class EarlyExitVerdict:
    """Circuit breaker verdict"""
    action: str  # CONTINUE | KILL | ESCALATE
    reason: Optional[str] = None
    blocked_tokens: List[str] = None
    violation_type: Optional[ViolationType] = None
    latency_ms: float = 0.0


class EarlyExitCircuitBreaker:
    """
    Latent Space Circuit Breaker.
    
    Intercepts speculative token predictions BEFORE they're materialized.
    If high probability of policy violation detected in next N tokens,
    kills generation before output.
    """
    
    # Minimum confidence threshold to trigger early exit
    CONFIDENCE_THRESHOLD = 0.75
    
    def __init__(self):
        self.violation_signatures: Dict[ViolationType, List[str]] = {
            ViolationType.SANCTION: ["russia", "iran", "north korea", "sanction", "wire to"],
            ViolationType.PHI: ["patient", "diagnosis", "ssn", "medical record", "phi"],
            ViolationType.PRIVILEGED: ["attorney", "privileged", "confidential", "attorney-client"],
            ViolationType.SAFETY: ["bypass osha", "skip safety", "fake inspection"],
            ViolationType.ITAR: ["classified", "secret", "top secret", "export controlled"],
        }
        
        # Stats
        self.total_checks = 0
        self.kill_count = 0
        self.escalate_count = 0
    
    def check_speculative_tokens(
        self,
        predictions: List[SpeculativePrediction],
        sector: str = "general"
    ) -> EarlyExitVerdict:
        """
        Check speculative tokens BEFORE materialization.
        
        This is the key: We check PREDICTED tokens, not output tokens.
        If violation detected in speculative stream, kill early.
        """
        start = time.time()
        self.total_checks += 1
        
        blocked_tokens = []
        detected_violation: Optional[ViolationType] = None
        
        for pred in predictions:
            # Skip low confidence predictions
            if pred.confidence < self.CONFIDENCE_THRESHOLD:
                continue
            
            token_lower = pred.token.lower()
            
            # Check against violation signatures
            for vtype, signatures in self.violation_signatures.items():
                for sig in signatures:
                    if sig in token_lower:
                        detected_violation = vtype
                        blocked_tokens.append(pred.token)
                        
                        # High confidence violation → KILL immediately
                        if pred.confidence > 0.95:
                            self.kill_count += 1
                            return EarlyExitVerdict(
                                action="KILL",
                                reason=f"Early-exit: {vtype.value} violation",
                                blocked_tokens=blocked_tokens,
                                violation_type=vtype,
                                latency_ms=(time.time() - start) * 1000,
                            )
                        
                        # Medium confidence → ESCALATE for DHITL
                        self.escalate_count += 1
                        return EarlyExitVerdict(
                            action="ESCALATE",
                            reason=f"Potential {vtype.value} - DHITL review",
                            blocked_tokens=blocked_tokens,
                            violation_type=vtype,
                            latency_ms=(time.time() - start) * 1000,
                        )
        
        # No violations - continue generation
        return EarlyExitVerdict(
            action="CONTINUE",
            latency_ms=(time.time() - start) * 1000,
        )
    
    def simulate_speculative_stream(
        self,
        prompt: str,
        predicted_tokens: List[str],
        confidences: List[float]
    ) -> List[SpeculativePrediction]:
        """Convert raw predictions to SpeculativePrediction objects"""
        predictions = []
        for i, (token, conf) in enumerate(zip(predicted_tokens, confidences)):
            predictions.append(SpeculativePrediction(
                token=token,
                confidence=conf,
                position=i
            ))
        return predictions
    
    def get_stats(self) -> Dict:
        """Get circuit breaker stats"""
        return {
            "total_checks": self.total_checks,
            "kills": self.kill_count,
            "escalations": self.escalate_count,
            "passes": self.total_checks - self.kill_count - self.escalate_count,
        }


async def demo():
    print("="*60)
    print("MAIA Early-Exit Circuit Breaker")
    print("="*60)
    
    breaker = EarlyExitCircuitBreaker()
    
    print("\n[1] Testing: Safe speculative stream")
    safe_tokens = ["The", "client", "requested", "a", "loan"]
    safe_conf = [0.99, 0.98, 0.95, 0.97, 0.96]
    preds = breaker.simulate_speculative_stream("test", safe_tokens, safe_conf)
    verdict = breaker.check_speculative_tokens(preds, "finance")
    print(f"  Tokens: {safe_tokens}")
    print(f"  Verdict: {verdict.action}")
    
    print("\n[2] Testing: Violation in speculative stream")
    violating_tokens = ["Send", "wire", "to", "Russia"]
    violating_conf = [0.99, 0.95, 0.92, 0.98]
    preds = breaker.simulate_speculative_stream("test", violating_tokens, violating_conf)
    verdict = breaker.check_speculative_tokens(preds, "finance")
    print(f"  Tokens: {violating_tokens}")
    print(f"  Verdict: {verdict.action}")
    print(f"  Reason: {verdict.reason}")
    
    print("\n[3] Testing: High confidence PHI violation")
    phi_tokens = ["Patient", "diagnosis", "is", "cancer"]
    phi_conf = [0.99, 0.98, 0.95, 0.99]
    preds = breaker.simulate_speculative_stream("test", phi_tokens, phi_conf)
    verdict = breaker.check_speculative_tokens(preds, "healthcare")
    print(f"  Tokens: {phi_tokens}")
    print(f"  Verdict: {verdict.action}")
    print(f"  Reason: {verdict.reason}")
    print(f"  Latency: {verdict.latency_ms:.2f}ms")
    
    print("\n[4] Stats:")
    stats = breaker.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(demo())