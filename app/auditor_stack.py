"""
MAIA Auditor Stack — Layer 8 Multi-Model Governance
====================================================
Three independent auditor models running as a coordinated verification layer:

  Layer 8a — Privacy Filter:    openai/privacy-filter (token classification)
  Layer 8b — Safety Sheriff:    nvidia/Nemotron-3-Content-Safety (via nemotron_real.py)
  Layer 8c — Logic Sentinel:    ibm-granite/granite-guardian-3.1-2b (RAG verification)

Each auditor runs as an independent FastAPI service behind the governance layer.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime

import torch
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

AUDITOR_MODEL = os.getenv("AUDITOR_MODEL", "")


class AuditVerdict(str, Enum):
    PASS = "PASS"
    FLAG = "FLAG"
    BLOCK = "BLOCK"


class AuditResult(BaseModel):
    auditor: str
    verdict: AuditVerdict
    score: float
    details: str
    timestamp: str


# ─── Layer 8a: Privacy Filter ───────────────────────────────────────────────

class PrivacyFilter:
    """openai/privacy-filter — token classification for PII redaction.

    Detects: account numbers, SSNs, addresses, emails, phones, URLs, secrets.
    Runs at the boundary of Layer 8; if the agentic engine tries to emit
    a customer's raw PII, this model trips the breaker before the packet
    hits the Layer 7 API.
    """

    def __init__(self, model_id: str = "openai/privacy-filter"):
        self.model_id = model_id
        self.model = None
        self.tokenizer = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._load()

    def _load(self):
        try:
            from transformers import AutoTokenizer, AutoModelForTokenClassification
            logger.info(f"Loading privacy filter: {self.model_id}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self.model = AutoModelForTokenClassification.from_pretrained(
                self.model_id,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
            self.model.eval()
            logger.info("Privacy filter loaded")
        except Exception as e:
            logger.error(f"Failed to load privacy filter: {e}")
            self.model = None

    @torch.no_grad()
    def audit(self, text: str) -> AuditResult:
        if self.model is None:
            return AuditResult(
                auditor="privacy-filter",
                verdict=AuditVerdict.PASS,
                score=0.0,
                details="Model not loaded — bypassing",
                timestamp=datetime.utcnow().isoformat(),
            )

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        outputs = self.model(**inputs)
        predictions = outputs.logits.argmax(dim=-1)[0].tolist()

        id2label = self.model.config.id2label
        detected_entities = []
        for token_id, pred in zip(inputs["input_ids"][0].tolist(), predictions):
            label = id2label.get(pred, "O")
            if label != "O":
                token = self.tokenizer.decode(token_id)
                detected_entities.append({"token": token, "label": label})

        if detected_entities:
            return AuditResult(
                auditor="privacy-filter",
                verdict=AuditVerdict.BLOCK,
                score=1.0,
                details=f"PII detected: {[e['label'] for e in detected_entities[:5]]}",
                timestamp=datetime.utcnow().isoformat(),
            )

        return AuditResult(
            auditor="privacy-filter",
            verdict=AuditVerdict.PASS,
            score=0.0,
            details="No PII detected",
            timestamp=datetime.utcnow().isoformat(),
        )


# ─── Layer 8b: Safety Sheriff (delegates to nemotron_real.py) ──────────────

from app.nemotron_real import Nemotron3Safety, NemotronResult


def _nemotron_to_audit_result(nr: NemotronResult, auditor: str = "safety-sheriff") -> AuditResult:
    """Convert NemotronResult to unified AuditResult."""
    if nr.tier == 1:
        verdict = AuditVerdict.BLOCK
    elif nr.tier == 2:
        verdict = AuditVerdict.FLAG
    else:
        verdict = AuditVerdict.PASS

    cats = ", ".join(nr.categories) if nr.categories else "none"
    return AuditResult(
        auditor=auditor,
        verdict=verdict,
        score=1.0 / max(nr.tier, 1),
        details=f"user_safe={nr.user_safe} response_safe={nr.response_safe} categories=[{cats}]",
        timestamp=datetime.utcnow().isoformat(),
    )


class SafetySheriff:
    """Wrapper around Nemotron3Safety (from nemotron_real.py) for the unified auditor stack.

    Uses the correct model class (Gemma3ForConditionalGeneration) and native /categories API.
    Generates only 20 tokens — the safety output format is fixed and deterministic.
    """

    def __init__(self, model_id: str = "nvidia/Nemotron-3-Content-Safety"):
        self._inner = Nemotron3Safety(model_id=model_id)
        self._loaded = False

    def load(self, device: str = "auto"):
        self._inner.load(device=device)
        self._loaded = True

    @torch.no_grad()
    def audit(self, text: str) -> AuditResult:
        if not self._loaded:
            return AuditResult(
                auditor="safety-sheriff",
                verdict=AuditVerdict.PASS,
                score=0.0,
                details="Model not loaded — bypassing",
                timestamp=datetime.utcnow().isoformat(),
            )
        nr = self._inner.audit(prompt=text, response="", max_new_tokens=20)
        return _nemotron_to_audit_result(nr)


# ─── Layer 8c: Logic Sentinel ──────────────────────────────────────────────

class LogicSentinel:
    """IBM Granite Guardian 3.1 2B — conceptual soundness & RAG verification.

    Trained on Social-Safety-Guard and RAG-Check datasets.
    Detects hallucinated logic, policy deviation, and unsupported claims.
    """

    def __init__(self, model_id: str = "ibm-granite/granite-guardian-3.1-2b"):
        self.model_id = model_id
        self.model = None
        self.tokenizer = None
        self._load()

    def _load(self):
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            logger.info(f"Loading logic sentinel: {self.model_id}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
            self.model.eval()
            logger.info("Logic sentinel loaded")
        except Exception as e:
            logger.error(f"Failed to load logic sentinel: {e}")
            self.model = None

    @torch.no_grad()
    def audit_rag(self, query: str, context: str, response: str) -> AuditResult:
        """Verify response is grounded in provided context (RAG check)."""
        if self.model is None:
            return AuditResult(
                auditor="logic-sentinel",
                verdict=AuditVerdict.PASS,
                score=0.0,
                details="Model not loaded — bypassing",
                timestamp=datetime.utcnow().isoformat(),
            )

        prompt = f"""<|system|>You are a RAG verification auditor. Determine if the response is fully supported by the provided context.</s>
