"""
MAIA Global Context
=============
Central initialization for all MAIA components.
Handles dependency injection and global state management.
"""

from typing import Optional
from config import (
    LORAX_URL,
    LORAX_API_KEY,
    QDRANT_URL,
    BASE_MODEL_ID,
)


class MAIAContext:
    """
    Global MAIA context - all components initialized here.
    """
    
    def __init__(self):
        self._initialized = False
        self._components = {}
    
    def initialize(self):
        """Initialize all components"""
        if self._initialized:
            return
        
        # Initialize in dependency order:
        # 1. Config + base services (no dependencies)
        # 2. Core components
        # 3.Speculation components
        # 4. Governance components
        
        self._init_base_services()
        self._init_core()
        self._init_speculation()
        self._init_governance()
        
        self._initialized = True
    
    def _init_base_services(self):
        """Initialize base services (httpx, qdrant, openai)"""
        from openai import AsyncOpenAI
        from qdrant_client import AsyncQdrantClient
        import httpx
        
        self._components["openai"] = AsyncOpenAI(
            base_url=f"{LORAX_URL}/v1",
            api_key=LORAX_API_KEY
        )
        self._components["qdrant"] = AsyncQdrantClient(url=QDRANT_URL)
        self._components["httpx"] = httpx.AsyncClient(timeout=30.0)
    
    def _init_core(self):
        """Initialize core components"""
        from memory_manager import MemoryManager
        from materiality_matrix import create_materiality_matrix
        
        self._components["memory_manager"] = MemoryManager()
        self._components["materiality_matrix"] = create_materiality_matrix()
    
    def _init_speculation(self):
        """Initialize speculation components"""
        from speculation import (
            speculation_config,
            gpu_config,
            dflash_engine,
            saguaro_scheduler,
        )
        
        self._components["speculation_config"] = speculation_config
        self._components["gpu_config"] = gpu_config
        self._components["dflash_engine"] = dflash_engine
        self._components["saguaro_scheduler"] = saguaro_scheduler
    
    def _init_governance(self):
        """Initialize governance components"""
        from circuit_breaker import CircuitBreaker
        from airlock import PVIAirlock, SMEPool, RLHFTrainingData
        from supervisor_router import SupervisorRouter
        from training_guardrails import guardrails
        from dme_engine import dme_engine, maia_orchestrator
        from security import security_orchestrator, get_security_orchestrator
        
        self._components["circuit_breaker"] = CircuitBreaker()
        self._components["airlock"] = PVIAirlock()
        self._components["sme_pool"] = SMEPool()
        self._components["rlhf_data"] = RLHFTrainingData()
        self._components["supervisor_router"] = SupervisorRouter()
        self._components["dme_engine"] = dme_engine
        self._components["maia_orchestrator"] = maia_orchestrator
        self._components["training_guardrails"] = guardrails
        self._components["security_orchestrator"] = security_orchestrator
    
    def get(self, key: str):
        """Get component by name"""
        return self._components.get(key)
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    @property
    def memory_manager(self):
        return self._components.get("memory_manager")
    
    @property
    def materiality_matrix(self):
        return self._components.get("materiality_matrix")
    
    @property
    def circuit_breaker(self):
        return self._components.get("circuit_breaker")
    
    @property
    def airlock(self):
        return self._components.get("airlock")
    
    @property
    def supervisor_router(self):
        return self._components.get("supervisor_router")
    
    @property
    def training_guardrails(self):
        return self._components.get("training_guardrails")
    
    @property
    def speculation_config(self):
        return self._components.get("speculation_config")
    
    @property
    def dflash_engine(self):
        return self._components.get("dflash_engine")
    
    @property
    def saguaro_scheduler(self):
        return self._components.get("saguaro_scheduler")
    
    @property
    def dme_engine(self):
        return self._components.get("dme_engine")
    
    @property
    def maia_orchestrator(self):
        return self._components.get("maia_orchestrator")
    
    @property
    def security_orchestrator(self):
        return self._components.get("security_orchestrator")


# Global context instance
maia_context = MAIAContext()


def get_maia_context() -> MAIAContext:
    """Get the global MAIA context"""
    return maia_context


def initialize_maia():
    """Initialize MAIA - call at startup"""
    maia_context.initialize()
    return maia_context