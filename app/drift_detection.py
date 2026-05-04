"""
Latent Drift Detection

Monitors model latent space for distribution shifts.
SR 26-02 Ongoing Monitoring compliance.
"""

import hashlib
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DriftMetrics:
    adapter_id: str
    timestamp: str
    kl_divergence: float
    earth_movers_distance: float
    latent_mean_shift: float
    latent_std_change: float
    confidence: float
    alert_triggered: bool = False


@dataclass
class LatentSnapshot:
    adapter_id: str
    timestamp: str
    latent_vector: List[float]
    query_hash: str
    materiality_tier: int


class DriftDetector:
    def __init__(
        self,
        window_size: int = 100,
        alert_threshold: float = 0.15,
        warmup_samples: int = 50,
        kafka_bootstrap: str = "localhost:9092",
        kafka_topic: str = "maia-latent-drift"
    ):
        self.window_size = window_size
        self.alert_threshold = alert_threshold
        self.warmup_samples = warmup_samples
        self.kafka_bootstrap = kafka_bootstrap
        self.kafka_topic = kafka_topic
        self._snapshots: Dict[str, deque] = {}
        self._baseline_stats: Dict[str, Dict] = {}
        self._kafka_available = False
        self._init_kafka()

    def _init_kafka(self):
        try:
            from kafka import KafkaProducer
            self._producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all'
            )
            self._kafka_available = True
            logger.info(f"Kafka producer connected to {self.kafka_bootstrap}")
        except Exception as e:
            logger.warning(f"Kafka not available: {e}. Using file-based logging.")
            self._kafka_available = False

    def _log_to_kafka(self, metrics: DriftMetrics):
        if not self._kafka_available:
            return
        try:
            self._producer.send(
                self.kafka_topic,
                value={
                    "adapter_id": metrics.adapter_id,
                    "timestamp": metrics.timestamp,
                    "kl_divergence": metrics.kl_divergence,
                    "earth_movers_distance": metrics.earth_movers_distance,
                    "latent_mean_shift": metrics.latent_mean_shift,
                    "latent_std_change": metrics.latent_std_change,
                    "confidence": metrics.confidence,
                    "alert_triggered": metrics.alert_triggered
                }
            )
        except Exception as e:
            logger.error(f"Failed to send to Kafka: {e}")

    def _compute_kl_divergence(self, p: np.ndarray, q: np.ndarray) -> float:
        p = np.clip(p, 1e-10, 1.0)
        q = np.clip(q, 1e-10, 1.0)
        return np.sum(p * np.log(p / q))

    def _compute_emd(self, p: np.ndarray, q: np.ndarray) -> float:
        p_sorted = np.sort(np.cumsum(p))
        q_sorted = np.sort(np.cumsum(q))
        return np.mean(np.abs(p_sorted - q_sorted))

    def record_latent(
        self,
        adapter_id: str,
        latent_vector: List[float],
        query: str,
        materiality_tier: int
    ) -> Optional[DriftMetrics]:
        if adapter_id not in self._snapshots:
            self._snapshots[adapter_id] = deque(maxlen=self.window_size)
            self._baseline_stats[adapter_id] = None

        query_hash = hashlib.sha256(query.encode()).hexdigest()[:12]
        snapshot = LatentSnapshot(
            adapter_id=adapter_id,
            timestamp=datetime.utcnow().isoformat(),
            latent_vector=latent_vector,
            query_hash=query_hash,
            materiality_tier=materiality_tier
        )

        self._snapshots[adapter_id].append(snapshot)

        if len(self._snapshots[adapter_id]) < self.warmup_samples:
            return None

        return self._compute_drift(adapter_id)

    def _compute_drift(self, adapter_id: str) -> DriftMetrics:
        snapshots = list(self._snapshots[adapter_id])
        latents = np.array([s.latent_vector for s in snapshots])

        current_window = latents[-self.warmup_samples:]
        baseline_window = latents[:self.warmup_samples]

        current_mean = np.mean(current_window, axis=0)
        baseline_mean = np.mean(baseline_window, axis=0)
        current_std = np.std(current_window, axis=0)
        baseline_std = np.std(baseline_window, axis=0)

        mean_shift = float(np.mean(np.abs(current_mean - baseline_mean)))
        std_change = float(np.mean(np.abs(current_std - baseline_std) / (baseline_std + 1e-8)))

        hist_current, _ = np.histogram(current_mean, bins=10, density=True)
        hist_baseline, _ = np.histogram(baseline_mean, bins=10, density=True)
        hist_current = hist_current / (np.sum(hist_current) + 1e-8)
        hist_baseline = hist_baseline / (np.sum(hist_baseline) + 1e-8)

        kl_div = self._compute_kl_divergence(hist_current, hist_baseline)
        emd = self._compute_emd(hist_current, hist_baseline)

        drift_score = (kl_div * 0.4 + mean_shift * 0.3 + std_change * 0.3)
        alert_triggered = drift_score > self.alert_threshold
        confidence = min(1.0, len(snapshots) / self.warmup_samples)

        metrics = DriftMetrics(
            adapter_id=adapter_id,
            timestamp=datetime.utcnow().isoformat(),
            kl_divergence=kl_div,
            earth_movers_distance=emd,
            latent_mean_shift=mean_shift,
            latent_std_change=std_change,
            confidence=confidence,
            alert_triggered=alert_triggered
        )

        self._log_to_kafka(metrics)

        if alert_triggered:
            logger.warning(f"DRIFT ALERT: {adapter_id} - score: {drift_score:.3f}")

        return metrics

    def get_status(self, adapter_id: str) -> Optional[Dict]:
        if adapter_id not in self._snapshots:
            return None

        snapshot_count = len(self._snapshots[adapter_id])
        warmup = "ready" if snapshot_count >= self.warmup_samples else f"{snapshot_count}/{self.warmup_samples}"

        return {
            "adapter_id": adapter_id,
            "sample_count": snapshot_count,
            "warmup_status": warmup,
            "kafka_connected": self._kafka_available
        }

    def reset_baseline(self, adapter_id: str):
        if adapter_id in self._snapshots:
            self._snapshots[adapter_id].clear()
            self._baseline_stats[adapter_id] = None
            logger.info(f"Baseline reset for {adapter_id}")


drift_detector = DriftDetector()