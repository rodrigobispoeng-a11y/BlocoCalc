"""Posições de armação em planta (D19, docs/02-metodos.md §4.10; ADR-010)."""

from __future__ import annotations

import math

import pytest

from blococalc.analysis import analyze
from blococalc.geometry.bar_layout import (
    BarRun,
    MeshBars,
    bar_positions,
    bend_diameter,
    hooked_length,
)
from blococalc.schemas import (
    Cap,
    Column,
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    HookShape,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Pile,
)
from tests.factories import four_pile_cap, grid_cap, quincunx_cap

CAP = Cap(lx=2000.0, ly=2000.0, h=1000.0, pile_embedment=100.0)  # B1, cobrimento 50


def test_bend_diameter_follows_table_9_1() -> None:
    assert bend_diameter(16.0, 500.0) == 80.0  # CA-50, φ < 20: 5φ
    assert bend_diameter(25.0, 500.0) == 200.0  # CA-50, φ ≥ 20: 8φ
    assert bend_diameter(10.0, 600.0) == 60.0  # CA-60: 6φ
    assert bend_diameter(16.0, 250.0) == 64.0  # CA-25: 4φ


@pytest.mark.golden
def test_hooked_length_along_the_centerline() -> None:
    # B1, φ16: pernas do gancho a 50 + 8 mm das faces, trecho entre elas 2000 − 116 = 1884 mm;
    # raio pela linha de centro 40 + 8 = 48; 1884 − 2·48 + π·48 + 2·8·16 = 2194,8 -> 2200 mm.
    assert hooked_length(1884.0, 16.0, 500.0, HookShape.RIGHT_ANGLE) == 2200.0
    assert hooked_length(1884.0, 16.0, 500.0, HookShape.NONE) == 1890.0


def test_b1_ties_and_mesh() -> None:
    runs = [
        BarRun(("tirante_E1_E2",), (-600.0, -600.0), (1.0, 0.0), 3, 16.0, 38.8),
        BarRun(("tirante_E3_E4",), (600.0, 600.0), (-1.0, 0.0), 3, 16.0, 38.8),
        BarRun(("tirante_E2_E3",), (600.0, -600.0), (0.0, 1.0), 2, 16.0, 38.8),
        BarRun(("tirante_E4_E1",), (-600.0, 600.0), (0.0, -1.0), 2, 16.0, 38.8),
    ]
    meshes = [
        MeshBars("malha_x", (1.0, 0.0), 6.3, 200.0),
        MeshBars("malha_y", (0.0, 1.0), 6.3, 200.0),
    ]
    positions = bar_positions(CAP, runs, meshes, HookShape.RIGHT_ANGLE, 500.0)

    assert [p.id for p in positions] == ["N1", "N2", "N3", "N4"]
    n1, n2, n3, n4 = positions
    assert (n1.bar_diameter, n1.count, n1.length, n1.layer) == (16.0, 6, 2200.0, 1)
    assert n1.reinforcement_ids == ("tirante_E1_E2", "tirante_E3_E4")
    assert (n2.count, n2.layer) == (4, 2)
    # Barras da faixa centradas na linha das estacas, a φ + ah = 38,8 mm.
    ys = sorted(b[0][1] for b in n1.bars)
    assert ys[:3] == pytest.approx([-638.8, -600.0, -561.2])
    assert all(sorted((b[0][0], b[1][0])) == pytest.approx([-942.0, 942.0]) for b in n1.bars)
    # Malha φ6,3 c/20 em 2000 − 2·53,15 mm: 10 barras.
    assert (n3.bar_diameter, n3.count, n3.layer, n3.reinforcement_ids) == (6.3, 10, 1, ("malha_x",))
    assert n4.layer == 2
    assert not any(p.variable_length for p in positions)


def test_diagonal_bars_get_a_variable_length_position() -> None:
    cap = Cap(lx=4200.0, ly=4200.0, h=2100.0, pile_embedment=100.0)
    diagonal = (1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0))
    run = BarRun(("tirante_E1_E5", "tirante_E3_E5"), (0.0, 0.0), diagonal, 5, 16.0, 38.8)
    (position,) = bar_positions(cap, [run], [], HookShape.RIGHT_ANGLE, 500.0)
    assert position.variable_length
    assert position.layer == 3
    lengths = [math.dist(*b) for b in position.bars]
    assert max(lengths) - min(lengths) > 100.0
    # Barra central de canto a canto: 2·(2100 − 58)·√2 entre as pernas dos ganchos.
    assert max(lengths) == pytest.approx(2 * 2042.0 * math.sqrt(2.0))


# Análise completa: posições no resultado (ADR-010).


def _loads(n: float) -> LoadsInput:
    return LoadsInput(cases=(LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=n),)),))


def test_b1_result_has_the_positions() -> None:
    result = analyze(four_pile_cap(), MaterialsInput(fck=35.0), _loads(980e3))
    ids = [(p.id, p.bar_diameter, p.count, p.length, p.layer) for p in result.bar_positions]
    assert ids == [
        ("N1", 16.0, 6, 2200.0, 1),
        ("N2", 16.0, 4, 2200.0, 2),
        ("N3", 6.3, 10, 2020.0, 1),
        ("N4", 6.3, 10, 2020.0, 2),
    ]
    covered = {i for p in result.bar_positions for i in p.reinforcement_ids}
    assert covered == {r.id for r in result.reinforcement if r.bar_count or r.spacing}


def test_quincunx_diagonals_cross_the_cap() -> None:
    result = analyze(quincunx_cap(), MaterialsInput(fck=25.0), _loads(8000e3))
    diagonal = next(p for p in result.bar_positions if p.layer == 3)
    assert diagonal.variable_length
    assert set(diagonal.reinforcement_ids) == {f"tirante_E{i}_E5" for i in range(1, 5)}
    ties = {r.id: r for r in result.reinforcement}
    assert diagonal.count == 2 * ties["tirante_E1_E5"].bar_count  # type: ignore[operator]


def test_straight_bars_without_hooks() -> None:
    options = DetailingInput(hooked=False)
    result = analyze(four_pile_cap(), MaterialsInput(fck=35.0), _loads(980e3), options)
    assert {p.hook for p in result.bar_positions} == {HookShape.NONE}
    assert result.bar_positions[0].length == 1900.0  # 2000 − 2·50


def test_bars_longer_than_12_m_warn_about_splices() -> None:
    long_cap = grid_cap(9, 2)  # 1290 cm
    deep = long_cap.model_copy(update={"cap": long_cap.cap.model_copy(update={"h": 4000.0})})
    result = analyze(deep, MaterialsInput(fck=35.0), _loads(30000e3))
    assert result.rigid
    longest = max(p.length for p in result.bar_positions)
    assert longest > 12000.0
    assert any("12 m" in w and "D19" in w for w in result.warnings)


def test_flexible_cap_gets_the_flexure_mesh() -> None:
    piles = tuple(
        Pile(id=f"E{i + 1}", x=sx * 1100.0, y=sy * 1100.0, size=400.0)
        for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)))
    )
    geometry = GeometryInput(
        cap=Cap(lx=3000.0, ly=3000.0, h=600.0, pile_embedment=100.0),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=400.0, by=400.0),),
    )
    result = analyze(geometry, MaterialsInput(fck=30.0), _loads(2000e3))
    assert not result.rigid
    assert [p.reinforcement_ids for p in result.bar_positions] == [("flexao_x",), ("flexao_y",)]
