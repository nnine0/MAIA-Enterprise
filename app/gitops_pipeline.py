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
