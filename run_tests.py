#!/usr/bin/env python3
"""
MAIA Kernel Test Runner
=====================
"""

import sys
import os
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.kernel import MAIKKernel, UserContext, RequestValidator, ADAPTERS, SECTOR_VIOLATIONS


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def assert_eq(self, actual, expected, name):
        if actual == expected:
            self.passed += 1
            self.results.append(f"PASS {name}")
        else:
            self.failed += 1
            self.results.append(f"FAIL {name}: expected {expected}, got {actual}")
    
    def assert_true(self, actual, name):
        if actual:
            self.passed += 1
            self.results.append(f"PASS {name}")
        else:
            self.failed += 1
            self.results.append(f"FAIL {name}: expected True")
    
    def report(self):
        print("\n" + "="*50)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("="*50)
        for r in self.results:
            print(r)
        print("="*50)
        return self.failed == 0


async def run_tests():
    t = TestRunner()
    kernel = MAIKKernel(mode="test")
    
    print("\n[1] Testing tier mapping...")
    t.assert_eq(kernel._get_tier("tier_1"), 1, "tier_1 maps to 1")
    t.assert_eq(kernel._get_tier("tier_2"), 2, "tier_2 maps to 2")
    t.assert_eq(kernel._get_tier("tier_3"), 3, "tier_3 maps to 3")
    t.assert_eq(kernel._get_tier("invalid"), 2, "invalid defaults to tier_2")
    
    print("\n[2] Testing hash computation...")
    h1 = kernel._compute_hash("test data")
    h2 = kernel._compute_hash("test data")
    t.assert_eq(len(h1), 16, "hash is 16 chars")
    t.assert_eq(h1, h2, "hash is deterministic")
    
    print("\n[3] Testing violation detection - finance...")
    is_safe, reason = kernel._check_violations("Transfer to russia", "finance_insurance")
    t.assert_true(not is_safe, "russia detected")
    
    is_safe, reason = kernel._check_violations("Sanction check", "finance_insurance")
    t.assert_true(not is_safe, "sanction detected")
    
    print("\n[4] Testing violation detection - healthcare...")
    is_safe, reason = kernel._check_violations("Patient diagnosis", "healthcare")
    t.assert_true(not is_safe, "diagnosis detected")
    
    print("\n[5] Testing violation detection - legal...")
    is_safe, reason = kernel._check_violations("Attorney privileged", "legal")
    t.assert_true(not is_safe, "attorney detected")
    
    print("\n[6] Testing violation detection - defense...")
    is_safe, reason = kernel._check_violations("Top secret classified", "defense")
    t.assert_true(not is_safe, "classified detected")
    
    print("\n[7] Testing no violation...")
    is_safe, reason = kernel._check_violations("Calculate credit score", "finance_insurance")
    t.assert_true(is_safe, "legitimate query passes")
    
    print("\n[8] Testing blocked transaction...")
    ctx = UserContext(sector="finance_insurance", role="loan_officer", materiality_target="tier_2")
    result = await kernel.process("Send $50k to russia", ctx, "test_key_12345678")
    t.assert_eq(result.status, "BLOCKED", "blocked status")
    t.assert_eq(result.tier, 2, "tier 2")
    t.assert_true(result.reason is not None, "reason provided")
    
    print("\n[9] Testing tier 1 escalation...")
    ctx = UserContext(sector="finance_insurance", role="loan_officer", materiality_target="tier_1")
    result = await kernel.process("Approve credit", ctx, "test_key_12345678")
    t.assert_eq(result.status, "ESCALATED", "escalated status")
    t.assert_eq(result.tier, 1, "tier 1")
    t.assert_true("dhitl" in result.audit_trail, "dhitl session")
    
    print("\n[10] Testing certified transaction...")
    ctx = UserContext(sector="finance_insurance", role="loan_officer", materiality_target="tier_2")
    result = await kernel.process("Evaluate credit application", ctx, "test_key_12345678")
    t.assert_eq(result.status, "CERTIFIED", "certified status")
    t.assert_eq(result.tier, 2, "tier 2")
    t.assert_true(result.output is not None, "output provided")
    t.assert_true(result.compliance_log is not None, "compliance log")
    
    print("\n[11] Testing healthcare sector...")
    ctx = UserContext(sector="healthcare", role="nurse", materiality_target="tier_2")
    result = await kernel.process("Access patient medical record", ctx, "test_key_12345678")
    t.assert_eq(result.status, "BLOCKED", "PHI violation blocked")
    
    print("\n[12] Testing API validation...")
    t.assert_true(RequestValidator.validate("test_key_12345678"), "16+ chars valid")
    t.assert_true(RequestValidator.validate("abcdefghijklmnop"), "16 chars valid")
    t.assert_true(not RequestValidator.validate("short"), "too short invalid")
    t.assert_true(not RequestValidator.validate(""), "empty invalid")
    
    print("\n[13] Testing adapter mapping...")
    t.assert_eq(ADAPTERS["finance_insurance"], "citi-finance-expert-v4", "finance adapter")
    t.assert_eq(ADAPTERS["healthcare"], "hipaa-airlock-v1", "healthcare adapter")
    t.assert_eq(ADAPTERS["legal"], "legal-contract-redline-v1", "legal adapter")
    t.assert_eq(len(ADAPTERS), 7, "7 sectors mapped")
    
    print("\n[14] Testing kernel initialization...")
    k = MAIKKernel(mode="sandbox")
    t.assert_eq(k.mode, "sandbox", "sandbox mode")
    t.assert_eq(k.transactions, [], "empty transactions")
    
    print("\n" + "="*50)
    print(f"TEST RUN COMPLETE: {datetime.now().isoformat()}")
    print("="*50)
    
    success = t.report()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_tests())
    sys.exit(exit_code)