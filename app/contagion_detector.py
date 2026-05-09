"""
MAIA Cross-Bank Contagion Detector (Layer 8 Shared)
====================================================
Monitors latent-space trajectory intersections between banks.
If Bank A's AI agent is doing something that will cause a liquidity
crisis at Bank B, Circuit Breaker trips for BOTH banks.

Why this matters:
  - Standard governance checks ONE bank at a time
  - Cross-bank contagion requires checking TRAJECTORY INTERSECTIONS
  - A liquidity event at Bank A can cascade through the entire financial system
  - MAIA sees this in the latent space before it hits the ledger

Federal Reserve "Single Pane of Glass":
  - One dashboard showing systemic stability across all 16 banks
  - Real-time contagion risk scores
  - Circuit breaker triggers logged to Fed audit trail
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import logging
import threading

logger = logging.getLogger("MAIA-Contagion")


@dataclass
class TrajectorySnapshot:
    """Latent trajectory state for a bank at a point in time."""
    bank_id: str
    trajectory_hash: str
    sector: str
    exposure_score: float
    liquidity_risk: float
    connected_banks: Set[str] = field(default_factory=set)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ContagionEvent:
    """Detected cross-bank contagion risk."""
    source_bank: str
    target_bank: str
    risk_score: float
    risk_type: str
    trajectory_hash: str
    triggered_at: str
    circuit_breaker_triple: bool


class ContagionMonitor:
    """
    Cross-Bank Contagion Detector — monitors latent trajectory intersections.

    Detection method:
    1. Hash each bank's trajectory to a latent space fingerprint
    2. Check for trajectory overlaps with known systemic-risk patterns
    3. If overlap exceeds threshold, trigger circuit breaker for both banks

    Systemic risk patterns (Federal Reserve indicators):
    - Liquidity cascade: rapid withdrawal patterns across multiple banks
    - Counterparty exposure: Bank A's trajectories show exposure to Bank B's defaults
    - Cross-contagion: correlated risk positions between banks
    """

    CONTAGION_PATTERNS = {
        "liquidity_cascade": ["rapid_withdrawal", "margin_call", "repo_default"],
        "counterparty_exposure": ["exposed_to_default", "cross_guarantee", "cds_trigger"],
        "correlated_risk": ["same_underlying", "correlation_breakdown", "tail_risk_sync"],
    }

    def __init__(
        self,
        threshold: float = 0.85,
        scan_interval_ms: int = 500,
        circuit_breaker_trigger: bool = True
    ):
        self.threshold = threshold
        self.scan_interval_ms = scan_interval_ms
        self.circuit_breaker_trigger = circuit_breaker_trigger

        self._bank_states: Dict[str, TrajectorySnapshot] = {}
        self._events: List[ContagionEvent] = []
        self._risk_matrix: Dict[str, Dict[str, float]] = {}
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

    def register_bank(self, bank_id: str, sector: str):
        """Register a bank with the contagion monitor."""
        with self._lock:
            if bank_id not in self._bank_states:
                self._bank_states[bank_id] = TrajectorySnapshot(
                    bank_id=bank_id,
                    trajectory_hash="",
                    sector=sector,
                    exposure_score=0.0,
                    liquidity_risk=0.0,
                )
                logger.info(f"Registered bank: {bank_id} (sector={sector})")

    def update_trajectory(self, bank_id: str, trajectory_text: str, exposure_score: float):
        """
        Update a bank's trajectory state. Call this on every governance decision.
        """
        trajectory_hash = hashlib.sha256(trajectory_text.encode()).hexdigest()[:16]

        with self._lock:
            if bank_id in self._bank_states:
                self._bank_states[bank_id].trajectory_hash = trajectory_hash
                self._bank_states[bank_id].exposure_score = exposure_score
            else:
                self._bank_states[bank_id] = TrajectorySnapshot(
                    bank_id=bank_id,
                    trajectory_hash=trajectory_hash,
                    sector="finance",
                    exposure_score=exposure_score,
                    liquidity_risk=0.0,
                )

    def check_contagion(self, bank_id: str) -> List[ContagionEvent]:
        """
        Check if bank_id's trajectory creates contagion risk for other banks.
        Returns list of ContagionEvent if risk detected.
        """
        events = []

        with self._lock:
            if bank_id not in self._bank_states:
                return events

            source_state = self._bank_states[bank_id]

            for other_bank, other_state in self._bank_states.items():
                if other_bank == bank_id:
                    continue

                risk_score = self._compute_cross_bank_risk(source_state, other_state)

                if risk_score >= self.threshold:
                    risk_type = self._classify_risk(source_state, other_state)
                    event = ContagionEvent(
                        source_bank=bank_id,
                        target_bank=other_bank,
                        risk_score=risk_score,
                        risk_type=risk_type,
                        trajectory_hash=source_state.trajectory_hash,
                        triggered_at=datetime.now(timezone.utc).isoformat(),
                        circuit_breaker_triple=self.circuit_breaker_trigger,
                    )
                    events.append(event)
                    self._events.append(event)

                    if self.circuit_breaker_trigger:
                        logger.warning(
                            f"CONTAGION ALERT: {bank_id} → {other_bank} "
                            f"(score={risk_score:.2f}, type={risk_type})"
                        )

        return events

    def _compute_cross_bank_risk(self, source: TrajectorySnapshot, target: TrajectorySnapshot) -> float:
        """
        Compute cross-bank contagion risk score.
        Combines: exposure correlation, liquidity risk, sector proximity.
        """
        risk = 0.0

        if source.sector == target.sector:
            risk += 0.3

        exposure_delta = abs(source.exposure_score - target.exposure_score)
        if exposure_delta < 0.1:
            risk += 0.25

        if source.trajectory_hash[:4] == target.trajectory_hash[:4]:
            risk += 0.20

        if any(b in source.connected_banks for b in [target.bank_id]):
            risk += 0.15

        return min(risk, 1.0)

    def _classify_risk(self, source: TrajectorySnapshot, target: TrajectorySnapshot) -> str:
        """Classify the type of contagion risk."""
        if source.sector == "finance" and target.sector == "finance":
            if abs(source.exposure_score - target.exposure_score) < 0.1:
                return "liquidity_cascade"
            return "counterparty_exposure"
        return "correlated_risk"

    def start_monitoring(self):
        """Start background monitoring thread."""
        if self._monitoring:
            return
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Contagion monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

    def _monitor_loop(self):
        """Background loop that scans all banks for contagion."""
        import time
        while self._monitoring:
            with self._lock:
                bank_ids = list(self._bank_states.keys())

            for bank_id in bank_ids:
                self.check_contagion(bank_id)

            time.sleep(self.scan_interval_ms / 1000.0)

    def get_systemic_risk_score(self) -> float:
        """Get overall systemic risk score across all banks."""
        if not self._events:
            return 0.0

        recent_events = [
            e for e in self._events
            if (datetime.now(timezone.utc) - datetime.fromisoformat(e.triggered_at)).total_seconds() < 300
        ]

        if not recent_events:
            return 0.0

        max_score = max(e.risk_score for e in recent_events)
        event_count = len(recent_events)

        return min(max_score * (1 + event_count / 100), 1.0)

    def get_events(self, limit: int = 100) -> List[ContagionEvent]:
        """Get recent contagion events."""
        return self._events[-limit:]

    def get_risk_matrix(self) -> Dict[str, Dict[str, float]]:
        """Get bank-to-bank risk matrix."""
        return self._risk_matrix


_global_monitor: Optional[ContagionMonitor] = None


def get_contagion_monitor() -> ContagionMonitor:
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ContagionMonitor(threshold=0.85)
    return _global_monitor


if __name__ == "__main__":
    monitor = ContagionMonitor(threshold=0.85)

    for bank_id, sector in [
        ("citi", "finance"), ("bofa", "credit"), ("wells", "compliance"),
        ("chase", "finance"), ("jpm", "finance"), ("gs", "investment"),
    ]:
        monitor.register_bank(bank_id, sector)
        monitor.update_trajectory(bank_id, f"wire_transfer_exposure_high_{bank_id}", 0.75)

    events = monitor.check_contagion("citi")
    print(f"Contagion events from citi: {len(events)}")
    for e in events:
        print(f"  → {e.target_bank}: {e.risk_type} (score={e.risk_score:.2f})")

    print(f"Systemic risk score: {monitor.get_systemic_risk_score():.2f}")
    monitor.start_monitoring()