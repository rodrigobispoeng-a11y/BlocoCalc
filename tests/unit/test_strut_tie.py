"""Bielas, nós e tirantes pelo método de Santos/Stucchi (docs/02-metodos.md §4.1).

Os valores de referência são recalculados aqui em forma fechada, sem passar pelo código:
com a origem de cada biela no centroide da parte do pilar voltada para a estaca, as decisões D6 e
D13 dão (b + 2y)·y·(d − y/2) = ΣR·lproj/fcd1 (ver `tests.factories.node_depth`).
"""

from __future__ import annotations

import math

import pytest

from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.strut_tie import StrutTieModel, UnsupportedLayoutError, santos_stucchi
from blococalc.schemas import (
    Cap,
    CheckStatus,
    Column,
    ColumnLoad,
    GeometryInput,
    LoadCase,
    MaterialsInput,
    Pile,
    PileReaction,
)
from blococalc.standards.strength import strut_tie_strengths
from blococalc.standards.strut_tie_checks import strut_tie_checks
from tests.factories import four_pile_cap, node_depth, two_pile_cap

C35 = strut_tie_strengths(MaterialsInput(fck=35.0))
GAMMA_N = 1.2
TIE_HEIGHT = 50.0


def solve(geometry: GeometryInput, n: float, **moments: float) -> StrutTieModel:
    case = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=n, **moments),))
    reactions = rigid_cap_reactions(geometry, case)
    return santos_stucchi(geometry, reactions, C35, GAMMA_N, TIE_HEIGHT)


def sin2(tan_theta: float) -> float:
    return tan_theta**2 / (1.0 + tan_theta**2)


@pytest.mark.golden
def test_b1_four_piles() -> None:
    # B1 (Macedo 2022, §6.1): Fd = 980 kN, Rd = 1,2·245 = 294 kN; d = 1000 − 100 − 50 = 850.
    # Pilar 200×650: origens em (±50, ±162,5). Em y a compressão cruza a face 200 + 2y e governa
    # sobre a de x (650 + 2y). D13 trocou a face de 200 por 200 + 2y: y passou de 87,29 a 55,16 mm.
    rd, d = 294e3, 850.0
    y = max(
        node_depth(d, 200.0, 2.0 * rd * 437.5 / C35.fcd1),
        node_depth(d, 650.0, 2.0 * rd * 550.0 / C35.fcd1),
    )
    z = d - y / 2.0
    l_proj = math.hypot(550.0, 437.5)
    tan_t = z / l_proj

    model = solve(four_pile_cap(), 980e3)

    assert model.d == pytest.approx(d)
    assert model.y == pytest.approx(y, rel=1e-6)
    assert model.y == pytest.approx(55.16, abs=0.01)
    assert model.z == pytest.approx(z, rel=1e-6)
    for strut in model.struts:
        assert strut.force_d == pytest.approx(rd)
        assert strut.l_proj == pytest.approx(l_proj)
        assert strut.tan_theta == pytest.approx(tan_t, rel=1e-6)
        area_c = (200.0 + 2.0 * y) * (650.0 + 2.0 * y) / 4.0
        assert strut.sigma_column_node == pytest.approx(rd / (area_c * sin2(tan_t)), rel=1e-6)
        area_p = math.pi * (400.0 + 2.0 * TIE_HEIGHT) ** 2 / 4.0
        assert strut.sigma_pile_node == pytest.approx(rd / (area_p * sin2(tan_t)), rel=1e-6)
    ties = {(t.dir_x != 0.0): t for t in model.ties}
    assert ties[True].force_d == pytest.approx(rd * 550.0 / z, rel=1e-6)  # tirantes em x
    assert ties[False].force_d == pytest.approx(rd * 437.5 / z, rel=1e-6)  # tirantes em y
    assert ties[True].area_required == pytest.approx(rd * 550.0 / z / C35.fyd, rel=1e-6)


@pytest.mark.golden
def test_two_piles() -> None:
    # Pilar 400×400 entre estacas a ±600: origens em ±100, lproj = 500, d = 900 − 100 − 50.
    rd, d = 600e3, 750.0
    y = node_depth(d, 400.0, rd * 500.0 / C35.fcd1)
    z = d - y / 2.0

    model = solve(two_pile_cap(), 1000e3)

    assert model.y == pytest.approx(y, rel=1e-6)
    (tie,) = model.ties
    assert tie.force_d == pytest.approx(rd * 500.0 / z, rel=1e-6)
    area_c = (400.0 + 2.0 * y) ** 2 / 2.0
    for strut in model.struts:
        assert strut.sigma_column_node == pytest.approx(rd / (area_c * sin2(z / 500.0)), rel=1e-6)


def three_pile_cap(spacing: float = 1200.0) -> GeometryInput:
    radius = spacing / math.sqrt(3.0)
    piles = tuple(
        Pile(
            id=f"E{i + 1}",
            x=radius * math.cos(math.radians(90.0 + 120.0 * i)),
            y=radius * math.sin(math.radians(90.0 + 120.0 * i)),
            size=400.0,
        )
        for i in range(3)
    )
    return GeometryInput(
        cap=Cap(lx=2200.0, ly=2000.0, h=1000.0, pile_embedment=100.0),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=400.0, by=400.0),),
    )


