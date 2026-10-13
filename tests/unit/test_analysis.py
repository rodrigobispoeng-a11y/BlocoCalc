"""Análise completa (contratos v2, ADR-002)."""

from __future__ import annotations

import math

import pytest

from blococalc.analysis import analyze
from blococalc.schemas import (
    Cap,
    CheckStatus,
    Column,
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Pile,
    ReinforcementKind,
)
from blococalc.standards.strength import strut_tie_strengths
from tests.factories import four_pile_cap, two_pile_cap

C35 = MaterialsInput(fck=35.0)


def loads(*normals: float, self_weight: bool = True) -> LoadsInput:
    return LoadsInput(
        cases=tuple(
            LoadCase(id=f"C{i + 1}", column_loads=(ColumnLoad(column_id="P1", n=n),))
            for i, n in enumerate(normals)
        ),
        include_cap_self_weight=self_weight,
    )


@pytest.mark.golden
def test_b1_full_analysis() -> None:
    # Peso próprio D7: 5 % de 980 kN -> R = 1,05·245 = 257,25 kN; Rd = 1,2·R.
    # d′ (D8) = 50 + 16/2 = 58 -> d = 1000 − 100 − 58 = 842; y pela forma fechada de D6.
    result = analyze(four_pile_cap(), C35, loads(980e3))
    rd, d = 1.2 * 257.25e3, 842.0
    k = 2.0 * rd * 437.5 / (strut_tie_strengths(C35).fcd1 * 200.0)
    z = d - (d - math.sqrt(d * d - 2.0 * k)) / 2.0
    fyd = 500.0 / 1.15

    assert result.rigid
    assert [r.force for r in result.reactions] == pytest.approx([257.25e3] * 4)
    items = {r.id: r for r in result.reinforcement}
    assert items["tirante_E1_E2"].force_d == pytest.approx(rd * 550.0 / z, rel=1e-6)
    assert items["tirante_E2_E3"].force_d == pytest.approx(rd * 437.5 / z, rel=1e-6)
    assert items["tirante_E1_E2"].area_required == pytest.approx(rd * 550.0 / z / fyd, rel=1e-6)
    assert items["malha_x"].area_required == pytest.approx(0.2 * 2 * rd * 550.0 / z / fyd)
    assert items["malha_x"].kind is ReinforcementKind.DISTRIBUTION
    assert all(c.status is CheckStatus.OK for c in result.checks)
    assert result.warnings == ()
    assert result.audit.parameters["tie_height_mm"] == 58.0
    assert result.disclaimer


def test_without_self_weight() -> None:
    result = analyze(four_pile_cap(), C35, loads(980e3, self_weight=False))
    assert [r.force for r in result.reactions] == pytest.approx([245e3] * 4)


def test_envelope_keeps_the_largest_area_and_tags_checks_by_case() -> None:
    result = analyze(four_pile_cap(), C35, loads(600e3, 980e3))
    single = analyze(four_pile_cap(), C35, loads(980e3))
    by_id = {r.id: r.area_required for r in single.reinforcement}
    assert {r.id: r.area_required for r in result.reinforcement} == pytest.approx(by_id)
    assert {c.id.split(":")[0] for c in result.checks if ":" in c.id} == {"C1", "C2"}
    assert len(result.reactions) == 8


def test_flexible_cap_is_blocked() -> None:
    result = analyze(four_pile_cap(h=500.0), C35, loads(980e3))  # exige h ≥ 600
    assert not result.rigid
    assert result.reinforcement == ()
    assert any("flexível" in w for w in result.warnings)


def test_piles_in_line_flag_lateral_and_top_bars() -> None:
    result = analyze(two_pile_cap(), C35, loads(1000e3))
    kinds = {r.kind for r in result.reinforcement}
    assert ReinforcementKind.LATERAL_TOP in kinds
    assert ReinforcementKind.SUSPENSION not in kinds


def test_wide_spacing_flags_suspension() -> None:
    # Pilar 1000×1000: rígido com h = 480 ≥ (2300 − 1000)/3, e espaçamento 1500 > 3·480.
    piles = tuple(
        Pile(id=f"E{i + 1}", x=sx * 750.0, y=sy * 750.0, size=400.0)
        for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)))
    )
    geometry = GeometryInput(
        cap=Cap(lx=2300.0, ly=2300.0, h=480.0),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=1000.0, by=1000.0),),
    )
    result = analyze(geometry, C35, loads(1500e3))
    assert result.rigid
    suspension = [r for r in result.reinforcement if r.kind is ReinforcementKind.SUSPENSION]
    assert len(suspension) == 1
    assert suspension[0].area_required == 0.0


def test_insufficient_cover_fails() -> None:
    options = DetailingInput(aggressiveness_class="IV")
    result = analyze(four_pile_cap(), C35, loads(980e3), options)
    cover = next(c for c in result.checks if c.id == "cobrimento")
    assert cover.status is CheckStatus.OK  # 50 mm atende CAA IV
    tight = four_pile_cap().model_copy(
        update={"cap": four_pile_cap().cap.model_copy(update={"cover": 40.0})}
    )
    failed = analyze(tight, C35, loads(980e3), options)
    assert next(c for c in failed.checks if c.id == "cobrimento").status is CheckStatus.FAIL


def test_two_columns_are_rejected() -> None:
    base = two_pile_cap()
    second = Column(id="P2", x=300.0, y=0.0, bx=200.0, by=200.0)
    geometry = base.model_copy(update={"columns": (*base.columns, second)})
    with pytest.raises(ValueError, match="único pilar"):
        analyze(geometry, C35, loads(1000e3))


def test_input_hash_tracks_inputs() -> None:
    first = analyze(four_pile_cap(), C35, loads(980e3)).audit.input_hash
    again = analyze(four_pile_cap(), C35, loads(980e3)).audit.input_hash
    other = analyze(four_pile_cap(), C35, loads(900e3)).audit.input_hash
    assert first == again != other
