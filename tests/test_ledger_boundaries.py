"""Boundary tests for Ledger core independence."""

from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN_RUNTIME_IMPORTS = {"microplex", "microplex_us"}


def test_ledger_modules_do_not_import_microplex_runtime():
    ledger_root = Path(__file__).resolve().parents[1] / "ledger"
    violations: list[str] = []

    for path in sorted(ledger_root.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            imported_roots: list[str] = []
            if isinstance(node, ast.Import):
                imported_roots = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_roots = [node.module.split(".", 1)[0]]

            for root in imported_roots:
                if root in FORBIDDEN_RUNTIME_IMPORTS:
                    relative_path = path.relative_to(ledger_root.parent)
                    violations.append(f"{relative_path}:{node.lineno}: {root}")

    assert violations == []
