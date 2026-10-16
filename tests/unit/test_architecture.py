"""Regra de dependência: core, standards e geometry não importam camadas de borda."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "blococalc"
PURE = ("core", "standards", "geometry", "report")
FORBIDDEN = ("blococalc.fem", "blococalc.viz", "blococalc.persistence", "blococalc.app")
FORBIDDEN_THIRD_PARTY = ("PySide6", "pyvista", "vtk", "gmsh")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("subpackage", PURE)
def test_pure_subpackages_do_not_import_edge_layers(subpackage: str) -> None:
    for path in (PACKAGE / subpackage).rglob("*.py"):
        for module in imported_modules(path):
            assert not module.startswith(FORBIDDEN + FORBIDDEN_THIRD_PARTY), (
                f"{path.relative_to(PACKAGE)} importa {module}"
            )


@pytest.mark.parametrize("subpackage", PURE)
def test_pure_subpackages_only_share_schemas(subpackage: str) -> None:
    others = tuple(f"blococalc.{name}" for name in PURE if name != subpackage)
    for path in (PACKAGE / subpackage).rglob("*.py"):
        for module in imported_modules(path):
            assert not module.startswith(others), f"{path.relative_to(PACKAGE)} importa {module}"
