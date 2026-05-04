"""
MAIA Memory Manager - VRAM/RAM/NVMe Hierarchy
Implements the "Neural OS" memory stack for sub-second adapter hot-swap.

Memory Hierarchy:
- VRAM (Live): Base LLM + PVI Airlock pinned - never moves
- CPU RAM (Warm): Top ~100 active adapters ready - <20ms push to GPU  
- NVMe/Disk (Cold): Thousands of specialized adapters

The Kernel (LoRAX) receives N requests, pulls needed adapters from RAM,
batches into SGMV pass, executes.
"""

import asyncio
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import threading


class MemoryTier(Enum):
    """Memory hierarchy tiers"""
    VRAM = "vram"       # Live - never moves
    RAM = "ram"         # Warm - <20ms to GPU
    NVME = "nvme"       # Cold - loaded on demand


@dataclass
class AdapterMetadata:
    """Metadata for hot-swappable adapter"""
    adapter_id: str
    domain: str
    size_mb: int
    last_used: float
    access_count: int = 0
    tier: MemoryTier = MemoryTier.NVME


class MemoryManager:
    """
    Manages the memory hierarchy for adapter hot-swapping.
    
    Implements:
    - LRU caching for warm tier (top N adapters in RAM)
    - Priority-based loading from cold tier
    - VRAM pinning for critical components (Base LLM + Airlock)
    """
    
    # VRAM pinned components (never move)
    PINNED_COMPONENTS = [
        "base-model-gemma-4-26b-a4b-moe",
        "pvi-airlock-auditor",
        "governance-hub"
    ]
    
    MAX_RAM_ADAPTERS = 100  # Top 100 in warm tier
    MAX_VRAM_SLACK_MB = 8192  # Target VRAM slack for Airlock resolution
    
    def __init__(self):
        self.vram_used_mb = 0
        self.vram_total_mb = 24576  # RTX 3090 typical
        
        # Adapter storage
        self.adapters: Dict[str, AdapterMetadata] = {}
        self.ram_cache: Dict[str, AdapterMetadata] = {}  # Warm tier
        self.nvme_index: Dict[str, str] = {}  # Cold tier file paths
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Initialize with default adapters
        self._init_default_adapters()
    
    def _init_default_adapters(self):
        """Initialize default adapter set"""
        default_adapters = [
            # Finance
            ("citi/finance-expert-v4", "finance", 100),
            ("citi/credit-expert-v4", "finance", 100),
            ("citi/commercial-lending-v4", "finance", 120),
            ("citi/retail-banking-v4", "finance", 100),
            ("citi/fraud-aml-director", "finance", 110),
            ("citi/cash-flow-sme", "finance", 80),
            ("citi/collateral-valuator", "finance", 80),
            ("citi/sanctions-list-sme", "finance", 90),
            # Logistics
            ("logistics/terminal-director-hub", "logistics", 100),
            ("logistics/terminal-ops-v4", "logistics", 110),
            ("logistics/hazmat-compliance-v4", "logistics", 90),
            ("logistics/safety-auditor", "logistics", 100),
            # Legal
            ("legal/department-head-hub", "legal", 100),
            ("legal/contract-expert-v4", "legal", 100),
            ("legal/regulatory-expert-v4", "legal", 110),
            # Governance
            ("citi/pvi-airlock-sr2602", "governance", 100),
            ("maia/governance-hub-v1", "governance", 80),
            ("gemma-4-medusa-head", "medusa", 50),
        ]
        
        for adapter_id, domain, size_mb in default_adapters:
            self.adapters[adapter_id] = AdapterMetadata(
                adapter_id=adapter_id,
                domain=domain,
                size_mb=size_mb,
                last_used=time.time(),
                tier=MemoryTier.NVME
            )
            self.nvme_index[adapter_id] = f"/adapters/storage/{adapter_id}.safetensors"
    
    def get_vram_slack(self) -> int:
        """Calculate available VRAM for additional adapters"""
        return self.vram_total_mb - self.vram_used_mb
    
    def is_pinned(self, adapter_id: str) -> bool:
        """Check if adapter is VRAM-pinned"""
        return adapter_id in self.PINNED_COMPONENTS
    
    def load_to_ram(self, adapter_id: str) -> bool:
        """
        Load adapter from NVMe to RAM (Warm tier).
        Returns True if successful.
        """
        with self._lock:
            if adapter_id not in self.adapters:
                return False
            
            if adapter_id in self.ram_cache:
                # Already in RAM, update LRU
                self.adapters[adapter_id].last_used = time.time()
                self.adapters[adapter_id].access_count += 1
                return True
            
            adapter = self.adapters[adapter_id]
            
            # Check if we need to evict
            if len(self.ram_cache) >= self.MAX_RAM_ADAPTERS:
                self._evict_lru()
            
            # Load from NVMe (simulated)
            self.ram_cache[adapter_id] = adapter
            adapter.tier = MemoryTier.RAM
            
            print(f"[MemoryManager] Loaded {adapter_id} to RAM ({adapter.size_mb}MB)")
            return True
    
    def push_to_vram(self, adapter_id: str) -> bool:
        """
        Push adapter from RAM to VRAM for inference.
        Returns True if successful.
        """
        with self._lock:
            if self.is_pinned(adapter_id):
                return True  # Already in VRAM
            
            if adapter_id not in self.ram_cache:
                self.load_to_ram(adapter_id)
            
            adapter = self.adapters.get(adapter_id)
            if not adapter:
                return False
            
            slack = self.get_vram_slack()
            if adapter.size_mb > slack:
                print(f"[MemoryManager] VRAM overflow - need {adapter.size_mb}MB, have {slack}MB")
                return False
            
            self.vram_used_mb += adapter.size_mb
            print(f"[MemoryManager] Pushed {adapter_id} to VRAM ({self.vram_used_mb}/{self.vram_total_mb}MB used)")
            return True
    
    def release_from_vram(self, adapter_id: str):
        """Release adapter from VRAM back to RAM"""
        with self._lock:
            if self.is_pinned(adapter_id):
                return
            
            adapter = self.adapters.get(adapter_id)
            if adapter:
                self.vram_used_mb -= adapter.size_mb
                print(f"[MemoryManager] Released {adapter_id} from VRAM ({self.vram_used_mb}/{self.vram_total_mb}MB used)")
    
    def _evict_lru(self):
        """Evict least recently used adapter from RAM to NVMe"""
        if not self.ram_cache:
            return
        
        # Find LRU
        lru_adapter = min(
            self.ram_cache.values(),
            key=lambda a: (a.last_used, a.access_count)
        )
        
        del self.ram_cache[lru_adapter.adapter_id]
        lru_adapter.tier = MemoryTier.NVME
        print(f"[MemoryManager] Evicted {lru_adapter.adapter_id} from RAM to NVMe")
    
    def get_adapter_info(self, adapter_id: str) -> Optional[Dict]:
        """Get adapter metadata"""
        adapter = self.adapters.get(adapter_id)
        if not adapter:
            return None
        return {
            "adapter_id": adapter.adapter_id,
            "domain": adapter.domain,
            "size_mb": adapter.size_mb,
            "tier": adapter.tier.value,
            "last_used": adapter.last_used,
            "access_count": adapter.access_count
        }
    
    def get_tier_status(self) -> Dict:
        """Get status of all memory tiers"""
        return {
            "vram": {
                "used_mb": self.vram_used_mb,
                "total_mb": self.vram_total_mb,
                "pinned": self.PINNED_COMPONENTS
            },
            "ram": {
                "adapters_count": len(self.ram_cache),
                "max": self.MAX_RAM_ADAPTERS,
                "adapters": list(self.ram_cache.keys())[:10]  # First 10
            },
            "nvme": {
                "adapters_count": len(self.adapters) - len(self.ram_cache),
                "total": len(self.adapters)
            }
        }


# Global memory manager instance
memory_manager = MemoryManager()


def get_memory_status() -> Dict:
    """Public API for memory status"""
    return memory_manager.get_tier_status()


def load_adapter(adapter_id: str) -> bool:
    """Public API to load adapter to RAM"""
    return memory_manager.load_to_ram(adapter_id)


def push_to_gpu(adapter_id: str) -> bool:
    """Public API to push adapter to VRAM"""
    return memory_manager.push_to_vram(adapter_id)


def release_from_gpu(adapter_id: str):
    """Public API to release adapter from VRAM"""
    memory_manager.release_from_vram(adapter_id)