def test_three_piles_balance_each_node() -> None:
    # Pilar quadrado não tem simetria de 120°: as bielas diferem pouco entre si (D4).
    model = solve(three_pile_cap(), 1500e3)

    tans = [s.tan_theta for s in model.struts]
    assert tans == pytest.approx([tans[0]] * 3, rel=1e-2)
    # E1 está no eixo de simetria: sua biela é radial e os dois tirantes a 60° dividem a
    # componente horizontal H igualmente, T = H/√3.
    top = next(s for s in model.struts if s.pile_id == "E1")
    expected = top.force_d * top.l_proj / model.z / math.sqrt(3.0)
    at_top = [t.force_d for t in model.ties if "E1" in (t.pile_a, t.pile_b)]
    assert at_top == pytest.approx([expected] * 2)


def test_four_piles_with_moment_size_ties_by_the_worst_end() -> None:
    model = solve(four_pile_cap(), 980e3, my=100e6)
    struts = {s.pile_id: s for s in model.struts}
    assert struts["E2"].force_d > struts["E1"].force_d
    x_ties = [t for t in model.ties if t.dir_y == 0.0]
    expected = struts["E2"].force_d * (600.0 - 50.0) / model.z
    assert [t.force_d for t in x_ties] == pytest.approx([expected] * 2)


def test_rejects_pile_in_tension() -> None:
    with pytest.raises(UnsupportedLayoutError, match="tracionada"):
        solve(two_pile_cap(), 100e3, my=200e6)


def test_rejects_more_than_four_piles() -> None:
    base = four_pile_cap()
    geometry = base.model_copy(
        update={"piles": (*base.piles, Pile(id="E5", x=0.0, y=0.0, size=400.0))}
    )
    with pytest.raises(UnsupportedLayoutError, match="2, 3 ou 4"):
        solve(geometry, 980e3)


def test_rejects_interior_pile() -> None:
    piles = (
        Pile(id="E1", x=-800.0, y=-600.0, size=300.0),
        Pile(id="E2", x=800.0, y=-600.0, size=300.0),
        Pile(id="E3", x=0.0, y=800.0, size=300.0),
        Pile(id="E4", x=0.0, y=-200.0, size=300.0),
    )
    geometry = four_pile_cap().model_copy(update={"piles": piles})
    with pytest.raises(UnsupportedLayoutError, match="E4 não está no contorno"):
        santos_stucchi(geometry, _equal_reactions(geometry), C35, GAMMA_N, TIE_HEIGHT)


def test_rejects_two_piles_in_the_same_direction() -> None:
    piles = (
        Pile(id="E1", x=400.0, y=0.0, size=300.0),
        Pile(id="E2", x=900.0, y=0.0, size=300.0),
    )
    geometry = two_pile_cap().model_copy(update={"piles": piles})
    with pytest.raises(UnsupportedLayoutError, match="mesma direção"):
        santos_stucchi(geometry, _equal_reactions(geometry), C35, GAMMA_N, TIE_HEIGHT)


def test_rejects_two_columns() -> None:
    base = two_pile_cap()
    second = Column(id="P2", x=300.0, y=0.0, bx=200.0, by=200.0)
    geometry = base.model_copy(update={"columns": (*base.columns, second)})
    with pytest.raises(UnsupportedLayoutError, match="único pilar"):
        santos_stucchi(geometry, _equal_reactions(geometry), C35, GAMMA_N, TIE_HEIGHT)


def test_rejects_compressed_tie() -> None:
    # Triângulo muito aberto com o pilar próximo da estaca do vértice obtuso.
    geometry = GeometryInput(
        cap=Cap(lx=3000.0, ly=1200.0, h=1000.0, pile_embedment=100.0),
        piles=(
            Pile(id="E1", x=-1200.0, y=0.0, size=300.0),
            Pile(id="E2", x=1200.0, y=0.0, size=300.0),
            Pile(id="E3", x=0.0, y=200.0, size=300.0),
        ),
        columns=(Column(id="P1", x=0.0, y=120.0, bx=300.0, by=300.0),),
    )
    with pytest.raises(UnsupportedLayoutError, match="Tirante comprimido"):
        solve(geometry, 900e3)


def test_rejects_node_deeper_than_lever_arm() -> None:
    with pytest.raises(UnsupportedLayoutError, match="Nó CCC"):
        solve(four_pile_cap(h=400.0), 40000e3)


def _equal_reactions(geometry: GeometryInput) -> tuple[PileReaction, ...]:
    share = 1000e3 / len(geometry.piles)
    return tuple(PileReaction(pile_id=p.id, case_id="ELU1", force=share) for p in geometry.piles)


@pytest.mark.golden
def test_b1_checks() -> None:
    checks = {c.id: c for c in strut_tie_checks(solve(four_pile_cap(), 980e3), C35)}
    assert checks["no_pilar_E1"].status is CheckStatus.OK
    assert checks["no_pilar_E1"].capacity == pytest.approx(18.275)
    assert checks["no_estaca_E1"].capacity == pytest.approx(15.48)
    assert checks["tg_theta_min_E1"].status is CheckStatus.OK
    assert checks["tg_theta_max_E1"].status is CheckStatus.OK
    assert checks["theta_45_E1"].status is CheckStatus.OK  # tg θ ≈ 1,15
    assert checks["ductilidade"].status is CheckStatus.OK  # y/d ≈ 0,10
    assert len(checks) == 5 * 4 + 1


def test_flat_strut_fails_angle_and_warns() -> None:
    # h = 500: d = 350, y ≈ 113 mm (y/d ≈ 0,32), tg θ ≈ 0,42.
    checks = {c.id: c for c in strut_tie_checks(solve(four_pile_cap(h=500.0), 980e3), C35)}
    assert checks["tg_theta_min_E1"].status is CheckStatus.FAIL
    assert checks["theta_45_E1"].status is CheckStatus.WARNING
    assert checks["tg_theta_max_E1"].status is CheckStatus.OK
    assert checks["ductilidade"].status is CheckStatus.WARNING
