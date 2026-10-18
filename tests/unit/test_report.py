"""Memorial de cálculo em HTML (ADR-005)."""

from __future__ import annotations

import base64
import re
from datetime import date

import pytest

from blococalc.analysis import analyze, strut_tie_layout
from blococalc.report import bar_label, calculation_report
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


def test_report_embeds_form_and_model_drawings() -> None:
    # ADR-008: forma na seção 1 e o modelo de cada caso na seção 3, como SVG embutido.
    saved = project()
    layout = strut_tie_layout(saved, "ELU1")
    assert layout is not None
    html = calculation_report(saved, ISSUED, {"ELU1": layout})
    images = re.findall(r"<img src='data:image/svg\+xml;base64,([^']+)' width='(\d+)'", html)
    assert len(images) == 3 + 3 + 3  # forma, modelo e armação: planta e 2 cortes cada
    svgs = [base64.b64decode(data).decode() for data, _ in images]
    assert all(s.startswith("<svg") for s in svgs)
    assert all(f"{m.force_d / 1e3:.0f} kN" in svgs[3] for m in layout.members)
    assert html.index("Forma (cotas em cm)") < html.index("<h2>2.")
    assert html.index("<h2>3.") < html.index("Modelo de bielas e tirantes: caso ELU1")
    assert html.index("Modelo de bielas") < html.index("<h2>4.")
    assert html.index("<h2>7.") < html.index("Desenho de armação") < html.index("<h2>9.")
    assert "N1: 6 φ16 C=220" in svgs[6]


@pytest.mark.golden
def test_report_has_the_steel_schedule() -> None:
    # D19, B1: N1 6 φ16 e N2 4 φ16 de 220 cm, malha N3 e N4 de 10 φ6,3 com 202 cm.
    # φ16: 22,00 m · π·16²/4·10⁻⁶·7850 = 1,578 kg/m -> 34,7 kg; φ6,3: 40,40 m · 0,2447 kg/m
    # -> 9,9 kg; total 44,6 kg.
    html = calculation_report(project(), ISSUED)
    assert "<td>N1</td><td>16</td><td>6</td><td>220</td><td>13.20</td>" in html
    assert "<td>N3</td><td>6,3</td><td>10</td><td>202</td><td>20.20</td>" in html
    assert "<td>16</td><td>22.00</td><td>34.7</td>" in html
    assert "<td>6,3</td><td>40.40</td><td>9.9</td>" in html
    assert "<td>Total</td><td></td><td>44.6</td>" in html
    assert "8.3.3" in html


def test_report_without_drawings() -> None:
    html = calculation_report(project(), ISSUED, drawings=False)
    assert "<img" not in html
    assert "Forma (cotas em cm)" not in html


def test_report_lists_the_chosen_bars() -> None:
    # D18: quantidade e diâmetro dos tirantes, φ e espaçamento da malha, e o agregado.
    html = calculation_report(project(), ISSUED)
    assert "3 φ16" in html and "φ6,3 c/20" in html
    assert "As,ef [cm²]" in html and "6.03" in html
    assert "agregado graúdo de 19 mm" in html


def test_bar_label() -> None:
    tie = project().result.reinforcement[0]  # type: ignore[union-attr]
    assert bar_label(tie.model_copy(update={"bar_count": 11, "bar_diameter": 32.0})) == "11 φ32"
    mesh = tie.model_copy(update={"bar_count": None, "spacing": 150.0, "bar_diameter": 12.5})
    assert bar_label(mesh) == "φ12,5 c/15"
    assert bar_label(tie.model_copy(update={"bar_count": None})) == "φ16"
