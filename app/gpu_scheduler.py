"""
MAIA GPU Scheduler - Inference Queue & VRAM Management

Manages GPU scheduling across concurrent requests:
- VRAM allocation per request
- Request queuing when GPUs are saturated
- Multi-GPU load balancing
- Priority-aware scheduling (TIER_1 > TIER_2 > TIER_3)
"""

import asyncio
import time
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class PriorityTier(Enum):
    """Request priority tiers (SR 26-02 aligned)"""
    TIER_1_CRITICAL = 1  # Wire transfers, contracts - immediate
    TIER_2_ELEVATED = 2  # Risk analysis, reports - <5s
    TIER_3_BENIGN = 3    # General queries - best effort


@dataclass
class GPURequest:
    """Single inference request"""
    request_id: str
    query: str
    priority: PriorityTier
    adapter_id: str
    vram_required_mb: int
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class GPUConfig:
    """Single GPU configuration"""
    gpu_id: str
    name: str
    total_vram_mb: int
    available_vram_mb: int
    current_load: float  # 0.0-1.0
    is_available: bool = True
    
    @property
    def utilization(self) -> float:
        return self.current_load
    
    @property
    def vram_used_percent(self) -> float:
        return (self.total_vram_mb - self.available_vram_mb) / self.total_vram_mb


