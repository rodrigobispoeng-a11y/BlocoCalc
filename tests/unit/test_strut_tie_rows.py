"""M5 para estacas em fileiras desencontradas (D17, docs/02-metodos.md §4.8).

Isoáreas do pilar proporcionais às reações, deslocadas da excentricidade, e tirantes na
triangulação das estacas pelo mínimo de Σ F·l (critério da D12), com o menor Σ F² entre os ótimos.
"""

from __future__ import annotations

import numpy as np
import pytest

from blococalc.analysis import analyze
from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.strut_tie import StrutTieModel, UnsupportedLayoutError, santos_stucchi
from blococalc.schemas import (
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
)
from blococalc.standards.strength import strut_tie_strengths
from tests.factories import staggered_cap

C30 = strut_tie_strengths(MaterialsInput(fck=30.0))
GAMMA_N = 1.2
TIE_HEIGHT = 60.0


def solve(geometry: GeometryInput, n: float, mx: float = 0.0, my: float = 0.0) -> StrutTieModel:
    case = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=n, mx=mx, my=my),))
    reactions = rigid_cap_reactions(geometry, case)
    return santos_stucchi(geometry, reactions, C30, GAMMA_N, TIE_HEIGHT)


def pushes(geometry: GeometryInput, model: StrutTieModel) -> dict[str, np.ndarray]:
    piles = {p.id: p for p in geometry.piles}
    return {
        s.pile_id: s.force_d
        / model.z
        * np.array((piles[s.pile_id].x - s.origin_x, piles[s.pile_id].y - s.origin_y))
        for s in model.struts
    }


def node_residual(geometry: GeometryInput, model: StrutTieModel) -> float:
    """Maior desequilíbrio entre empuxo e tirantes numa estaca, relativo ao maior empuxo."""
    load = pushes(geometry, model)
    net = dict(load)
    for t in model.ties:
        pull = t.force_d * np.array((t.dir_x, t.dir_y))
        net[t.pile_a] = net[t.pile_a] + pull
        net[t.pile_b] = net[t.pile_b] - pull
    largest = max(float(np.linalg.norm(v)) for v in load.values())
    return max(float(np.linalg.norm(v)) for v in net.values()) / largest


def force(model: StrutTieModel, a: str, b: str) -> float:
    return next(t.force_d for t in model.ties if {t.pile_a, t.pile_b} == {a, b})


@pytest.mark.parametrize("rows", [(5, 4), (3, 2, 3), (4, 3, 4), (4, 2, 4)])
def test_ties_balance_every_pile(rows: tuple[int, ...]) -> None:
    geometry = staggered_cap(rows, h=2000.0)
    model = solve(geometry, 8e6)
    assert model.staggered
    assert model.equilibrium_correction < 1e-9
    assert node_residual(geometry, model) < 1e-4  # tirantes abaixo de 1e-4 do maior são descartados
    assert all(t.force_d > 0.0 for t in model.ties)


def test_isoareas_follow_rows_and_reactions() -> None:
    # 3-2-3 centrado: reações iguais, faixas com 3/8, 2/8 e 3/8 do lado do pilar em y.
    geometry = staggered_cap((3, 2, 3))
    model = solve(geometry, 6e6)
    origin = {s.pile_id: (s.origin_x, s.origin_y) for s in model.struts}
    cy = geometry.columns[0].y
    assert origin["E1"] == pytest.approx((-800.0 / 3.0, cy - 400.0 + 150.0))
    assert origin["E4"] == pytest.approx((-200.0, cy))
    assert origin["E8"] == pytest.approx((800.0 / 3.0, cy + 400.0 - 150.0))


def test_symmetric_layout_gives_symmetric_ties() -> None:
    # Entre os ótimos de Σ F·l, o de menor Σ F² respeita a simetria do 3-2-3 em x e em y.
    model = solve(staggered_cap((3, 2, 3)), 6e6)
    assert force(model, "E1", "E2") == pytest.approx(force(model, "E2", "E3"), rel=1e-6)
    assert force(model, "E1", "E2") == pytest.approx(force(model, "E7", "E8"), rel=1e-6)
    assert force(model, "E2", "E4") == pytest.approx(force(model, "E2", "E5"), rel=1e-6)
    assert force(model, "E1", "E6") == pytest.approx(force(model, "E3", "E8"), rel=1e-6)


