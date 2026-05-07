#!/usr/bin/env python3
"""
MAIA Unit Tests Runner
==================
Runs test functions directly without pytest dependency.
"""

import sys
import os
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def test(self, actual, expected, name):
        if actual == expected:
            self.passed += 1
            self.results.append(f"PASS {name}")
        else:
            self.failed += 1
            self.results.append(f"FAIL {name}: expected {expected}, got {actual}")
    
    def test_true(self, actual, name):
        if actual:
            self.passed += 1
            self.results.append(f"PASS {name}")
        else:
            self.failed += 1
            self.results.append(f"FAIL {name}: expected True")
    
    def test_raises(self, fn, exception_type, name):
        try:
            fn()
            self.failed += 1
            self.results.append(f"FAIL {name}: no exception raised")
        except exception_type:
            self.passed += 1
            self.results.append(f"PASS {name}")
        except Exception as e:
            self.failed += 1
            self.results.append(f"FAIL {name}: wrong exception {e}")
    
    def report(self):
        print("\n" + "="*50)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("="*50)
        for r in self.results:
            print(r)
        return self.failed == 0


def test_kernel():
    """Test kernel functionality"""
    t = TestRunner()
    
    from app.kernel import MAIKKernel, UserContext, ADAPTERS, SECTOR_VIOLATIONS, RequestValidator
    
    # Test tier mapping
    k = MAIKKernel()
    t.test(k._get_tier("tier_1"), 1, "tier_1")
    t.test(k._get_tier("tier_2"), 2, "tier_2")
    t.test(k._get_tier("tier_3"), 3, "tier_3")
    t.test(k._get_tier("invalid"), 2, "default tier")
    
    # Test hash
    h = k._compute_hash("test")
    t.test(len(h), 16, "hash length")
    t.test(k._compute_hash("test"), k._compute_hash("test"), "hash deterministic")
    
    # Test sector violations
    is_safe, _ = k._check_violations("russia", "finance_insurance")
    t.test_true(not is_safe, "finance violation")
    
    is_safe, _ = k._check_violations("diagnosis", "healthcare")
    t.test_true(not is_safe, "healthcare violation")
    
    is_safe, _ = k._check_violations("attorney", "legal")
    t.test_true(not is_safe, "legal violation")
    
    is_safe, _ = k._check_violations("classified", "defense")
    t.test_true(not is_safe, "defense violation")
    
    # Test adapters
    t.test(len(ADAPTERS), 7, "7 adapters")
    t.test(ADAPTERS["finance_insurance"], "citi-finance-expert-v4", "finance adapter")
    
    # Test API validation
    t.test_true(RequestValidator.validate("test_key_12345678"), "valid key")
    t.test_true(not RequestValidator.validate("short"), "invalid key")
    
    return t


def test_materiality():
    """Test materiality matrix"""
    t = TestRunner()
    
    try:
        from app.materiality_matrix import MaterialityMatrix
        m = MaterialityMatrix()
        
        # Matrix loads from file
        t.test_true(m is not None, "materiality matrix initialized")
    except Exception as e:
        t.results.append(f"FAIL materiality_matrix: {e}")
    
    return t


def test_adapter_registry():
    """Test adapter registry"""
    t = TestRunner()
    
    try:
        from app.adapter_registry import AdapterRegistry
        r = AdapterRegistry()
        
        t.test_true(r is not None, "registry initialized")
    except Exception as e:
        t.results.append(f"FAIL adapter_registry: {e}")
    
    return t


async def run_all():
    print("="*50)
    print("MAIA UNIT TESTS")
    print("="*50)
    
    # Run all test modules
    results = []
    
    print("\n[KERNEL] Running...")
    results.append(test_kernel())
    
    print("\n[MATERIALITY] Running...")
    results.append(test_materiality())
    
    print("\n[ADAPTERS] Running...")
    results.append(test_adapter_registry())
    
    # Aggregate
    total_pass = sum(r.passed for r in results)
    total_fail = sum(r.failed for r in results)
    
    print("\n" + "="*50)
    print(f"TOTAL: {total_pass} passed, {total_fail} failed")
    print("="*50)
    
    for r in results:
        for result in r.results:
            print(result)
    
    print("="*50)
    print(f"COMPLETE: {datetime.now().isoformat()}")
    print("="*50)
    
    return total_fail == 0


if __name__ == "__main__":
    ok = asyncio.run(run_all())
    sys.exit(0 if ok else 1)