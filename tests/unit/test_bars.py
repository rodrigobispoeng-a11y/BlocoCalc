"""Escolha de barras (D18, docs/02-metodos.md §4.9)."""

from __future__ import annotations

import math

import pytest

from blococalc.analysis import adopted_bar_diameter, analyze, strut_tie_layout
from blococalc.schemas import (
    CheckStatus,
    ColumnLoad,
    DetailingInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Project,
    ReinforcementKind,
)
from blococalc.standards.bars import (
    BAR_SERIES,
    MIN_MESH_SPACING,
    bar_area,
    clear_spacing,
    layer_width,
    max_slab_spacing,
    mesh_bars,
    tie_bar_count,
)
from tests.factories import four_pile_cap, grid_cap

TF = 9.80665e3  # N


def test_series_and_area() -> None:
    assert BAR_SERIES == (6.3, 8.0, 10.0, 12.5, 16.0, 20.0, 25.0, 32.0, 40.0)
    assert bar_area(16.0) == pytest.approx(math.pi * 64.0)


def test_clear_spacing_follows_18_3_2_2() -> None:
    assert clear_spacing(16.0, 19.0) == pytest.approx(22.8)  # 1,2 · dmáx
    assert clear_spacing(25.0, 19.0) == 25.0  # φ
    assert clear_spacing(10.0, 9.5) == 20.0  # 20 mm


@pytest.mark.golden
def test_b2_central_tie_needs_phi32_to_fit_the_band() -> None:
    # §4.9: 80,14 cm² com φ25 pede 17 barras em 825 mm, numa faixa de 1,2 × 600 = 720 mm.
    n25 = tie_bar_count(8014.0, 25.0)
    assert n25 == 17
    assert layer_width(n25, 25.0, 19.0) == pytest.approx(825.0)
    n32 = tie_bar_count(8043.0, 32.0)
    assert n32 == 11
    assert layer_width(n32, 32.0, 19.0) == pytest.approx(672.0)


def test_slab_spacing_limits_of_20_1() -> None:
    assert max_slab_spacing(1000.0, 16.0) == 200.0
    assert max_slab_spacing(80.0, 10.0) == 160.0  # 2h
    assert max_slab_spacing(1000.0, 25.0) == 375.0  # 15φ para φ ≥ 20 mm


@pytest.mark.golden
def test_mesh_takes_the_smallest_bar_with_a_workable_spacing() -> None:
    # B1: 1,92 cm² em 200 cm -> φ6,3 c/20 (limite da 20.1).
    phi, spacing = mesh_bars(192.0, 2000.0, 1000.0, BAR_SERIES[0])
    assert (phi, spacing) == (6.3, 200.0)
    # B2, malha em x: 32,05 cm² em 240 cm; φ12,5 daria c/9, abaixo de 10 cm -> φ16 c/15.
    assert mesh_bars(3205.0, 2400.0, 1400.0, BAR_SERIES[0]) == (16.0, 150.0)
    # B7: 16,12 cm² em 420 cm; φ6,3 daria c/8 -> φ8 c/13.
    assert mesh_bars(1612.0, 4200.0, 2100.0, BAR_SERIES[0]) == (8.0, 130.0)


def test_mesh_starts_at_the_given_diameter_and_never_goes_below_the_minimum() -> None:
    phi, spacing = mesh_bars(500.0, 2000.0, 1000.0, 16.0)
    assert (phi, spacing) == (16.0, 200.0)
    phi, spacing = mesh_bars(1e6, 1000.0, 1000.0, 6.3)
    assert phi == BAR_SERIES[-1]
    assert spacing < MIN_MESH_SPACING  # nem φ40 cabe: quem chama avisa


# Análise completa (D18, opção B: o φ sobe até caber e o modelo é refeito).


def _loads(n: float) -> LoadsInput:
    case = LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=n),))
    return LoadsInput(cases=(case,))


