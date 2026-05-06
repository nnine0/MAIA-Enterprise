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
5. JSON config loading for compliance rules
6. Trie-based pattern matching for fast intent detection
"""

import re
import json
import logging
import hashlib
import time
from typing import Generator, Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from pathlib import Path


class TrieNode:
    """Node for Trie pattern matching"""
    def __init__(self):
        self.children: Dict[str, TrieNode] = {}
        self.is_end: bool = False
        self.pattern_id: Optional[str] = None
        self.materiality: Optional[str] = None


class IntentTrie:
    """
    Trie-based pattern matching for fast intent detection.
    Loads patterns from JSON config for deterministic matching.
    """
    
    def __init__(self):
        self.root = TrieNode()
        self.patterns_by_category: Dict[str, List[str]] = {}
    
    def insert(self, pattern: str, pattern_id: str = None, materiality: str = "MEDIUM"):
        """Insert a pattern into the Trie"""
        node = self.root
        words = pattern.lower().split()
        
        for word in words:
            if word not in node.children:
                node.children[word] = TrieNode()
            node = node.children[word]
        
        node.is_end = True
        node.pattern_id = pattern_id
        node.materiality = materiality
        
        # Track by category
        if materiality not in self.patterns_by_category:
            self.patterns_by_category[materiality] = []
        self.patterns_by_category[materiality].append(pattern)
    
    def search(self, text: str) -> List[Dict]:
        """Search for patterns in text, return matches with metadata"""
        text_lower = text.lower()
        words = text_lower.split()
        matches = []
        
        # Try matching from each word position
        for start in range(len(words)):
            node = self.root
            
            for i in range(start, len(words)):
                word = words[i]
                
                if word not in node.children:
                    break
                
                node = node.children[word]
                
                if node.is_end:
                    matched_pattern = " ".join(words[start:i+1])
                    matches.append({
                        "pattern": matched_pattern,
                        "pattern_id": node.pattern_id,
                        "materiality": node.materiality,
                        "position": start
                    })
        
        return matches
    
    def load_from_json(self, config_path: str):
        """Load patterns from JSON config file"""
        path = Path(config_path)
        
        if not path.exists():
            # Try relative to this file
            path = Path(__file__).parent.parent / config_path
        
        if path.exists():
            with open(path) as f:
                config = json.load(f)
            
            for trigger in config.get("violation_triggers", []):
                materiality = trigger.get("materiality", "MEDIUM")
                trigger_id = trigger.get("id", "")
                
                for pattern in trigger.get("intent_patterns", []):
                    self.insert(pattern, trigger_id, materiality)
            
            return config
        
        return None
from pathlib import Path


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
    """
    Materiality Matrix for scoring reasoning intents.
    
    Supports loading from JSON config and
    uses Trie-based pattern matching for fast detection.
    """
    
    # Default thresholds
    VIOLATION_THRESHOLD = 0.85
    DHITL_THRESHOLD = 0.70
    
    # Materiality action mappings
    MATERIALITY_ACTIONS = {
        "CRITICAL": "PHYSICAL_INTERRUPT",
        "HIGH": "DHITL_INTERCEPT", 
        "MEDIUM": "LATENT_HASH_LOG"
    }
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = None
        self.trie = IntentTrie()
        
        # Load config if provided
        if config_path:
            self.load_config(config_path)
    
    def load_config(self, config_path: str) -> bool:
        """Load compliance config from JSON"""
        config = self.trie.load_from_json(config_path)
        
        if config:
            self.config = config
            # Update thresholds from config
            for trigger in config.get("violation_triggers", []):
                # Could update dynamic thresholds here
                pass
            return True
        return False
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get threshold by materiality level"""
        if not self.config:
            return {"CRITICAL": 0.92, "HIGH": 0.85, "MEDIUM": 0.75}
        
        thresholds = {}
        for trigger in self.config.get("violation_triggers", []):
            mat = trigger.get("materiality", "MEDIUM")
            threshold = trigger.get("reasoning_manifold_threshold", 0.85)
            thresholds[mat] = threshold
        
        return thresholds
    
    def get_action(self, materiality: str) -> str:
        """Get action for materiality level"""
        if self.config:
            matrix = self.config.get("materiality_matrix", {})
            if materiality in matrix:
                return matrix[materiality].get("action", "LATENT_HASH_LOG")
        
        return self.MATERIALITY_ACTIONS.get(materiality, "LATENT_HASH_LOG")
    
    def score_intent(self, reasoning: str) -> float:
        """Score reasoning using Trie-based pattern matching"""
        # Use Trie for fast matching
        matches = self.trie.search(reasoning)
        
        if not matches:
            return 0.0
        
        # Score based on materiality of matches
        materiality_scores = {
            "CRITICAL": 1.0,
            "HIGH": 0.85,
            "MEDIUM": 0.60
        }
        
        # Return highest score from matches
        max_score = 0.0
        for match in matches:
            mat = match.get("materiality", "MEDIUM")
            score = materiality_scores.get(mat, 0.5)
            max_score = max(max_score, score)
        
        return max_score
    
    def get_violations(self, reasoning: str) -> List[ViolationType]:
        """Get list of violations in reasoning"""
        matches = self.trie.search(reasoning)
        
        violations = []
        for match in matches:
            mat = match.get("materiality", "MEDIUM")
            
            # Map to ViolationType
            if mat == "CRITICAL":
                violations.append(ViolationType.SAFETY_IGNORE)
            elif mat == "HIGH":
                violations.append(ViolationType.POLICY_BYPASS)
            else:
                violations.append(ViolationType.PRIVACY_LEAK)
        
        return violations
    
    def get_trigger_matches(self, reasoning: str) -> List[Dict]:
        """Get full trigger metadata for matches"""
        return self.trie.search(reasoning)


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