"""
MAIA Speculation Metrics
=====================
Thread-safe statistics for speculative decoding.

Layer: Telemetry (Neural EKG)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
import threading


@dataclass
class SpeculationMetrics:
    dflash_drafts: int = 0
    dflash_tokens: int = 0
    dflash_time_ms: float = 0.0
    dflash_verification_failures: int = 0
    
    saguaro_hypotheses: int = 0
    saguaro_selections: int = 0
    saguaro_time_ms: float = 0.0
    saguaro_acceptance_rate: float = 0.0
    
    circuit_breaker_blocks: int = 0
    circuit_breaker_passes: int = 0
    sme_escalations: int = 0
    
    total_requests: int = 0
    tier1_requests: int = 0
    tier2_requests: int = 0
    tier3_requests: int = 0


class MetricsCollector:
    """Thread-safe metrics collection"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._metrics = defaultdict(SpeculationMetrics)
        self._history: List[Dict] = []
    
    def record_dflash(self, draft_id: str, tokens: int, time_ms: float, verified: bool):
        with self._lock:
            m = self._metrics["dflash"]
            m.dflash_drafts += 1
            m.dflash_tokens += tokens
            m.dflash_time_ms += time_ms
            if not verified:
                m.dflash_verification_failures += 1
    
    def record_saguaro(self, hypotheses: int, time_ms: float, acceptance_rate: float):
        with self._lock:
            m = self._metrics["saguaro"]
            m.saguaro_hypotheses += hypotheses
            m.saguaro_selections += 1
            m.saguaro_time_ms += time_ms
            m.saguaro_acceptance_rate = acceptance_rate
    
    def record_circuit_breaker(self, passed: bool, tier: int):
        with self._lock:
            m = self._metrics["circuit_breaker"]
            if passed:
                m.circuit_breaker_passes += 1
            else:
                m.circuit_breaker_blocks += 1
            
            if tier == 1:
                self._metrics[""].tier1_requests += 1
            elif tier == 2:
                self._metrics[""].tier2_requests += 1
            else:
                self._metrics[""].tier3_requests += 1
            
            self._metrics[""].total_requests += 1
    
    def record_sme_escalation(self):
        with self._lock:
            self._metrics["circuit_breaker"].sme_escalations += 1
    
    def get_metrics(self) -> Dict:
        with self._lock:
            return {
                "dflash": {
                    "total_drafts": self._metrics["dflash"].dflash_drafts,
                    "total_tokens": self._metrics["dflash"].dflash_tokens,
                    "avg_time_ms": (
                        self._metrics["dflash"].dflash_time_ms / 
                        max(1, self._metrics["dflash"].dflash_drafts)
                    ),
                    "verification_failure_rate": (
                        self._metrics["dflash"].dflash_verification_failures /
                        max(1, self._metrics["dflash"].dflash_drafts)
                    )
                },
                "saguaro": {
                    "total_hypotheses": self._metrics["saguaro"].saguaro_hypotheses,
                    "total_selections": self._metrics["saguaro"].saguaro_selections,
                    "avg_time_ms": (
                        self._metrics["saguaro"].saguaro_time_ms /
                        max(1, self._metrics["saguaro"].saguaro_selections)
                    ),
                    "acceptance_rate": self._metrics["saguaro"].saguaro_acceptance_rate
                },
                "circuit_breaker": {
                    "total_blocks": self._metrics["circuit_breaker"].circuit_breaker_blocks,
                    "total_passes": self._metrics["circuit_breaker"].circuit_breaker_passes,
                    "sme_escalations": self._metrics["circuit_breaker"].sme_escalations
                },
                "tiers": {
                    "tier1": self._metrics[""].tier1_requests,
                    "tier2": self._metrics[""].tier2_requests,
                    "tier3": self._metrics[""].tier3_requests,
                    "total": self._metrics[""].total_requests
                }
            }
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            return self._history[-limit:]


metrics_collector = MetricsCollector()