"""Altura útil por camada (D20, docs/02-metodos.md §4.11).

Os tirantes em x ficam na 1ª camada (d′ = c + φ/2), os em y φ acima e as diagonais 2φ acima,
como no desenho da D19. Valores de referência recalculados em forma fechada (D6, D13).
"""

from __future__ import annotations

import pytest

from blococalc.analysis import analyze, strut_tie_layout
from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.strut_tie import santos_stucchi
from blococalc.schemas import (
    ColumnLoad,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Project,
)
from blococalc.standards.strength import strut_tie_strengths
from tests.factories import four_pile_cap, node_depth, quincunx_cap, two_pile_cap

C35 = strut_tie_strengths(MaterialsInput(fck=35.0))


def _loads(n: float) -> LoadsInput:
    return LoadsInput(cases=(LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=n),)),))


def _forces(result_reinforcement: object) -> dict[str, float]:
    return {r.id: r.force_d for r in result_reinforcement}  # type: ignore[attr-defined]


def test_pile_node_keeps_the_first_layer_spread() -> None:
    # O nó da estaca usa a área ampliada da 1ª camada mesmo no modelo de uma camada mais alta.
    geometry = four_pile_cap()
    case = LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=980e3),))
    reactions = rigid_cap_reactions(geometry, case)
    upper = santos_stucchi(geometry, reactions, C35, 1.2, 74.0)
    kept = santos_stucchi(geometry, reactions, C35, 1.2, 74.0, pile_node_height=58.0)
    assert kept.z == pytest.approx(upper.z)
    ratio = ((400.0 + 2 * 74.0) / (400.0 + 2 * 58.0)) ** 2
    for a, b in zip(upper.struts, kept.struts, strict=True):
        assert b.sigma_pile_node == pytest.approx(a.sigma_pile_node * ratio)


@pytest.mark.golden
def test_b1_y_ties_use_the_second_layer() -> None:
    # B1: Rd = 1,2·1,05·245 = 308,7 kN (D3, D7); φ16, c = 50.
    # x: d1 = 1000 − 100 − 58 = 842; y: d2 = 842 − 16 = 826 (D20).
    # Tirante em x = Rd·550/z1; em y = Rd·437,5/z2, cada z com o seu y (D6).
    rd = 1.2 * 1.05 * 245e3

    def lever_arm(d: float) -> float:
        y = max(
            node_depth(d, 200.0, 2.0 * rd * 437.5 / C35.fcd1),
            node_depth(d, 650.0, 2.0 * rd * 550.0 / C35.fcd1),
        )
        return d - y / 2.0

    z1, z2 = lever_arm(842.0), lever_arm(826.0)
    result = analyze(four_pile_cap(), MaterialsInput(fck=35.0), _loads(980e3))
    forces = _forces(result.reinforcement)
    assert forces["tirante_E1_E2"] == pytest.approx(rd * 550.0 / z1, rel=1e-6)
    assert forces["tirante_E2_E3"] == pytest.approx(rd * 437.5 / z2, rel=1e-6)
    assert forces["tirante_E2_E3"] / 1e3 == pytest.approx(169.5, abs=0.05)
    assert result.audit.parameters["tie_height_mm"] == 58.0
    assert result.audit.parameters["tie_height_layer_2_mm"] == 74.0
    assert "tie_height_layer_3_mm" not in result.audit.parameters
    assert any("D20" in a for a in result.audit.assumptions)


def test_one_layer_cap_is_unchanged() -> None:
    # Duas estacas em x: só a 1ª camada; o modelo é o mesmo de antes da D20.
    geometry = two_pile_cap()
    result = analyze(geometry, MaterialsInput(fck=35.0), _loads(1000e3))
    case = LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=1000e3),))
    reactions = rigid_cap_reactions(geometry, case, 0.05 * 1000e3)
    phi = result.audit.parameters["bar_diameter_mm"]
    model = santos_stucchi(geometry, reactions, C35, 1.2, 50.0 + phi / 2.0)  # type: ignore[operator]
    assert _forces(result.reinforcement)["tirante_E2_E1"] == pytest.approx(model.ties[0].force_d)
    assert "tie_height_layer_2_mm" not in result.audit.parameters


def test_quincunx_diagonals_use_the_third_layer() -> None:
    geometry, materials = quincunx_cap(), MaterialsInput(fck=25.0)
    result = analyze(geometry, materials, _loads(10000e3))
    case = LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=10000e3),))
    reactions = rigid_cap_reactions(geometry, case, 0.05 * 10000e3)
    strengths = strut_tie_strengths(materials)
    phi = result.audit.parameters["bar_diameter_mm"]
    assert isinstance(phi, float)
    h1 = geometry.cap.cover + phi / 2.0
    by_layer = {
        k: {
            (t.pile_a, t.pile_b): t.force_d
            for t in santos_stucchi(geometry, reactions, strengths, 1.2, h1 + (k - 1) * phi).ties
        }
        for k in (1, 2, 3)
    }
    forces = _forces(result.reinforcement)
    assert forces["tirante_E1_E2"] == pytest.approx(by_layer[1][("E1", "E2")])  # x
    assert forces["tirante_E2_E3"] == pytest.approx(by_layer[2][("E2", "E3")])  # y
    assert forces["tirante_E1_E5"] == pytest.approx(by_layer[3][("E1", "E5")])  # diagonal
    assert result.audit.parameters["tie_height_layer_3_mm"] == h1 + 2 * phi


def test_layout_struts_come_from_the_highest_layer() -> None:
    # Bielas e nó do pilar pelo modelo da camada mais alta (menor z, a favor da segurança).
    geometry, materials, loads = four_pile_cap(), MaterialsInput(fck=35.0), _loads(980e3)
    project = Project(name="B1", geometry=geometry, materials=materials, loads=loads)
    layout = strut_tie_layout(project, "C1")
    assert layout is not None
    case = loads.cases[0]
    reactions = rigid_cap_reactions(geometry, case, 0.05 * 980e3)
    upper = santos_stucchi(geometry, reactions, C35, 1.2, 74.0)
    tops = [n.z for n in layout.nodes if n.id.startswith("topo_")]
    assert tops == pytest.approx([geometry.cap.h - upper.y / 2.0] * 4)
    piles = [n.z for n in layout.nodes if n.id.startswith("estaca_")]
    assert piles == pytest.approx([geometry.cap.pile_embedment + 74.0] * 4)
    ties = {m.id: m.force_d for m in layout.members if m.id.startswith("tirante_")}
    design = _forces(analyze(geometry, materials, loads).reinforcement)
    assert ties == pytest.approx({k: design[k] for k in ties})
