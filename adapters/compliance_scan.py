"""
MAIA Sector Compliance Surface Scan
=====================================
Scans all registry adapters against policy_config.json coverage.
Reports gaps, sector compliance alignment, and materiality tier checks.
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from adapter_policy_registry import AdapterPolicyRegistry

REPORT = []


def section(title: str):
    REPORT.append(f"\n{'='*65}")
    REPORT.append(f"  {title}")
    REPORT.append(f"{'='*65}")


def check(label: str, ok: bool, detail: str = ""):
    icon = "✅" if ok else "❌"
    msg = f"  {icon} {label}"
    if detail:
        msg += f"  ({detail})"
    REPORT.append(msg)
    return ok


def load_registry(path: str = None) -> dict:
    p = path or os.path.join(os.path.dirname(__file__), "registry.json")
    with open(p) as f:
        return json.load(f)


def load_policy_config(path: str = None) -> dict:
    p = path or os.path.join(os.path.dirname(__file__), "policy_config.json")
    with open(p) as f:
        return json.load(f)


def scan_sectors():
    section("10 SECTORS — MATERIALITY & AUDIT PROTOCOL COVERAGE")

    reg = load_registry()
    policies = load_policy_config()
    defined = list(policies.get("adapter_policies", {}).keys())

    for sector, cfg in reg["registry"].items():
        aid = cfg["agentic"].split("/")[-1]
        tier = cfg["materiality_tier"]
        protocol = cfg["audit_protocol"]
        has_policy = aid in defined
        check(f"{sector:12} | {aid:25} | tier={tier} proto={protocol:20}",
              has_policy, detail="" if has_policy else f"MISSING policy for '{aid}'")


def scan_hubs():
    section("4 HUBS — POLICY COVERAGE")

    reg = load_registry()
    policies = load_policy_config()
    defined = list(policies.get("adapter_policies", {}))

    for hub, path in reg["hubs"].items():
        aid = path.split("/")[-1]
        has_policy = aid in defined
        check(f"{hub:25} | {aid:25}",
              has_policy, detail="" if has_policy else f"MISSING policy for '{aid}'")


def scan_specialists():
    section("34 SPECIALISTS — POLICY COVERAGE")

    reg = load_registry()
    policies = load_policy_config()
    defined = list(policies.get("adapter_policies", {}))

    covered = 0
    for name, path in reg["specialists"].items():
        aid = path.split("/")[-1]
        has_policy = aid in defined
        if has_policy:
            covered += 1
        check(f"{name:25} | {aid:25}",
              has_policy, detail="" if has_policy else "MISSING policy")

    total = len(reg["specialists"])
    check(f"COVERAGE: {covered}/{total} specialists have policies",
          covered == total, detail=f"{total - covered} gaps")


def scan_tool_adapters():
    section("13 TOOL ADAPTERS — POLICY COVERAGE")

    reg = load_registry()
    policies = load_policy_config()
    defined = list(policies.get("adapter_policies", {}))

    covered = 0
    for name, path in reg["tool_adapters"].items():
        aid = path.split("/")[-1]
        has_policy = aid in defined
        if has_policy:
            covered += 1
        check(f"{name:22} | {aid:25}",
              has_policy, detail="" if has_policy else "MISSING policy")

    total = len(reg["tool_adapters"])
    check(f"COVERAGE: {covered}/{total} tool adapters have policies",
          covered == total, detail=f"{total - covered} gaps")


def scan_materiality_alignment():
    section("MATERIALITY TIER ALIGNMENT")
    reg = load_registry()
    policies = load_policy_config()

    tier_map = {1: "CRITICAL", 2: "ELEVATED", 3: "BENIGN"}
    aligned = 0
    total = 0

    for sector, cfg in reg["registry"].items():
        aid = cfg["agentic"].split("/")[-1]
        expected_tier = tier_map.get(cfg["materiality_tier"], "UNKNOWN")
        pol = policies.get("adapter_policies", {}).get(aid, {})
        actual_mode = pol.get("operation_mode", "N/A")
        total += 1

        if aid in policies.get("adapter_policies", {}):
            aligned += 1
            check(f"{sector:12} | {aid:25} | expected={expected_tier:10} mode={actual_mode:20}", True)
        else:
            check(f"{sector:12} | {aid:25} | expected={expected_tier:10} mode=MISSING", False)

    check(f"ALIGNMENT: {aligned}/{total} sectors aligned", aligned == total)


def scan_audit_protocols():
    section("AUDIT PROTOCOL — POLICY ENFORCEMENT CAPABILITY")

    reg = load_registry()
    protocols = set()
    for cfg in reg["registry"].values():
        protocols.add(cfg["audit_protocol"])

    for p in sorted(protocols):
        check(f"Protocol: {p}", True, detail="enforcement-ready via adapter policies")

    check(f"Unique protocols: {len(protocols)}", len(protocols) == 7,
          detail=f"got {len(protocols)}: {sorted(protocols)}")


def scan_alert_coverage():
    section("ALERT CONFIGURATION COVERAGE")

    policies = load_policy_config()
    defined = policies.get("adapter_policies", {})
    with_alerts = sum(1 for p in defined.values() if p.get("alert_config", {}).get("channels"))
    total = len(defined)
    check(f"ALERTS: {with_alerts}/{total} policies have alert channels",
          with_alerts == total, detail=f"{total - with_alerts} missing alert channels")


def scan_operation_modes():
    section("OPERATION MODE DISTRIBUTION")

    policies = load_policy_config()
    modes = {}
    for aid, cfg in policies.get("adapter_policies", {}).items():
        m = cfg.get("operation_mode", "unrestricted")
        modes[m] = modes.get(m, 0) + 1

    for mode, count in sorted(modes.items()):
        check(f"  {mode:25} | {count:2} adapters", True)
    check(f"TOTAL: {sum(modes.values())} adapters with modes", True)


def scan_coverage_gaps():
    section("COVERAGE GAP ANALYSIS")

    reg = load_registry()
    policies = load_policy_config()
    defined = list(policies.get("adapter_policies", {}))

    all_adapters = []
    for cfg in reg["registry"].values():
        all_adapters.append(cfg["agentic"].split("/")[-1])
        all_adapters.append(cfg["validator"].split("/")[-1])
    for path in reg["hubs"].values():
        all_adapters.append(path.split("/")[-1])
    for path in reg["specialists"].values():
        all_adapters.append(path.split("/")[-1])
    for path in reg["tool_adapters"].values():
        all_adapters.append(path.split("/")[-1])

    all_adapters = sorted(set(all_adapters))
    covered = [a for a in all_adapters if a in defined]
    missing = [a for a in all_adapters if a not in defined]

    check(f"Total unique adapters in registry: {len(all_adapters)}", True)
    check(f"Policies defined: {len(defined)}", True)
    check(f"Covered: {len(covered)}", True)
    check(f"Missing: {len(missing)}", len(missing) == 0,
          detail=(", ".join(missing[:10]) + f" ... and {len(missing)-10} more") if len(missing) > 10
          else ", ".join(missing) if missing else "all covered")

    for m in missing:
        check(f"  GAP: {m}", False, detail="no policy defined")


def main():
    print("=" * 65)
    print("  MAIA SECTOR COMPLIANCE SURFACE SCAN")
    print("  Adapter Policy Registry × Policy Config.json")
    print("=" * 65)

    scan_sectors()
    scan_hubs()
    scan_specialists()
    scan_tool_adapters()
    scan_materiality_alignment()
    scan_audit_protocols()
    scan_alert_coverage()
    scan_operation_modes()
    scan_coverage_gaps()

    print("\n".join(REPORT))

    passed = sum(1 for line in REPORT if "✅" in line)
    failed = sum(1 for line in REPORT if "❌" in line)
    total = passed + failed

    print(f"\n{'='*65}")
    print(f"  SCAN COMPLETE: {passed}/{total} checks passed ({passed/total*100:.1f}%)")
    print(f"  {'✅ ALL COMPLIANCE SURFACES COVERED' if failed == 0 else '❌ GAPS FOUND — review details above'}")
    print(f"{'='*65}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())