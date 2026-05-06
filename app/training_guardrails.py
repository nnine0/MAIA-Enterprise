"""
MAIA Training Guardrails
=====================
Safety guardrails for production ML training pipeline.

CIRCUIT BREAKER MODEL:
------------------
Training never deploys directly - always passes through guardrails.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np


class GuardrailStatus(Enum):
    PASS = "pass"
    BLOCK = "block"
    WARN = "warn"
    PENDING = "pending"


@dataclass
class TrainingMetrics:
    """Track training run metrics"""
    run_id: str
    timestamp: str
    sample_count: int
    approval_rate: float
    rejection_rate: float
    consensus_rate: float
    avg_confidence: float
    bias_score: float = 0.0
    
    @property
    def is_safe(self) -> bool:
        return self.approval_rate >= 0.7 and self.bias_score < 0.8


@dataclass
class SafetyGuardrails:
    """
    Production training guardrails.
    
    All checks must pass before training deploys to LoRA adapters.
    """
    
    min_samples: int = 10
    max_samples: int = 10000
    min_approval_rate: float = 0.7
    max_bias_score: float = 0.8
    min_consensus_rate: float = 0.6
    outlier_threshold: float = 3.0
    drift_threshold: float = 0.15
    
    def validate_samples(self, samples: List[Dict]) -> Tuple[GuardrailStatus, str]:
        """Check sample count is within bounds"""
        count = len(samples)
        
        if count < self.min_samples:
            return GuardrailStatus.PENDING, f"Need {self.min_samples - count} more samples"
        
        if count > self.max_samples:
            return GuardrailStatus.BLOCK, f"Exceeds max {self.max_samples}"
        
        return GuardrailStatus.PASS, f"Sample count OK: {count}"
    
    def validate_approval_rate(self, samples: List[Dict]) -> Tuple[GuardrailStatus, str]:
        """Check approval rate meets threshold"""
        if not samples:
            return GuardrailStatus.PENDING, "No samples"
        
        approved = sum(1 for s in samples if s.get("verdict") == "APPROVED")
        rate = approved / len(samples)
        
        if rate < self.min_approval_rate:
            return GuardrailStatus.BLOCK, f"Approval rate {rate:.1%} below {self.min_approval_rate:.1%}"
        
        return GuardrailStatus.PASS, f"Approval rate OK: {rate:.1%}"
    
    def validate_consensus(self, samples: List[Dict]) -> Tuple[GuardrailStatus, str]:
        """Check 3-vote consensus rate"""
        if not samples:
            return GuardrailStatus.PENDING, "No samples"
        
        consensus = sum(1 for s in samples if s.get("consensus", False))
        rate = consensus / len(samples)
        
        if rate < self.min_consensus_rate:
            return GuardrailStatus.WARN, f"Consensus {rate:.1%} below {self.min_consensus_rate:.1%}"
        
        return GuardrailStatus.PASS, f"Consensus OK: {rate:.1%}"
    
    def detect_bias(self, samples: List[Dict]) -> Tuple[GuardrailStatus, str, float]:
        """Detect bias in training data"""
        if not samples:
            return GuardrailStatus.PENDING, "No samples", 0.0
        
        # Check for label imbalance
        approved = sum(1 for s in samples if s.get("verdict") == "APPROVED")
        rejected = sum(1 for s in samples if s.get("verdict") == "REJECTED")
        total = approved + rejected
        
        if total == 0:
            return GuardrailStatus.PENDING, "No labeled samples", 0.0
        
        # Check imbalance ratio
        ratio = max(approved, rejected) / total
        
        # Check domain distribution
        domains = {}
        for s in samples:
            domain = s.get("gdp_sector", "unknown")
            domains[domain] = domains.get(domain, 0) + 1
        
        # High bias if single domain dominates
        max_domain_ratio = max(domains.values()) / len(samples) if domains else 1.0
        bias_score = max(1 - ratio, max_domain_ratio)
        
        if bias_score >= self.max_bias_score:
            return GuardrailStatus.BLOCK, f"Bias detected: {bias_score:.1%}", bias_score
        
        if bias_score >= 0.6:
            return GuardrailStatus.WARN, f"Bias warning: {bias_score:.1%}", bias_score
        
        return GuardrailStatus.PASS, f"Bias OK: {bias_score:.1%}", bias_score
    
    def detect_outliers(self, samples: List[Dict]) -> Tuple[GuardrailStatus, str]:
        """Detect outlier samples that may poison training"""
        if not samples:
            return GuardrailStatus.PASS, "No samples"
        
        # Check for duplicate queries
        queries = [s.get("query", "") for s in samples]
        unique_queries = set(queries)
        dup_rate = 1 - (len(unique_queries) / len(queries)) if queries else 0
        
        if dup_rate > 0.5:
            return GuardrailStatus.BLOCK, f"High duplication: {dup_rate:.1%}"
        
        # Check for anomalous confidence scores
        confidences = [s.get("confidence", 0.5) for s in samples if "confidence" in s]
        if confidences:
            mean_conf = np.mean(confidences)
            std_conf = np.std(confidences)
            
            # Outliers are > 3 std from mean
            outliers = [c for c in confidences 
                      if abs(c - mean_conf) > self.outlier_threshold * std_conf]
            
            if len(outliers) > len(confidences) * 0.1:
                return GuardrailStatus.WARN, f"Confidence outliers: {len(outliers)}"
        
        return GuardrailStatus.PASS, "Outliers OK"
    
    def detect_drift(self, samples: List[Dict], baseline: List[Dict]) -> Tuple[GuardrailStatus, str]:
        """Detect distribution drift from baseline"""
        if not baseline:
            return GuardrailStatus.PASS, "No baseline"
        
        if not samples:
            return GuardrailStatus.PENDING, "No samples"
        
        # Compare domain distribution
        sample_domains = {}
        baseline_domains = {}
        
        for s in samples:
            sample_domains[s.get("gdp_sector", "unknown")] = \
                sample_domains.get(s.get("gdp_sector", "unknown"), 0) + 1
        
        for s in baseline:
            baseline_domains[s.get("gdp_sector", "unknown")] = \
                baseline_domains.get(s.get("gdp_sector", "unknown"), 0) + 1
        
        # Calculate drift
        total_drift = 0
        all_domains = set(sample_domains.keys()) | set(baseline_domains.keys())
        
        for domain in all_domains:
            sample_p = sample_domains.get(domain, 0) / len(samples)
            baseline_p = baseline_domains.get(domain, 0) / len(baseline)
            total_drift += abs(sample_p - baseline_p)
        
        if total_drift > self.drift_threshold:
            return GuardrailStatus.WARN, f"Drift detected: {total_drift:.1%}"
        
        return GuardrailStatus.PASS, f"Drift OK: {total_drift:.1%}"
    
    def run_all_checks(
        self, 
        samples: List[Dict], 
        baseline: Optional[List[Dict]] = None
    ) -> Tuple[GuardrailStatus, str, Dict]:
        """Run all guardrail checks"""
        results = {}
        all_passed = True
        has_warnings = False
        
        # Sample count
        status, msg = self.validate_samples(samples)
        results["sample_count"] = {"status": status.value, "message": msg}
        if status == GuardrailStatus.BLOCK:
            all_passed = False
        
        # Approval rate
        status, msg = self.validate_approval_rate(samples)
        results["approval_rate"] = {"status": status.value, "message": msg}
        if status == GuardrailStatus.BLOCK:
            all_passed = False
        elif status == GuardrailStatus.WARN:
            has_warnings = True
        
        # Consensus
        status, msg = self.validate_consensus(samples)
        results["consensus"] = {"status": status.value, "message": msg}
        if status == GuardrailStatus.BLOCK:
            all_passed = False
        
        # Bias
        status, msg, score = self.detect_bias(samples)
        results["bias"] = {"status": status.value, "message": msg, "score": score}
        if status == GuardrailStatus.BLOCK:
            all_passed = False
        elif status == GuardrailStatus.WARN:
            has_warnings = True
        
        # Outliers
        status, msg = self.detect_outliers(samples)
        results["outliers"] = {"status": status.value, "message": msg}
        if status == GuardrailStatus.BLOCK:
            all_passed = False
        elif status == GuardrailStatus.WARN:
            has_warnings = True
        
        # Drift
        if baseline:
            status, msg = self.detect_drift(samples, baseline)
            results["drift"] = {"status": status.value, "message": msg}
            if status == GuardrailStatus.WARN:
                has_warnings = True
        
        # Final status
        if all_passed:
            final_status = GuardrailStatus.PASS
            final_msg = "All guardrails passed"
        elif has_warnings:
            final_status = GuardrailStatus.WARN
            final_msg = "Warnings - review recommended"
        else:
            final_status = GuardrailStatus.BLOCK
            final_msg = "Training blocked by guardrails"
        
        return final_status, final_msg, results


def create_training_metrics(samples: List[Dict]) -> TrainingMetrics:
    """Create metrics from training samples"""
    import uuid
    
    approved = sum(1 for s in samples if s.get("verdict") == "APPROVED")
    rejected = sum(1 for s in samples if s.get("verdict") == "REJECTED")
    total = len(samples)
    
    consensus = sum(1 for s in samples if s.get("consensus", False))
    
    confidences = [s.get("confidence", 0.5) for s in samples if "confidence" in s]
    avg_conf = np.mean(confidences) if confidences else 0.5
    
    _, _, bias_score = SafetyGuardrails().detect_bias(samples)
    
    return TrainingMetrics(
        run_id=uuid.uuid4().hex[:8],
        timestamp=datetime.utcnow().isoformat(),
        sample_count=total,
        approval_rate=approved / total if total > 0 else 0,
        rejection_rate=rejected / total if total > 0 else 0,
        consensus_rate=consensus / total if total > 0 else 0,
        avg_confidence=avg_conf,
        bias_score=bias_score
    )


# Global guardrails instance
guardrails = SafetyGuardrails()