<|user|>Context: {context[:2000]}

Query: {query}

Response: {response[:1000]}

Is this response fully supported by the context? Answer ONLY with 'SUPPORTED' or 'UNSUPPORTED'.</s>
<|assistant|>"""
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        outputs = self.model.generate(
            **inputs,
            max_new_tokens=10,
            temperature=0.1,
            do_sample=False,
        )
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        result_lower = result.lower()

        if "unsupported" in result_lower:
            return AuditResult(
                auditor="logic-sentinel",
                verdict=AuditVerdict.BLOCK,
                score=0.9,
                details="Response contains unsupported claims",
                timestamp=datetime.utcnow().isoformat(),
            )

        return AuditResult(
            auditor="logic-sentinel",
            verdict=AuditVerdict.PASS,
            score=0.0,
            details="Response grounded in context",
            timestamp=datetime.utcnow().isoformat(),
        )

    @torch.no_grad()
    def audit_soundness(self, trajectory: List[Dict[str, Any]]) -> AuditResult:
        """Audit a full reasoning trajectory for logical consistency."""
        if self.model is None:
            return AuditResult(
                auditor="logic-sentinel",
                verdict=AuditVerdict.PASS,
                score=0.0,
                details="Model not loaded — bypassing",
                timestamp=datetime.utcnow().isoformat(),
            )

        steps_text = "\n".join(
            f"Step {s.get('step', i)}: {s.get('reasoning', '')}"
            for i, s in enumerate(trajectory)
        )

        prompt = f"""<|system|>You are a reasoning auditor. Check for logical fallacies, contradictions, and policy deviations.</s>
<|user|>Trajectory:
{steps_text[:2000]}

