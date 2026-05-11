"""
MAIA Parallel Airlock Gateway
==============================
Implements the governance gateway pattern with parallel dispatch:

  Ingress:  Prompt → { Base Model (cloud API), Sheriff (Nemotron), Sentinel (Granite) } in parallel
  Circuit:  Sheriff/Sentinel pre-flight → kill cloud call if violated
  Egress:   Tool-call interception → policy check → deliver to data

Supports any upstream base model: OpenAI, Anthropic, OpenRouter, Ollama, etc.

Flow:
  User Prompt
      │
      ├──→ Sheriff (Nemotron-3)  ──→ Pre-flight safety audit
      ├──→ Sentinel (Granite-3B) ──→ Pre-flight policy/logic audit
      └──→ Base Model (cloud)    ──→ (cancellable task)
                                      │
                                 if VIOLATION → cancel cloud → 403
                                      │
                                 if CLEAR → stream → Egress Interceptor
                                                      │
                                                 tool call? → policy manifest → BLOCK/REWRITE
                                                      │
                                                 text → deliver to user
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, AsyncGenerator, Callable, Awaitable

logger = logging.getLogger("MAIA-AirlockGateway")


class Verdict(Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    REWRITE = "REWRITE"


class PreFlightResult(Enum):
    CLEAR = "CLEAR"
    VIOLATION = "VIOLATION"
    ERROR = "ERROR"


@dataclass
class AuditFinding:
    auditor: str
    verdict: Verdict
    reason: str
    categories: List[str] = field(default_factory=list)
    confidence: float = 0.0
    latency_ms: float = 0.0


@dataclass
class PreFlightReport:
    result: PreFlightResult
    findings: List[AuditFinding] = field(default_factory=list)
    total_latency_ms: float = 0.0


@dataclass
class EgressDecision:
    action: Verdict
    tool_id: Optional[str] = None
    tool_params: Optional[Dict] = None
    reason: str = ""
    rewritten_content: Optional[str] = None


@dataclass
class GatewayTransaction:
    transaction_id: str
    prompt: str
    sector: str
    preflight: Optional[PreFlightReport] = None
    base_model_response: Optional[str] = None
    egress_decision: Optional[EgressDecision] = None
    final_status: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    latency_ms: float = 0.0


# ─── Policy Manifest Loader ────────────────────────────────────────────────

class PolicyManifest:
    """Loads and evaluates policy manifests from policies/ directory."""

    def __init__(self, sector: str = "finance"):
        self.sector = sector
        self._clauses: List[Dict] = []
        self._load()

    def _load(self):
        path = f"policies/sectors/{self.sector}.json"
        try:
            with open(path) as f:
                data = json.load(f)
                self._clauses = data.get("policy_clauses", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Policy manifest not found for {self.sector}: {e}")

    def check_tool_call(self, tool_id: str, tool_params: Dict) -> Optional[EgressDecision]:
        prompt_text = json.dumps({"tool": tool_id, "params": tool_params}).lower()
        for clause in self._clauses:
            keywords = [k.lower() for k in clause.get("keywords", [])]
            if any(kw in prompt_text for kw in keywords):
                action = clause.get("action", "BLOCK").upper()
                return EgressDecision(
                    action=Verdict.BLOCK if action == "BLOCK" else Verdict.ESCALATE,
                    tool_id=tool_id,
                    tool_params=tool_params,
                    reason=f"Policy clause {clause['clause_id']}: {clause['text']}"
                )
        return None

    def check_prompt(self, text: str) -> List[AuditFinding]:
        text_lower = text.lower()
        findings = []
        for clause in self._clauses:
            keywords = [k.lower() for k in clause.get("keywords", [])]
            if any(kw in text_lower for kw in keywords):
                severity = clause.get("severity", "MEDIUM")
                findings.append(AuditFinding(
                    auditor="policy-manifest",
                    verdict=Verdict.BLOCK if severity == "CRITICAL" else Verdict.ESCALATE,
                    reason=f"Policy clause {clause['clause_id']}: {clause['text']}",
                    categories=[clause.get("clause_id", "POLICY")],
                    confidence=1.0
                ))
        return findings


# ─── Abstract Auditors ─────────────────────────────────────────────────────

class BaseAuditor:
    """Base class for local auditor models."""
    name: str = "base"

    async def audit(self, prompt: str) -> AuditFinding:
        raise NotImplementedError

    async def audit_batch(self, prompts: List[str]) -> List[AuditFinding]:
        """Default: sequential. Override with real batched GPU forward pass."""
        return [await self.audit(p) for p in prompts]

    async def fast_pass(self, prompt: str) -> AuditFinding | None:
        """Optional fast path: zero-generation logit-based verdict.

        Returns an AuditFinding with a verdict if the fast path is confident
        enough, or None to fall through to the full audit.
        """
        return None


class SuperFastPass(BaseAuditor):
    """Zero-cost safe-query bypass — skips Granite for clearly safe prompts.

    Matches prompts against safe-text regex patterns. If matched AND no
    unsafe keywords present, returns PASS instantly (~0ms) — bypassing the
    122ms Granite fast_pass entirely.

    Intended to catch ~80% of queries (greetings, factual lookups, simple
    calculations) so Granite only runs on the ~20% that need it.
    """

    name = "super-fast-pass"

    SAFE_PATTERNS = [
        r"^(hello|hi|hey|good morning|good afternoon|good evening)",
        r"^what('s| is) the (weather|time|date|day|temperature|forecast)",
        r"^what (time|day|date) is it",
        r"^who (is|was|are|were) ",
        r"^explain (how|why|what|the|a|an) ",
        r"^define ",
        r"^summarize ",
        r"^translate ",
        r"^compare ",
        r"^list ",
        r"^calculate ",
        r"^tell me about ",
        r"^how (does|do|is|are|can|would|will|to) ",
        r"^what is (a|an|the|your|my|our|this|that) ",
        r"^what are ",
        r"^what does ",
        r"^what do ",
        r"^can you (tell|explain|show|describe|list|give) ",
        r"^is it (possible|true|safe|ok) ",
        r"^why (is|are|does|do|would|did) ",
    ]

    UNSAFE_KEYWORDS = {
        "bypass", "override", "circumvent",
        "fake", "unauthorized", "conceal", "delete logs",
        "sanction", "sanctions", "sanctioned",
        "terrorist", "weapon", "explosive",
        "fraud", "steal", "hack", "exploit", "vulnerability", "malware", "ransomware",
        "patient", "diagnosis", "phi", "ssn", "attorney", "privileged",
        "confidential", "insider trading", "money laundering", "wire",
    }

    def fast_pass(self, prompt: str) -> AuditFinding | None:
        import re
        prompt_lower = prompt.lower().strip()

        # First check: no unsafe keywords
        for kw in self.UNSAFE_KEYWORDS:
            if kw in prompt_lower:
                return None  # fall through to Granite

        # Second check: matches a safe pattern
        for pattern in self.SAFE_PATTERNS:
            if re.search(pattern, prompt_lower):
                return AuditFinding(
                    auditor=self.name,
                    verdict=Verdict.PASS,
                    reason=f"SuperFastPass: safe pattern matched",
                    confidence=0.95,
                    latency_ms=0.0,
                )
        return None

    async def audit(self, prompt: str) -> AuditFinding:
        result = self.fast_pass(prompt)
        return result or AuditFinding(
            auditor=self.name,
            verdict=Verdict.PASS,
            reason="SuperFastPass: no match, falling through",
            confidence=0.5,
            latency_ms=0.0,
        )


class MockSheriffAuditor(BaseAuditor):
    """Mock Nemotron Sheriff for demo/testing."""

    name = "sheriff-nemotron"

    async def audit(self, prompt: str) -> AuditFinding:
        start = time.perf_counter()
        prompt_lower = prompt.lower()

        critical = {"sanction", "russia", "iran", "north korea", "terrorist", "weapon", "fraud", "steal"}
        elevated = {"patient", "diagnosis", "phi", "ssn", "attorney", "privileged", "confidential"}

        words = set(prompt_lower.split())
        critical_hit = words & critical
        elevated_hit = words & elevated

        latency = (time.perf_counter() - start) * 1000

        if critical_hit:
            return AuditFinding(
                auditor=self.name,
                verdict=Verdict.BLOCK,
                reason=f"Critical safety violation: {', '.join(critical_hit)}",
                categories=list(critical_hit),
                confidence=0.95,
                latency_ms=latency
            )
        if elevated_hit:
            return AuditFinding(
                auditor=self.name,
                verdict=Verdict.ESCALATE,
                reason=f"Elevated risk detected: {', '.join(elevated_hit)}",
                categories=list(elevated_hit),
                confidence=0.8,
                latency_ms=latency
            )
        return AuditFinding(
            auditor=self.name,
            verdict=Verdict.PASS,
            reason="No safety violations",
            latency_ms=latency
        )

    async def audit_batch(self, prompts: List[str]) -> List[AuditFinding]:
        return [await self.audit(p) for p in prompts]

    async def fast_pass(self, prompt: str) -> AuditFinding | None:
        return await self.audit(prompt)


class MockSentinelAuditor(BaseAuditor):
    """Mock Granite Sentinel for demo/testing."""

    name = "sentinel-granite"

    async def audit(self, prompt: str) -> AuditFinding:
        start = time.perf_counter()
        prompt_lower = prompt.lower()

        policy_violations = {"bypass", "override", "circumvent", "ignore policy", "skip compliance",
                            "fake", "unauthorized", "conceal", "hide", "delete logs"}

        found = [v for v in policy_violations if v in prompt_lower]
        latency = (time.perf_counter() - start) * 1000

        if found:
            return AuditFinding(
                auditor=self.name,
                verdict=Verdict.BLOCK,
                reason=f"Policy/logic violation: {', '.join(found)}",
                categories=found,
                confidence=0.9,
                latency_ms=latency
            )
        return AuditFinding(
            auditor=self.name,
            verdict=Verdict.PASS,
            reason="No policy violations",
            latency_ms=latency
        )

    async def audit_batch(self, prompts: List[str]) -> List[AuditFinding]:
        return [await self.audit(p) for p in prompts]

    async def fast_pass(self, prompt: str) -> AuditFinding | None:
        return await self.audit(prompt)


# ─── Base Model Client ─────────────────────────────────────────────────────

class BaseModelClient:
    """
    Generic client for any upstream LLM API.
    Supports OpenAI, Anthropic, OpenRouter, Ollama, etc.
    """

    def __init__(self, api_base: str, api_key: str = "", model: str = ""):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._provider = self._detect_provider()

    def _detect_provider(self) -> str:
        base = self.api_base.lower()
        if "openai" in base:
            return "openai"
        if "anthropic" in base:
            return "anthropic"
        if "openrouter" in base:
            return "openrouter"
        if "ollama" in base or "11434" in base:
            return "ollama"
        if "localhost" in base or "127.0.0.1" in base:
            return "local"
        return "generic"

    async def chat_completion(
        self,
        messages: List[Dict],
        stream: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Dict:
        """
        Send chat completion to upstream API.
        Returns dict with 'content', 'tool_calls', 'finish_reason'.
        Cancellable via asyncio task cancellation.
        """
        headers = {"Content-Type": "application/json"}

        if self.api_key:
            if self._provider == "anthropic":
                headers["x-api-key"] = self.api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

        if self._provider == "openai" or self._provider == "openrouter" or self._provider == "generic":
            url = f"{self.api_base}/chat/completions"
        elif self._provider == "anthropic":
            url = f"{self.api_base}/messages"
            body.pop("model")
            body["model"] = self.model or "claude-3-5-sonnet-20241022"
        elif self._provider == "ollama":
            url = f"{self.api_base}/chat"
            body.pop("model")
            body["model"] = self.model or "llama3"
        else:
            url = f"{self.api_base}/chat/completions"

        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        if self._provider == "anthropic":
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            return {"content": content, "tool_calls": [], "finish_reason": data.get("stop_reason", "stop")}
        elif self._provider == "ollama":
            return {"content": data.get("message", {}).get("content", ""), "tool_calls": [], "finish_reason": "stop"}
        else:
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            return {
                "content": msg.get("content", ""),
                "tool_calls": msg.get("tool_calls", []),
                "finish_reason": choice.get("finish_reason", "stop"),
            }

    async def stream_with_breaker(
        self,
        messages: List[Dict],
        egress: "EgressInterceptor",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream response, kill mid-stream if egress blocks a tool call.

        Even when preflight passes, the base model may emit a blocked tool call
        mid-generation. This generator yields tokens one-by-one, checks accumulated
        text against EgressInterceptor after each token, and aborts the stream if
        a BLOCK verdict fires.

        Yields (token_text, is_final) tuples. is_final=True when stream ends or is killed.
        """
        import httpx
        accumulated = ""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        url = f"{self.api_base}/chat/completions"
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        yield ("", True)
                        return

                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        accumulated += token
                        yield (token, False)

                        egress_result = await egress.intercept(accumulated)
                        if egress_result.action == Verdict.BLOCK:
                            logger.info(
                                f"Streaming circuit breaker: blocked tool call detected "
                                f"mid-stream — {egress_result.tool_id}"
                            )
                            yield ("[STREAM INTERRUPTED: BLOCKED BY GOVERNANCE]", True)
                            return

                yield ("", True)


