"""Adaptador do CalculiX: entrada, execução e leitura (D14, docs/02-metodos.md §4.5).

Os testes que executam o CalculiX ficam marcados com `fem` e são pulados onde ele não existe.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("gmsh")

from blococalc.fem.ccx import (
    FemError,
    FemResult,
    find_ccx,
    horizontal_supports,
    input_deck,
    read_frd,
    secant_modulus,
    solve,
)
from blococalc.fem.loads import column_nodal_forces
from blococalc.fem.mesh import CapMesh, mesh_cap
from blococalc.fem.post import pile_reactions
from blococalc.schemas import ColumnLoad, GeometryInput
from tests.factories import four_pile_cap

COARSE = 200.0
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason="CalculiX (ccx) não instalado")


@pytest.fixture(scope="module")
def b1() -> tuple[GeometryInput, CapMesh]:
    geometry = four_pile_cap()
    return geometry, mesh_cap(geometry, COARSE)


@pytest.mark.golden
def test_secant_modulus() -> None:
    # fck = 35: αi = 0,8 + 0,2·35/80 = 0,8875; Eci = 5600·√35 = 33 130 MPa; Ecs = 29 403 MPa.
    assert secant_modulus(35.0) == pytest.approx(0.8875 * 5600.0 * math.sqrt(35.0))
    assert secant_modulus(35.0) == pytest.approx(29403.0, abs=1.0)
    assert secant_modulus(90.0) == pytest.approx(5600.0 * math.sqrt(90.0))  # αi ≤ 1


def test_horizontal_supports_are_isostatic(b1: tuple[GeometryInput, CapMesh]) -> None:
    _, mesh = b1
    (a, dof_a1), (a2, dof_a2), (b, dof_b) = horizontal_supports(mesh)
    assert a == a2 and {dof_a1, dof_a2} == {1, 2}
    assert b != a and dof_b in (1, 2)
    assert np.hypot(*(mesh.nodes[a, :2] - (-600.0, -600.0))) < COARSE


def test_input_deck_lists_supports_and_loads(b1: tuple[GeometryInput, CapMesh]) -> None:
    _, mesh = b1
    forces = np.zeros_like(mesh.nodes)
    forces[0] = (0.0, 0.0, -5.0)
    deck = input_deck(mesh, forces, 29403.0)
    assert "*NSET, NSET=PILE3" in deck
    assert "PILE3,3,3,0" in deck
    assert "\n1,3,-5.000000\n" in deck
    assert deck.count("*ELEMENT") == 1


def test_input_deck_puts_springs_under_rigid_heads(b1: tuple[GeometryInput, CapMesh]) -> None:
    # D16: cabeça rígida (uz dos nós da cabeça = uz do nó de referência) sobre uma mola k.
    _, mesh = b1
    deck = input_deck(mesh, np.zeros_like(mesh.nodes), 29403.0, {"E1": 720e3})
    head = mesh.pile_nodes["E1"]
    ref = len(mesh.nodes) + 1
    assert "PILE0,3,3,0" not in deck and "PILE1,3,3,0" in deck
    assert deck.count("*EQUATION") == len(head)
    assert f"\n{head[0] + 1},3,1.0,{ref},3,-1.0\n" in deck
    assert "*ELEMENT, TYPE=SPRING1, ELSET=MOLA0" in deck
    assert f"\n{len(mesh.tets) + 1},{ref}\n" in deck
    assert "*SPRING, ELSET=MOLA0\n3,\n7.200000E+05\n" in deck
    assert f"\n{ref},1,2,0\n" in deck
    with pytest.raises(ValueError, match="E9"):
        input_deck(mesh, np.zeros_like(mesh.nodes), 29403.0, {"E9": 1.0})


def test_spring_pile_reaction_is_k_times_settlement(b1: tuple[GeometryInput, CapMesh]) -> None:
    _, mesh = b1
    n = len(mesh.nodes)
    displacements = np.zeros((n, 3))
    displacements[mesh.pile_nodes["E1"], 2] = -0.5
    reactions = np.zeros((n, 3))
    reactions[mesh.pile_nodes["E2"], 2] = 1e3
    result = FemResult(displacements, np.zeros((n, 6)), reactions)
    found = pile_reactions(mesh, result, {"E1": 720e3})
    assert found["E1"] == pytest.approx(360e3)
    assert found["E2"] == pytest.approx(1e3 * len(mesh.pile_nodes["E2"]))


def test_read_frd_parses_fixed_columns() -> None:
    def row(node: int, *values: float) -> str:
        return " -1" + f"{node:10d}" + "".join(f"{v:12.5E}" for v in values)

    text = "\n".join(
        [
            " -4  DISP        4    1",
            row(1, 0.1, -0.2, -1.5e-3),
            row(2, 0.0, 0.0, 0.0),
            " -3",
            " -4  STRESS      6    1",
            row(2, -1.0, -2.0, -3.0, 0.5, 0.25, 0.125),
            " -3",
            " -4  FORC        4    1",
            row(1, 0.0, 0.0, 294e3),
            " -3",
        ]
    )
    result = read_frd(text, 2)
    assert result.displacements[0] == pytest.approx([0.1, -0.2, -1.5e-3])
    assert result.stresses[1] == pytest.approx([-1.0, -2.0, -3.0, 0.5, 0.25, 0.125])
    assert result.reactions[0, 2] == pytest.approx(294e3)
    with pytest.raises(FemError, match="FORC"):
        read_frd(text.split(" -4  FORC")[0], 2)


def test_missing_ccx_raises(b1: tuple[GeometryInput, CapMesh]) -> None:
    _, mesh = b1
    with pytest.raises(FemError, match="não encontrado"):
        solve(mesh, np.zeros_like(mesh.nodes), 35.0, ccx="ccx-inexistente-blococalc")


@pytest.mark.fem
@needs_ccx
def test_b1_reactions_match_rigid_cap(b1: tuple[GeometryInput, CapMesh]) -> None:
    # B1: Nd = 980 kN, γn·(1 + D7) = 1,2 · 1,05. M1: 1/4 por estaca mais o momento de H no
    # topo em relação ao fundo, H·h/(4·600²)·x.
    geometry, mesh = b1
    factor = 1.2 * 1.05
    load = ColumnLoad(column_id="P1", n=980e3, hx=50e3)
    forces = column_nodal_forces(mesh, {"P1": geometry.columns[0]}, [load], factor)
    result = solve(mesh, forces, 35.0)
    for pile in geometry.piles:
        reaction = result.reactions[mesh.pile_nodes[pile.id], 2].sum()
        m1 = factor * (980e3 / 4 + 50e3 * 1000.0 / (4 * 600.0**2) * pile.x)
        assert reaction == pytest.approx(m1, rel=0.01)
    supported = sorted({node for node, _ in horizontal_supports(mesh)})
    assert result.reactions[supported, 0].sum() == pytest.approx(-factor * 50e3, rel=1e-6)
    assert abs(result.reactions[supported, 1].sum()) < 1e-6 * factor * 980e3
    assert float(np.min(result.displacements[:, 2])) < 0.0


@pytest.mark.fem
@needs_ccx
def test_springs_share_the_load(b1: tuple[GeometryInput, CapMesh]) -> None:
    # Carga centrada e molas iguais: cada estaca recalca N/(4·k) e leva N/4.
    geometry, mesh = b1
    load = ColumnLoad(column_id="P1", n=980e3)
    forces = column_nodal_forces(mesh, {"P1": geometry.columns[0]}, [load], 1.0)
    stiffness = {p.id: 200e3 for p in geometry.piles}
    result = solve(mesh, forces, 35.0, stiffness=stiffness)
    found = pile_reactions(mesh, result, stiffness)
    assert list(found.values()) == pytest.approx([245e3] * 4, rel=1e-3)
    head = mesh.pile_nodes["E1"]
    assert np.ptp(result.displacements[head, 2]) < 1e-9
    assert result.displacements[head[0], 2] == pytest.approx(-245e3 / 200e3, rel=1e-3)
