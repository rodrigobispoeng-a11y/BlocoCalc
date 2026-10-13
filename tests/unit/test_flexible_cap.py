"""Bloco flexível: esforços nas seções S1, cortante na face e punção (docs/02-metodos.md §4.2).

Valores de referência recalculados à mão. Bloco 3000×3000×600, estacas φ400 a ±1100, pilar
400×400, Nd = 2000 kN, C30: (a − ap)/3 = 867 > 600, logo flexível (NBR 6118:2023, 22.7.1).
"""

from __future__ import annotations

import math

import pytest

from blococalc.core.flexible_cap import face_shears, punching_load, s1_moments
from blococalc.core.reactions import rigid_cap_reactions
from blococalc.schemas import (
    Cap,
    Column,
    ColumnLoad,
    GeometryInput,
    LoadCase,
    MaterialsInput,
    Pile,
)
from blococalc.standards.flexure import (
    design_section,
    minimum_area,
    neutral_axis_limit,
    stress_block,
    tension_area,
)

GAMMA_N = 1.2
C30 = MaterialsInput(fck=30.0)
DX, DY = 442.0, 426.0  # 600 − 100 − (50 + 8); segunda camada a φ = 16 acima


def flexible_cap(spacing: float = 1100.0, column: float = 400.0) -> GeometryInput:
    piles = tuple(
        Pile(id=f"E{i + 1}", x=sx * spacing, y=sy * spacing, size=400.0)
        for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)))
    )
    return GeometryInput(
        cap=Cap(lx=3000.0, ly=3000.0, h=600.0, pile_embedment=100.0),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=column, by=column),),
    )


CASE = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=2000e3, my=50e6),))


@pytest.mark.golden
def test_s1_moment_and_area() -> None:
    geometry = flexible_cap()
    case = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=2000e3),))
    sections = s1_moments(geometry, rigid_cap_reactions(geometry, case), GAMMA_N, DX, DY)

    # S1 a 0,15·400 = 60 para dentro da face: x = 140; braço até a estaca = 960.
    moment = GAMMA_N * 2 * 500e3 * 960.0
    assert len(sections) == 4
    for s in sections:
        assert s.moment_d == pytest.approx(moment)
        assert s.width == 3000.0
    sx = next(s for s in sections if s.axis == "x")
    assert sx.depth == DX

    sigma = 0.85 * 30.0 / 1.4
    y = DX - math.sqrt(DX**2 - 2.0 * moment / (sigma * 3000.0))
    area = sigma * 3000.0 * y / (500.0 / 1.15)
    design = design_section(moment, 3000.0, 600.0, DX, C30)
    assert design.area_calc == pytest.approx(area)
    assert design.area == pytest.approx(6358.5, abs=0.1)
    assert design.x_over_d == pytest.approx(y / 0.8 / DX)
    assert design.x_over_d < design.x_over_d_limit == 0.45


@pytest.mark.golden
def test_minimum_area() -> None:
    # Md,mín = 0,8·(3000·600²/6)·1,3·0,3·30^(2/3) = 542,2 kN·m -> 2897 mm² > 0,15 %·b·h = 2700.
    assert minimum_area(3000.0, 600.0, DX, C30) == pytest.approx(2897.0, abs=0.1)
    assert minimum_area(3000.0, 600.0, 580.0, C30) == pytest.approx(2700.0)


def test_moment_sides_follow_eccentricity() -> None:
    geometry = flexible_cap()
    reactions = rigid_cap_reactions(geometry, CASE)
    sections = {(s.axis, s.side): s for s in s1_moments(geometry, reactions, GAMMA_N, DX, DY)}
    assert sections[("x", 1)].moment_d > sections[("x", -1)].moment_d
    assert sections[("y", 1)].moment_d == pytest.approx(sections[("y", -1)].moment_d)


def test_depth_limited_by_nearest_far_pile() -> None:
    geometry = flexible_cap(spacing=300.0)
    case = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=1000e3),))
    sections = s1_moments(geometry, rigid_cap_reactions(geometry, case), GAMMA_N, DX, DY)
    assert {s.depth for s in sections} == {1.5 * (300.0 - 140.0)}


def test_face_shear_counts_piles_beyond_face() -> None:
    geometry = flexible_cap()
    shears = face_shears(geometry, rigid_cap_reactions(geometry, CASE), GAMMA_N, DX, DY)
    total = sum(s.shear_d for s in shears if s.axis == "x")
    assert total == pytest.approx(GAMMA_N * 2000e3)


def test_face_shear_partial_pile() -> None:
    # Eixo da estaca 100 além da face: entra com 0,5 + 100/400 = 75 %.
    geometry = flexible_cap(spacing=300.0)
    case = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=1000e3),))
    shears = face_shears(geometry, rigid_cap_reactions(geometry, case), GAMMA_N, DX, DY)
    assert [s.shear_d for s in shears] == pytest.approx([GAMMA_N * 2 * 250e3 * 0.75] * 4)


def test_punching_without_piles_inside_c1() -> None:
    geometry = flexible_cap()
    load = punching_load(geometry, CASE, rigid_cap_reactions(geometry, CASE), GAMMA_N, 434.0)
    assert load.force_c == pytest.approx(2400e3)
    assert load.force_c1 == pytest.approx(2400e3)
    assert load.moment_y == pytest.approx(60e6)
    assert load.piles_inside_c1 == ()
    assert load.c1_inside_cap  # 200 + 868 ≤ 1500


def test_punching_discounts_piles_inside_c1() -> None:
    # 2d = 1400 > distância do pilar às estacas (√2·900 = 1273): todas dentro; 200 + 1400 > 1500.
    geometry = flexible_cap()
    load = punching_load(geometry, CASE, rigid_cap_reactions(geometry, CASE), GAMMA_N, 700.0)
    assert load.force_c1 == pytest.approx(0.0, abs=1e-6)
    assert len(load.piles_inside_c1) == 4
    assert not load.c1_inside_cap


def test_rejects_two_columns() -> None:
    base = flexible_cap()
    second = Column(id="P2", x=500.0, y=0.0, bx=200.0, by=200.0)
    geometry = base.model_copy(update={"columns": (*base.columns, second)})
    with pytest.raises(ValueError, match="único pilar"):
        s1_moments(geometry, (), GAMMA_N, DX, DY)


def test_stress_block_above_50() -> None:
    block = stress_block(70.0)
    assert block.lambda_ == pytest.approx(0.75)
    assert block.alpha_c == pytest.approx(0.765)
    assert block.eta_c == pytest.approx((40.0 / 70.0) ** (1.0 / 3.0))
    assert neutral_axis_limit(70.0) == 0.35
    assert stress_block(40.0).eta_c == 1.0


def test_section_beyond_concrete_capacity() -> None:
    assert tension_area(-1.0, 1000.0, 400.0, C30) == 0.0
    design = design_section(1e12, 1000.0, 500.0, 400.0, C30)
    assert math.isinf(design.area_calc)
    assert math.isinf(design.x_over_d)