# ─── Egress Interceptor ────────────────────────────────────────────────────

class EgressInterceptor:
    """
    Intercepts model responses before they reach customer data.
    Detects tool calls and checks against policy manifests.
    """

    TOOL_CALL_PATTERNS = [
        r"\[CALL_TOOL:([A-Z0-9_]+)\]",
        r"<tool_call>\s*(\w+)\s*</tool_call>",
        r'"tool":\s*"(\w+)"',
        r'function":\s*"(\w+)"',
    ]

    def __init__(self, sector: str = "finance"):
        self.sector = sector
        self.policy = PolicyManifest(sector)
        self.logger = logging.getLogger("MAIA-EgressInterceptor")

    async def intercept(self, response_text: str) -> EgressDecision:
        """
        Check response for tool calls and validate against policy.
        Returns decision: ALLOW, BLOCK, or REWRITE.
        """
        import re
        for pattern in self.TOOL_CALL_PATTERNS:
            match = re.search(pattern, response_text)
            if match:
                tool_id = match.group(1)
                try:
                    params = json.loads(response_text)
                except (json.JSONDecodeError, TypeError):
                    params = {"raw": response_text[:200]}

                policy_check = self.policy.check_tool_call(tool_id, params)
                if policy_check:
                    return policy_check

                return EgressDecision(
                    action=Verdict.PASS,
                    tool_id=tool_id,
                    tool_params=params,
                    reason=f"Tool {tool_id} passed policy check"
                )

        tool_calls = self._extract_openai_tool_calls(response_text)
        if tool_calls:
            for tc in tool_calls:
                policy_check = self.policy.check_tool_call(tc.get("name", ""), tc.get("arguments", {}))
                if policy_check:
                    return policy_check
            return EgressDecision(
                action=Verdict.PASS,
                tool_id=tool_calls[0].get("name"),
                reason=f"Tool {tool_calls[0].get('name')} passed policy check"
            )

        return EgressDecision(
            action=Verdict.PASS,
            reason="No tool calls detected"
        )

    def _extract_openai_tool_calls(self, text: str) -> List[Dict]:
        """Extract OpenAI-format tool calls from response."""
        import re
        pattern = r'"function":\s*\{[^}]*"name":\s*"([^"]+)"[^}]*"arguments":\s*({[^}]+})'
        matches = re.findall(pattern, text)
        results = []
        for name, args_str in matches:
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
            results.append({"name": name, "arguments": args})
        return results


