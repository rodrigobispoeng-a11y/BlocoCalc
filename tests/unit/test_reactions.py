"""Reações em bloco rígido (método M1)."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from blococalc.core.reactions import (
    UnbalancedMomentError,
    applied_resultant,
    rigid_cap_reactions,
)
from blococalc.schemas import Cap, Column, ColumnLoad, GeometryInput, LoadCase, Pile
from tests.factories import four_pile_cap, two_pile_cap


def case(**load: float) -> LoadCase:
    return LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", **load),))


def forces(geometry: GeometryInput, load_case: LoadCase, self_weight: float = 0.0) -> list[float]:
    return [r.force for r in rigid_cap_reactions(geometry, load_case, self_weight)]


def test_b1_centered_load_is_shared_equally() -> None:
    # B1: Fk = 700 kN, γf = 1,4 -> Fd = 980 kN; sem γn (aplicado nas verificações).
    assert forces(four_pile_cap(), case(n=980e3)) == pytest.approx([245e3] * 4)


def test_two_piles_with_moment_along_the_line() -> None:
    result = forces(two_pile_cap(), case(n=1000e3, my=100e6))
    assert result == pytest.approx([500e3 - 100e6 / 1200, 500e3 + 100e6 / 1200])


def test_two_piles_reject_moment_across_the_line() -> None:
    with pytest.raises(UnbalancedMomentError, match="vigas de travamento"):
        rigid_cap_reactions(two_pile_cap(), case(n=1000e3, mx=10e6))


def test_single_pile_takes_axial_load_and_rejects_moment() -> None:
    geometry = GeometryInput(
        cap=Cap(lx=800.0, ly=800.0, h=700.0),
        piles=(Pile(id="E1", x=0.0, y=0.0, size=500.0),),
        columns=(Column(id="P1", x=0.0, y=0.0, bx=300.0, by=300.0),),
    )
    assert forces(geometry, case(n=500e3)) == pytest.approx([500e3])
    with pytest.raises(UnbalancedMomentError):
        rigid_cap_reactions(geometry, case(n=500e3, my=1e6))


def test_three_piles_equilateral_centered_load() -> None:
    radius = 700.0
    piles = tuple(
        Pile(
            id=f"E{i + 1}",
            x=radius * math.cos(math.radians(90 + 120 * i)),
            y=radius * math.sin(math.radians(90 + 120 * i)),
            size=400.0,
        )
        for i in range(3)
    )
    geometry = GeometryInput(
        cap=Cap(lx=2200.0, ly=2000.0, h=900.0),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=300.0, by=300.0),),
    )
    assert forces(geometry, case(n=900e3)) == pytest.approx([300e3] * 3)


def test_horizontal_force_acts_with_arm_to_pile_heads() -> None:
    geometry = two_pile_cap()  # h = 900, embutimento = 100 -> braço 800 mm
    with_h = forces(geometry, case(n=1000e3, hx=50e3))
    with_m = forces(geometry, case(n=1000e3, my=50e3 * 800.0))
    assert with_h == pytest.approx(with_m)


def test_self_weight_is_added_at_cap_centre() -> None:
    assert forces(four_pile_cap(), case(n=980e3), self_weight=40e3) == pytest.approx([255e3] * 4)


def test_coincident_piles_behave_as_single_point() -> None:
    geometry = GeometryInput(
        cap=Cap(lx=800.0, ly=800.0, h=700.0),
        piles=(
            Pile(id="E1", x=0.0, y=0.0, size=300.0),
            Pile(id="E2", x=0.0, y=1e-140, size=300.0),
        ),
        columns=(Column(id="P1", x=0.0, y=0.0, bx=300.0, by=300.0),),
    )
    with pytest.raises(UnbalancedMomentError):
        rigid_cap_reactions(geometry, case(n=1000e3, mx=1.0))


def test_unknown_column_is_rejected() -> None:
    bad = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P9", n=1.0),))
    with pytest.raises(ValueError, match="P9"):
        rigid_cap_reactions(four_pile_cap(), bad)


coordinate = st.floats(min_value=-2000.0, max_value=2000.0)


@given(
    pile_xy=st.lists(st.tuples(coordinate, coordinate), min_size=3, max_size=9),
    n=st.floats(min_value=1e3, max_value=1e7),
    mx=st.floats(min_value=-1e9, max_value=1e9),
    my=st.floats(min_value=-1e9, max_value=1e9),
    column_x=st.floats(min_value=-300.0, max_value=300.0),
)
def test_reactions_satisfy_equilibrium(
    pile_xy: list[tuple[float, float]], n: float, mx: float, my: float, column_x: float
) -> None:
    xs = [x for x, _ in pile_xy]
    ys = [y for _, y in pile_xy]
    xc, yc = sum(xs) / len(xs), sum(ys) / len(ys)
    ixx = sum((x - xc) ** 2 for x in xs)
    iyy = sum((y - yc) ** 2 for y in ys)
    ixy = sum((x - xc) * (y - yc) for x, y in pile_xy)
    if ixx + iyy < 1e4 or ixx * iyy - ixy * ixy < 1e-3 * (ixx + iyy) ** 2:
        return  # estacas coincidentes ou alinhadas: cobertas por testes próprios
    geometry = GeometryInput(
        cap=Cap(lx=4500.0, ly=4500.0, h=1500.0),
        piles=tuple(Pile(id=f"E{i}", x=x, y=y, size=300.0) for i, (x, y) in enumerate(pile_xy)),
        columns=(Column(id="P1", x=column_x, y=0.0, bx=300.0, by=300.0),),
    )
    load_case = case(n=n, mx=mx, my=my)
    reactions = forces(geometry, load_case)
    resultant = applied_resultant(geometry, load_case)
    tol = 1e-6 * (abs(n) * 2000.0 + abs(mx) + abs(my))
    assert sum(reactions) == pytest.approx(resultant.fz, rel=1e-9)
    assert sum(r * x for r, x in zip(reactions, xs, strict=True)) == pytest.approx(
        resultant.sx, abs=tol
    )
    assert sum(r * y for r, y in zip(reactions, ys, strict=True)) == pytest.approx(
        resultant.sy, abs=tol
    )
