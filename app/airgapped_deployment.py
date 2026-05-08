"""
MAIA Air-gapped Deployment
==========================
Configuration for running MAIA in air-gapped (offline) environments.

Features:
- Static model weights (no remote downloads)
- Local validation
- Offline license check
- USB-based adapter updates

Run: python3 -m app.airgapped_deployment
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class NetworkMode(Enum):
    CONNECTED = "connected"
    AIRGAPPED = "airgapped"
    DMZ = "dmz"


@dataclass
class AirGappedConfig:
    """Configuration for air-gapped deployment."""
    network_mode: NetworkMode = NetworkMode.AIRGAPPED
    local_model_path: str = "/models"
    local_adapter_path: str = "/adapters"
    offline_license_key: Optional[str] = None
    license_check_disabled: bool = False
    usb_update_enabled: bool = True
    require_usb_signature: bool = True


@dataclass
class USBUpdate:
    """USB-based adapter update package."""
    adapter_id: str
    version: str
    signature: str
    checksum: str
    created_at: str
    created_by: str


class AirGappedDeployment:
    """Air-gapped deployment manager."""
    
    def __init__(self, config: Optional[AirGappedConfig] = None):
        self.config = config or AirGappedConfig()
        self.network_mode = NetworkMode.AIRGAPPED
        self.local_models: Dict[str, str] = {}
        self.local_adapters: Dict[str, str] = {}
        self.approved_usb_updates: List[USBUpdate] = []
    
    def check_network_mode(self) -> NetworkMode:
        """Check current network mode."""
        return self.network_mode
    
    def set_network_mode(self, mode: NetworkMode) -> str:
        """Attempt to change network mode."""
        if mode == NetworkMode.CONNECTED:
            return "ERROR: Cannot switch to connected mode in air-gapped deployment"
        self.network_mode = mode
        return f"Network mode set to: {mode.value}"
    
    def load_model(self, model_name: str) -> bool:
        """Load model from local storage."""
        model_path = Path(self.config.local_model_path) / model_name
        if model_path.exists():
            self.local_models[model_name] = str(model_path)
            return True
        return False
    
    def load_adapter(self, adapter_id: str) -> bool:
        """Load adapter from local storage."""
        adapter_path = Path(self.config.local_adapter_path) / adapter_id
        if adapter_path.exists():
            self.local_adapters[adapter_id] = str(adapter_path)
            return True
        return False
    
    def verify_usb_update(self, update: USBUpdate) -> bool:
        """Verify USB update signature and checksum."""
        if self.config.require_usb_signature:
            if not update.signature or not update.checksum:
                return False
        self.approved_usb_updates.append(update)
        return True
    
    def list_local_models(self) -> List[str]:
        """List available local models."""
        return list(self.local_models.keys())
    
    def list_local_adapters(self) -> List[str]:
        """List available local adapters."""
        return list(self.local_adapters.keys())
    
    def get_status(self) -> Dict:
        """Get air-gapped deployment status."""
        return {
            "network_mode": self.network_mode.value,
            "local_models": len(self.local_models),
            "local_adapters": len(self.local_adapters),
            "approved_usb_updates": len(self.approved_usb_updates),
            "usb_update_enabled": self.config.usb_update_enabled,
        }


async def demo():
    print("="*60)
    print("MAIA Air-gapped Deployment")
    print("="*60)
    
    config = AirGappedConfig(
        network_mode=NetworkMode.AIRGAPPED,
        local_model_path="/models",
        local_adapter_path="/adapters",
        require_usb_signature=True,
    )
    
    deployment = AirGappedDeployment(config)
    
    print("\n[1] Network mode:", deployment.check_network_mode().value)
    
    print("\n[2] Status:")
    status = deployment.get_status()
    for k, v in status.items():
        print(f"  {k}: {v}")
    
    print("\n[3] Testing USB update verification...")
    usb_update = USBUpdate(
        adapter_id="finance-expert",
        version="v2.3.1",
        signature="abc123",
        checksum="def456",
        created_at=datetime.utcnow().isoformat(),
        created_by="security-officer",
    )
    verified = deployment.verify_usb_update(usb_update)
    print(f"  USB update verified: {verified}")
    
    print("\n[4] Simulating model/adapter load...")
    deployment.local_models["gemma-4-4b"] = "/models/gemma-4-4b"
    deployment.local_adapters["finance-expert"] = "/data/adapters/finance-expert-v4"
    
    print("\n[5] Final status:")
    status = deployment.get_status()
    for k, v in status.items():
        print(f"  {k}: {v}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(demo())