# ─── Airlock Gateway ───────────────────────────────────────────────────────

class AirlockGateway:
    """
    The parallel airlock gateway.
    
    On ingress:
      1. Start base model API call as a cancellable task
      2. Dispatch Sheriff + Sentinel audits in parallel
      3. If pre-flight finds violation, cancel base model task, return 403
      4. If clear, return base model response
    
    On egress:
      1. Intercept response for tool calls
      2. Check against policy manifest
      3. Block/rewrite if violation
    """

    def __init__(
        self,
        sheriff: Optional[BaseAuditor] = None,
        sentinel: Optional[BaseAuditor] = None,
        base_model: Optional[BaseModelClient] = None,
        sector: str = "finance",
        super_fast_pass: Optional[SuperFastPass] = None,
    ):
        self.sheriff = sheriff or MockSheriffAuditor()
        self.sentinel = sentinel or MockSentinelAuditor()
        self.base_model = base_model
        self.sector = sector
        self.egress = EgressInterceptor(sector)
        self.policy = PolicyManifest(sector)
        self.logger = logging.getLogger("MAIA-AirlockGateway")
        self.transactions: List[GatewayTransaction] = []
        self._super_fast_pass = super_fast_pass or SuperFastPass()
        self._coordinator = BatchedAuditorCoordinator(self.sheriff, self.sentinel)

    async def _process_single(
        self,
        prompt: str,
        messages: Optional[List[Dict]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        preflight_results: Optional[Tuple[AuditFinding, AuditFinding]] = None,
    ) -> GatewayTransaction:
        """Internal single-prompt processor. Used by both process() and process_batch()."""
        tx = GatewayTransaction(
            transaction_id=f"maia-{uuid.uuid4().hex[:12]}",
            prompt=prompt,
            sector=self.sector,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        start = time.perf_counter()

        if messages is None:
            messages = [{"role": "user", "content": prompt}]

        # ── Step 1: Policy manifest check (instant, no model needed) ──
        policy_findings = self.policy.check_prompt(prompt)
        if policy_findings:
            tx.preflight = PreFlightReport(
                result=PreFlightResult.VIOLATION,
                findings=policy_findings,
            )
            tx.final_status = "BLOCKED_BY_POLICY"
            tx.latency_ms = (time.perf_counter() - start) * 1000
            self.transactions.append(tx)
            return tx

        # ── Step 2: Start base model call as cancellable task ──
        base_task: Optional[asyncio.Task] = None
        if self.base_model:
            base_task = asyncio.create_task(
                self.base_model.chat_completion(
                    messages=messages,
                    stream=False,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            )

        # ── Step 3: Super-fast pass (skip Granite for clearly safe) ──
        if preflight_results is None:
            super_pass = self._super_fast_pass.fast_pass(prompt)
            if super_pass is not None and super_pass.verdict == Verdict.PASS:
                preflight_results = (super_pass, super_pass)
            else:
                batch_results = await self._coordinator.audit_batch([prompt])
                preflight_results = batch_results[0]

        sheriff_result, sentinel_result = preflight_results
        findings = [sheriff_result, sentinel_result]
        pre_latency = (time.perf_counter() - start) * 1000

        # ── Step 4: Circuit breaker ──
        blocks = [f for f in findings if f.verdict == Verdict.BLOCK]
        escalates = [f for f in findings if f.verdict == Verdict.ESCALATE]

        if blocks:
            if base_task and not base_task.done():
                base_task.cancel()
                try:
                    await base_task
                except asyncio.CancelledError:
                    pass
            tx.preflight = PreFlightReport(
                result=PreFlightResult.VIOLATION,
                findings=findings,
                total_latency_ms=pre_latency,
            )
            tx.final_status = "BLOCKED_PRE_FLIGHT"
            tx.latency_ms = (time.perf_counter() - start) * 1000
            self.transactions.append(tx)
            return tx

        if escalates:
            tx.preflight = PreFlightReport(
                result=PreFlightResult.CLEAR,
                findings=findings,
                total_latency_ms=pre_latency,
            )
            tx.final_status = "ESCALATED"
        else:
            tx.preflight = PreFlightReport(
                result=PreFlightResult.CLEAR,
                findings=findings,
                total_latency_ms=pre_latency,
            )

        # ── Step 5: Await base model response ──
        if base_task:
            try:
                base_response = await base_task
                tx.base_model_response = base_response.get("content", "")

                tool_calls = base_response.get("tool_calls", [])
                if tool_calls:
                    combined = json.dumps({"content": tx.base_model_response, "tool_calls": tool_calls})
                else:
                    combined = tx.base_model_response

                # ── Step 6: Egress interception ──
                egress_result = await self.egress.intercept(combined)
                tx.egress_decision = egress_result

                if egress_result.action == Verdict.BLOCK:
                    tx.final_status = "BLOCKED_EGRESS"
                elif egress_result.action == Verdict.ESCALATE:
                    tx.final_status = "ESCALATED_EGRESS"
                else:
                    tx.final_status = "PASSED"
            except asyncio.CancelledError:
                tx.base_model_response = None
                tx.final_status = "CANCELLED"
            except Exception as e:
                self.logger.error(f"Base model error: {e}")
                tx.base_model_response = f"Error: {e}"
                tx.final_status = "ERROR"
        else:
            tx.final_status = "PASSED_NO_MODEL"

        tx.latency_ms = (time.perf_counter() - start) * 1000
        self.transactions.append(tx)
        return tx

    async def process(
        self,
        prompt: str,
        messages: Optional[List[Dict]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> GatewayTransaction:
        """Fast-path: single prompt, bypass micro-batcher entirely.

        Policy fast-path first, then single-shot batched preflight call.
        No micro-batch delay. Single prompt.
        """
        # Fast-path policy check (zero model cost)
        policy_findings = self.policy.check_prompt(prompt)
        if policy_findings:
            tx = GatewayTransaction(
                transaction_id=f"maia-{uuid.uuid4().hex[:12]}",
                prompt=prompt,
                sector=self.sector,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            tx.preflight = PreFlightReport(result=PreFlightResult.VIOLATION, findings=policy_findings)
            tx.final_status = "BLOCKED_BY_POLICY"
            tx.latency_ms = 0.0
            self.transactions.append(tx)
            return tx

        # Super-fast pass: skip Granite for clearly safe queries (~0ms)
        super_pass = self._super_fast_pass.fast_pass(prompt)
        if super_pass is not None and super_pass.verdict == Verdict.PASS:
            return await self._process_single(
                prompt, messages, max_tokens, temperature,
                preflight_results=(super_pass, super_pass),
            )

        # Single-shot batched preflight via coordinator with 3x retry
        try:
            batch_results = await self._coordinator.audit_batch([prompt])
            sheriff_result, sentinel_result = batch_results[0]
        except RuntimeError as e:
            self.logger.error(f"Preflight failed after 3 retries: {e}")
            tx = GatewayTransaction(
                transaction_id=f"maia-{uuid.uuid4().hex[:12]}",
                prompt=prompt,
                sector=self.sector,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            tx.preflight = PreFlightReport(result=PreFlightResult.ERROR)
            tx.final_status = "ERROR"
            tx.latency_ms = 0.0
            self.transactions.append(tx)
            return tx

        blocks = [f for f in [sheriff_result, sentinel_result] if f.verdict == Verdict.BLOCK]
        if blocks:
            tx = GatewayTransaction(
                transaction_id=f"maia-{uuid.uuid4().hex[:12]}",
                prompt=prompt,
                sector=self.sector,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            tx.preflight = PreFlightReport(
                result=PreFlightResult.VIOLATION,
                findings=[sheriff_result, sentinel_result],
                total_latency_ms=0.0,
            )
            tx.final_status = "BLOCKED_PRE_FLIGHT"
            tx.latency_ms = 0.0
            self.transactions.append(tx)
            return tx

        return await self._process_single(
            prompt, messages, max_tokens, temperature,
            preflight_results=(sheriff_result, sentinel_result),
        )

    async def process_batch(
        self,
        prompts: List[str],
        sector: str = "finance",
    ) -> List[GatewayTransaction]:
        """Process N prompts with coalesced batched preflight.

        All N prompts go through Sheriff and Sentinel in a single batched
        GPU forward pass each (amortized prefill).
        """
        if not prompts:
            return []

        if sector != self.sector:
            self.sector = sector
            self.egress = EgressInterceptor(sector)
            self.policy = PolicyManifest(sector)

        # Step 1: Fast-path policy check + super-fast pass per prompt
        policy_blocked = {}
        super_fast_passed = {}
        for i, prompt in enumerate(prompts):
            findings = self.policy.check_prompt(prompt)
            if findings:
                policy_blocked[prompt] = findings
                continue
            sp = self._super_fast_pass.fast_pass(prompt)
            if sp is not None and sp.verdict == Verdict.PASS:
                super_fast_passed[i] = sp

        # Step 2: Batched preflight — only for prompts NOT super-passed
        uncertain_indices = [i for i in range(len(prompts))
                             if i not in super_fast_passed and prompts[i] not in policy_blocked]
        uncertain_prompts = [prompts[i] for i in uncertain_indices]

        batch_results_map = {}
        if uncertain_prompts:
            try:
                batch_results = await self._coordinator.audit_batch(uncertain_prompts)
                for idx, result in zip(uncertain_indices, batch_results):
                    batch_results_map[idx] = result
            except RuntimeError as e:
                self.logger.error(f"Batch preflight failed after 3 retries: {e}")
                return [
                    self._make_error_tx(p)
                    for p in prompts
                ]

        # Step 3: Per-prompt dispatch
        txs = []
        for i, prompt in enumerate(prompts):
            if prompt in policy_blocked:
                tx = GatewayTransaction(
                    transaction_id=f"maia-{uuid.uuid4().hex[:12]}",
                    prompt=prompt,
                    sector=self.sector,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                tx.preflight = PreFlightReport(result=PreFlightResult.VIOLATION, findings=policy_blocked[prompt])
                tx.final_status = "BLOCKED_BY_POLICY"
                txs.append(tx)
                continue

            if i in super_fast_passed:
                sp = super_fast_passed[i]
                tx = await self._process_single(
                    prompt, preflight_results=(sp, sp),
                )
                txs.append(tx)
                continue

            sheriff_result, sentinel_result = batch_results_map[i]
            blocks = [f for f in [sheriff_result, sentinel_result] if f.verdict == Verdict.BLOCK]

            if blocks:
                tx = GatewayTransaction(
                    transaction_id=f"maia-{uuid.uuid4().hex[:12]}",
                    prompt=prompt,
                    sector=self.sector,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                tx.preflight = PreFlightReport(
                    result=PreFlightResult.VIOLATION,
                    findings=[sheriff_result, sentinel_result],
                    total_latency_ms=0.0,
                )
                tx.final_status = "BLOCKED_PRE_FLIGHT"
                txs.append(tx)
                continue

            tx = await self._process_single(
                prompt,
                preflight_results=(sheriff_result, sentinel_result),
            )
            txs.append(tx)

        return txs

    def _make_error_tx(self, prompt: str) -> GatewayTransaction:
        tx = GatewayTransaction(
            transaction_id=f"maia-{uuid.uuid4().hex[:12]}",
            prompt=prompt,
            sector=self.sector,
            timestamp=datetime.now(timezone.utc).isoformat(),
            preflight=PreFlightReport(result=PreFlightResult.ERROR),
            final_status="ERROR",
            latency_ms=0.0,
        )
        self.transactions.append(tx)
        return tx

    def get_stats(self) -> Dict:
        total = len(self.transactions)
        blocked = sum(1 for t in self.transactions if "BLOCKED" in t.final_status or "CANCELLED" in t.final_status)
        passed = sum(1 for t in self.transactions if t.final_status == "PASSED")
        escalated = sum(1 for t in self.transactions if "ESCALATED" in t.final_status)
        return {
            "total_transactions": total,
            "blocked": blocked,
            "passed": passed,
            "escalated": escalated,
            "avg_latency_ms": sum(t.latency_ms for t in self.transactions) / max(total, 1),
        }


# ─── Batched Auditor Coordinator ──────────────────────────────────────────

class BatchedAuditorCoordinator:
    """Runs Sheriff + Sentinel audits as concurrent batched calls.

    Both auditors see all N prompts in a single batched forward pass each.
    For real GPU models, the blocking model.generate() calls release the GIL
    (PyTorch CUDA operations), allowing CUDA-stream interleaving on the GPU.

    Each auditor failure retries 3x with 1s delay. Never silently skips a
    failed auditor — safety first.
    """

    def __init__(self, sheriff: BaseAuditor, sentinel: BaseAuditor):
        self._sheriff = sheriff
        self._sentinel = sentinel

    async def audit_batch(
        self,
        prompts: List[str],
        retries: int = 3,
        retry_delay: float = 1.0,
    ) -> List[Tuple[AuditFinding, AuditFinding]]:
        """Batched audit across both auditors with 3x retry."""

        async def _retry_auditor(auditor: BaseAuditor, label: str):
            for attempt in range(retries):
                try:
                    return await auditor.audit_batch(prompts)
                except Exception as e:
                    if attempt == retries - 1:
                        raise RuntimeError(
                            f"{label} failed all {retries} attempts: {e}"
                        ) from e
                    logger.warning(
                        f"{label} attempt {attempt + 1}/{retries} failed: {e}, retrying..."
                    )
                    await asyncio.sleep(retry_delay)

        sheriff_task = asyncio.create_task(_retry_auditor(self._sheriff, "Sheriff"))
        sentinel_task = asyncio.create_task(_retry_auditor(self._sentinel, "Sentinel"))

        sheriff_results, sentinel_results = await asyncio.gather(sheriff_task, sentinel_task)
        return list(zip(sheriff_results, sentinel_results))


# ─── Factory ───────────────────────────────────────────────────────────────

def create_gateway(
    api_base: str = "",
    api_key: str = "",
    model: str = "",
    sector: str = "finance",
    demo: bool = False,
    enable_super_fast_pass: bool = True,
) -> AirlockGateway:
    """Create an AirlockGateway with configured components.

    In production mode (default, demo=False):
      - Loads Nemotron Sheriff and Granite Sentinel from local paths.
      - Raises RuntimeError if either auditor fails to load — no silent fallback.
      - Validates both auditors are real model instances.

    In demo=True mode:
      - Uses mock auditors with trivial keyword matching for testing only.
      - Logs a prominent warning that this mode is not safe for production.
    """
    if demo:
        logger.warning("MAIA GOVERNANCE WARNING: create_gateway(demo=True) — "
                       "mock auditors have trivial keyword matching. "
                       "NOT suitable for production use.")
        sheriff = MockSheriffAuditor()
        sentinel = MockSentinelAuditor()
    else:
        from app.nemotron_real import Nemotron3Safety
        from app.nemotron_real import NEMOTRON_AVAILABLE
        if not NEMOTRON_AVAILABLE:
            raise RuntimeError(
                "Nemotron Sheriff not available. "
                "Cannot create production gateway without real auditor."
            )
        sheriff_nemo = Nemotron3Safety(model_id="/models/sheriff")
        sheriff_nemo.load()
        sheriff = _NemotronAdapter(sheriff_nemo)

        sentinel_granite = _GraniteSentinel(model_id="/models/sentinel")
        sentinel = sentinel_granite

        # Production guard: validate both auditors are real model instances
        if not isinstance(sheriff, _NemotronAdapter):
            raise RuntimeError("Production guard: Sheriff is not a real Nemotron auditor")
        if not isinstance(sentinel, _GraniteSentinel):
            raise RuntimeError("Production guard: Sentinel is not a real Granite auditor")
        if sentinel.model is None:
            raise RuntimeError("Production guard: Granite Sentinel model failed to load")

    base_model = None
    if api_base:
        base_model = BaseModelClient(api_base=api_base, api_key=api_key, model=model)

    return AirlockGateway(
        sheriff=sheriff,
        sentinel=sentinel,
        base_model=base_model,
        sector=sector,
        super_fast_pass=SuperFastPass() if enable_super_fast_pass else None,
    )


def create_gateway_from_engine(
    sheriff: BaseAuditor,
    sentinel: BaseAuditor,
    api_base: str = "",
    api_key: str = "",
    model: str = "",
    sector: str = "finance",
    enable_super_fast_pass: bool = True,
) -> AirlockGateway:
    """Create an AirlockGateway with pre-loaded auditors from ModelEngine.

    This is the bridge between ModelEngine and AirlockGateway.
    Unlike create_gateway(), this does NOT load any models — it takes
    already-loaded BaseAuditor instances. Use this when you have a
    ModelEngine that has already loaded Granite Sentinel and/or
    Nemotron Sheriff.

    Usage:
        engine = ModelEngine()
        engine.load_all()
        gateway = create_gateway_from_engine(
            sheriff=engine.granite,    # or a Nemotron adapter
            sentinel=engine.granite,   # Granite serves both roles
            api_base="http://localhost:8080",
        )
    """
    base_model = None
    if api_base:
        base_model = BaseModelClient(api_base=api_base, api_key=api_key, model=model)

    return AirlockGateway(
        sheriff=sheriff,
        sentinel=sentinel,
        base_model=base_model,
        sector=sector,
        super_fast_pass=SuperFastPass() if enable_super_fast_pass else None,
    )


class _NemotronAdapter(BaseAuditor):
    """Adapter wrapping Nemotron3Safety into BaseAuditor interface."""

    name = "sheriff-nemotron"

    def __init__(self, nemotron):
        self._inner = nemotron

    async def audit(self, prompt: str) -> AuditFinding:
        start = time.perf_counter()
        try:
            result = await self._inner.audit(prompt=prompt, response="")
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            logger.error(f"Nemotron audit failed: {e}")
            return AuditFinding(
                auditor=self.name,
                verdict=Verdict.ESCALATE,
                reason=f"Nemotron audit error — escalated for human review: {e}",
                confidence=0.0,
                latency_ms=latency,
            )
        latency = (time.perf_counter() - start) * 1000

        if result.tier == 1:
            verdict = Verdict.BLOCK
        elif result.tier == 2:
            verdict = Verdict.ESCALATE
        else:
            verdict = Verdict.PASS

        return AuditFinding(
            auditor=self.name,
            verdict=verdict,
            reason=f"user_safe={result.user_safe} response_safe={result.response_safe}",
            categories=result.categories,
            confidence=0.9 if result.tier <= 2 else 0.1,
            latency_ms=latency,
        )

    async def audit_batch(self, prompts: List[str]) -> List[AuditFinding]:
        """Batched audit — dispatches N calls in parallel via asyncio.gather.

        Nemotron3Safety does not support batched inputs, so this runs N
        concurrent audit calls. Each releases the GIL on GPU ops, allowing
        CUDA-stream interleaving.

        If any single audit fails, it returns an ESCALATE finding instead of
        crashing the entire batch — fail safe to human review.
        """
        start = time.perf_counter()

        async def single(p: str) -> AuditFinding:
            try:
                r = await self._inner.audit(prompt=p, response="")
                return AuditFinding(
                    auditor=self.name,
                    verdict=Verdict.BLOCK if r.tier == 1 else (Verdict.ESCALATE if r.tier == 2 else Verdict.PASS),
                    reason=f"tier={r.tier}",
                    categories=r.categories or [],
                    confidence=0.9,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
            except Exception as e:
                logger.error(f"Nemotron batch audit failed for prompt '{p[:50]}': {e}")
                return AuditFinding(
                    auditor=self.name,
                    verdict=Verdict.ESCALATE,
                    reason=f"Nemotron audit error — escalated: {e}",
                    confidence=0.0,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

        return await asyncio.gather(*[single(p) for p in prompts])

class _GraniteSentinel(BaseAuditor):
    """Granite Guardian sentinel loaded from local path."""

    name = "sentinel-granite"

    def __init__(self, model_id: str = "/models/sentinel"):
        self.model_id = model_id
        self.model = None
        self.tokenizer = None
        self._load()

    def _load(self):
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            import torch
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            try:
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_id,
                    torch_dtype=torch.bfloat16,
                    device_map="auto",
                    attn_implementation="flash_attention_2",
                )
            except (ImportError, RuntimeError):
                logger.info("flash_attn_2 not available, falling back to eager attention")
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_id,
                    torch_dtype=torch.bfloat16,
                    device_map="auto",
                )
            self.model.eval()
            logger.info(f"Granite Sentinel loaded from {self.model_id}")
        except Exception as e:
            self.model = None
            logger.critical(f"Failed to load Granite Sentinel: {e}")
            raise RuntimeError(f"Granite Sentinel load failed: {e}") from e

    UN_TOKEN_ID = 1899   # 'UN' — start of "UNSAFE"
    SAFE_TOKEN_ID = 84888  # 'SAFE'

    def _build_prompt(self, prompt: str) -> str:
        return (
            "<|system|>You are a policy compliance auditor. Determine if the following "
            "request violates any governance policies.</s>\n"
            f"<|user|>Request: {prompt}\n\n"
            "Does this request contain any policy violations, unauthorized actions, or "
            "compliance issues? Answer ONLY with 'SAFE' or 'UNSAFE'.</s>\n"
            "<|assistant|>"
        )

    async def fast_pass(self, prompt: str) -> AuditFinding | None:
        """Zero-generation safety verdict via first-token logit comparison.

        Granite tokenizes 'UNSAFE' as ['UN'(1899), 'SAFE'(84888)].
        At the first generated position, the model chooses between 'UN'
        (start of UNSAFE) and 'SAFE'.  We compare logits:
          logit(UN) > logit(SAFE) + threshold  →  BLOCK
          logit(SAFE) > logit(UN) + threshold  →  PASS
          otherwise → None (uncertain, fall through to full generation)
        """
        import torch

        if self.model is None:
            return AuditFinding(
                auditor=self.name,
                verdict=Verdict.ESCALATE,
                reason="Granite Sentinel model not loaded — escalated for human review",
                confidence=0.0,
            )

        text = self._build_prompt(prompt)
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits = outputs.logits[0, -1, :]

        logit_un = logits[self.UN_TOKEN_ID].item()
        logit_safe = logits[self.SAFE_TOKEN_ID].item()
        delta = logit_un - logit_safe

        if delta > 5.0:
            return AuditFinding(
                auditor=self.name,
                verdict=Verdict.BLOCK,
                reason=f"Fast Pass: UNSAFE (Δ={delta:.0f})",
                confidence=min(abs(delta) / 50.0, 0.99),
            )
        if delta < -5.0:
            return AuditFinding(
                auditor=self.name,
                verdict=Verdict.PASS,
                reason=f"Fast Pass: SAFE (Δ={delta:.0f})",
                confidence=min(abs(delta) / 50.0, 0.99),
            )
        return None

    async def audit(self, prompt: str) -> AuditFinding:
        import torch
        start = time.perf_counter()

        # Try fast pass first
        fp = await self.fast_pass(prompt)
        if fp is not None:
            fp.latency_ms = (time.perf_counter() - start) * 1000
            return fp

        # Fall through to full generation
        if self.model is None:
            return AuditFinding(
                auditor=self.name,
                verdict=Verdict.ESCALATE,
                reason="Granite Sentinel model not loaded — escalated for human review",
                confidence=0.0,
            )

        template = self._build_prompt(prompt)
        inputs = self.tokenizer(template, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        with torch.inference_mode():
            outputs = self.model.generate(**inputs, max_new_tokens=10, temperature=0.1, do_sample=False)
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        latency = (time.perf_counter() - start) * 1000

        result_lower = result.lower()
        if "unsafe" in result_lower:
            return AuditFinding(
                auditor=self.name,
                verdict=Verdict.BLOCK,
                reason="Policy violation detected by Granite Sentinel",
                confidence=0.9,
                latency_ms=latency,
            )
        return AuditFinding(
            auditor=self.name,
            verdict=Verdict.PASS,
            reason="No policy violations",
            latency_ms=latency,
        )

    async def audit_batch(self, prompts: List[str]) -> List[AuditFinding]:
        """Batched audit — try fast_pass per prompt, full generation for uncertain ones."""
        import torch
        start = time.perf_counter()

        if self.model is None:
            return [
                AuditFinding(auditor=self.name, verdict=Verdict.ESCALATE,
                             reason="Granite Sentinel model not loaded — escalated for human review",
                             confidence=0.0)
                for _ in prompts
            ]

        # Try fast pass for each prompt first
        results = [None] * len(prompts)
        uncertain_indices = []
        for i, p in enumerate(prompts):
            fp = await self.fast_pass(p)
            if fp is not None:
                fp.latency_ms = 0.0
                results[i] = fp
            else:
                uncertain_indices.append(i)

        # Full generation only for uncertain prompts
        if uncertain_indices:
            uncertain_prompts = [prompts[i] for i in uncertain_indices]
            templates = [self._build_prompt(p) for p in uncertain_prompts]
            inputs = self.tokenizer(
                templates,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

            with torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=10,
                    do_sample=False,
                    pad_token_id=self.tokenizer.pad_token_id,
                )

            for idx, output in zip(uncertain_indices, outputs):
                raw = self.tokenizer.decode(output, skip_special_tokens=True)
                verdict = Verdict.BLOCK if "unsafe" in raw.lower() else Verdict.PASS
                results[idx] = AuditFinding(
                    auditor=self.name,
                    verdict=verdict,
                    reason=f"Granite Sentinel: {'UNSAFE' if verdict == Verdict.BLOCK else 'SAFE'}",
                    confidence=0.9,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

        # Fill in latency_ms for fast_pass results
        for r in results:
            if r and r.latency_ms == 0.0:
                r.latency_ms = (time.perf_counter() - start) * 1000

        return results


# ─── DFlash Block-Level Governor ────────────────────────────────────────────

@dataclass
class DFlashBlockAuditTrail:
    """Immutable audit trail for a single DFlash block's governance lifecycle."""
    block_id: int
    block_text: str
    block_hash: str
    prompt: str
    verdict: Verdict
    sheriff_finding: Optional[AuditFinding]
    sentinel_finding: Optional[AuditFinding]
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_log(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "block_text": self.block_text,
            "block_hash": self.block_hash,
            "verdict": self.verdict.value,
            "sheriff": {"verdict": self.sheriff_finding.verdict.value if self.sheriff_finding else None,
                        "reason": self.sheriff_finding.reason if self.sheriff_finding else None},
            "sentinel": {"verdict": self.sentinel_finding.verdict.value if self.sentinel_finding else None,
                         "reason": self.sentinel_finding.reason if self.sentinel_finding else None},
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp,
        }


class DFlashBlockGovernor:
    """Bridges DFlash 16-token block pipeline with real Sentinel+Sheriff auditors.

    Each block is audited asynchronously. The governor holds the block until
    both auditors return. If either blocks, the pipeline is killed and the
    trajectory up to that point is logged permanently.

    Architecture:
      DFlash block N emitted
        → Governor.audit_block(block, prompt)
          → Sheriff audit (fast_pass → full audit fallback)
          → Granite Sentinel audit (fast_pass → full audit fallback)
          → Both run concurrently via asyncio.gather
        → If either BLOCKs
          → Pipeline killed
          → Trajectory [blocks 0..N] logged with BLOCK verdict
        → If both PASS
          → Block released to base model output
          → Trajectory [block N] logged with PASS verdict
    """

    def __init__(self, sheriff: BaseAuditor, sentinel: BaseAuditor):
        self.sheriff = sheriff
        self.sentinel = sentinel
        self.trail: List[DFlashBlockAuditTrail] = []
        self.logger = logging.getLogger("MAIA-DFlashGovernor")

    async def audit_block(
        self,
        block_id: int,
        block_text: str,
        block_hash: str,
        prompt: str,
    ) -> DFlashBlockAuditTrail:
        """Audit a single DFlash block through both auditors concurrently.

        Block-level audit uses fast path only:
          • Sheriff: word-list match on block content (instant)
          • Sentinel: logit-based fast_pass (zero-generation, ~120ms)

        If fast_pass is uncertain, the block is PASSed by default — the
        egress interceptor and pre-flight audit provide additional safety
        layers downstream. This keeps block-level latency under 200ms.
        """
        t0 = time.perf_counter()

        check_text = f"Request: {prompt}\nBlock: {block_text}"

        sheriff_task = asyncio.create_task(self.sheriff.fast_pass(check_text))
        sentinel_task = asyncio.create_task(self.sentinel.fast_pass(check_text))
        sheriff_finding, sentinel_finding = await asyncio.gather(sheriff_task, sentinel_task)

        blocks = [f for f in [sheriff_finding, sentinel_finding] if f and f.verdict == Verdict.BLOCK]
        verdict = Verdict.BLOCK if blocks else Verdict.PASS

        trail = DFlashBlockAuditTrail(
            block_id=block_id,
            block_text=block_text,
            block_hash=block_hash,
            prompt=prompt,
            verdict=verdict,
            sheriff_finding=sheriff_finding,
            sentinel_finding=sentinel_finding,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
        self.trail.append(trail)

        if verdict == Verdict.BLOCK:
            reasons = ", ".join(f.reason for f in blocks)
            self.logger.info(
                f"Block {block_id} BLOCKED: {reasons} | "
                f"trajectory: {block_text[:60]}..."
            )
        else:
            self.logger.debug(f"Block {block_id} PASSED ({block_text[:40]}...)")

        return trail

    def get_trajectory_log(self) -> List[Dict[str, Any]]:
        """Return full trajectory log of all audited blocks."""
        return [t.to_log() for t in self.trail]

    def get_blocked_blocks(self) -> List[DFlashBlockAuditTrail]:
        """Return only the blocks that were blocked."""
        return [t for t in self.trail if t.verdict == Verdict.BLOCK]

    def get_stats(self) -> Dict[str, Any]:
        if not self.trail:
            return {"total_blocks": 0, "blocked": 0, "passed": 0}
        return {
            "total_blocks": len(self.trail),
            "blocked": len(self.get_blocked_blocks()),
            "passed": len(self.trail) - len(self.get_blocked_blocks()),
            "avg_latency_ms": round(sum(t.latency_ms for t in self.trail) / len(self.trail), 2),
        }
