"""M5 para N estacas em grade retangular (D13, docs/02-metodos.md §4.4).

Os valores de referência do B2 são recalculados aqui em forma fechada: biela de cada estaca a
partir do centroide da sua parte do pilar dividido em nx × ny, `y` por D6 com a face espraiada a
45° (`tests.factories.node_depth`) e tirantes por linha com a força acumulada dos nós.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.space_truss import TrussNode, optimal_truss
from blococalc.core.strut_tie import StrutTieModel, santos_stucchi
from blococalc.schemas import CheckStatus, ColumnLoad, GeometryInput, LoadCase, MaterialsInput
from blococalc.standards.strength import strut_tie_strengths
from blococalc.standards.strut_tie_checks import strut_tie_checks
from tests.factories import grid_cap, node_depth

C35 = strut_tie_strengths(MaterialsInput(fck=35.0))
GAMMA_N = 1.2
TIE_HEIGHT = 62.5  # D8: cobrimento 50 + φ25/2
TF = 9.80665e3  # N


def solve(geometry: GeometryInput, n: float, **moments: float) -> StrutTieModel:
    case = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=n, **moments),))
    reactions = rigid_cap_reactions(geometry, case)
    return santos_stucchi(geometry, reactions, C35, GAMMA_N, TIE_HEIGHT)


def projections(model: StrutTieModel) -> tuple[float, float]:
    return (
        sum(t.force_d * abs(t.dir_x) for t in model.ties),
        sum(t.force_d * abs(t.dir_y) for t in model.ties),
    )


def m7_projections(geometry: GeometryInput, model: StrutTieModel) -> tuple[float, float]:
    """Treliça M7 com os mesmos nós: origens das bielas no topo (y/2), estacas no fundo (d).

    A carga do pilar se divide entre as partes linearmente em planta (como M1), com a mesma
    resultante e os mesmos momentos das reações, para os nós ficarem em equilíbrio.
    """
    piles = {p.id: p for p in geometry.piles}
    origins = np.array([(1.0, s.origin_x, s.origin_y) for s in model.struts])
    targets = np.array([(1.0, piles[s.pile_id].x, piles[s.pile_id].y) for s in model.struts])
    forces = np.array([s.force_d for s in model.struts])
    coefficients = np.linalg.lstsq(origins.T @ origins, targets.T @ forces, rcond=None)[0]
    nodes = []
    for strut, load in zip(model.struts, origins @ coefficients, strict=True):
        pile = piles[strut.pile_id]
        nodes += [
            TrussNode(f"{pile.id}_pilar", strut.origin_x, strut.origin_y, -model.y / 2.0,
                      fz=-float(load)),
            TrussNode(pile.id, pile.x, pile.y, -model.d, fz=strut.force_d),
        ]  # fmt: skip
    truss = optimal_truss(nodes)
    bottom = [m for m in truss.members if m.force > 0.0 and abs(m.direction[2]) < 1e-9]
    return (
        sum(m.force * abs(m.direction[0]) for m in bottom),
        sum(m.force * abs(m.direction[1]) for m in bottom),
    )


@pytest.mark.golden
def test_b2_eight_piles() -> None:
    # B2: 8 × 113,96 tf, γf = 1,4; Rd = 1,2·Nd/8. d = 1400 − 100 − 62,5 = 1237,5.
    nd = 1.4 * 8 * 113.96 * TF
    rd, d = GAMMA_N * nd / 8.0, 1237.5
    # Pilar 2090×300 em 4×2 partes: origens em x = ±261,25 e ±783,75, y = ±75.
    outer, inner, side = 2250.0 - 783.75, 750.0 - 261.25, 750.0 - 75.0
    y = max(
        node_depth(d, 300.0, rd * 2.0 * (outer + inner) / C35.fcd1),  # x: face by + 2y
        node_depth(d, 2090.0, rd * 4.0 * side / C35.fcd1),  # y: face bx + 2y
    )
    z = d - y / 2.0

    model = solve(grid_cap(4, 2), nd)

    assert model.y == pytest.approx(y, rel=1e-6)
    assert model.y == pytest.approx(368.0, abs=0.1)
    assert model.y / model.d < 0.3
    corner = next(s for s in model.struts if s.pile_id == "E8")
    # Fonte: a = 161,4 cm e α = 24,719° "medidos".
    assert corner.l_proj == pytest.approx(1614.0, abs=1.0)
    alpha = math.degrees(math.atan2(750.0 - corner.origin_y, 2250.0 - corner.origin_x))
    assert alpha == pytest.approx(24.719, abs=1e-3)
    assert corner.tan_theta == pytest.approx(z / math.hypot(outer, side), rel=1e-6)

    row = [
        t for t in model.ties if t.dir_x != 0.0 and {t.pile_a, t.pile_b} <= {"E5", "E6", "E7", "E8"}
    ]
    assert [t.force_d for t in row] == pytest.approx(
        [rd * outer / z, rd * (outer + inner) / z, rd * outer / z], rel=1e-6
    )
    assert max(t.area_required for t in row) == pytest.approx(8014.0, abs=1.0)  # 80,14 cm²
    columns = [t for t in model.ties if t.dir_y != 0.0]
    assert len(columns) == 4
    assert [t.force_d for t in columns] == pytest.approx([rd * side / z] * 4, rel=1e-6)


def test_b2_matches_space_truss() -> None:
    geometry = grid_cap(4, 2)
    model = solve(geometry, 15e6)
    assert projections(model) == pytest.approx(m7_projections(geometry, model), rel=1e-6)


@pytest.mark.parametrize(("nx", "ny"), [(2, 3), (3, 3), (4, 4)])
def test_square_column_grids_are_symmetric_and_balanced(nx: int, ny: int) -> None:
    geometry = grid_cap(nx, ny, column=(600.0, 600.0))
    nd = 3e6 * nx * ny
    model = solve(geometry, nd)

    assert sum(s.force_d for s in model.struts) == pytest.approx(GAMMA_N * nd)
    tx, ty = projections(model)
    if nx == ny:
        assert tx == pytest.approx(ty, rel=1e-9)
    assert (tx, ty) == pytest.approx(m7_projections(geometry, model), rel=1e-6)


def test_center_pile_under_column_gets_vertical_strut() -> None:
    model = solve(grid_cap(3, 3, column=(600.0, 600.0)), 27e6)
    center = next(s for s in model.struts if s.pile_id == "E5")
    assert center.l_proj == pytest.approx(0.0)
    assert math.isinf(center.tan_theta)
    checks = {c.id: c for c in strut_tie_checks(model, C35)}
    assert "tg_theta_max_E5" not in checks
    assert checks["no_pilar_E5"].status is CheckStatus.OK


def test_moment_keeps_ties_on_safe_side_of_space_truss() -> None:
    geometry = grid_cap(4, 2)
    model = solve(geometry, 15e6, my=3000e6)
    reactions = {s.pile_id: s.force_d for s in model.struts}
    assert reactions["E4"] > reactions["E1"]
    tx, ty = projections(model)
    m7x, m7y = m7_projections(geometry, model)
    assert tx >= m7x * (1.0 - 1e-6)
    assert ty >= m7y * (1.0 - 1e-6)
