#!/usr/bin/env python3
"""
MAIA Import Isolation Hook — Phase 4 (Runtime Enforcement).

Prevents Python code from importing banned modules at runtime.
When a banned import is detected, it:
  1. Logs a CRITICAL bypass event to the BypassMonitor
  2. Raises a RuntimeError (blocks the import)

Install by adding to a sitecustomize.py or the application entry point:

    # At the VERY TOP of main.py / server.py:
    from app.import_isolation import install_import_isolation
    install_import_isolation()

The hook can be configured with:
  - block: If True, raises error (prevents import). If False, logs only.
  - allowlist: Files/modules exempt from checking.

Usage:
    # In application entry point:
    from app.import_isolation import install_import_isolation
    install_import_isolation(block=True)

    # Test mode: log only, don't block
    install_import_isolation(block=False)
"""
import sys
import os
import logging
from typing import Set, Optional

logger = logging.getLogger("MAIA-ImportIsolation")

# Banned modules that bypass the Airlock Gateway
# These should ONLY be imported by the gateway module itself.
BANNED_MODULES: Set[str] = {
    # Direct model instantiation
    "transformers",
    # Direct API clients
    "openai",
    "anthropic",
    # Low-level HTTP (could bypass proxy)
    "httpx",
    "requests",
}

# Allowlisted files (can import anything)
ALLOWLISTED_FILES: Set[str] = {
    # The gateway itself
    "airlock_gateway.py",
    # Model wrappers
    "nemotron_real.py",
    "gemma4_complete.py",
    # Our monitor
    "bypass_monitor.py",
    "import_isolation.py",
    # Test files
    "test_",
    "conftest.py",
}

# Allowlisted import paths inside banned modules
# e.g. "openai" is banned, but specific safe submodules can be allowed
ALLOWLISTED_SUBMODULES: Set[str] = {
    "openai.types",       # type definitions only, no API calls
}


class ImportIsolationFinder:
    """sys.meta_path finder that intercepts banned module imports."""

    def __init__(self, block: bool = True):
        self.block = block
        self._hits: int = 0

    def find_spec(self, fullname, path, target=None):
        # Check if this is a banned module
        top_module = fullname.split(".")[0]

        if top_module not in BANNED_MODULES:
            return None  # not banned, let normal import proceed

        # Check if the full module+submodule is allowlisted
        if fullname in ALLOWLISTED_SUBMODULES:
            return None

        # Check if the calling file is allowlisted
        caller = self._get_caller_file()
        if caller and self._is_allowlisted(caller):
            return None

        # Banned import detected!
        self._hits += 1
        message = (
            f"IMPORT ISOLATION: '{fullname}' is a banned module that bypasses "
            f"Airlock Governance. Import only through the Gateway module. "
            f"(caller: {caller})"
        )

        # Log to bypass monitor
        try:
            from app.bypass_monitor import bypass_detected
            bypass_detected(
                event_type="import_hook_violation",
                source=f"import_hook:{fullname}",
                message=message,
                severity="CRITICAL",
            )
        except ImportError:
            logger.critical(message)

        if self.block:
            logger.critical(message)
            raise RuntimeError(message)

        logger.warning(f"ALLOWED (log-only): {message}")
        return None

    def _get_caller_file(self) -> Optional[str]:
        """Walk the stack to find the file that triggered the import."""
        import traceback
        stack = traceback.extract_stack()
        # Skip frames from this module and import machinery
        for frame in reversed(stack):
            fname = frame.filename
            if "import_isolation" in fname:
                continue
            if "<frozen" in fname:
                continue
            if fname.startswith("<"):
                continue
            return fname
        return None

    def _is_allowlisted(self, filepath: str) -> bool:
        """Check if a file is allowlisted for banned imports."""
        filename = os.path.basename(filepath)
        for allow in ALLOWLISTED_FILES:
            if allow.startswith("test_") and filename.startswith("test_"):
                return True
            if filename == allow:
                return True
            if allow in filepath:
                return True
        return False

    @property
    def hit_count(self) -> int:
        return self._hits


def install_import_isolation(block: bool = True):
    """Install the import isolation hook into sys.meta_path.

    Call this at the VERY BEGINNING of the application entry point
    (before any model imports).

    Args:
        block: If True, raise RuntimeError on banned import.
               If False, log warning only (for testing).
    """
    # Check if already installed
    for finder in sys.meta_path:
        if isinstance(finder, ImportIsolationFinder):
            logger.warning("Import isolation already installed")
            return finder

    finder = ImportIsolationFinder(block=block)
    sys.meta_path.insert(0, finder)

    mode = "BLOCK" if block else "LOG-ONLY"
    logger.warning(f"MAIA Import Isolation installed ({mode}): "
                   f"banned={BANNED_MODULES}, allowlisted_files={len(ALLOWLISTED_FILES)}")

    return finder


def uninstall_import_isolation():
    """Remove the import isolation hook."""
    for i, finder in enumerate(sys.meta_path):
        if isinstance(finder, ImportIsolationFinder):
            sys.meta_path.pop(i)
            logger.info("Import isolation uninstalled")
            return
