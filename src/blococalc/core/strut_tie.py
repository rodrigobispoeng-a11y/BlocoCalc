"""Modelo de bielas e tirantes de Santos/Stucchi para bloco rígido (método M5, padrão).

Especificação: docs/02-metodos.md §4.1 (Santos, Carvalho e Stucchi, 2019, eq. 19 a 21), com as
decisões D4 (pilar retangular com as dimensões reais), D6 (profundidade `y` do nó CCC pelo
equilíbrio horizontal do nó sob fcd1) e D13 (face do nó espraiada a 45°; grade de N estacas).

Premissas do modelo, registradas na trilha de auditoria pelo chamador:
- v1: um pilar, 2 a 4 estacas comprimidas, todas no contorno do estaqueamento;
- a biela de cada estaca parte do centroide da parte da seção do pilar voltada para ela
  (generaliza ac/4 de Blévot para 2 e 4 estacas e ≈0,3·ac para 3 estacas);
- o nó CCC tem profundidade `y`; o braço de alavanca é z = d − y/2;
- d = h − embutimento − d′, com d′ = altura do eixo do tirante acima da cabeça da estaca;
- tirantes ligam estacas vizinhas no contorno; a força em cada um é a maior entre as duas
  extremidades (NBR 6118:2023, 22.7.4.1.1: armadura concentrada nas faixas sobre as estacas).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from blococalc.schemas import Column, GeometryInput, Pile, PileReaction, PileShape

_GRID = 100
_MAX_ITER = 200
_Y_TOL_MM = 1e-6


class UnsupportedLayoutError(ValueError):
    """Estaqueamento fora do escopo do modelo v1."""


class NodeStrengths(Protocol):
    """Resistências de cálculo usadas pelo modelo [MPa] (ver `standards.strength`)."""

    @property
    def fcd1(self) -> float: ...

    @property
    def fyd(self) -> float: ...


@dataclass(frozen=True)
class Strut:
    pile_id: str
    force_d: float  # reação de cálculo com γn [N]
    origin_x: float
    origin_y: float
    l_proj: float  # projeção horizontal da biela [mm]
    tan_theta: float
    sigma_column_node: float  # σcd,c [MPa], eq. (20)
    sigma_pile_node: float  # σcd,p [MPa], eq. (19)


@dataclass(frozen=True)
class Tie:
    pile_a: str
    pile_b: str
    force_d: float  # [N]
    area_required: float  # As = Ftd/fyd [mm²], NBR 6118:2023, 22.3.3
    dir_x: float  # cosseno diretor em planta
    dir_y: float


@dataclass(frozen=True)
class StrutTieModel:
    d: float
    y: float
    z: float
    struts: tuple[Strut, ...]
    ties: tuple[Tie, ...]


def santos_stucchi(
    geometry: GeometryInput,
    reactions: Sequence[PileReaction],
    strengths: NodeStrengths,
    gamma_n: float,
    tie_height: float,
) -> StrutTieModel:
    """Resolve o modelo para um caso de carga. `reactions` vem de `rigid_cap_reactions`."""
    if len(geometry.columns) != 1:
        raise UnsupportedLayoutError("Modelo v1 aceita um único pilar por bloco")
    column = geometry.columns[0]
    piles = _hull_order(geometry.piles, column)
    by_id = {r.pile_id: gamma_n * r.force for r in reactions}
    if any(by_id[p.id] <= 0.0 for p in piles):
        raise UnsupportedLayoutError("Estaca tracionada: fora do escopo do modelo v1")

    d = geometry.cap.h - geometry.cap.pile_embedment - tie_height
    origins = _strut_origins(column, piles)
    l_proj = [math.hypot(p.x - ox, p.y - oy) for p, (ox, oy, _) in zip(piles, origins, strict=True)]
    forces = [by_id[p.id] for p in piles]

    y = 0.0
    for _ in range(_MAX_ITER):
        z = d - y / 2.0
        if z <= 0.0:
            raise UnsupportedLayoutError("Nó CCC mais profundo que 2·d: aumente a altura do bloco")
        horizontal = [
            (f / z * (p.x - ox), f / z * (p.y - oy))
            for p, (ox, oy, _), f in zip(piles, origins, forces, strict=True)
        ]
        new_y = _node_depth(horizontal, column, strengths.fcd1)
        if abs(new_y - y) < _Y_TOL_MM:
            y = new_y
            break
        y = new_y
    else:  # pragma: no cover - a iteração é uma contração para blocos usuais
        raise ArithmeticError("Profundidade do nó CCC não convergiu")
    z = d - y / 2.0

    area_column = (column.bx + 2.0 * y) * (column.by + 2.0 * y)
    struts = []
    for pile, (ox, oy, share), force, lp in zip(piles, origins, forces, l_proj, strict=True):
        tan_t = z / lp
        sin2 = tan_t * tan_t / (1.0 + tan_t * tan_t)
        struts.append(
            Strut(
                pile_id=pile.id,
                force_d=force,
                origin_x=ox,
                origin_y=oy,
                l_proj=lp,
                tan_theta=tan_t,
                sigma_column_node=force / (area_column * share * sin2),
                sigma_pile_node=force / (_pile_spread_area(pile, tie_height) * sin2),
            )
        )
    ties = _ties(piles, struts, z, strengths.fyd)
    return StrutTieModel(d=d, y=y, z=z, struts=tuple(struts), ties=ties)


def _hull_order(piles: Sequence[Pile], column: Column) -> list[Pile]:
    if not 2 <= len(piles) <= 4:
        raise UnsupportedLayoutError("Modelo v1 aceita blocos de 2, 3 ou 4 estacas")
    ordered = sorted(piles, key=lambda p: math.atan2(p.y - column.y, p.x - column.x))
    if len(ordered) == 4:
        for i, p in enumerate(ordered):  # estaca interna ao triângulo das outras três
            a, b, c = (ordered[(i + k) % 4] for k in (1, 2, 3))
            if _inside_triangle(p, a, b, c):
                raise UnsupportedLayoutError(f"Estaca {p.id} não está no contorno")
    return ordered


def _inside_triangle(p: Pile, a: Pile, b: Pile, c: Pile) -> bool:
    def cross(o: Pile, u: Pile, v: Pile) -> float:
        return (u.x - o.x) * (v.y - o.y) - (u.y - o.y) * (v.x - o.x)

    signs = (cross(a, b, p), cross(b, c, p), cross(c, a, p))
    return all(s > 0 for s in signs) or all(s < 0 for s in signs)


def _strut_origins(column: Column, piles: Sequence[Pile]) -> list[tuple[float, float, float]]:
    """Centroide e fração da área do pilar voltada para cada estaca (grade de _GRID²)."""
    dirs = [_unit(p.x - column.x, p.y - column.y) for p in piles]
    sums: list[list[float]] = [[0.0, 0.0, 0.0] for _ in piles]
    for i in range(_GRID):
        u = (i + 0.5) / _GRID - 0.5
        for j in range(_GRID):
            v = (j + 0.5) / _GRID - 0.5
            px, py = u * column.bx, v * column.by
            k = max(range(len(piles)), key=lambda n: dirs[n][0] * px + dirs[n][1] * py)
            sums[k][0] += px
            sums[k][1] += py
            sums[k][2] += 1
    if any(count == 0 for _, _, count in sums):
        raise UnsupportedLayoutError("Duas estacas na mesma direção a partir do pilar")
    total = _GRID * _GRID
    return [(column.x + sx / c, column.y + sy / c, c / total) for sx, sy, c in sums]


def _node_depth(horizontal: Sequence[tuple[float, float]], column: Column, fcd1: float) -> float:
    """D6 e D13: y tal que a compressão horizontal do nó, em cada direção, atue sob fcd1.

    `horizontal` são as componentes em planta das bielas, H = R·lproj/z, em direção à estaca.
    Em x, a compressão atravessa uma face de largura by + 2y; em y, de largura bx + 2y
    (espraiamento a 45°, como a área ampliada da eq. 20). Para cada direção, C = fcd1·(b + 2y)·y
    dá y = (−b + √(b² + 8C/fcd1))/4.
    """
    pos_x = sum(max(hx, 0.0) for hx, _ in horizontal)
    neg_x = sum(max(-hx, 0.0) for hx, _ in horizontal)
    pos_y = sum(max(hy, 0.0) for _, hy in horizontal)
    neg_y = sum(max(-hy, 0.0) for _, hy in horizontal)

    def depth(compression: float, width: float) -> float:
        return (math.sqrt(width * width + 8.0 * compression / fcd1) - width) / 4.0

    return max(depth(max(pos_x, neg_x), column.by), depth(max(pos_y, neg_y), column.bx))


def _pile_spread_area(pile: Pile, tie_height: float) -> float:
    """Ap,sp: π(φ + 2d′)²/4 (circular) ou (a + 2d′)² (quadrada) [mm²]."""
    size = pile.size + 2.0 * tie_height
    return math.pi * size * size / 4.0 if pile.shape is PileShape.CIRCULAR else size * size


def _ties(piles: Sequence[Pile], struts: Sequence[Strut], z: float, fyd: float) -> tuple[Tie, ...]:
    n = len(piles)
    edges = [(0, 1)] if n == 2 else [(i, (i + 1) % n) for i in range(n)]
    edge_force = {e: 0.0 for e in edges}
    for i, (pile, strut) in enumerate(zip(piles, struts, strict=True)):
        hx = strut.force_d / z * (pile.x - strut.origin_x)
        hy = strut.force_d / z * (pile.y - strut.origin_y)
        mine = [e for e in edges if i in e]
        others = [piles[e[0] + e[1] - i] for e in mine]
        vecs = [_unit(o.x - pile.x, o.y - pile.y) for o in others]
        if len(mine) == 1:
            tensions = [-(hx * vecs[0][0] + hy * vecs[0][1])]
        else:
            (ax, ay), (bx, by) = vecs
            det = ax * by - ay * bx
            tensions = [(-hx * by + hy * bx) / det, (-ax * hy + ay * hx) / det]
        for e, t in zip(mine, tensions, strict=True):
            if t < 0.0:
                raise UnsupportedLayoutError("Tirante comprimido: geometria fora do escopo do v1")
            edge_force[e] = max(edge_force[e], t)
    ties = []
    for (a, b), force in edge_force.items():
        ux, uy = _unit(piles[b].x - piles[a].x, piles[b].y - piles[a].y)
        ties.append(Tie(piles[a].id, piles[b].id, force, force / fyd, ux, uy))
    return tuple(ties)


def _unit(x: float, y: float) -> tuple[float, float]:
    norm = math.hypot(x, y)
    return (x / norm, y / norm)
