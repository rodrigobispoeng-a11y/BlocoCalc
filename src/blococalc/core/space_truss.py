"""Treliça espacial de bielas e tirantes de menor energia (M7, decisão D12).

docs/02-metodos.md §4.3. O critério é o de Gomes (2015), eq. 3.7: mínimo de `Σ Ft·lt` sobre os
tirantes. Em vez de enumerar as treliças isostáticas (Gomes, cap. 4), o ótimo é obtido por
programa linear sobre todas as ligações possíveis entre os nós (ground structure; Dorn, Gomory e
Greenberg, 1964), com as mesmas restrições construtivas da fonte:

- barras entre os planos (não verticais) só podem ser bielas (Gomes §4.14);
- barra que passa por outro nó é descartada, ficando os trechos menores (Gomes §4.6).

Desempates (D12): tirante horizontal fora das direções x e y pesa 0,1 % a mais, e as bielas pesam
0,01 % de um tirante, para o ótimo impresso ser único e construtivo. Unidades N e mm; tração
positiva.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

OFF_AXIS_TIE_PENALTY = 1e-3
STRUT_WEIGHT = 1e-4
_GEOMETRY_TOL = 1e-6  # mm, relativo ao maior comprimento
_EQUILIBRIUM_TOL = 1e-6  # relativo à maior força aplicada


@dataclass(frozen=True)
class TrussNode:
    """Nó com coordenadas [mm] e força externa aplicada [N] (z positivo para cima)."""

    id: str
    x: float
    y: float
    z: float
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0


@dataclass(frozen=True)
class TrussMember:
    start: str
    end: str
    length: float
    force: float  # tração positiva [N]
    direction: tuple[float, float, float]  # vetor unitário de start para end


@dataclass(frozen=True)
class SpaceTruss:
    members: tuple[TrussMember, ...]  # só as barras com força
    tie_energy: float  # Σ Ft·lt dos tirantes [N·mm], sem os pesos de desempate


def candidate_members(nodes: Sequence[TrussNode]) -> list[tuple[int, int]]:
    """Ligações possíveis: todos os pares, menos os que passam por um terceiro nó (Gomes §4.6)."""
    points = np.array([(n.x, n.y, n.z) for n in nodes], dtype=float)
    scale = float(np.ptp(points, axis=0).max()) or 1.0
    pairs = []
    for a, b in itertools.combinations(range(len(nodes)), 2):
        segment = points[b] - points[a]
        length = float(np.linalg.norm(segment))
        if length <= _GEOMETRY_TOL * scale:
            raise ValueError(f"nós coincidentes: {nodes[a].id} e {nodes[b].id}")
        blocked = False
        for c in range(len(nodes)):
            if c in (a, b):
                continue
            offset = points[c] - points[a]
            t = float(offset @ segment) / (length * length)
            distance = float(np.linalg.norm(offset - t * segment))
            if 0.0 < t < 1.0 and distance <= _GEOMETRY_TOL * scale:
                blocked = True
                break
        if not blocked:
            pairs.append((a, b))
    return pairs


def optimal_truss(nodes: Sequence[TrussNode]) -> SpaceTruss:
    """Treliça de menor `Σ Ft·lt` que equilibra as forças dos nós (Gomes 2015, eq. 3.7; D12).

    As forças externas (cargas dos pilares e reações das estacas) já devem estar em equilíbrio.
    """
    if len(nodes) < 4:
        raise ValueError("a treliça espacial precisa de ao menos 4 nós")
    points = np.array([(n.x, n.y, n.z) for n in nodes], dtype=float)
    loads = np.array([(n.fx, n.fy, n.fz) for n in nodes], dtype=float)
    _check_equilibrium(points, loads)

    pairs = candidate_members(nodes)
    length_scale = float(np.ptp(points, axis=0).max())
    force_scale = float(np.abs(loads).max())
    count = len(pairs)
    matrix = np.zeros((3 * len(nodes), count))
    lengths = np.zeros(count)
    directions = np.zeros((count, 3))
    tie_weight = np.zeros(count)
    tie_allowed = np.zeros(count, dtype=bool)
    for j, (a, b) in enumerate(pairs):
        segment = points[b] - points[a]
        lengths[j] = float(np.linalg.norm(segment))
        directions[j] = segment / lengths[j]
        matrix[3 * a : 3 * a + 3, j] += directions[j]
        matrix[3 * b : 3 * b + 3, j] -= directions[j]
        horizontal = abs(directions[j][2]) <= _GEOMETRY_TOL
        vertical = math.hypot(directions[j][0], directions[j][1]) <= _GEOMETRY_TOL
        tie_allowed[j] = horizontal or vertical
        on_axis = min(abs(directions[j][0]), abs(directions[j][1])) <= _GEOMETRY_TOL
        tie_weight[j] = 1.0 if (vertical or on_axis) else 1.0 + OFF_AXIS_TIE_PENALTY

    # Variáveis: f = t − s, com t (tração) e s (compressão) ≥ 0, em unidades adimensionais.
    relative = lengths / length_scale
    cost = np.concatenate([relative * tie_weight, relative * STRUT_WEIGHT])
    bounds = [(0.0, None if allowed else 0.0) for allowed in tie_allowed] + [(0.0, None)] * count
    solution = linprog(
        cost,
        A_eq=np.hstack([matrix, -matrix]),
        b_eq=-loads.reshape(-1) / force_scale,
        bounds=bounds,
        method="highs",
    )
    if solution.status != 0:
        raise ValueError(f"treliça sem solução de equilíbrio: {solution.message}")
    forces = (solution.x[:count] - solution.x[count:]) * force_scale

    cutoff = _EQUILIBRIUM_TOL * force_scale
    members = tuple(
        TrussMember(
            start=nodes[a].id,
            end=nodes[b].id,
            length=float(lengths[j]),
            force=float(forces[j]),
            direction=(float(directions[j][0]), float(directions[j][1]), float(directions[j][2])),
        )
        for j, (a, b) in enumerate(pairs)
        if abs(forces[j]) > cutoff
    )
    energy = sum(m.force * m.length for m in members if m.force > 0.0)
    return SpaceTruss(members=members, tie_energy=energy)


def _check_equilibrium(points: np.ndarray, loads: np.ndarray) -> None:
    scale = float(np.abs(loads).max())
    if scale == 0.0:
        raise ValueError("nenhuma força aplicada nos nós")
    length = float(np.ptp(points, axis=0).max()) or 1.0
    resultant = loads.sum(axis=0)
    moment = np.cross(points, loads).sum(axis=0)
    if np.abs(resultant).max() > _EQUILIBRIUM_TOL * scale * len(points) or (
        np.abs(moment).max() > _EQUILIBRIUM_TOL * scale * length * len(points)
    ):
        raise ValueError("as forças nos nós não estão em equilíbrio")
