"""Treliça 3D (M7) montada sobre o bloco para confrontar o pilar fictício (D10, D12).

docs/02-metodos.md §4.3. Cada pilar real vira quatro nós de carga nos centros dos quadrantes da
seção (±bx/4, ±by/4), que reproduzem as origens das bielas do M5 (D6) e decompõem os momentos em
binários verticais (Gomes 2015, §5.1.3). Os planos são os do M5 no mesmo caso: topo a `y/2` e fundo
no eixo do tirante (`d`), e as forças levam γn como no M5. Com um único pilar, as trações no fundo
coincidem com as do M5; com vários, a diferença mede o efeito do pilar fictício.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np

from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.space_truss import SpaceTruss, TrussNode, optimal_truss
from blococalc.schemas import GeometryInput, LoadCase

TAN_THETA_MIN = 0.57  # NBR 6118:2023, 22.3.1
TAN_THETA_MAX = 2.0
_QUADRANTS = ((-1, -1), (1, -1), (1, 1), (-1, 1))
_LABELS = "abcd"
_TOL = 1e-6


@dataclass(frozen=True)
class CapTruss:
    truss: SpaceTruss
    tension_x: float  # Σ Ft·|cos αx| dos tirantes no plano do fundo [N]
    tension_y: float
    inclined_struts: tuple[str, ...]  # bielas até estacas fora de 0,57 ≤ tg θ ≤ 2
    # Pares de bielas que se cruzam fora dos nós; bielas horizontais de um mesmo plano formam o
    # campo de compressão do topo e não entram (Gomes 2015, §4.12, trata das bielas no volume).
    crossing_struts: tuple[tuple[str, str], ...]


def cap_truss(
    geometry: GeometryInput,
    case: LoadCase,
    gamma_n: float,
    self_weight_ratio: float,
    planes: tuple[float, float],
) -> CapTruss:
    """Treliça de menor energia (Gomes 2015, eq. 3.7) com os pilares reais do caso (D12).

    O peso próprio (D7) entra em cada pilar como fração da sua normal e as reações (M1) são
    recalculadas com ele nos pilares, para que as forças nos nós fiquem em equilíbrio.
    `planes` = (profundidade do topo, profundidade do fundo) a partir da face superior [mm].
    """
    top_depth, bottom_depth = planes
    columns = {column.id: column for column in geometry.columns}
    arm = geometry.cap.h - geometry.cap.pile_embedment  # mesmo braço de H usado em M1
    scaled = case.model_copy(
        update={
            "column_loads": tuple(
                load.model_copy(update={"n": load.n * (1.0 + self_weight_ratio)})
                for load in case.column_loads
            )
        }
    )
    nodes: list[TrussNode] = []
    for load in scaled.column_loads:
        column = columns[load.column_id]
        moment_y = load.my + load.hx * arm  # comprime o lado +x
        moment_x = load.mx + load.hy * arm  # comprime o lado +y
        for label, (sx, sy) in zip(_LABELS, _QUADRANTS, strict=True):
            force = load.n / 4.0 + sx * moment_y / column.bx + sy * moment_x / column.by
            nodes.append(
                TrussNode(
                    f"{column.id}{label}",
                    column.x + sx * column.bx / 4.0,
                    column.y + sy * column.by / 4.0,
                    -top_depth,
                    fz=-gamma_n * force,
                )
            )
    for top in [n for n in nodes if n.fz > 0.0]:  # nó tracionado: tirante vertical até o fundo
        nodes.append(TrussNode(f"{top.id}_fundo", top.x, top.y, -bottom_depth))
    for reaction, pile in zip(rigid_cap_reactions(geometry, scaled), geometry.piles, strict=True):
        nodes.append(TrussNode(pile.id, pile.x, pile.y, -bottom_depth, fz=gamma_n * reaction.force))
        if reaction.force < 0.0:  # estaca tracionada: tirante vertical até o topo
            nodes.append(TrussNode(f"{pile.id}_topo", pile.x, pile.y, -top_depth))

    truss = optimal_truss(nodes)
    depth_of = {node.id: node.z for node in nodes}
    pile_ids = {pile.id for pile in geometry.piles}
    bottom_ties = [
        m
        for m in truss.members
        if m.force > 0.0 and depth_of[m.start] == depth_of[m.end] == -bottom_depth
    ]
    struts = [m for m in truss.members if m.force < 0.0]
    inclined = []
    for strut in struts:
        if (strut.start in pile_ids) == (strut.end in pile_ids):
            continue
        dx, dy, dz = strut.direction
        horizontal = math.hypot(dx, dy)
        tan_theta = abs(dz) / horizontal if horizontal > _TOL else math.inf
        if not TAN_THETA_MIN <= tan_theta <= TAN_THETA_MAX:
            inclined.append(f"{strut.start}-{strut.end}")
    coordinates = {node.id: np.array((node.x, node.y, node.z)) for node in nodes}
    crossings = tuple(
        (f"{a.start}-{a.end}", f"{b.start}-{b.end}")
        for a, b in itertools.combinations(struts, 2)
        if not {a.start, a.end} & {b.start, b.end}
        and not (abs(a.direction[2]) <= _TOL and abs(b.direction[2]) <= _TOL)
        and _segments_cross(
            coordinates[a.start], coordinates[a.end], coordinates[b.start], coordinates[b.end]
        )
    )
    return CapTruss(
        truss=truss,
        tension_x=sum(m.force * abs(m.direction[0]) for m in bottom_ties),
        tension_y=sum(m.force * abs(m.direction[1]) for m in bottom_ties),
        inclined_struts=tuple(inclined),
        crossing_struts=crossings,
    )


def _segments_cross(p1: np.ndarray, p2: np.ndarray, q1: np.ndarray, q2: np.ndarray) -> bool:
    """Segmentos que se tocam fora das extremidades (Gomes 2015, §4.12)."""
    u, v, w = p2 - p1, q2 - q1, p1 - q1
    a, b, c = float(u @ u), float(u @ v), float(v @ v)
    d, e = float(u @ w), float(v @ w)
    denominator = a * c - b * b
    if denominator <= _TOL * a * c:  # paralelos: bielas sobrepostas já foram excluídas
        return False
    s = (b * e - c * d) / denominator
    t = (a * e - b * d) / denominator
    if not (_TOL < s < 1.0 - _TOL and _TOL < t < 1.0 - _TOL):
        return False
    gap = (p1 + s * u) - (q1 + t * v)
    return float(np.linalg.norm(gap)) <= _TOL * math.sqrt(max(a, c))
