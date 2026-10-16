"""Memorial de cálculo em HTML (ADR-005)."""

from __future__ import annotations

from datetime import date

import pytest

from blococalc.analysis import analyze
from blococalc.report import calculation_report
from blococalc.schemas import (
    AnalysisResult,
    CheckStatus,
    ColumnLoad,
    DetailingInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Project,
)
from tests.factories import four_pile_cap

ISSUED = date(2026, 10, 16)
LOADS = LoadsInput(
    cases=(LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=980e3),)),)
)


def project(**update: object) -> Project:
    geometry, materials = four_pile_cap(), MaterialsInput(fck=35.0)
    result = analyze(geometry, materials, LOADS, DetailingInput())
    base = Project(
        name="Bloco B1 <P12>",
        notes="Obra & revisão 1",
        geometry=geometry,
        materials=materials,
        loads=LOADS,
        result=result,
    )
    return base.model_copy(update=update)


def test_report_lists_inputs_method_and_audit() -> None:
    saved = project()
    assert saved.result is not None
    html = calculation_report(saved, ISSUED)
    assert "Bloco B1 &lt;P12&gt;" in html and "Obra &amp; revisão 1" in html
    assert "16/10/2026" in html
    assert saved.result.disclaimer in html
    assert saved.result.audit.app_version in html
    assert saved.result.audit.method in html
    assert saved.result.audit.input_hash in html
    assert all(a in html for a in saved.result.audit.assumptions)
    assert "rígido" in html and "22.7.1" in html
    assert "257.25" in html  # B1: (980 + 5 %)/4 kN por estaca
    assert "980.00" in html  # Nd em kN
    for check in saved.result.checks:
        assert check.reference.item in html
    for item in saved.result.reinforcement:
        assert item.id in html
    assert "MEF" not in html
    assert "<script" not in html and "http" not in html


def test_failed_checks_are_highlighted() -> None:
    saved = project()
    assert saved.result is not None
    first = saved.result.checks[0].model_copy(update={"status": CheckStatus.FAIL})
    failed = saved.result.model_copy(update={"checks": (first, *saved.result.checks[1:])})
    html = calculation_report(project(result=failed), ISSUED)
    assert "1 verificação não atendida" in html
    assert html.count('class="falha"') == 1


def test_fem_section_only_with_fem_result() -> None:
    saved = project()
    assert saved.result is not None
    fem: AnalysisResult = saved.result.model_copy(
        update={"audit": saved.result.audit.model_copy(update={"method": "mef-linear-d14"})}
    )
    html = calculation_report(project(fem_result=fem), ISSUED)
    assert "Conferência por MEF" in html
    assert "mef-linear-d14" in html


def test_report_needs_a_result() -> None:
    with pytest.raises(ValueError, match="Calcule"):
        calculation_report(project(result=None), ISSUED)


def test_pile_table_shows_stiffness() -> None:
    # D16: rigidez em kN/mm; estaca sem rigidez aparece como apoio rígido.
    geometry = four_pile_cap()
    piles = (geometry.piles[0].model_copy(update={"axial_stiffness": 720e3}), *geometry.piles[1:])
    html = calculation_report(
        project(geometry=geometry.model_copy(update={"piles": piles})), ISSUED
    )
    assert "k [kN/mm]" in html
    assert "<td>720.0</td>" in html
    assert html.count("<td>rígida</td>") == 3
