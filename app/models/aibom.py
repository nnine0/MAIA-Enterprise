"""
AIBOM Registry - AI Bill of Materials

Model inventory tracking with auto-tagging for SR 26-02 compliance.
"""

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path
from enum import Enum


class AdapterType(Enum):
    LORA = "lora"
    ADAPTER = "adapter"
    FULL_MODEL = "full_model"


@dataclass
class ModelCard:
    adapter_id: str
    name: str
    version: str
    domain: str
    materiality_tier: int
    base_model: str
    created_at: str
    description: str
    training_data_hash: Optional[str] = None
    performance_metrics: Optional[Dict] = None
    risk_flags: List[str] = field(default_factory=list)
    governance_controls: List[str] = field(default_factory=list)


@dataclass
class AIBOMEntry:
    adapter_id: str
    adapter_type: str
    model_card: ModelCard
    registry_timestamp: str
    provenance_hash: str
    active: bool = True
    deprecated_at: Optional[str] = None


class AIBOMRegistry:
    def __init__(self, registry_path: str = "aibom_registry.json"):
        self.registry_path = Path(registry_path)
        self._entries: Dict[str, AIBOMEntry] = {}
        self._load()

    def _load(self):
        if self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
                for entry in data.get('entries', []):
                    mc_data = entry.pop('model_card')
                    mc = ModelCard(**mc_data)
                    entry['model_card'] = mc
                    self._entries[entry['adapter_id']] = AIBOMEntry(**entry)

    def _save(self):
        data = {
            'entries': [
                {
                    **asdict(entry),
                    'model_card': asdict(entry.model_card)
                }
                for entry in self._entries.values()
            ]
        }
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)

    def register_adapter(
        self,
        adapter_id: str,
        name: str,
        version: str,
        domain: str,
        materiality_tier: int,
        base_model: str,
        description: str,
        training_data_hash: Optional[str] = None,
    ) -> AIBOMEntry:
        model_card = ModelCard(
            adapter_id=adapter_id,
            name=name,
            version=version,
            domain=domain,
            materiality_tier=materiality_tier,
            base_model=base_model,
            created_at=datetime.utcnow().isoformat(),
            description=description,
            training_data_hash=training_data_hash,
        )

        provenance_data = f"{adapter_id}:{name}:{version}:{materiality_tier}"
        provenance_hash = hashlib.sha256(provenance_data.encode()).hexdigest()[:16]

        entry = AIBOMEntry(
            adapter_id=adapter_id,
            adapter_type=AdapterType.LORA.value,
            model_card=model_card,
            registry_timestamp=datetime.utcnow().isoformat(),
            provenance_hash=provenance_hash,
        )

        self._entries[adapter_id] = entry
        self._save()
        return entry

    def tag_inference(self, adapter_id: str, query: str, materiality_tier: int) -> Dict:
        if adapter_id not in self._entries:
            raise ValueError(f"Adapter {adapter_id} not registered in AIBOM")

        entry = self._entries[adapter_id]
        inference_hash = hashlib.sha256(f"{query}:{adapter_id}".encode()).hexdigest()[:12]

        return {
            "adapter_id": adapter_id,
            "materiality_tier": materiality_tier,
            "model_card_version": entry.model_card.version,
            "inference_tag": f"{adapter_id}:{materiality_tier}:{inference_hash}",
            "provenance_hash": entry.provenance_hash,
        }

    def get_adapter(self, adapter_id: str) -> Optional[AIBOMEntry]:
        return self._entries.get(adapter_id)

    def list_adapters(self, active_only: bool = True) -> List[AIBOMEntry]:
        if active_only:
            return [e for e in self._entries.values() if e.active]
        return list(self._entries.values())

    def deprecate(self, adapter_id: str):
        if adapter_id in self._entries:
            self._entries[adapter_id].active = False
            self._entries[adapter_id].deprecated_at = datetime.utcnow().isoformat()
            self._save()


registry = AIBOMRegistry()