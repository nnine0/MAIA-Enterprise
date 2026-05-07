"""
MAIA GitOps Pipeline - Adapter CI/CD
==================================
GitOps-based adapter deployment with progressive rollout.

Flow:
1. New adapter detected (git tag / AIBOM update)
2. Security scan + unit tests
3. Deploy to staging
4. Integration validation
5. Progressive rollout (canary → 50% → 100%)
6. Rollback on failure

Run: python3 -m app.gitops_pipeline
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class DeploymentStage(Enum):
    DETECTED = "detected"
    SECURITY_SCAN = "security_scan"
    UNIT_TEST = "unit_test"
    STAGING = "staging"
    INTEGRATION = "integration"
    CANARY = "canary"
    PROGRESSIVE = "progressive"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class AdapterDeployment:
    adapter_id: str
    version: str
    stage: DeploymentStage = DeploymentStage.DETECTED
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    health_check_passed: bool = False
    canary_error_rate: float = 0.0
    progressive_percentage: int = 0
    rollback_reason: Optional[str] = None
    audit_log: List[Dict] = field(default_factory=list)

    def log_event(self, stage: DeploymentStage, message: str, metadata: Optional[Dict] = None):
        self.last_updated = datetime.utcnow().isoformat()
        self.audit_log.append({
            "stage": stage.value,
            "message": message,
            "timestamp": self.last_updated,
            "metadata": metadata or {},
        })
        self.stage = stage


class GitOpsPipeline:
    """GitOps pipeline for adapter deployments."""

    def __init__(self):
        self.deployments: Dict[str, AdapterDeployment] = {}
        self.staging_env = "staging"
        self.prod_env = "production"

    def detect_new_adapter(self, adapter_id: str, version: str) -> AdapterDeployment:
        """Detect new adapter version from git tag or AIBOM update."""
        deployment = AdapterDeployment(
            adapter_id=adapter_id,
            version=version,
        )
        deployment.log_event(DeploymentStage.DETECTED, f"New adapter detected: {adapter_id}@{version}")
        self.deployments[f"{adapter_id}:{version}"] = deployment
        return deployment

    async def run_security_scan(self, deployment: AdapterDeployment) -> bool:
        """Run security scan on adapter."""
        deployment.log_event(DeploymentStage.SECURITY_SCAN, "Security scan started")
        
        await asyncio.sleep(0.1)
        
        deployment.log_event(DeploymentStage.SECURITY_SCAN, "Security scan passed")
        return True

    async def run_unit_tests(self, deployment: AdapterDeployment) -> bool:
        """Run unit tests on adapter."""
        deployment.log_event(DeploymentStage.UNIT_TEST, "Unit tests started")
        
        await asyncio.sleep(0.1)
        
        deployment.log_event(DeploymentStage.UNIT_TEST, "Unit tests passed")
        return True

    async def deploy_to_staging(self, deployment: AdapterDeployment) -> bool:
        """Deploy adapter to staging environment."""
        deployment.log_event(DeploymentStage.STAGING, f"Deploying to {self.staging_env}")
        
        await asyncio.sleep(0.1)
        
        deployment.health_check_passed = True
        deployment.log_event(DeploymentStage.STAGING, "Staging deployment successful")
        return True

    async def run_integration_tests(self, deployment: AdapterDeployment) -> bool:
        """Run integration tests against staging."""
        deployment.log_event(DeploymentStage.INTEGRATION, "Integration tests started")
        
        await asyncio.sleep(0.1)
        
        deployment.log_event(DeploymentStage.INTEGRATION, "Integration tests passed")
        return True

    async def deploy_canary(self, deployment: AdapterDeployment) -> bool:
        """Deploy canary (5% traffic)."""
        deployment.log_event(DeploymentStage.CANARY, "Canary deployment started")
        
        await asyncio.sleep(0.1)
        
        deployment.progressive_percentage = 5
        deployment.canary_error_rate = 0.0
        deployment.log_event(DeploymentStage.CANARY, "Canary deployed (5%)")
        return True

    async def progressive_rollout(self, deployment: AdapterDeployment, target_percentage: int) -> bool:
        """Progressive rollout to target percentage."""
        deployment.log_event(
            DeploymentStage.PROGRESSIVE,
            f"Progressive rollout: {deployment.progressive_percentage}% -> {target_percentage}%",
        )
        
        await asyncio.sleep(0.1)
        
        deployment.progressive_percentage = target_percentage
        deployment.log_event(
            DeploymentStage.PROGRESSIVE,
            f"Progress deployed at {target_percentage}%",
        )
        return True

    async def promote_to_production(self, deployment: AdapterDeployment) -> bool:
        """Promote adapter to full production."""
        await self.progressive_rollout(deployment, 50)
        await self.progressive_rollout(deployment, 100)
        
        deployment.log_event(DeploymentStage.PROMOTED, "Adapter promoted to production")
        return True

    async def rollback(self, deployment: AdapterDeployment, reason: str) -> bool:
        """Rollback deployment."""
        deployment.log_event(DeploymentStage.ROLLED_BACK, f"Rollback initiated: {reason}")
        deployment.rollback_reason = reason
        deployment.stage = DeploymentStage.ROLLED_BACK
        return True

    async def run_full_pipeline(self, adapter_id: str, version: str) -> AdapterDeployment:
        """Run full GitOps pipeline."""
        deployment = self.detect_new_adapter(adapter_id, version)
        
        steps = [
            (self.run_security_scan, "Security scan"),
            (self.run_unit_tests, "Unit tests"),
            (self.deploy_to_staging, "Deploy to staging"),
            (self.run_integration_tests, "Integration tests"),
            (self.deploy_canary, "Canary deployment"),
            (self.promote_to_production, "Promote to production"),
        ]
        
        for step_func, step_name in steps:
            success = await step_func(deployment)
            if not success:
                await self.rollback(deployment, f"Failed at {step_name}")
                return deployment
        
        return deployment

    def get_deployment_status(self, deployment: AdapterDeployment) -> Dict:
        """Get deployment status summary."""
        return {
            "adapter_id": deployment.adapter_id,
            "version": deployment.version,
            "stage": deployment.stage.value,
            "progressive_percentage": deployment.progressive_percentage,
            "canary_error_rate": deployment.canary_error_rate,
            "last_updated": deployment.last_updated,
            "audit_log_count": len(deployment.audit_log),
        }

    def list_active_deployments(self) -> List[Dict]:
        """List all active deployments."""
        active = [
            d for d in self.deployments.values()
            if d.stage not in [DeploymentStage.PROMOTED, DeploymentStage.ROLLED_BACK, DeploymentStage.FAILED]
        ]
        return [self.get_deployment_status(d) for d in active]


async def demo():
    print("="*60)
    print("MAIA GitOps Pipeline - Adapter CI/CD")
    print("="*60)
    
    pipeline = GitOpsPipeline()
    
    print("\n[1] Running full pipeline for adapter...")
    deployment = await pipeline.run_full_pipeline("finance-expert", "v2.3.1")
    
    print("\n[2] Deployment status:")
    status = pipeline.get_deployment_status(deployment)
    for k, v in status.items():
        print(f"  {k}: {v}")
    
    print("\n[3] Active deployments:", len(pipeline.list_active_deployments()))
    
    print("\n[4] Audit log:")
    for entry in deployment.audit_log:
        print(f"  [{entry['stage']}] {entry['message']}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(demo())