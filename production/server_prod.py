"""
MAIA Production FastAPI Server
==============================
- Auth middleware (JWT)
- Rate limiting
- Audit trail
- Health/readiness probes
- Circuit breaker status
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

import sys, os, time, json
sys.path.insert(0, os.path.dirname(__file__))

from maia_production import (
    ProductionMAIA, UserContext, Permission, AuditLogger,
    RateLimiter, CircuitBreaker, AuthMiddleware, HashChain, TENANT_ISOLATION
)

# ============================================================
# CONFIG
# ============================================================

SECRET_KEY = os.getenv("MAIA_SECRET", "change-me-in-prod")
REDIS_URL = os.getenv("MAIA_REDIS_URL", "redis://localhost:6379")

# ============================================================
# MODELS
# ============================================================

class GovernanceRequest(BaseModel):
    query: str

class GovernanceResponse(BaseModel):
    tier: str
    blocked: bool
    violations: List[str]
    attacks: List[str]
    requires_dhitl: bool
    forensic_hash: str
    overhead_ms: float
    rate_info: dict

class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    circuit_breaker: dict

class ReadinessResponse(BaseModel):
    ready: bool
    checks: dict

class ComplianceReport(BaseModel):
    tenant_id: str
    total_requests: int
    blocked_requests: int
    critical_tier_requests: int
    date_range: dict

class AuditExport(BaseModel):
    tenant_id: str
    output_file: str

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="MAIA Governance API",
    version="1.0.0",
    description="Production-ready AI governance with audit trail, auth, rate limiting",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global MAIA instance
maia = ProductionMAIA(secret_key=SECRET_KEY, redis_url=REDIS_URL)


# ============================================================
# AUTH DEPENDENCY
# ============================================================

def get_user(authorization: Optional[str] = Header(None)) -> UserContext:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization
    
    user = maia.auth.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/health", response_model=HealthResponse)
def health():
    return maia.health_check()

@app.get("/ready", response_model=ReadinessResponse)
def ready():
    return maia.readiness_check()

@app.get("/circuit-breaker/status")
def circuit_status():
    return maia.circuit_breaker.get_status()

@app.post("/governance", response_model=GovernanceResponse)
def govern(
    request: GovernanceRequest,
    user: UserContext = Depends(get_user)
):
    result = maia.process(request.query, user_context=user)
    
    if result.get("error"):
        status_codes = {"unauthorized": 401, "rate_limit_exceeded": 429}
        raise HTTPException(
            status_code=status_codes.get(result["error"], 500),
            detail=result
        )
    
    return GovernanceResponse(**result)

@app.get("/compliance/report/{tenant_id}", response_model=ComplianceReport)
def compliance_report(tenant_id: str, user: UserContext = Depends(get_user)):
    if not maia.auth.check_permission(user, Permission.READ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    if TENANT_ISOLATION and user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant isolation: cannot access other tenant data")
    
    return maia.export_compliance_report(tenant_id)

@app.post("/compliance/export")
def export_siem(export: AuditExport, user: UserContext = Depends(get_user)):
    if not maia.auth.check_permission(user, Permission.ADMIN):
        raise HTTPException(status_code=403, detail="Admin permission required")
    
    if TENANT_ISOLATION and user.tenant_id != export.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant isolation: cannot export other tenant data")
    
    try:
        maia.audit_logger.export_siem(export.tenant_id, export.output_file)
        return {"status": "exported", "file": export.output_file, "entries": len(maia.audit_logger.get_audit_trail(export.tenant_id))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audit/{tenant_id}")
def get_audit_trail(tenant_id: str, limit: int = 100, user: UserContext = Depends(get_user)):
    if TENANT_ISOLATION and user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant isolation: cannot access other tenant data")
    
    return maia.audit_logger.get_audit_trail(tenant_id, limit=limit)

@app.get("/token/generate/{user_id}")
def generate_token(user_id: str, tenant_id: str, roles: str = "analyst"):
    if not maia.auth.check_permission(UserContext(user_id="system", tenant_id="system", roles=["admin"]), Permission.ADMIN):
        raise HTTPException(status_code=403, detail="Admin permission required")
    
    user = UserContext(user_id=user_id, tenant_id=tenant_id, roles=roles.split(","))
    token = maia.auth.create_token(user)
    return {"token": token, "user_id": user_id, "tenant_id": tenant_id, "roles": roles.split(",")}


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("MAIA_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)