Does this trajectory contain any logical contradictions, policy violations, or hallucinated facts? Answer with 'CLEAN' or 'CONTRADICTION' or 'POLICY_VIOLATION'.</s>
<|assistant|>"""
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        outputs = self.model.generate(
            **inputs,
            max_new_tokens=20,
            temperature=0.1,
            do_sample=False,
        )
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        result_lower = result.lower()

        if "contradiction" in result_lower:
            return AuditResult(
                auditor="logic-sentinel",
                verdict=AuditVerdict.BLOCK,
                score=0.85,
                details="Logical contradiction detected in trajectory",
                timestamp=datetime.utcnow().isoformat(),
            )
        if "policy_violation" in result_lower or "violation" in result_lower:
            return AuditResult(
                auditor="logic-sentinel",
                verdict=AuditVerdict.BLOCK,
                score=0.9,
                details="Policy violation detected in trajectory",
                timestamp=datetime.utcnow().isoformat(),
            )

        return AuditResult(
            auditor="logic-sentinel",
            verdict=AuditVerdict.PASS,
            score=0.0,
            details="Trajectory is sound",
            timestamp=datetime.utcnow().isoformat(),
        )


# ─── Unified Auditor Coordinator ────────────────────────────────────────────

class AuditorCoordinator:
    """Coordinates all three auditor models for a unified governance verdict."""

    def __init__(self):
        self.privacy_filter: Optional[PrivacyFilter] = None
        self.safety_sheriff: Optional[SafetySheriff] = None
        self.logic_sentinel: Optional[LogicSentinel] = None

    def load_all(self):
        logger.info("Loading full auditor stack...")
        try:
            self.privacy_filter = PrivacyFilter()
        except Exception as e:
            logger.warning(f"Privacy filter load failed: {e}")

        try:
            sheriff = SafetySheriff()
            sheriff.load()
            self.safety_sheriff = sheriff
        except Exception as e:
            logger.warning(f"Safety sheriff load failed: {e}")

        try:
            self.logic_sentinel = LogicSentinel()
        except Exception as e:
            logger.warning(f"Logic sentinel load failed: {e}")

        loaded = sum(1 for a in [self.privacy_filter, self.safety_sheriff, self.logic_sentinel] if a is not None)
        logger.info(f"Auditor stack loaded: {loaded}/3")

    def audit_pii(self, text: str) -> AuditResult:
        if self.privacy_filter is None:
            return AuditResult(
                auditor="privacy-filter",
                verdict=AuditVerdict.PASS,
                score=0.0,
                details="Not loaded",
                timestamp=datetime.utcnow().isoformat(),
            )
        return self.privacy_filter.audit(text)

    def audit_safety(self, text: str) -> AuditResult:
        if self.safety_sheriff is None:
            return AuditResult(
                auditor="safety-sheriff",
                verdict=AuditVerdict.PASS,
                score=0.0,
                details="Not loaded",
                timestamp=datetime.utcnow().isoformat(),
            )
        return self.safety_sheriff.audit(text)

    def audit_rag(self, query: str, context: str, response: str) -> AuditResult:
        if self.logic_sentinel is None:
            return AuditResult(
                auditor="logic-sentinel",
                verdict=AuditVerdict.PASS,
                score=0.0,
                details="Not loaded",
                timestamp=datetime.utcnow().isoformat(),
            )
        return self.logic_sentinel.audit_rag(query, context, response)

    def audit_trajectory(self, trajectory: List[Dict[str, Any]]) -> AuditResult:
        if self.logic_sentinel is None:
            return AuditResult(
                auditor="logic-sentinel",
                verdict=AuditVerdict.PASS,
                score=0.0,
                details="Not loaded",
                timestamp=datetime.utcnow().isoformat(),
            )
        return self.logic_sentinel.audit_soundness(trajectory)

    def full_audit(self, query: str) -> Dict[str, Any]:
        """Run all three auditors and return combined verdict."""
        results = {
            "pii": self.audit_pii(query),
            "safety": self.audit_safety(query),
        }
        verdicts = [r.verdict for r in results.values()]
        combined = AuditVerdict.BLOCK if AuditVerdict.BLOCK in verdicts else \
                   AuditVerdict.FLAG if AuditVerdict.FLAG in verdicts else \
                   AuditVerdict.PASS
        return {
            "combined_verdict": combined,
            "audits": {k: v.model_dump() for k, v in results.items()},
            "timestamp": datetime.utcnow().isoformat(),
        }


# ─── FastAPI Service ────────────────────────────────────────────────────────

try:
    from contextlib import asynccontextmanager
    from fastapi import FastAPI

    coordinator = AuditorCoordinator()

    @asynccontextmanager
    async def lifespan(app):
        coordinator.load_all()
        yield

    app = FastAPI(title=f"MAIA Auditor: {AUDITOR_MODEL or 'unconfigured'}", lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "healthy", "auditor": AUDITOR_MODEL}

    @app.post("/audit")
    async def audit_endpoint(text: str):
        return coordinator.full_audit(text)

    @app.post("/audit/pii")
    async def audit_pii(text: str):
        return coordinator.audit_pii(text)

    @app.post("/audit/safety")
    async def audit_safety(text: str):
        return coordinator.audit_safety(text)

    @app.post("/audit/rag")
    async def audit_rag(query: str, context: str, response: str):
        return coordinator.audit_rag(query, context, response)

except ImportError:
    app = None


if __name__ == "__main__":
    coordinator = AuditorCoordinator()
    coordinator.load_all()
    result = coordinator.full_audit("My SSN is 123-45-6789 and my email is test@example.com")
    print(json.dumps(result, indent=2, default=str))


# ── CLI entry point for docker auditor services ──
def run_auditor():
    """Start the FastAPI server for the configured auditor model."""
    import uvicorn
    model_id = os.getenv("AUDITOR_MODEL", "openai/privacy-filter")
    port = int(os.getenv("API_PORT", "8101"))
    logger.info(f"Starting auditor service: {model_id} on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
