"""Pilar fictício de área equivalente (M8, D10 proposta), valores recalculados à mão."""

from __future__ import annotations

import math

import pytest

from blococalc.core.reactions import rigid_cap_reactions
from blococalc.geometry.fictitious_column import FICTITIOUS_ID, fictitious_column
from blococalc.schemas import Cap, Column, ColumnLoad, LoadCase
from tests.factories import four_pile_cap

CAP = Cap(lx=3000.0, ly=2000.0, h=1000.0, pile_embedment=100.0)
P1 = Column(id="P1", x=-600.0, y=0.0, bx=400.0, by=400.0)
P2 = Column(id="P2", x=600.0, y=0.0, bx=400.0, by=400.0)


def case(n1: float, n2: float, **extra: float) -> LoadCase:
    return LoadCase(
        id="ELU1",
        column_loads=(
            ColumnLoad(column_id="P1", n=n1, **extra),
            ColumnLoad(column_id="P2", n=n2, **extra),
        ),
    )


def test_single_column_is_unchanged() -> None:
    load = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=1e6),))
    column, column_load = fictitious_column((P1,), load, CAP)
    assert column == P1
    assert column_load == load.column_loads[0]


@pytest.mark.golden
def test_two_equal_columns() -> None:
    # A = 2·400² = 320000; Sx = A·(400²/12 + 600²); Sy = A·400²/12; bx/by = √28.
    column, load = fictitious_column((P1, P2), case(1e6, 1e6), CAP)
    ratio = math.sqrt((400.0**2 / 12.0 + 600.0**2) / (400.0**2 / 12.0))
    assert ratio == pytest.approx(math.sqrt(28.0))
    assert column.id == FICTITIOUS_ID
    assert column.bx == pytest.approx(math.sqrt(320000.0 * ratio))
    assert column.bx == pytest.approx(1301.3, abs=0.1)
    assert column.bx * column.by == pytest.approx(320000.0)
    assert (column.x, column.y) == (0.0, 0.0)
    assert load.n == 2e6


def test_position_follows_load_resultant_and_sums_actions() -> None:
    column, load = fictitious_column((P1, P2), case(1e6, 3e6, mx=10e6, hy=5e3), CAP)
    assert column.x == pytest.approx(300.0)
    assert load.mx == pytest.approx(20e6)
    assert load.hy == pytest.approx(10e3)


def test_sides_limited_by_cap() -> None:
    narrow = CAP.model_copy(update={"lx": 1000.0})
    column, _ = fictitious_column((P1, P2), case(1e6, 1e6), narrow)
    assert column.bx == 1000.0
    assert column.by == pytest.approx(320.0)


def test_rejects_non_compressive_resultant() -> None:
    with pytest.raises(ValueError, match="≤ 0"):
        fictitious_column((P1, P2), case(1e6, -1e6), CAP)


def test_reactions_match_real_columns() -> None:
    # Equilíbrio: o pilar fictício reproduz as reações dos pilares reais.
    base = four_pile_cap()
    real = base.model_copy(update={"columns": (P1, P2)})
    loads = case(1e6, 3e6, my=40e6, hx=20e3)
    column, load = fictitious_column((P1, P2), loads, base.cap)
    single = base.model_copy(update={"columns": (column,)})
    expected = rigid_cap_reactions(real, loads)
    got = rigid_cap_reactions(single, LoadCase(id="ELU1", column_loads=(load,)))
    assert [r.force for r in got] == pytest.approx([r.force for r in expected])