@pytest.mark.golden
def test_b1_result_carries_the_bars() -> None:
    result = analyze(four_pile_cap(), MaterialsInput(fck=35.0), _loads(980e3))
    items = {r.id: r for r in result.reinforcement}
    x_tie = items["tirante_E1_E2"]
    assert (x_tie.bar_diameter, x_tie.bar_count) == (16.0, 3)
    assert x_tie.area_provided == pytest.approx(3 * bar_area(16.0))
    assert items["tirante_E2_E3"].bar_count == 2
    mesh = items["malha_x"]
    assert (mesh.bar_diameter, mesh.spacing) == (6.3, 200.0)
    assert mesh.area_provided == pytest.approx(bar_area(6.3) * 2000.0 / 200.0)
    assert not any("D18" in w for w in result.warnings)


@pytest.mark.golden
def test_b2_raises_phi25_to_phi32_and_reruns_the_model() -> None:
    # §4.9: 17 φ25 ocupam 825 mm na faixa de 720 mm; com φ32 cabem 11 barras em 672 mm.
    case = LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=1.4 * 8 * 113.96 * TF),))
    loads = LoadsInput(cases=(case,), include_cap_self_weight=False)
    asked = DetailingInput(bar_diameter=25.0)
    result = analyze(grid_cap(4, 2), MaterialsInput(fck=35.0), loads, asked)

    central = next(r for r in result.reinforcement if r.id == "tirante_E2_E3")
    assert (central.bar_diameter, central.bar_count) == (32.0, 11)
    assert central.area_required == pytest.approx(8043.0, rel=1e-3)  # d′ com φ32
    assert result.audit.parameters["bar_diameter_mm"] == 32.0
    assert result.audit.parameters["bar_diameter_input_mm"] == 25.0
    assert any("φ25" in w and "φ32" in w and "D18" in w for w in result.warnings)
    band = [c for c in result.checks if ":faixa_" in c.id]
    assert band and all(c.status is CheckStatus.OK for c in band)
    # O hash é o das entradas do usuário, para o .bloco reconhecer o resultado.
    plain = analyze(
        grid_cap(4, 2), MaterialsInput(fck=35.0), loads, DetailingInput(bar_diameter=32.0)
    )
    assert result.audit.input_hash != plain.audit.input_hash


def test_no_bar_fits_keeps_the_asked_diameter_and_warns() -> None:
    narrow = tuple(p.model_copy(update={"size": 150.0}) for p in four_pile_cap().piles)
    geometry = four_pile_cap().model_copy(update={"piles": narrow})
    result = analyze(geometry, MaterialsInput(fck=35.0), _loads(20000e3))
    tie = next(r for r in result.reinforcement if r.kind is ReinforcementKind.TIE)
    assert tie.bar_diameter == 16.0
    assert any(c.status is CheckStatus.FAIL for c in result.checks if ":faixa_" in c.id)
    assert any("φ40" in w and "D18" in w for w in result.warnings)


def test_layout_and_fem_use_the_adopted_diameter() -> None:
    # O 3D, os desenhos e o MEF refazem o modelo com o φ adotado, não com o digitado.
    case = LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=1.4 * 8 * 113.96 * TF),))
    loads = LoadsInput(cases=(case,), include_cap_self_weight=False)
    geometry, materials = grid_cap(4, 2), MaterialsInput(fck=35.0)
    asked = DetailingInput(bar_diameter=25.0)
    assert adopted_bar_diameter(geometry, materials, loads, asked) == 32.0
    project = Project(
        name="B2", geometry=geometry, materials=materials, loads=loads, detailing=asked
    )
    layout = strut_tie_layout(project, "C1")
    assert layout is not None
    pile = next(n for n in layout.nodes if n.id == "estaca_E1")
    assert pile.z == pytest.approx(geometry.cap.pile_embedment + geometry.cap.cover + 16.0)


def test_flexible_section_without_solution_keeps_the_analysis_running() -> None:
    # Flexão sem solução (área infinita) não tem barras; antes, divisão por zero na escolha.
    result = analyze(grid_cap(9, 2), MaterialsInput(fck=35.0), _loads(30000e3))
    assert not result.rigid
    flexure = next(r for r in result.reinforcement if r.id == "flexao_x")
    assert math.isinf(flexure.area_required)
    assert flexure.spacing is None
