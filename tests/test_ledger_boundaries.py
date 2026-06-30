"""Boundary tests for Ledger source-data ownership."""

from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN_PACKAGE_ROOTS = {"calibration", "micro"}


def test_ledger_modules_do_not_import_non_ledger_runtime_packages():
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
                if root in FORBIDDEN_PACKAGE_ROOTS:
                    relative_path = path.relative_to(ledger_root.parent)
                    violations.append(f"{relative_path}:{node.lineno}: {root}")

    assert violations == []


def test_repository_does_not_ship_raw_microdata_namespace():
    repo_root = Path(__file__).resolve().parents[1]

    assert not (repo_root / "ledger" / "microdata").exists()
    assert not (repo_root / "policyengine_ledger" / "microdata").exists()
    assert not (repo_root / "micro").exists()
    assert not (repo_root / "calibration").exists()
    assert not (repo_root / "storage").exists()