def test_five_four_net_matches_the_source_figure() -> None:
    # TQS, 9 estacas 5-4: tirantes nas fileiras e diagonais em zigue-zague, 2n − 3 = 15 barras.
    geometry = staggered_cap((5, 4), column=(2000.0, 400.0), h=2000.0)
    model = solve(geometry, 9e6)
    pairs = {frozenset((t.pile_a, t.pile_b)) for t in model.ties}
    rows = {frozenset((f"E{i}", f"E{i + 1}")) for i in (1, 2, 3, 4, 6, 7, 8)}
    zigzag = {frozenset((f"E{i}", f"E{i + 5}")) for i in range(1, 5)}
    zigzag |= {frozenset((f"E{i + 1}", f"E{i + 5}")) for i in range(1, 5)}
    assert pairs == rows | zigzag


def test_five_four_forces_from_node_equilibrium() -> None:
    # Rede isostática: as forças saem só do equilíbrio dos nós, conferido aqui por mínimos
    # quadrados, sem programa linear.
    geometry = staggered_cap((5, 4), column=(2000.0, 400.0), h=2000.0)
    model = solve(geometry, 9e6)
    ids = [p.id for p in geometry.piles]
    load = pushes(geometry, model)
    matrix = np.zeros((2 * len(ids), len(model.ties)))
    for k, t in enumerate(model.ties):
        a, b = ids.index(t.pile_a), ids.index(t.pile_b)
        matrix[2 * a : 2 * a + 2, k] += (t.dir_x, t.dir_y)
        matrix[2 * b : 2 * b + 2, k] -= (t.dir_x, t.dir_y)
    rhs = -np.concatenate([load[i] for i in ids])
    expected = np.linalg.lstsq(matrix, rhs, rcond=None)[0]
    assert [t.force_d for t in model.ties] == pytest.approx(list(expected), rel=1e-6)


def test_moment_shifts_isoareas_and_keeps_equilibrium() -> None:
    geometry = staggered_cap((3, 2, 3))
    centered = solve(geometry, 6e6)
    model = solve(geometry, 6e6, my=1500e6)
    shift = [b.origin_x - a.origin_x for a, b in zip(centered.struts, model.struts, strict=True)]
    assert min(shift) > 0.0  # a carga anda para +x e as isoáreas vão junto
    assert model.equilibrium_correction < 0.01
    assert node_residual(geometry, model) < 0.01 + 1e-4


def test_eccentricity_outside_column_is_rejected() -> None:
    with pytest.raises(UnsupportedLayoutError, match="fora da seção do pilar"):
        solve(staggered_cap((3, 2, 3)), 6e6, my=6000e6)


def test_rows_along_y_are_recognized() -> None:
    geometry = staggered_cap((3, 2, 3))
    turned = geometry.model_copy(
        update={
            "piles": tuple(p.model_copy(update={"x": p.y, "y": p.x}) for p in geometry.piles),
            "columns": tuple(
                c.model_copy(update={"x": c.y, "y": c.x, "bx": c.by, "by": c.bx})
                for c in geometry.columns
            ),
        }
    )
    a, b = solve(geometry, 6e6), solve(turned, 6e6)
    assert sorted(t.force_d for t in b.ties) == pytest.approx(sorted(t.force_d for t in a.ties))


def test_analysis_records_d17() -> None:
    geometry = staggered_cap((3, 2, 3))
    loads = LoadsInput(
        cases=(LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=6e6),)),)
    )
    result = analyze(geometry, MaterialsInput(fck=30.0), loads, DetailingInput())
    assert any("D17" in a for a in result.audit.assumptions)
    assert result.audit.parameters["equilibrium_correction_ELU1"] == pytest.approx(0.0, abs=1e-9)