class GPUScheduler:
    """
    GPU Scheduler with priority queueing.
    
    Features:
    - Priority-based scheduling (TIER_1 first)
    - VRAM-aware allocation
    - Multi-GPU load balancing
    - Request timeouts
    """
    
    # Fixed VRAM rent (always reserved for base model + Airlock)
    FIXED_VRAM_RENT_MB = 18200  # ~17.8GB
    
    # Max concurrent requests per GPU
    MAX_CONCURRENT_PER_GPU = 4
    
    def __init__(
        self,
        gpu_configs: List[Dict] = None,
        default_vram_mb: int = 24576
    ):
        self.gpus: Dict[str, GPUConfig] = {}
        self.request_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.active_requests: Dict[str, GPURequest] = {}
        self.completed_requests: Dict[str, GPURequest] = {}
        
        # Initialize GPUs
        if gpu_configs:
            for config in gpu_configs:
                self.add_gpu(**config)
        else:
            # Single GPU default
            self.add_gpu(
                gpu_id="gpu-0",
                name="NVIDIA GPU",
                total_vram_mb=default_vram_mb
            )
        
        # Start scheduler loop
        self._scheduler_task = None
        self._running = False
    
    def add_gpu(
        self,
        gpu_id: str,
        name: str,
        total_vram_mb: int = 24576
    ) -> None:
        """Register a GPU with the scheduler"""
        available = total_vram_mb - self.FIXED_VRAM_RENT_MB
        self.gpus[gpu_id] = GPUConfig(
            gpu_id=gpu_id,
            name=name,
            total_vram_mb=total_vram_mb,
            available_vram_mb=available,
            current_load=0.0,
            is_available=True
        )
        print(f"[Scheduler] Added GPU {gpu_id}: {total_vram_mb}MB total, {available}MB available")
    
    async def submit_request(
        self,
        query: str,
        adapter_id: str = "default",
        priority: PriorityTier = PriorityTier.TIER_3_BENIGN,
        vram_required_mb: int = 2048,
        timeout_seconds: float = 30.0
    ) -> str:
        """Submit inference request to queue"""
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        
        request = GPURequest(
            request_id=request_id,
            query=query,
            priority=priority,
            adapter_id=adapter_id,
            vram_required_mb=vram_required_mb
        )
        
        # Add to queue (priority, timestamp, request)
        priority_value = (priority.value, request.created_at, request)
        await self.request_queue.put(priority_value)
        
        print(f"[Scheduler] Submitted {request_id} (tier={priority.value}, vram={vram_required_mb}MB)")
        
        # Wait for completion or timeout
        try:
            result = await asyncio.wait_for(
                self._wait_for_request(request_id),
                timeout=timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            request.status = "timeout"
            request.error = f"Request timeout after {timeout_seconds}s"
            print(f"[Scheduler] {request_id} timed out")
            raise TimeoutError(f"Request {request_id} timed out after {timeout_seconds}s")
    
    async def _wait_for_request(self, request_id: str) -> str:
        """Wait for request to complete"""
        while True:
            if request_id in self.completed_requests:
                req = self.completed_requests[request_id]
                if req.error:
                    raise RuntimeError(req.error)
                return req.result
            await asyncio.sleep(0.01)
    
    async def schedule_loop(self) -> None:
        """Main scheduling loop - runs in background"""
        self._running = True
        
        while self._running:
            # Get next request from queue
            try:
                priority, timestamp, request = await asyncio.wait_for(
                    self.request_queue.get(),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                continue
            
            # Find available GPU
            gpu_id = self._find_available_gpu(request.vram_required_mb)
            
            if gpu_id:
                # Execute on GPU
                await self._execute_on_gpu(request, gpu_id)
            else:
                # Re-queue with lower priority (wait for GPU)
                priority_value = (request.priority.value + 1, time.time(), request)
                await self.request_queue.put(priority_value)
                await asyncio.sleep(0.1)
    
    def _find_available_gpu(self, vram_required_mb: int) -> Optional[str]:
        """Find GPU with enough VRAM for request"""
        for gpu_id, config in self.gpus.items():
            if not config.is_available:
                continue
            if config.available_vram_mb >= vram_required_mb:
                return gpu_id
        return None
    
    async def _execute_on_gpu(self, request: GPURequest, gpu_id: str) -> None:
        """Execute request on specified GPU"""
        gpu = self.gpus[gpu_id]
        
        # Mark request running
        request.status = "running"
        request.started_at = time.time()
        self.active_requests[request.request_id] = request
        
        # Reserve VRAM
        gpu.available_vram_mb -= request.vram_required_mb
        gpu.current_load = min(1.0, gpu.current_load + 0.25)
        
        print(f"[Scheduler] {request.request_id} running on {gpu_id}")
        
        try:
            # Simulate inference (replace with real LoRAX call)
            await asyncio.sleep(0.1)  # Placeholder for inference
            
            request.result = f"Processed on {gpu_id}"
            request.status = "completed"
            request.completed_at = time.time()
            
        except Exception as e:
            request.status = "failed"
            request.error = str(e)
        
        finally:
            # Release VRAM
            gpu.available_vram_mb += request.vram_required_mb
            gpu.current_load = max(0.0, gpu.current_load - 0.25)
            
            # Move to completed
            self.active_requests.pop(request.request_id, None)
            self.completed_requests[request.request_id] = request
    
    def get_status(self) -> Dict:
        """Get scheduler status"""
        return {
            "queue_size": self.request_queue.qsize(),
            "active_requests": len(self.active_requests),
            "completed_requests": len(self.completed_requests),
            "gpus": {
                gpu_id: {
                    "name": config.name,
                    "total_vram_mb": config.total_vram_mb,
                    "available_vram_mb": config.available_vram_mb,
                    "utilization": f"{config.utilization:.1%}",
                    "is_available": config.is_available
                }
                for gpu_id, config in self.gpus.items()
            }
        }
    
    async def start(self) -> None:
        """Start scheduler"""
        if not self._running:
            self._scheduler_task = asyncio.create_task(self.schedule_loop())
            print("[Scheduler] Started")
    
    async def stop(self) -> None:
        """Stop scheduler"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            print("[Scheduler] Stopped")


def create_scheduler(
    gpu_count: int = 1,
    vram_per_gpu_mb: int = 24576
) -> GPUScheduler:
    """Factory function to create scheduler with GPUs"""
    gpu_configs = [
        {
            "gpu_id": f"gpu-{i}",
            "name": f"NVIDIA GPU {i}",
            "total_vram_mb": vram_per_gpu_mb
        }
        for i in range(gpu_count)
    ]
    return GPUScheduler(gpu_configs=gpu_configs)


# Example usage
if __name__ == "__main__":
    async def main():
        # Create scheduler with 2 GPUs
        scheduler = create_scheduler(gpu_count=2, vram_per_gpu_mb=24576)
        await scheduler.start()
        
        # Submit requests with different priorities
        print("\n=== Submitting Requests ===")
        
        # TIER_1 - Critical (immediate)
        req1 = await asyncio.create_task(
            scheduler.submit_request(
                query="Wire $1M to Russia",
                adapter_id="finance-expert",
                priority=PriorityTier.TIER_1_CRITICAL,
                vram_required_mb=4096
            )
        )
        
        # TIER_2 - Elevated
        req2 = await asyncio.create_task(
            scheduler.submit_request(
                query="Analyze Q3 risk report",
                adapter_id="risk-expert", 
                priority=PriorityTier.TIER_2_ELEVATED,
                vram_required_mb=2048
            )
        )
        
        # TIER_3 - Benign
        req3 = await asyncio.create_task(
            scheduler.submit_request(
                query="What's the weather?",
                adapter_id="general-assistant",
                priority=PriorityTier.TIER_3_BENIGN,
                vram_required_mb=1024
            )
        )
        
        # Wait and print status
        await asyncio.sleep(0.5)
        
        print("\n=== Scheduler Status ===")
        status = scheduler.get_status()
        print(f"Queue: {status['queue_size']}")
        print(f"Active: {status['active_requests']}")
        
        for gpu_id, info in status['gpus'].items():
            print(f"  {gpu_id}: {info['available_vram_mb']}MB free, {info['utilization']} load")
        
        await scheduler.stop()
    
    asyncio.run(main())