"""Treliça espacial de menor energia (M7, D12; docs/02-metodos.md §4.3)."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from blococalc.core.space_truss import TrussNode, candidate_members, optimal_truss

KN = 1e3


def gomes_b5() -> list[TrussNode]:
    """Gomes (2015) §5.1: binário de 320 e 2820 kN, estacas a ±750 mm, braço de 650 mm."""
    heavy, light = 3140.0 / 4 + 500.0 / 3, 3140.0 / 4 - 500.0 / 3
    z = -650.0
    return [
        TrussNode("N1", -200.0, 0.0, 0.0, fz=-320 * KN),
        TrussNode("N2", 200.0, 0.0, 0.0, fz=-2820 * KN),
        TrussNode("E1", -750.0, -750.0, z, fz=light * KN),
        TrussNode("E3", -750.0, 750.0, z, fz=light * KN),
        TrussNode("E2", 750.0, -750.0, z, fz=heavy * KN),
        TrussNode("E4", 750.0, 750.0, z, fz=heavy * KN),
    ]


def forces(nodes: list[TrussNode]) -> dict[frozenset[str], float]:
    return {frozenset((m.start, m.end)): m.force for m in optimal_truss(nodes).members}


@pytest.mark.golden
def test_gomes_b5_matches_table_5_2() -> None:
    # Tab. 5.2 recalculada com as reações exatas (docs/02-metodos.md §4.3).
    result = forces(gomes_b5())
    expected = {
        ("N1", "E1"): -279.3, ("N1", "E3"): -279.3, ("N2", "E1"): -968.7,
        ("N2", "E3"): -968.7, ("N2", "E2"): -1661.3, ("N2", "E4"): -1661.3,
        ("N1", "N2"): -270.8, ("E1", "E3"): 713.5, ("E2", "E4"): 1098.1,
        ("E1", "E2"): 805.3, ("E3", "E4"): 805.3,
    }  # fmt: skip
    assert set(result) == {frozenset(pair) for pair in expected}
    for pair, value in expected.items():
        assert result[frozenset(pair)] == pytest.approx(value * KN, abs=0.1 * KN)


@pytest.mark.golden
def test_tie_energy_equals_the_best_isostatic_truss() -> None:
    # Força bruta de Gomes (cap. 4): 3n − 6 = 12 barras entre as 15 possíveis.
    nodes = gomes_b5()
    points = np.array([(n.x, n.y, n.z) for n in nodes])
    loads = np.array([(n.fx, n.fy, n.fz) for n in nodes]).reshape(-1)
    pairs = candidate_members(nodes)
    best = np.inf
    for subset in itertools.combinations(range(len(pairs)), 3 * len(nodes) - 6):
        matrix = np.zeros((3 * len(nodes), len(subset)))
        lengths, diagonal = [], []
        for j, k in enumerate(subset):
            a, b = pairs[k]
            segment = points[b] - points[a]
            length = float(np.linalg.norm(segment))
            matrix[3 * a : 3 * a + 3, j] += segment / length
            matrix[3 * b : 3 * b + 3, j] -= segment / length
            lengths.append(length)
            diagonal.append(segment[2] != 0.0 and np.hypot(segment[0], segment[1]) > 0.0)
        if np.linalg.matrix_rank(matrix) < len(subset):
            continue
        solution = np.linalg.lstsq(matrix, -loads, rcond=None)[0]
        if np.abs(matrix @ solution + loads).max() > 1e-3:
            continue
        if any(f > 1e-6 and d for f, d in zip(solution, diagonal, strict=True)):
            continue  # tirante diagonal entre planos (Gomes §4.14)
        best = min(best, sum(f * L for f, L in zip(solution, lengths, strict=True) if f > 0))
    assert optimal_truss(nodes).tie_energy == pytest.approx(best, rel=1e-6)
    assert best == pytest.approx(1.5 * (713.5 + 1098.1 + 2 * 805.3) * 1e6, rel=1e-4)


def test_two_columns_are_in_equilibrium_and_ties_stay_in_planes() -> None:
    # Pilares de 500 e 300 kN em x = ±300 sobre 4 estacas (mesmo caso de test_analysis).
    reactions = {"E1": 225.0, "E2": 175.0, "E3": 175.0, "E4": 225.0}
    piles = {"E1": (-600, -600), "E2": (600, -600), "E3": (600, 600), "E4": (-600, 600)}
    nodes = [
        TrussNode("P1", -300.0, 0.0, 0.0, fz=-500 * KN),
        TrussNode("P2", 300.0, 0.0, 0.0, fz=-300 * KN),
        *(TrussNode(k, x, y, -700.0, fz=reactions[k] * KN) for k, (x, y) in piles.items()),
    ]
    truss = optimal_truss(nodes)
    by_id = {n.id: n for n in nodes}
    residual = {n.id: np.array([n.fx, n.fy, n.fz]) for n in nodes}
    for member in truss.members:
        pull = member.force * np.array(member.direction)
        residual[member.start] += pull
        residual[member.end] -= pull
        if member.force > 0:
            assert by_id[member.start].z == by_id[member.end].z
    assert max(np.abs(r).max() for r in residual.values()) < 1.0  # N
    assert truss.tie_energy > 0


def test_member_through_a_node_is_replaced_by_its_parts() -> None:
    nodes = [TrussNode(f"N{i}", float(x), 0.0, 0.0) for i, x in enumerate((0, 500, 1000))]
    nodes.append(TrussNode("N3", 0.0, 500.0, -500.0))
    pairs = {(nodes[a].id, nodes[b].id) for a, b in candidate_members(nodes)}
    assert ("N0", "N2") not in pairs
    assert {("N0", "N1"), ("N1", "N2")} <= pairs


def test_unbalanced_loads_are_rejected() -> None:
    nodes = gomes_b5()
    nodes[0] = TrussNode("N1", -200.0, 0.0, 0.0, fz=-400 * KN)
    with pytest.raises(ValueError, match="equilíbrio"):
        optimal_truss(nodes)


def test_coincident_nodes_are_rejected() -> None:
    nodes = gomes_b5()
    nodes.append(TrussNode("X", -200.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="coincidentes"):
        optimal_truss(nodes)


def test_degenerate_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="4 nós"):
        optimal_truss(gomes_b5()[:3])
    with pytest.raises(ValueError, match="nenhuma força"):
        optimal_truss([TrussNode(n.id, n.x, n.y, n.z) for n in gomes_b5()])
    # Todos os nós no mesmo plano: cargas verticais não têm caminho de barras.
    flat = [TrussNode(n.id, n.x, n.y, 0.0, fz=n.fz) for n in gomes_b5()]
    with pytest.raises(ValueError, match="sem solução"):
        optimal_truss(flat)
