"""M5 para estacas fora de grade (D15, docs/02-metodos.md §4.6).

Contorno convexo com as bielas da regra de 2 a 4 estacas, estacas internas sob o pilar com biela
vertical e tirantes com metade do empuxo no anel e metade em tirantes radiais. Os valores do B7
(Bavaresco 2016, B05P01) são recalculados aqui em forma fechada.
"""

from __future__ import annotations

import math

import pytest

from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.strut_tie import (
    INTERIOR_PILE_FACTOR,
    StrutTieModel,
    Tie,
    UnsupportedLayoutError,
    santos_stucchi,
)
from blococalc.schemas import Column, ColumnLoad, GeometryInput, LoadCase, MaterialsInput, Pile
from blococalc.standards.strength import strut_tie_strengths
from tests.factories import node_depth, polygon_cap, quincunx_cap

C25 = strut_tie_strengths(MaterialsInput(fck=25.0))
GAMMA_N = 1.2
TIE_HEIGHT = 58.0  # D8: cobrimento 50 + φ16/2


def solve(geometry: GeometryInput, n: float) -> StrutTieModel:
    case = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=n),))
    reactions = rigid_cap_reactions(geometry, case)
    return santos_stucchi(geometry, reactions, C25, GAMMA_N, TIE_HEIGHT)


def tie(model: StrutTieModel, a: str, b: str) -> Tie:
    return next(t for t in model.ties if {t.pile_a, t.pile_b} == {a, b})


@pytest.mark.golden
def test_b7_quincunx() -> None:
    # B7: Rd = 1,2·10 000/5 = 2400 kN; d = 2100 − 100 − 58 = 1942; origens nos quadrantes (±250).
    rd, d, run = 2400e3, 1942.0, 1600.0 - 250.0
    y = node_depth(d, 1000.0, 2.0 * rd * run / C25.fcd1)  # duas estacas empurram cada face
    z = d - y / 2.0
    push = rd * math.sqrt(2.0) * run / z  # H = R·lproj/z

    model = solve(quincunx_cap(), 10_000e3)

    assert model.y == pytest.approx(y, rel=1e-6)
    assert model.y == pytest.approx(186.8, abs=0.1)
    assert model.interior_piles == ("E5",)
    corner = next(s for s in model.struts if s.pile_id == "E1")
    assert corner.l_proj == pytest.approx(1909.2, abs=0.1)  # fonte: 190,9 cm
    center = next(s for s in model.struts if s.pile_id == "E5")
    assert math.isinf(center.tan_theta)
    assert center.sigma_pile_node == pytest.approx(INTERIOR_PILE_FACTOR * rd / 716.0**2)
    assert INTERIOR_PILE_FACTOR == 1.4  # Bavaresco (2016), §5: folga de 40 %
    # Metade no anel (H/2 em dois lados a 45°) e metade nos tirantes radiais até a estaca central.
    assert tie(model, "E1", "E2").force_d == pytest.approx(push / 2.0 / math.sqrt(2.0), rel=1e-6)
    assert tie(model, "E1", "E2").force_d == pytest.approx(876.4e3, abs=0.1e3)
    assert tie(model, "E1", "E5").force_d == pytest.approx(push / 2.0, rel=1e-6)
    assert tie(model, "E1", "E5").force_d == pytest.approx(1239.3e3, abs=0.1e3)
    assert len(model.ties) == 8


def horizontal_balance(model: StrutTieModel, geometry: GeometryInput) -> float:
    """Maior resíduo em planta nas estacas: empuxo da biela menos a soma dos tirantes [N]."""
    piles = {p.id: p for p in geometry.piles}
    worst = 0.0
    for strut in model.struts:
        p = piles[strut.pile_id]
        fx = strut.force_d / model.z * (p.x - strut.origin_x)
        fy = strut.force_d / model.z * (p.y - strut.origin_y)
        for t in model.ties:
            if p.id in (t.pile_a, t.pile_b):
                sign = 1.0 if t.pile_a == p.id else -1.0
                fx += sign * t.force_d * t.dir_x
                fy += sign * t.force_d * t.dir_y
        worst = max(worst, math.hypot(fx, fy))
    return worst


@pytest.mark.parametrize(("n", "center"), [(6, True), (6, False), (7, True)])
def test_regular_polygons_split_push_between_ring_and_radial_ties(n: int, center: bool) -> None:
    geometry = polygon_cap(n, center=center)
    model = solve(geometry, 1e6 * len(geometry.piles))
    outline = {f"E{i + 1}": i for i in range(n)}

    def on_ring(t: Tie) -> bool:
        if t.pile_a not in outline or t.pile_b not in outline:
            return False
        return abs(outline[t.pile_a] - outline[t.pile_b]) in (1, n - 1)

    ring = [t for t in model.ties if on_ring(t)]
    radial = [t for t in model.ties if not on_ring(t)]
    assert len(ring) == n
    assert len(radial) == (n if center else n // 2)
    assert all(t.force_d > 0.0 for t in model.ties)
    if center:
        assert {t.pile_b for t in radial} | {t.pile_a for t in radial} >= {f"E{n + 1}"}
    else:  # diagonais de uma estaca à oposta
        assert all(abs(outline[t.pile_a] - outline[t.pile_b]) == n // 2 for t in radial)


def test_b7_ties_balance_every_pile() -> None:
    geometry = quincunx_cap()
    model = solve(geometry, 10_000e3)
    assert horizontal_balance(model, geometry) < 1e-6 * model.struts[0].force_d


def test_odd_polygon_without_center_keeps_full_ring() -> None:
    # Pentágono sem estaca central: não há estaca oposta para o tirante radial.
    geometry = polygon_cap(5)
    model = solve(geometry, 5e6)
    assert len(model.ties) == 5
    assert model.interior_piles == ()


def test_triangle_with_center_pile_under_column() -> None:
    model = solve(polygon_cap(3, center=True), 4e6)
    assert model.interior_piles == ("E4",)
    assert len(model.ties) == 6


def test_interior_pile_outside_column_is_rejected() -> None:
    geometry = polygon_cap(6, center=True)
    shifted = geometry.model_copy(
        update={"piles": (*geometry.piles[:-1], Pile(id="E7", x=300.0, y=0.0, size=400.0))}
    )
    with pytest.raises(UnsupportedLayoutError, match="sob o pilar"):
        solve(shifted, 7e6)


def test_collinear_piles_on_outline_are_rejected() -> None:
    # Fileiras desencontradas: 3 estacas alinhadas no lado de cima e 2 embaixo.
    geometry = polygon_cap(6).model_copy(
        update={
            "piles": tuple(
                Pile(id=f"E{i + 1}", x=x, y=y, size=400.0)
                for i, (x, y) in enumerate(
                    (
                        (-1000.0, 600.0),
                        (0.0, 600.0),
                        (1000.0, 600.0),
                        (-500.0, -600.0),
                        (500.0, -600.0),
                    )
                )
            ),
            "columns": (Column(id="P1", x=0.0, y=120.0, bx=400.0, by=400.0),),
        }
    )
    with pytest.raises(UnsupportedLayoutError, match="alinhadas"):
        solve(geometry, 5e6)
