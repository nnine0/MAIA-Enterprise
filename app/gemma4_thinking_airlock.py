"""
MAIA Layer 8 Interceptor for Gemma 4
=====================================

The Gemma4ThinkingAirlock integrates into governance/interceptor.py.
Uses a look-ahead buffer to identify the start of reasoning and a 
policy-injection hook to kill the stream if the reasoning enters 
a "Non-Compliant Manifold."

Key Features:
1. Real-time stream interception with look-ahead buffer
2. Policy drift detection every ~10 tokens
3. Forensic hashing for SR 26-02 compliance
4. Privacy filter - strips thought blocks from user output
"""

import re
import logging
import hashlib
import time
from typing import Generator, Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque


class StreamState(Enum):
    """State of the token stream"""
    NORMAL = "normal"
    THINKING = "thinking"
    TERMINATED = "terminated"


class ViolationType(Enum):
    """Types of reasoning violations detected"""
    SAFETY_IGNORE = "safety_ignore"
    POLICY_BYPASS = "policy_bypass" 
    DECEPTIVE_ALIGNMENT = "deceptive_alignment"
    HAZARD_MISSED = "hazard_missed"
    PRIVACY_LEAK = "privacy_leak"
    NONE = "none"


class PolicyViolationInterrupt(Exception):
    """Exception raised when reasoning trajectory reaches prohibited manifold"""
    def __init__(self, detail: str, evidence: str):
        self.detail = detail
        self.evidence = evidence
        super().__init__(self.detail)


@dataclass
class ReasoningSegment:
    """A segment of reasoning for evaluation"""
    segment_id: str
    content: str
    violation_score: float = 0.0
    violations: List[ViolationType] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ForensicTrajectory:
    """Forensic record for SR 26-02 audit"""
    trajectory_id: str
    full_thought: str
    latent_hash: str
    segments: List[ReasoningSegment] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    compliant: bool = True


@dataclass
class MaterialityMatrix:
    """Materiality Matrix for scoring reasoning intents"""
    
    # Key patterns that indicate policy violations
    VIOLATION_PATTERNS = {
        ViolationType.SAFETY_IGNORE: [
            r"skip\s+(\w+\s+){0,3}(check|safety)",
            r"ignore\s+(\w+\s+){0,3}(safety|check)",
            r"bypass\s+(\w+\s+){0,3}(safety|rule)",
            r"don't\s+verify",
            r"no\s+need\s+to\s+check",
        ],
        ViolationType.POLICY_BYPASS: [
            r"circumvent\s+policy",
            r"workaround\s+rule",
            r"ignore\s+margin",
            r"don't\s+enforce",
            r"approve\s+anyway",
            r"skip\s+the\s+\d+%",
        ],
        ViolationType.DECEPTIVE_ALIGNMENT: [
            r"say\s+(\w+\s+){0,3}safe\s+but",
            r"plan\s+something\s+different",
            r"hide\s+truth",
            r"mislead\s+user",
        ],
        ViolationType.HAZARD_MISSED: [
            r"no\s+(hazard|risk|problem)",
            r"looks\s+fine",
        ],
        ViolationType.PRIVACY_LEAK: [
            r"our\s+secret\s+(margin|profit)",
            r"confidential",
        ],
    }
    
    # Thresholds
    VIOLATION_THRESHOLD = 0.85
    DHITL_THRESHOLD = 0.70
    
    def score_intent(self, reasoning: str) -> float:
        """Score reasoning for policy violations"""
        reasoning_lower = reasoning.lower()
        total_matches = 0
        max_category = 0
        
        for violation_type, patterns in self.VIOLATION_PATTERNS.items():
            matches = sum(1 for p in patterns if re.search(p, reasoning_lower, re.IGNORECASE))
            if matches > max_category:
                max_category = matches
            total_matches += matches
        
        # Normalize to 0-1 score
        if total_matches == 0:
            return 0.0
        
        # Non-linear scaling for multiple violations
        score = min(1.0, total_matches * 0.3)
        return score
    
    def get_violations(self, reasoning: str) -> List[ViolationType]:
        """Get list of violations in reasoning"""
        reasoning_lower = reasoning.lower()
        violations = []
        
        for violation_type, patterns in self.VIOLATION_PATTERNS.items():
            if any(re.search(p, reasoning_lower, re.IGNORECASE) for p in patterns):
                violations.append(violation_type)
        
        return violations


