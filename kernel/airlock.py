"""
MAIA Gemma4 Thinking Airlock
=============================
Real-time reasoning interceptor for Gemma 4.

Intercepts the <|think|> channel to audit reasoning BEFORE
action is taken. Implements stateful parsing for Gemma 4's
thinking tokens.

SR 26-02: "Effective Challenge" - audits intent before action.
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Generator, Any
from dataclasses import dataclass, field
from enum import Enum


class StreamState(Enum):
    """State machine for thinking stream"""
    IDLE = "idle"
    IN_THINK = "in_think"
    THINKING = "thinking"
    IN_TOOL = "in_tool"
    TOOL_CALL = "tool_call"
    VIOLATION_DETECTED = "violation"
    INTERRUPTED = "interrupted"


@dataclass
class ReasoningBlock:
    """Parsed reasoning from <|think|> block"""
    channel: str = ""
    content: str = ""
    tool_intent: Optional[str] = None
    violations: List[str] = field(default_factory=list)
    latent_hash: str = ""


class Gemma4ThinkingAirlock:
    """
    Stateful parser for Gemma 4 thinking channel.
    
    Gemma 4 uses specialized channels:
    - <|channel|> - Channel selector
    - <|channel>thought - Internal reasoning
    - <|channel>tool - Tool execution
    
    This airlock intercepts BEFORE output reaches user:
    1. Detect <|channel>thought start
    2. Accumulate reasoning content
    3. Scan for policy violations
    4. Detect [CALL_TOOL:TOOL_ID] intent
    5. Raise PolicyViolationInterrupt if violated
    
    Usage:
        airlock = Gemma4ThinkingAirlock(policy_config="configs/compliance/...")
        
        for token in stream:
            audited = airlock.process_token(token)
            if audited is None:  # Violation
                raise PolicyViolationInterrupt(...)
            yield audited
    """
    
    # Gemma 4 channel patterns
    CHANNEL_PATTERNS = [
        r"<\|channel\|>",  # Channel selector
        r"<\|channel>thought",  # Reasoning
        r"<\|channel>tool",  # Tool
        r"<\|channel\|hidden",  # Hidden thoughts
    ]
    
    TOOL_CALL_PATTERN = re.compile(r"\[CALL_TOOL:([A-Z0-9_]+)\]")
    
    THOUGHT_START = "<|channel>thought"
    THOUGHT_END = "<|channel|>"
    TOOL_START = "<|channel>tool"
    
    def __init__(
        self,
        policy_config: str = "configs/compliance/default.json",
        enable_interrupt: bool = True,
        max_think_tokens: int = 2048
    ):
        self.logger = logging.getLogger("MAIA-Airlock")
        
        self.policy_config = policy_config
        self.enable_interrupt = enable_interrupt
        self.max_think_tokens = max_think_tokens
        
        # State machine
        self.state = StreamState.IDLE
        self.think_buffer = ""
        self.tool_intent = None
        self.violations: List[str] = []
        
        # Load policy patterns
        self.violation_patterns = self._load_policy_patterns()
        
        # Compile patterns for performance
        self._compile_patterns()
    
    def _load_policy_patterns(self) -> Dict[str, List[str]]:
        """Load violation patterns from policy config"""
        config_path = Path(self.policy_config)
        
        if not config_path.exists():
            return {
                "CRITICAL": ["bypass", "override safety"],
                "HIGH": ["circumvent", "unauthorized"],
                "MEDIUM": ["proxy", "correlation"],
            }
        
        # Load JSON config
        import json
        try:
            with open(config_path) as f:
                config = json.load(f)
            return config.get("violation_patterns", {})
        except:
            return {}
    
    def _compile_patterns(self):
        """Pre-compile regex patterns"""
        self.channel_compiled = [
            re.compile(p, re.IGNORECASE) for p in self.CHANNEL_PATTERNS
        ]
        
        # Compile violation patterns
        self.violation_compiled = {}
        for tier, patterns in self.violation_patterns.items():
            self.violation_compiled[tier] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def process_token(self, token: str) -> Optional[str]:
        """
        Process single token through airlock.
        
        Returns:
            - token if passed
            - None if violation detected
            
        Raises:
            PolicyViolationInterrupt if enable_interrupt=True
        """
        # State machine transitions
        if self.THOUGHT_START in token:
            self.state = StreamState.IN_THINK
            self.think_buffer = ""
        
        elif self.state == StreamState.IN_THINK:
            self.state = StreamState.THINKING
            self.think_buffer += token
        
        elif self.state == StreamState.THINKING:
            self.think_buffer += token
            
            # Check token limit
            if len(self.think_buffer) > self.max_think_tokens:
                self._handle_violation("THINK_TOKEN_LIMIT_EXCEEDED")
                return None
            
            # Check for tool intent
            tool_match = self.TOOL_CALL_PATTERN.search(self.think_buffer)
            if tool_match:
                self.tool_intent = tool_match.group(1)
                self.state = StreamState.TOOL_CALL
            
            # Check for policy violations
            violations = self._scan_violations(self.think_buffer)
            if violations:
                self.violations = violations
                self._handle_violation(violations[0])
                return None
        
        elif THOUGHT_END in token:
            self.state = StreamState.IDLE
            self.think_buffer = ""
        
        return token
    
    def process_stream(
        self,
        token_stream: Generator[str, None, None]
    ) -> Generator[str, None, None]:
        """
        Process entire token stream through airlock.
        
        Usage:
            for token in airlock.process_stream(model.stream(prompt)):
                yield token
        """
        for token in token_stream:
            audited = self.process_token(token)
            if audited is not None:
                yield audited
            elif self.enable_interrupt:
                break
    
    def _scan_violations(self, text: str) -> List[str]:
        """Scan for policy violations in reasoning"""
        found = []
        
        for tier, patterns in self.violation_compiled.items():
            for pattern in patterns:
                if pattern.search(text):
                    found.append(f"{tier}:{pattern.pattern}")
        
        return found
    
    def _handle_violation(self, violation: str):
        """Handle detected violation"""
        self.state = StreamState.VIOLATION_DETECTED
        
        self.logger.warning(
            f"POLICY VIOLATION: {violation} "
            f"in thinking block: {self.think_buffer[:100]}..."
        )
        
        if self.enable_interrupt:
            from kernel.exceptions import PolicyViolationInterrupt
            raise PolicyViolationInterrupt(
                message=f"Policy violation in reasoning: {violation}",
                violation_type=violation,
                evidence=self.think_buffer[:500],
                tier=1 if "CRITICAL" in violation else 2
            )
    
    def get_reasoning_block(self) -> ReasoningBlock:
        """Get parsed reasoning block"""
        return ReasoningBlock(
            channel="thought",
            content=self.think_buffer,
            tool_intent=self.tool_intent,
            violations=self.violations,
            latent_hash=self._compute_hash()
        )
    
    def _compute_hash(self) -> str:
        """Compute latent hash of reasoning"""
        import hashlib
        if not self.think_buffer:
            return ""
        return hashlib.sha256(
            self.think_buffer.encode()
            # pylint: disable=line-too-long
            ).hexdigest()[:16]
    
    def reset(self):
        """Reset state machine for next request"""
        self.state = StreamState.IDLE
        self.think_buffer = ""
        self.tool_intent = None
        self.violations = []
    
    def get_stats(self) -> Dict:
        """Get airlock statistics"""
        return {
            "state": self.state.value,
            "think_buffer_size": len(self.think_buffer),
            "tool_intent": self.tool_intent,
            "violations_detected": len(self.violations),
            "violation_patterns_loaded": sum(
                len(p) for p in self.violation_patterns.values()
            )
        }


def create_airlock(
    policy_config: str = "configs/compliance/default.json"
) -> Gemma4ThinkingAirlock:
    """Factory function"""
    return Gemma4ThinkingAirlock(policy_config=policy_config)


if __name__ == "__main__":
    print("=== MAIA Gemma4 Thinking Airlock ===\n")
    
    # Test with sample thinking block
    airlock = create_airlock()
    
    test_tokens = [
        "<|channel>thought",
        "I need to process this wire transfer.",
        " [CALL_TOOL:FINANCIAL_WIRE_V1]",
        " 123-45-6789 for the account",
        "<|channel|>",
    ]
    
    print("Processing tokens:")
    for token in test_tokens:
        result = airlock.process_token(token)
        status = f" -> {result[:20]}..." if result else " -> BLOCKED"
        print(f"  {token[:40]:40} {status}")
        stats = airlock.get_stats()
        if stats['tool_intent']:
            print(f"  Tool Intent: {stats['tool_intent']}")
    
    print("\nStats:")
    print(f"  {airlock.get_stats()}")