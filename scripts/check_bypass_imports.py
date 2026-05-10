#!/usr/bin/env python3
"""
MAIA Bypass Import Checker — Phase 2 (CI lint rule).

Scans for banned import patterns that bypass the Airlock Gateway.

Usage:
    python3 scripts/check_bypass_imports.py              # scan full repo
    python3 scripts/check_bypass_imports.py path/to/file  # single file
    python3 scripts/check_bypass_imports.py --ci          # exit 1 on any bypass

Returns exit code:
  0 — no bypasses found
  1 — bypasses found (--ci mode)
  2 — internal error
"""
import ast
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Banned import patterns: (module, name, severity)
# Any file importing these OUTSIDE the allowlist triggers a violation.
BANNED_IMPORTS = [
    # Direct model instantiation — must go through gateway factories
    ("transformers", "AutoModelForCausalLM", "CRITICAL"),
    ("transformers", "AutoModelForTokenClassification", "CRITICAL"),
    ("transformers", "AutoModelForSequenceClassification", "HIGH"),
    ("transformers", "AutoModelForVision2Seq", "HIGH"),
    ("transformers", "pipeline", "HIGH"),
    # Direct API client — must go through gateway sidecar
    ("openai", "AsyncOpenAI", "CRITICAL"),
    ("openai", "OpenAI", "CRITICAL"),
    ("anthropic", "AsyncAnthropic", "HIGH"),
    ("anthropic", "Anthropic", "HIGH"),
]

# Allowlisted files (these are the ONLY files permitted to import directly)
# Format: relative path from repo root
ALLOWLIST = {
    "app/airlock_gateway.py",       # The gateway itself — loads Granite Sentinel
    "app/nemotron_real.py",         # Official Nemotron safety model wrapper
    "app/gemma4_complete.py",       # Official Gemma kernel
    "scripts/test_granite.py",      # Test script
    "scripts/test_inference.py",    # Test script
    "kernel/maia_kernel.py",        # Legacy — will be refactored in Phase 3
    "kernel/optimized_engine_v3.py",# Legacy — will be refactored
    "kernel/e2e_real.py",           # Legacy — will be refactored
    "kernel/optimized_engine.py",   # Legacy — will be refactored
    "kernel/optimized_engine_v2.py",# Legacy — will be refactored
    "kernel/autobatch_kernel.py",   # Legacy — will be refactored
    "kernel/e2e_v4.py",             # Legacy — will be refactored
    "app/auditor_stack.py",         # Legacy — will be refactored
    "app/gemma4_kernel.py",         # Legacy — will be refactored
    "app/nemotron_airlock.py",      # Legacy — will be refactored
    "app/speculation/dflash_engine.py", # Legacy — will be refactored
    "app/speculation/kernel.py",    # Legacy — will be refactored
    "app/main.py",                  # Uses AsyncOpenAI for LoRAX client route
    "app/airlock.py",               # PVI module — will be refactored
    "app/circuit_breaker.py",       # Uses AsyncOpenAI
    "app/supervisor_router.py",     # Uses AsyncOpenAI
    "app/rag.py",                   # Uses AsyncOpenAI
    "app/auditing.py",              # Uses AsyncOpenAI
    "app/context.py",               # Uses AsyncOpenAI
    "tests/test_airlock.py",        # Test file
    "tests/conftest.py",            # Test fixture
    "tests/test_airlock_gateway.py",# Test file
    "tests/test_race_guard.py",     # Test file
    "tests/test_e2e_latency.py",    # Test file
    "tests/test_comprehensive_orig.py", # Test file
    "train_adapter.py",             # Training script
    "docs/MODEL_STACK.md",          # Documentation-only
    "scripts/check_bypass_imports.py",  # Self — defines patterns as strings
}

# Direct API call patterns (method calls, not imports)
DIRECT_CALL_PATTERNS = [
    ".chat.completions.create",
]


def normalize_path(filepath: str) -> str:
    """Convert absolute path to repo-relative."""
    path = Path(filepath).resolve()
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def check_file(filepath: str, ci_mode: bool = False) -> list:
    """Check a single file for banned imports. Returns list of violations."""
    rel_path = normalize_path(filepath)
    violations = []

    # Skip non-Python files
    if not filepath.endswith(".py"):
        return violations

    # Read source
    try:
        with open(filepath) as f:
            source = f.read()
    except (FileNotFoundError, IOError) as e:
        return [{"file": rel_path, "line": 0, "severity": "ERROR", "message": str(e)}]

    # Parse AST
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return [{"file": rel_path, "line": e.lineno or 0, "severity": "ERROR",
                 "message": f"Syntax error: {e}"}]

    # Check imports
    for node in ast.walk(tree):
        # import X
        if isinstance(node, ast.Import):
            for alias in node.names:
                for mod, name, sev in BANNED_IMPORTS:
                    if alias.name == mod or alias.name.startswith(mod + "."):
                        violations.append({
                            "file": rel_path,
                            "line": node.lineno,
                            "severity": sev,
                            "message": f"Import '{alias.name}' bypasses Airlock Gateway. "
                                       f"Use gateway factories instead. ({sev})",
                        })

        # from X import Y
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            for alias in node.names:
                imported_name = alias.name if alias.asname is None else alias.asname
                for mod, name, sev in BANNED_IMPORTS:
                    if node.module == mod and imported_name == name:
                        violations.append({
                            "file": rel_path,
                            "line": node.lineno,
                            "severity": sev,
                            "message": f"'{imported_name}' imported from '{node.module}' "
                                       f"bypasses Airlock Gateway. Use gateway factories instead. ({sev})",
                        })

    # Check for direct API call patterns
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue
        for pattern in DIRECT_CALL_PATTERNS:
            if pattern in stripped and "def " not in stripped and "class " not in stripped:
                violations.append({
                    "file": rel_path,
                    "line": i,
                    "severity": "CRITICAL",
                    "message": f"Direct API call pattern '{pattern}' detected. "
                               f"Must route through Airlock Gateway. (CRITICAL)",
                })

    # Apply allowlist — remove violations for allowlisted files
    if rel_path in ALLOWLIST:
        violations = []

    return violations


def main():
    ci_mode = "--ci" in sys.argv

    # Determine files to check
    targets = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not targets:
        # Walk all Python files in the repo
        targets = []
        for root, dirs, files in os.walk(REPO_ROOT):
            # Skip venv, __pycache__, .git
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "venv", ".venv",
                                                      "node_modules", ".tox", "dist", "build")]
            for f in files:
                if f.endswith(".py"):
                    targets.append(os.path.join(root, f))

    all_violations = []
    for target in targets:
        violations = check_file(target, ci_mode=ci_mode)
        all_violations.extend(violations)

    # Sort by severity then file
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "ERROR": 4}
    all_violations.sort(key=lambda v: (severity_order.get(v["severity"], 99), v["file"], v["line"]))

    # Print
    if all_violations:
        print("=" * 72)
        print(f"MAIA Bypass Import Check — {len(all_violations)} violation(s) found")
        print("=" * 72)
        for v in all_violations:
            sev = v["severity"].ljust(10)
            print(f"  [{sev}] {v['file']}:{v['line']}")
            print(f"         {v['message']}")
        print("=" * 72)

        if ci_mode:
            critical = sum(1 for v in all_violations if v["severity"] == "CRITICAL")
            print(f"\nFAILED: {critical} CRITICAL, {len(all_violations)} total violations")
            sys.exit(1)
    else:
        print(f"MAIA Bypass Import Check — 0 violations found across all files")
        sys.exit(0)


if __name__ == "__main__":
    main()