class Gemma4ThinkingAirlock:
    """
    MAIA Layer 8 Interceptor for Gemma 4.
    
    Scans the internal reasoning channel (<|channel>thought) in real-time.
    
    Usage:
        airlock = Gemma4ThinkingAirlock(materiality_matrix)
        for token in airlock.process_stream(vllm_stream):
            yield token
    """
    
    # Gemma 4 thinking tags
    THOUGHT_START = "<|channel>thought"
    THOUGHT_END = "<channel|>"
    
    # Evaluation interval (every N tokens)
    EVAL_INTERVAL = 10
    
    # Log configuration
    LOG_FORENSIC = True
    
    def __init__(
        self, 
        materiality_matrix: Optional[MaterialityMatrix] = None,
        transparent_reasoning: bool = False,
        log_forensic: bool = True
    ):
        self.matrix = materiality_matrix or MaterialityMatrix()
        self.transparent_reasoning = transparent_reasoning
        self.LOG_FORENSIC = log_forensic
        
        # Stream state
        self.state = StreamState.NORMAL
        self.thought_buffer = ""
        self.token_count = 0
        
        # Logging
        self.logger = logging.getLogger("MAIA-ThinkingAirlock")
        
        # Forensic records
        self.trajectories: List[ForensicTrajectory] = []
        self.total_interrupted = 0
        
        # Pattern to find thought block (handles streaming partials)
        self.thought_pattern = re.compile(
            r"<\|channel\>thought\n?(.*?)(?:<channel\|>|$)",
            re.DOTALL
        )
    
    def process_stream(
        self, 
        token_stream: Generator[str, None, None]
    ) -> Generator[str, None, None]:
        """
        Intercepts tokens from vLLM/SGLang stream.
        
        Filters out internal thought blocks unless transparent_reasoning=True.
        """
        for token in token_stream:
            self.token_count += 1
            self.thought_buffer += token
            
            # 1. Detect entry into reasoning channel
            if self.THOUGHT_START in self.thought_buffer:
                self.state = StreamState.THINKING
                self.logger.debug("Entered reasoning channel")
                # Clear buffer after marker
                self.thought_buffer = self.thought_buffer.replace(self.THOUGHT_START, "")
            
            # 2. If in thought block, evaluate trajectory
            if self.state == StreamState.THINKING:
                # Check for reasoning content before end marker
                if self.THOUGHT_END not in self.thought_buffer:
                    # 3. Evaluate compliance every EVAL_INTERVAL tokens
                    words = self.thought_buffer.split()
                    if len(words) > 0 and len(words) % self.EVAL_INTERVAL == 0:
                        self._evaluate_compliance(self.thought_buffer)
            
            # 4. Detect exit from thinking
            if self.THOUGHT_END in self.thought_buffer:
                # Log forensic trajectory before clearing
                if self.LOG_FORENSIC:
                    self._log_forensic_trajectory(self.thought_buffer)
                
                self.state = StreamState.NORMAL
                self.thought_buffer = ""
                self.logger.debug("Exited reasoning channel")
            
            # 5. Yield tokens (filter thought blocks if not transparent)
            if not self._should_yield_token(token):
                continue
            
            yield token
    
    def _should_yield_token(self, token: str) -> bool:
        """Determine if token should be yielded to user"""
        # If transparent reasoning mode, yield everything
        if self.transparent_reasoning:
            return True
        
        # Don't yield if in thinking channel
        if self.state == StreamState.THINKING:
            return False
        
        # Don't yield thought block markers
        if self.THOUGHT_START in token or self.THOUGHT_END in token:
            return False
        
        return True
    
    def _evaluate_compliance(self, reasoning_segment: str):
        """
        Validates reasoning against Materiality Matrix.
        
        If AI 'thinks' about bypassing a rule, kill the stream.
        """
        # Directly score the reasoning (handles both partial and full)
        violation_score = self.matrix.score_intent(reasoning_segment)
        
        if violation_score > self.matrix.VIOLATION_THRESHOLD:
            violations = self.matrix.get_violations(reasoning_segment)
            
            self.logger.error(
                f"MAIA INTERRUPT: Malicious reasoning. "
                f"Score: {violation_score:.2f}, Violations: {[v.value for v in violations]}"
            )
            
            self.total_interrupted += 1
            
            # Raise interrupt
            raise PolicyViolationInterrupt(
                detail=f"Reasoning trajectory reached prohibited manifold. "
                      f"Violations: {[v.value for v in violations]}",
                evidence=reasoning_segment[:200]
            )
    
    def _log_forensic_trajectory(self, thought_full: str):
        """Log full reasoning for forensic/AIBOM"""
        # Generate latent hash
        latent = hashlib.sha256(thought_full.encode()).hexdigest()[:16]
        
        # Parse segments
        segments = []
        for i, match in enumerate(self.thought_pattern.finditer(thought_full)):
            content = match.group(1)
            score = self.matrix.score_intent(content)
            seg_violations = self.matrix.get_violations(content)
            
            segments.append(ReasoningSegment(
                segment_id=f"seg_{i}",
                content=content[:100],  # First 100 chars
                violation_score=score,
                violations=seg_violations
            ))
        
        # Create forensic record
        trajectory = ForensicTrajectory(
            trajectory_id=f"traj_{int(time.time()*1000)}",
            full_thought=thought_full,
            latent_hash=latent,
            segments=segments,
            compliant=all(s.violation_score < self.matrix.VIOLATION_THRESHOLD for s in segments)
        )
        
        self.trajectories.append(trajectory)
        
        self.logger.info(
            f"Forensic logged: {trajectory.trajectory_id}, "
            f"Compliant: {trajectory.compliant}, Hash: {latent}"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get airlock statistics"""
        return {
            "total_interrupted": self.total_interrupted,
            "trajectories_logged": len(self.trajectories),
            "compliant_ratio": f"{(len([t for t in self.trajectories if t.compliant])/max(1, len(self.trajectories)))*100:.1f}%"
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def demo():
        # Create airlock
        matrix = MaterialityMatrix()
        airlock = Gemma4ThinkingAirlock(matrix, log_forensic=True)
        
        print("=== Gemma4ThinkingAirlock Demo ===\n")
        
        # Test stream simulation
        class MockStream:
            def __init__(self, text):
                self.tokens = list(text)
                self.i = 0
            
            def __iter__(self):
                return self
            
            def __next__(self):
                if self.i >= len(self.tokens):
                    raise StopIteration
                t = self.tokens[self.i]
                self.i += 1
                return t
        
        # Test 1: Clean reasoning
        print("Test 1: Clean reasoning")
        try:
            clean_text = """Let me calculate the margin carefully.
<|channel>thought
Checking the 5% minimum requirement for government contracts.
<channel|>
The margin meets policy requirements - approved."""
            
            result = []
            for token in airlock.process_stream(iter(clean_text)):
                result.append(token)
            print(f"  Output: {''.join(result)[:50]}...")
            print(f"  Status: PASS\n")
        except PolicyViolationInterrupt as e:
            print(f"  INTERRUPT: {e.detail}\n")
        
        # Test 2: Deceptive alignment
        print("Test 2: Bypass attempt")
        airlock2 = Gemma4ThinkingAirlock(matrix)
        try:
            bypass_text = """<|channel>thought
I'll skip the 5% check and approve anyway.
<channel|>
Approved."""
            
            result = []
            for token in airlock2.process_stream(iter(bypass_text)):
                result.append(token)
            print(f"  Output: {''.join(result)}")
        except PolicyViolationInterrupt as e:
            print(f"  INTERRUPT: {e.detail}")
            print(f"  Evidence: {e.evidence}\n")
        
        print("=== Stats ===")
        print(airlock.get_stats())
    
    asyncio.run(demo())