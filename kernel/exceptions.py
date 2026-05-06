"""
MAIA Kernel Exceptions
========================
SR 26-02 compliance exceptions.
"""


class PolicyViolationInterrupt(Exception):
    """
    Raised when governance intercepts a policy violation.
    
    This is the "Kill Switch" - when detected in reasoning phase,
    immediately halts generation before user sees prohibited content.
    """
    
    def __init__(
        self,
        message: str,
        violation_type: str = "UNKNOWN",
        evidence: str = "",
        policy_id: str = "default",
        tier: int = 1
    ):
        super().__init__(message)
        self.violation_type = violation_type
        self.evidence = evidence
        self.policy_id = policy_id
        self.tier = tier
    
    def __str__(self):
        return f"[{self.violation_type}] {super().__str__()}"


class DHITLRequired(Exception):
    """
    Raised when transaction requires Human-in-the-Loop approval.
    
    TIER_1 (Critical) transactions cannot auto-proceed.
    """
    
    def __init__(self, message: str, requires_signatures: int = 1):
        super().__init__(message)
        self.requires_signatures = requires_signatures


class MaterialityThresholdExceeded(Exception):
    """
    Raised when query exceeds materiality threshold.
    
    Triggers circuit breaker for governance escalation.
    """
    
    def __init__(self, message: str, tier: int = 1, threshold: float = 0.0):
        super().__init__(message)
        self.tier = tier
        self.threshold = threshold


class ToolExecutionError(Exception):
    """Raised when tool execution fails"""
    
    def __init__(self, message: str, tool_id: str = ""):
        super().__init__(message)
        self.tool_id = tool_id


class ForensicsWriteError(Exception):
    """Raised when forensic logging fails"""
    pass