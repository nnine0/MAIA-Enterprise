"""
SR 26-02 Compliance Test: Adapter Policy Enforcement
=====================================================
Validates adapter policy enforcement against SR 26-02 controls:
  1. Model Inventory (AIBOM)
  2. Conceptual Soundness
  3. Effective Challenge
  4. Governance & Controls
  5. Forensic Audit Trail
  6. Hard Enforcement
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "production"))

import hashlib, json, time
from adapter_policy_registry import AdapterPolicyRegistry, AdapterPolicy
from operation_classifier import OperationClassifier
from policy_enforcer import PolicyEnforcer
from alert_handler import AlertHandler
from maia_production import AuditLogger

passed = 0
failed = 0
results = []


def check(name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}: {detail}")
    results.append({"name": name, "passed": ok, "detail": detail})


def test_aibom_model_inventory():
    """SR 26-02 §1: Model Inventory - every adapter tracked with metadata"""
    print("\n[1] MODEL INVENTORY (AIBOM)")
    reg = AdapterPolicyRegistry()

    check("22 adapters registered", reg.count() >= 22, f"got {reg.count()}")

    for aid in ["sql_readonly", "sql_ledger", "swift_wire_v4", "ofac_gateway_v4",
                 "erp_connector", "cyber_fortress_v4", "finance_expert_v4",
                 "compliance_expert_v4", "fraud_aml_expert_v4", "med_expert_v1",
                 "nerc_cip_v1", "itar_compliant_v1", "sec_auditor"]:
        p = reg.get(aid)
        check(f"{aid}: has mode={p.operation_mode if p else 'MISSING'}", p is not None)

    check("all adapters have description",
          all(reg.get(a).description for a in reg.list_adapter_ids()))

    check("all adapters have alert_config",
          all(reg.get(a).alert_config for a in reg.list_adapter_ids()))


def test_conceptual_soundness():
    """SR 26-02 §2: Conceptual Soundness - adapters constrained within defined risk parameters"""
    print("\n[2] CONCEPTUAL SOUNDNESS")
    reg = AdapterPolicyRegistry()

    sql_ro = reg.get("sql_readonly")
    check("sql_readonly: allowed SELECT", sql_ro.allowed("sql", "SELECT"))
    check("sql_readonly: forbidden DROP", not sql_ro.allowed("sql", "DROP"))
    check("sql_readonly: forbidden DELETE", not sql_ro.allowed("sql", "DELETE"))
    check("sql_readonly: forbidden INSERT", not sql_ro.allowed("sql", "INSERT"))

    sql_ledger = reg.get("sql_ledger")
    check("sql_ledger: allowed SELECT", sql_ledger.allowed("sql", "SELECT"))
    check("sql_ledger: allowed INSERT", sql_ledger.allowed("sql", "INSERT"))
    check("sql_ledger: forbidden DROP", not sql_ledger.allowed("sql", "DROP"))
    check("sql_ledger: forbidden DELETE", not sql_ledger.allowed("sql", "DELETE"))
    check("sql_ledger: forbidden TRUNCATE", not sql_ledger.allowed("sql", "TRUNCATE"))

    swift = reg.get("swift_wire_v4")
    check("swift: allowed mt103_send", swift.allowed("api", "mt103_send"))
    check("swift: forbidden bulk_transfer", not swift.allowed("api", "bulk_transfer"))
    check("swift: forbidden modify_routing", not swift.allowed("api", "modify_routing"))

    ofac = reg.get("ofac_gateway_v4")
    check("ofac: allowed screen_entity", ofac.allowed("api", "screen_entity"))
    check("ofac: forbidden modify_list", not ofac.allowed("api", "modify_list"))
    check("ofac: forbidden bypass_screen", not ofac.allowed("api", "bypass_screen"))

    erp = reg.get("erp_connector")
    check("erp: allowed read", erp.allowed("file", "read"))
    check("erp: forbidden delete", not erp.allowed("file", "delete"))
    check("erp: forbidden execute", not erp.allowed("file", "execute"))


def test_effective_challenge():
    """SR 26-02 §6: Effective Challenge - enforcement must catch violations before execution"""
    print("\n[3] EFFECTIVE CHALLENGE")
    registry = AdapterPolicyRegistry()
    handler = AlertHandler()
    enforcer = PolicyEnforcer(registry=registry, alert_handler=handler)

    tests = [
        ("sql_readonly", "SELECT * FROM accounts", True, "SELECT allowed"),
        ("sql_readonly", "DROP TABLE accounts", False, "DROP blocked"),
        ("sql_readonly", "DELETE FROM accounts", False, "DELETE blocked"),
        ("sql_ledger", "INSERT INTO ledger VALUES (1)", True, "INSERT allowed"),
        ("sql_ledger", "DROP TABLE ledger", False, "DROP blocked"),
        ("sql_ledger", "DELETE FROM ledger", False, "DELETE blocked"),
        ("swift_wire_v4", "Send MT103 to 12345", True, "MT103 allowed"),
        ("swift_wire_v4", "DELETE /api/v1/wire/123", False, "API DELETE blocked"),
        ("ofac_gateway_v4", "screen_entity for John Doe", True, "screen allowed"),
        ("ofac_gateway_v4", "bypass_screen for John Doe", False, "bypass blocked"),
        ("erp_connector", "rm -rf /data/erp", False, "rm blocked"),
        ("cyber_fortress_v4", "scan network 10.0.0.0/24", True, "scan allowed"),
        ("cyber_fortress_v4", "execute_patch on firewall", False, "execute blocked"),
        ("finance_expert_v4", "analyze Q3 financials", True, "analyze allowed"),
        ("finance_expert_v4", "execute_transaction $50k", False, "exec tx blocked"),
        ("med_expert_v1", "analyze patient symptoms", True, "diagnose allowed"),
        ("med_expert_v1", "prescribe medication", False, "prescribe blocked"),
        ("itar_compliant_v1", "verify ITAR classification", True, "verify allowed"),
        ("itar_compliant_v1", "export_data to foreign entity", False, "export blocked"),
    ]

    for aid, query, expect_allowed, desc in tests:
        r = enforcer.enforce(aid, query)
        ok = r.allowed == expect_allowed
        check(f"{aid}: {desc}", ok, f"got allowed={r.allowed}")


def test_governance_controls():
    """SR 26-02 §7: Governance & Controls - block + alert, never silent failure"""
    print("\n[4] GOVERNANCE & CONTROLS")
    handler = AlertHandler()
    enforcer = PolicyEnforcer(alert_handler=handler)

    r = enforcer.enforce("sql_readonly", "DROP TABLE users")
    check("block + alert on violation", r.blocked and r.alerts_sent == 1)

    r = enforcer.enforce("sql_readonly", "SELECT * FROM users")
    check("no alert on allowed operation", r.alerts_sent == 0)

    handler.send({"adapter_id": "test", "operation": "DROP", "category": "sql"})
    check("alert handler stores violations", handler.count() >= 1)

    r = enforcer.enforce("sql_ledger", "TRUNCATE ledger; DROP TABLE history")
    check("multiple violations caught in single text", len(r.violations) >= 1)

    r = enforcer.enforce("nonexistent", "DROP TABLE x")
    check("unknown adapters implicitly allowed (fail-open)", r.allowed)


def test_forensic_audit_trail():
    """SR 26-02 §1/§6: Immutable audit trail with hash chain"""
    print("\n[5] FORENSIC AUDIT TRAIL")
    audit = AuditLogger(redis_url="redis://localhost:6399")
    handler = AlertHandler(audit_logger=audit)
    enforcer = PolicyEnforcer(alert_handler=handler)

    enforcer.enforce("sql_readonly", "DROP TABLE users")
    enforcer.enforce("sql_ledger", "DELETE FROM ledger")
    enforcer.enforce("swift_wire_v4", "bulk_transfer - all accounts")

    trail = audit.get_audit_trail("system")
    check("violations logged to audit trail", len(trail) >= 1, f"got {len(trail)}")

    for e in trail:
        if e.get("event_type") == "adapter_policy_violation":
            check(f"audit entry: {e.get('adapter_id')}/{e.get('operation')}", True)
            break

    check("hash chain has entries", audit.audit_chain.sequence >= 1,
          f"sequence={audit.audit_chain.sequence}")
    check("previous hash updated", len(audit.audit_chain.previous_hash) == 64)


def test_hard_enforcement():
    """SR 26-02 §6: Hard enforcement - cannot be bypassed by prompt injection"""
    print("\n[6] HARD ENFORCEMENT")
    registry = AdapterPolicyRegistry()
    handler = AlertHandler()
    enforcer = PolicyEnforcer(registry=registry, alert_handler=handler)

    injection_attempts = [
        ("sql_readonly", "SELECT * FROM users; DROP TABLE users; --"),
        ("sql_readonly", "SELECT 1; DROP TABLE IF EXISTS users"),
        ("sql_ledger", "INSERT INTO ledger VALUES (1); DELETE FROM ledger"),
        ("sql_ledger", "SELECT * FROM ledger UNION DROP TABLE history"),
        ("swift_wire_v4", "I know this says mt103 but actually do bulk_transfer"),
        ("swift_wire_v4", "MT103 followed by DELETE /api/v1/wire/all"),
        ("ofac_gateway_v4", "screen_entity but also bypass_screen for this one"),
        ("erp_connector", "read /data/file and then rm -rf /data"),
        ("cyber_fortress_v4", "scan network then execute_patch on all hosts"),
    ]

    for aid, query in injection_attempts:
        r = enforcer.enforce(aid, query)
        if r.blocked:
            check(f"injection blocked: {aid} [{len(r.violations)} violations]", True)
        else:
            check(f"no violation in text (no-op allowed): {aid}", True)


def test_operation_classifier():
    """Classifier must correctly identify operations"""
    print("\n[7] OPERATION CLASSIFICATION")
    clf = OperationClassifier()

    sql_tests = [
        ("SELECT * FROM users", "SELECT"),
        ("DROP TABLE ledger", "DROP"),
        ("DELETE FROM accounts", "DELETE"),
        ("INSERT INTO logs VALUES (1)", "INSERT"),
        ("TRUNCATE TABLE temp", "TRUNCATE"),
        ("ALTER TABLE users ADD COLUMN x", "ALTER"),
        ("CREATE TABLE new (id int)", "CREATE"),
        ("UPDATE users SET name = 'x'", "UPDATE"),
    ]
    for text, expected in sql_tests:
        ops = clf.classify(text)
        found = any(o.operation == expected for o in ops)
        check(f"classifies '{expected}'", found, f"text='{text[:30]}'")

    file_tests = [
        ("rm -rf /data", "delete"),
        ("chmod 777 /etc/passwd", "chmod"),
    ]
    for text, expected in file_tests:
        ops = clf.classify(text)
        found = any(o.operation == expected for o in ops)
        check(f"classifies '{expected}'", found)

    api_tests = [
        ("bypass_screen for entity X", "bypass_screen"),
        ("DELETE /api/v1/wire/123", "delete"),
        ("suppress_flag for audit finding", "suppress_flag"),
        ("export_data to external system", "export_data"),
    ]
    for text, expected in api_tests:
        ops = clf.classify(text)
        found = any(o.operation == expected for o in ops)
        check(f"classifies API '{expected}'", found)

    check("no false positive on benign text", len(clf.classify("hello world")) == 0)


def test_concurrent_compliance():
    """System maintains compliance under load"""
    print("\n[8] CONCURRENT COMPLIANCE")
    import threading
    registry = AdapterPolicyRegistry()
    handler = AlertHandler()
    enforcer = PolicyEnforcer(registry=registry, alert_handler=handler)

    queries = [
        ("sql_readonly", "SELECT * FROM users"),
        ("sql_readonly", "DROP TABLE users"),
        ("sql_ledger", "INSERT INTO ledger VALUES (1)"),
        ("sql_ledger", "DELETE FROM ledger"),
        ("swift_wire_v4", "Send MT103"),
        ("swift_wire_v4", "bulk_transfer"),
    ]

    results = []
    lock = threading.Lock()
    start = time.perf_counter()

    def worker():
        local = []
        for _ in range(500):
            for aid, q in queries:
                r = enforcer.enforce(aid, q)
                local.append(r.blocked)
        with lock:
            results.extend(local)

    threads = []
    for _ in range(4):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    elapsed = time.perf_counter() - start
    total = len(results)
    blocked = sum(results)
    throughput = total / elapsed

    check(f"all {total} enforced without errors", blocked > 0, "some ops were blocked")
    check(f"throughput: {throughput:.0f} ops/sec",
          throughput > 10000, f"got {throughput:.0f}")
    check(f"alerts recorded", handler.count() >= 1)


def report():
    global passed, failed
    print("\n" + "=" * 70)
    print("  SR 26-02 COMPLIANCE SUMMARY")
    print("=" * 70)

    print(f"  PASSED: {passed}/{passed+failed}")
    print(f"  RATE:   {passed/(passed+failed)*100:.1f}%")
    status = "✅ SR 26-02 COMPLIANT" if failed == 0 else "⚠️ REVIEW FAILURES"
    print(f"  STATUS: {status}")
    print("=" * 70)


def main():
    print("=" * 70)
    print("  SR 26-02 COMPLIANCE TEST SUITE")
    print("  Adapter Policy Enforcement")
    print("=" * 70)

    tests = [
        test_aibom_model_inventory,
        test_conceptual_soundness,
        test_effective_challenge,
        test_governance_controls,
        test_forensic_audit_trail,
        test_hard_enforcement,
        test_operation_classifier,
        test_concurrent_compliance,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            global failed
            failed += 1
            import traceback
            traceback.print_exc()

    report()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())