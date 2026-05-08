"""
MAIA Operation Classifier
=========================
Parses LLM output text into structured operations (SQL, file, API).
Regex-based for performance. No AST parsing.
"""

import re
from typing import List, Dict


class ClassifiedOp:
    def __init__(self, category: str, operation: str, raw: str):
        self.category = category
        self.operation = operation
        self.raw = raw

    def to_dict(self) -> dict:
        return {"category": self.category, "operation": self.operation, "raw": self.raw[:80]}


class OperationClassifier:
    SQL_PATTERNS = [
        (r"\bSELECT\b", "SELECT"),
        (r"\bINSERT\s+INTO\b", "INSERT"),
        (r"\bUPDATE\b", "UPDATE"),
        (r"\bDELETE\s+FROM\b", "DELETE"),
        (r"\bDROP\s+(TABLE|DATABASE|INDEX|VIEW|TRIGGER|PROCEDURE)\b", "DROP"),
        (r"\bTRUNCATE\b", "TRUNCATE"),
        (r"\bALTER\s+(TABLE|DATABASE|INDEX|VIEW|COLUMN)\b", "ALTER"),
        (r"\bCREATE\s+(TABLE|DATABASE|INDEX|VIEW|TRIGGER|PROCEDURE)\b", "CREATE"),
        (r"\bGRANT\b", "GRANT"),
        (r"\bREVOKE\b", "REVOKE"),
        (r"\bMERGE\b", "MERGE"),
        (r"\bCALL\b", "CALL"),
        (r"\bSHOW\b", "SHOW"),
        (r"\bDESCRIBE\b", "DESCRIBE"),
        (r"\bEXPLAIN\b", "EXPLAIN"),
        (r"\bWITH\b", "WITH"),
    ]

    FILE_PATTERNS = [
        (r"\brm\s+-rf\b", "delete"),
        (r"\brm\b", "delete"),
        (r"\bchmod\s+\d{3,4}\b", "chmod"),
        (r"\bsudo\b\s+\w+\s+", "execute"),
        (r"\beval\s*\(.*\)", "execute"),
        (r"\bexec\s*\(.*\)", "execute"),
        (r"\bwrite_file\b", "write"),
        (r"\bfile_put_contents\b", "write"),
        (r"\bmkfs\b", "format"),
        (r"\bdd\s+if=.*of=", "format"),
        (r"\bmv\b", "rename"),
        (r"\bln\s+-s\b", "symlink"),
    ]

    API_PATTERNS = [
        (r"\bDELETE\s+(/|https?://)", "delete"),
        (r"\bPUT\s+(/|https?://)", "update"),
        (r"\bPOST\s+\S*(?:admin|delete|remove|clear|bypass)", "admin_action"),
        (r"\bPATCH\s+\S*(?:admin|config|restriction)", "modify_config"),
        (r"\bcurl\s+-X\s+DELETE\b", "delete"),
        (r"\bwget\s+.*--delete\b", "delete"),
        (r"\bbulk[-_\s]*transfer\b", "bulk_transfer"),
        (r"\bbulk[-_\s]*(?:delete|update|create|modify)", "bulk_operation"),
        (r"\bexecute[-_\s]*(?:patch|transaction|funds|wire|approve)\b", "execute"),
        (r"\bprescribe\b", "prescribe"),
        (r"\bbypass[-_\s]*(?:screen|check|aml|ofac|sanctions|audit)\b", "bypass_screen"),
        (r"\bdelete[-_\s]*(?:entry|record|log|audit|manifest)\b", "delete_entry"),
        (r"\bmodify[-_\s]*(?:list|score|record|result|audit)\b", "modify_list"),
        (r"\bsuppress[-_\s]*flag\b", "suppress_flag"),
        (r"\bshare[-_\s]*(?:external|across_wall|patient_data)\b", "share_external"),
        (r"\bexport[-_\s]*(?:data|phi|list|unredacted)\b", "export_data"),
    ]

    def __init__(self):
        self.sql_compiled = [(re.compile(p, re.IGNORECASE), op) for p, op in self.SQL_PATTERNS]
        self.file_compiled = [(re.compile(p, re.IGNORECASE), op) for p, op in self.FILE_PATTERNS]
        self.api_compiled = [(re.compile(p, re.IGNORECASE), op) for p, op in self.API_PATTERNS]

    def classify(self, text: str) -> List[ClassifiedOp]:
        ops = []
        ops.extend(self._check(text, self.sql_compiled, "sql"))
        ops.extend(self._check(text, self.file_compiled, "file"))
        ops.extend(self._check(text, self.api_compiled, "api"))
        return ops

    def _check(self, text: str, patterns: list, category: str) -> List[ClassifiedOp]:
        found = []
        seen = set()
        for pattern, op_name in patterns:
            if pattern.search(text):
                key = f"{category}:{op_name}"
                if key not in seen:
                    found.append(ClassifiedOp(category, op_name, pattern.pattern))
                    seen.add(key)
        return found