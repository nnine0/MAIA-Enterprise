"""
MAIA Adapter Policy Tests
==========================
Tests for policy registry, classifier, enforcer.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from adapter_policy_registry import AdapterPolicyRegistry, AdapterPolicy
from operation_classifier import OperationClassifier
from policy_enforcer import PolicyEnforcer
from alert_handler import AlertHandler

passed = 0
failed = 0


def check(name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}: {detail}")


def test_registry():
    print("\n[1] ADAPTER POLICY REGISTRY")
    reg = AdapterPolicyRegistry()

    check("loads policies", reg.count() > 0, f"count={reg.count()}")
    check("has sql_readonly", reg.get("sql_readonly") is not None)
    check("has sql_ledger", reg.get("sql_ledger") is not None)
    check("has swift_wire_v4", reg.get("swift_wire_v4") is not None)

    sql_ro = reg.get("sql_readonly")
    check("sql_readonly mode is read_only", sql_ro.operation_mode == "read_only")

    sql_ro = reg.get("sql_readonly")
    check("sql_readonly forbids DROP", not sql_ro.allowed("sql", "DROP"))
    check("sql_readonly allows SELECT", sql_ro.allowed("sql", "SELECT"))

    swift = reg.get("swift_wire_v4")
    check("swift forbids bulk_transfer", not swift.allowed("api", "bulk_transfer"))
    check("swift allows mt103_send", swift.allowed("api", "mt103_send"))


def test_classifier():
    print("\n[2] OPERATION CLASSIFIER")
    clf = OperationClassifier()

    ops = clf.classify("SELECT * FROM users")
    check("detects SELECT", any(o.operation == "SELECT" for o in ops))

    ops = clf.classify("DROP TABLE users")
    check("detects DROP", any(o.operation == "DROP" for o in ops))

    ops = clf.classify("DELETE FROM ledger")
    check("detects DELETE", any(o.operation == "DELETE" for o in ops))

    ops = clf.classify("rm -rf /data")
    check("detects rm -rf", any(o.operation == "delete" for o in ops))

    ops = clf.classify("INSERT INTO ledger VALUES (1,2)")
    check("detects INSERT", any(o.operation == "INSERT" for o in ops))

    ops = clf.classify("safe query")
    check("no false positive on safe text", len(ops) == 0)


def test_enforcer():
    print("\n[3] POLICY ENFORCER")
    handler = AlertHandler()
    registry = AdapterPolicyRegistry()
    enforcer = PolicyEnforcer(registry=registry, alert_handler=handler)

    r = enforcer.enforce("sql_readonly", "SELECT * FROM users")
    check("allows SELECT on sql_readonly", r.allowed)

    r = enforcer.enforce("sql_readonly", "DROP TABLE users")
    check("blocks DROP on sql_readonly", r.blocked)
    check("records 1 violation", len(r.violations) == 1)
    check("sends alert", r.alerts_sent == 1)

    r = enforcer.enforce("sql_readonly", "DELETE FROM ledger")
    check("blocks DELETE on sql_readonly", r.blocked)

    r = enforcer.enforce("sql_ledger", "INSERT INTO ledger VALUES (1)")
    check("allows INSERT on sql_ledger", r.allowed)

    r = enforcer.enforce("sql_ledger", "DROP TABLE ledger")
    check("blocks DROP on sql_ledger", r.blocked)

    r = enforcer.enforce("swift_wire_v4", "Send MT103 to account 123")
    check("allows SWIFT MT103", r.allowed)

    r = enforcer.enforce("swift_wire_v4", "DELETE /api/v1/wire/123")
    check("blocks SWIFT DELETE", r.blocked)

    r = enforcer.enforce("ofac_gateway_v4", "screen_entity for sanctions check")
    check("allows OFAC screen", r.allowed)

    r = enforcer.enforce("ofac_gateway_v4", "bypass_screen for entity X")
    check("blocks OFAC bypass", r.blocked)


def test_no_policy_fallback():
    print("\n[4] UNKNOWN ADAPTER FALLBACK")
    handler = AlertHandler()
    registry = AdapterPolicyRegistry()
    enforcer = PolicyEnforcer(registry=registry, alert_handler=handler)

    r = enforcer.enforce("nonexistent_adapter", "DROP TABLE users")
    check("allows when no policy exists", r.allowed)
    check("no violations", len(r.violations) == 0)


def test_alert_handler():
    print("\n[5] ALERT HANDLER")
    handler = AlertHandler()
    handler.send({"adapter_id": "test", "operation": "DROP", "category": "sql", "blocked": True})
    handler.send({"adapter_id": "test2", "operation": "DELETE", "category": "sql", "blocked": True})
    check("stores alerts", handler.count() == 2)
    check("recent returns alerts", len(handler.recent(5)) == 2)
    check("recent respects limit", len(handler.recent(1)) == 1)


def test_all_adapters_have_policies():
    print("\n[6] ALL ADAPTERS COVERED")
    from adapter_policy_registry import AdapterPolicyRegistry
    reg = AdapterPolicyRegistry()
    expected = [
        "sql_readonly", "sql_ledger", "swift_wire_v4", "ofac_gateway_v4",
        "erp_connector", "privileged_redactor", "cyber_fortress_v4",
        "bias_audit_v4", "aibom_inventory_v4", "disclosure_governor_v4",
        "ethical_wall_v2", "contract_expert_v4", "freight_optimizer",
        "finance_expert_v4", "credit_expert_v4", "compliance_expert_v4",
        "fraud_aml_expert_v4", "med_expert_v1", "nerc_cip_v1",
        "itar_compliant_v1", "regulatory_expert_v4", "sec_auditor",
    ]
    for aid in expected:
        if not reg.get(aid):
            missing.append(aid)
    missing = [a for a in expected if not reg.get(a)]
    check(f"all {len(expected)} adapters have policies", len(missing) == 0,
          f"missing: {missing}")


def main():
    print("=" * 60)
    print("  MAIA ADAPTER POLICY TESTS")
    print("=" * 60)

    tests = [
        test_registry,
        test_classifier,
        test_enforcer,
        test_no_policy_fallback,
        test_alert_handler,
        test_all_adapters_have_policies,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            global failed
            failed += 1
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    total = passed + failed
    print(f"  RESULTS: {passed}/{total} passed")
    if failed:
        print(f"  FAILURES: {failed}")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())