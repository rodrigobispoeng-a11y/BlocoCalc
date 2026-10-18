"""Modelo de bielas e tirantes de Santos/Stucchi para bloco rígido (método M5, padrão).

Especificação: docs/02-metodos.md §4.1 (Santos, Carvalho e Stucchi, 2019, eq. 19 a 21), com as
decisões D4 (pilar retangular com as dimensões reais), D6 (profundidade `y` do nó CCC pelo
equilíbrio horizontal do nó sob fcd1), D13 (face do nó espraiada a 45°; grade de N estacas) e
D15 (estacas fora de grade, docs/02-metodos.md §4.6) e D17 (fileiras desencontradas, §4.8).

Premissas do modelo, registradas na trilha de auditoria pelo chamador:
- um pilar e estacas comprimidas: 2 a 4 no contorno do estaqueamento, 5 ou mais em grade
  retangular completa nx × ny (D13, docs/02-metodos.md §4.4), ou contorno convexo com estacas
  internas só sob o pilar (D15, §4.6);
- a biela de cada estaca parte do centroide da parte da seção do pilar voltada para ela
  (generaliza ac/4 de Blévot para 2 e 4 estacas e ≈0,3·ac para 3 estacas); na grade, o pilar
  é dividido em nx × ny partes iguais;
- o nó CCC tem profundidade `y`; o braço de alavanca é z = d − y/2;
- d = h − embutimento − d′, com d′ = altura do eixo do tirante acima da cabeça da estaca;
- tirantes ligam estacas vizinhas no contorno; a força em cada um é a maior entre as duas
  extremidades (NBR 6118:2023, 22.7.4.1.1: armadura concentrada nas faixas sobre as estacas);
  na grade, há um tirante por linha e por coluna de estacas, com trechos entre estacas vizinhas
  e força em cada trecho pelo equilíbrio dos nós de um lado ou do outro (o maior);
- fora de grade (D15), estaca interna tem biela vertical a partir do próprio eixo; metade do
  empuxo de cada estaca do contorno vai para um tirante radial (até a estaca interna ou a estaca
  oposta, quando houver) e o resto para o anel do contorno;
- em fileiras desencontradas (D17), o pilar é dividido em isoáreas (faixa por fileira e parte por
  estaca, proporcionais às reações) deslocadas da excentricidade da carga, e os tirantes formam a
  rede triangulada entre estacas vizinhas, com as forças pelo mínimo de Σ F·l (critério da D12).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy.optimize import linprog, minimize
from scipy.spatial import Delaunay

from blococalc.core.space_truss import OFF_AXIS_TIE_PENALTY
from blococalc.schemas import Column, GeometryInput, Pile, PileReaction, PileShape

_GRID = 100
_LEVEL_TOL_MM = 1e-3  # coordenadas que diferem menos que isso estão na mesma linha da grade
_MAX_ITER = 200
_Y_TOL_MM = 1e-6
_RADIAL_SHARE = 0.5  # D15: metade do empuxo no tirante radial (Bavaresco 2016, §5)
INTERIOR_PILE_FACTOR = 1.4  # D15: folga de 40 % no nó da estaca interna (Bavaresco 2016, §5)
EQUILIBRIUM_WARNING_RATIO = 0.01  # D17: correção dos empuxos acima disso vira aviso
_FORCE_TOL = 1e-4  # D17: tirante com menos que isso do maior empuxo é descartado


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
class _PileGrid:
    nx: int
    ny: int
    cell: dict[str, tuple[int, int]]  # (coluna, linha) de cada estaca, a partir de x e y mínimos


@dataclass(frozen=True)
class StrutTieModel:
    d: float
    y: float
    z: float
    struts: tuple[Strut, ...]
    ties: tuple[Tie, ...]
    interior_piles: tuple[str, ...] = ()  # D15: estacas internas sob o pilar
    staggered: bool = False  # D17: fileiras desencontradas
    equilibrium_correction: float = 0.0  # D17: correção dos empuxos / maior empuxo


def santos_stucchi(  # noqa: PLR0913 - entradas do modelo e d′ do nó da estaca (D20)
    geometry: GeometryInput,
    reactions: Sequence[PileReaction],
    strengths: NodeStrengths,
    gamma_n: float,
    tie_height: float,
    *,
    pile_node_height: float | None = None,
) -> StrutTieModel:
    """Resolve o modelo para um caso de carga. `reactions` vem de `rigid_cap_reactions`.

    `pile_node_height` é o d′ da área ampliada no nó da estaca; sem ele, vale `tie_height`.
    A D20 refaz o modelo para cada camada de tirantes e mantém o nó da estaca na 1ª camada.
    """
    if len(geometry.columns) != 1:
        raise UnsupportedLayoutError("Modelo v1 aceita um único pilar por bloco")
    column = geometry.columns[0]
    by_id = {r.pile_id: gamma_n * r.force for r in reactions}
    layout = _layout(geometry.piles, column, by_id)
    piles, origins, interior = layout.piles, layout.origins, layout.interior
    if any(by_id[p.id] <= 0.0 for p in piles):
        raise UnsupportedLayoutError("Estaca tracionada: fora do escopo do modelo v1")

    d = geometry.cap.h - geometry.cap.pile_embedment - tie_height
    node_height = tie_height if pile_node_height is None else pile_node_height
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
    inner_ids = {p.id for p in interior}
    struts = []
    for pile, (ox, oy, share), force, lp in zip(piles, origins, forces, l_proj, strict=True):
        # Estaca sob o centroide da sua parte do pilar (grade): biela vertical, sen²θ = 1.
        tan_t = z / lp if lp > _Y_TOL_MM else math.inf
        sin2 = 1.0 if math.isinf(tan_t) else tan_t * tan_t / (1.0 + tan_t * tan_t)
        struts.append(
            Strut(
                pile_id=pile.id,
                force_d=force,
                origin_x=ox,
                origin_y=oy,
                l_proj=lp,
                tan_theta=tan_t,
                sigma_column_node=force / (area_column * share * sin2),
                sigma_pile_node=force
                * (INTERIOR_PILE_FACTOR if pile.id in inner_ids else 1.0)
                / (_pile_spread_area(pile, node_height) * sin2),
            )
        )
    correction = 0.0
    if layout.grid is not None:
        ties = _grid_ties(piles, struts, z, strengths.fyd, layout.grid)
    elif layout.rows:
        pushes = [_push(p, s, z) for p, s in zip(piles, struts, strict=True)]
        ties, correction = _network_ties(piles, pushes, strengths.fyd)
    elif layout.polygon:
        pushes = [_push(p, s, z) for p, s in zip(layout.outline, struts, strict=False)]
        ties = _polygon_ties(layout.outline, interior, pushes, strengths.fyd, column)
    else:
        ties = _ties(piles, struts, z, strengths.fyd)
    return StrutTieModel(
        d=d,
        y=y,
        z=z,
        struts=tuple(struts),
        ties=ties,
        interior_piles=tuple(p.id for p in interior),
        staggered=layout.rows,
        equilibrium_correction=correction,
    )


@dataclass(frozen=True)
class _Layout:
    piles: list[Pile]  # contorno primeiro, internas depois (D15)
    origins: list[tuple[float, float, float]]  # origem da biela e fração da área do pilar
    grid: _PileGrid | None = None
    outline: tuple[Pile, ...] = ()
    interior: tuple[Pile, ...] = ()
    rows: bool = False  # D17: fileiras desencontradas

    @property
    def polygon(self) -> bool:
        return bool(self.outline)


def _layout(piles: Sequence[Pile], column: Column, reactions: dict[str, float]) -> _Layout:
    """Grade (D13), contorno de 2 a 4 estacas (§4.1) ou contorno com estacas internas (D15)."""
    grid = _grid_or_none(piles) if len(piles) > 4 else None
    if grid is not None:
        return _Layout(list(piles), _grid_origins(column, piles, grid), grid=grid)
    try:
        outline, interior = _outline(piles, column)
    except UnsupportedLayoutError:
        rows = _pile_rows(piles)
        if rows is None:
            raise
        return _Layout(list(piles), _row_origins(column, piles, rows, reactions), rows=True)
    if not interior and len(piles) <= 4:
        ordered = _hull_order(piles, column)
        return _Layout(ordered, _strut_origins(column, ordered))
    # D15: a estaca interna fica com a parte do pilar proporcional à sua reação.
    total = sum(reactions[p.id] for p in piles)
    inner = sum(reactions[p.id] for p in interior) / total
    origins = [(ox, oy, f * (1.0 - inner)) for ox, oy, f in _strut_origins(column, outline)]
    origins += [(p.x, p.y, reactions[p.id] / total) for p in interior]
    return _Layout([*outline, *interior], origins, outline=tuple(outline), interior=tuple(interior))


def _hull_order(piles: Sequence[Pile], column: Column) -> list[Pile]:
    if len(piles) < 2:
        raise UnsupportedLayoutError("O modelo precisa de ao menos 2 estacas")
    return sorted(piles, key=lambda p: math.atan2(p.y - column.y, p.x - column.x))


def _grid_or_none(piles: Sequence[Pile]) -> _PileGrid | None:
    """Grade da D13 ou None, para o estaqueamento seguir a D15."""
    try:
        return _pile_grid(piles)
    except UnsupportedLayoutError:
        return None


def _outline(piles: Sequence[Pile], column: Column) -> tuple[list[Pile], list[Pile]]:
    """Estacas do contorno convexo (em ordem angular) e estacas internas (D15).

    Estaca sobre um lado do contorno, entre dois vértices, não tem tirante que a equilibre no anel
    e fica fora do escopo; estaca interna precisa estar sob o pilar (biela vertical).
    """
    hull = _convex_hull(piles)
    on_hull = {p.id for p in hull}
    interior = [p for p in piles if p.id not in on_hull]
    for p in interior:
        for a, b in zip(hull, [*hull[1:], hull[0]], strict=True):
            if abs(_cross(a, b, p)) <= _LEVEL_TOL_MM * math.dist((a.x, a.y), (b.x, b.y)):
                raise UnsupportedLayoutError(
                    f"Estacas alinhadas no contorno ({a.id}, {p.id}, {b.id}): fora do escopo (D15)"
                )
        if abs(p.x - column.x) > column.bx / 2.0 or abs(p.y - column.y) > column.by / 2.0:
            raise UnsupportedLayoutError(
                f"Estaca interna {p.id} precisa estar sob o pilar (D15, docs/02-metodos.md §4.6)"
            )
    ordered = sorted(hull, key=lambda p: math.atan2(p.y - column.y, p.x - column.x))
    return ordered, interior


def _convex_hull(piles: Sequence[Pile]) -> list[Pile]:
    """Vértices do contorno convexo (cadeia monótona), sem pontos alinhados nos lados."""
    pts = sorted(piles, key=lambda p: (p.x, p.y))
    if len(pts) < 3:
        return pts

    def chain(points: Sequence[Pile]) -> list[Pile]:
        out: list[Pile] = []
        for p in points:
            while len(out) >= 2 and _cross(out[-2], out[-1], p) <= _LEVEL_TOL_MM:
                out.pop()
            out.append(p)
        return out[:-1]

    return chain(pts) + chain(pts[::-1])


def _cross(o: Pile, u: Pile, v: Pile) -> float:
    return (u.x - o.x) * (v.y - o.y) - (u.y - o.y) * (v.x - o.x)


def _pile_grid(piles: Sequence[Pile]) -> _PileGrid:
    """Grade retangular completa nx × ny alinhada com x e y (D13)."""
    xs = _levels([p.x for p in piles])
    ys = _levels([p.y for p in piles])
    cell = {p.id: (_level_index(xs, p.x), _level_index(ys, p.y)) for p in piles}
    if len(xs) * len(ys) != len(piles) or len(set(cell.values())) != len(piles):
        raise UnsupportedLayoutError(
            "Com mais de 4 estacas, o modelo aceita só grade retangular completa nx × ny (D13)"
        )
    return _PileGrid(nx=len(xs), ny=len(ys), cell=cell)


def _levels(values: Sequence[float]) -> list[float]:
    levels: list[float] = []
    for value in sorted(values):
        if not levels or value - levels[-1] > _LEVEL_TOL_MM:
            levels.append(value)
    return levels


def _level_index(levels: Sequence[float], value: float) -> int:
    return min(range(len(levels)), key=lambda i: abs(levels[i] - value))


def _grid_origins(
    column: Column, piles: Sequence[Pile], grid: _PileGrid
) -> list[tuple[float, float, float]]:
    """Centroide da parte (i, j) do pilar dividido em nx × ny partes iguais (D13)."""
    share = 1.0 / (grid.nx * grid.ny)
    origins = []
    for pile in piles:
        i, j = grid.cell[pile.id]
        origins.append(
            (
                column.x + column.bx * ((i + 0.5) / grid.nx - 0.5),
                column.y + column.by * ((j + 0.5) / grid.ny - 0.5),
                share,
            )
        )
    return origins


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
    return _ring_ties(piles, [_push(p, s, z) for p, s in zip(piles, struts, strict=True)], fyd)


def _push(pile: Pile, strut: Strut, z: float) -> tuple[float, float]:
    """Componente horizontal da biela na estaca, H = R·lproj/z, para fora [N]."""
    return (
        strut.force_d / z * (pile.x - strut.origin_x),
        strut.force_d / z * (pile.y - strut.origin_y),
    )


def _ring_ties(
    piles: Sequence[Pile], pushes: Sequence[tuple[float, float]], fyd: float
) -> tuple[Tie, ...]:
    """Tirantes entre estacas vizinhas do contorno; cada um com a maior força das extremidades."""
    n = len(piles)
    edges = [(0, 1)] if n == 2 else [(i, (i + 1) % n) for i in range(n)]
    edge_force = {e: 0.0 for e in edges}
    for i, (pile, (hx, hy)) in enumerate(zip(piles, pushes, strict=True)):
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


def _polygon_ties(
    outline: Sequence[Pile],
    interior: Sequence[Pile],
    pushes: Sequence[tuple[float, float]],
    fyd: float,
    column: Column,
) -> tuple[Tie, ...]:
    """D15: metade do empuxo em tirantes radiais e o resto no anel do contorno.

    O tirante radial vai até a estaca interna (se houver uma só) ou até a estaca oposta, quando a
    linha entre as duas passa sob o pilar; sem parceiro, o anel fica com todo o empuxo. A força no
    radial é metade da projeção do empuxo na sua direção, e o anel equilibra o restante.
    """
    by_id = {p.id: p for p in (*outline, *interior)}
    reach = min(column.bx, column.by) / 2.0
    radial: dict[tuple[str, str], float] = {}
    ring_pushes = []
    for pile, (hx, hy) in zip(outline, pushes, strict=True):
        center = len(interior) == 1
        partner = interior[0] if center else _opposite(pile, outline, column, reach)
        if partner is not None and not center:  # diagonal só entre estacas mutuamente opostas
            partner = partner if _opposite(partner, outline, column, reach) is pile else None
        if partner is None:
            ring_pushes.append((hx, hy))
            continue
        ux, uy = _unit(partner.x - pile.x, partner.y - pile.y)
        force = max(-_RADIAL_SHARE * (hx * ux + hy * uy), 0.0)
        ring_pushes.append((hx + force * ux, hy + force * uy))
        key = (
            (pile.id, partner.id)
            if interior
            else (min(pile.id, partner.id), max(pile.id, partner.id))
        )
        radial[key] = max(radial.get(key, 0.0), force)
    ties = list(_ring_ties(outline, ring_pushes, fyd))
    for (a, b), force in radial.items():
        ux, uy = _unit(by_id[b].x - by_id[a].x, by_id[b].y - by_id[a].y)
        ties.append(Tie(a, b, force, force / fyd, ux, uy))
    return tuple(ties)


def _opposite(pile: Pile, outline: Sequence[Pile], column: Column, reach: float) -> Pile | None:
    """Estaca do contorno cuja linha até `pile` passa a menos de `reach` do centro do pilar."""
    best, best_gap = None, reach
    for other in outline:
        if other is pile:
            continue
        ux, uy = _unit(other.x - pile.x, other.y - pile.y)
        along = (column.x - pile.x) * ux + (column.y - pile.y) * uy
        if not 0.0 < along < math.dist((pile.x, pile.y), (other.x, other.y)):
            continue
        gap = abs((column.x - pile.x) * uy - (column.y - pile.y) * ux)
        if gap < best_gap:
            best, best_gap = other, gap
    return best


@dataclass(frozen=True)
class _PileRows:
    rows: list[list[Pile]]  # em ordem crescente da coordenada transversal
    along_x: bool  # fileiras paralelas a x


def _pile_rows(piles: Sequence[Pile]) -> _PileRows | None:
    """Fileiras paralelas a x ou a y (D17), ordenadas; None se as estacas não formam fileiras.

    As fileiras seguem o eixo com menos níveis de coordenada; são aceitas com ao menos duas
    fileiras, todas com duas ou mais estacas.
    """
    by_axis = []
    for axis in (1, 0):  # fileiras paralelas a x (níveis de y) ou a y (níveis de x)
        levels = _levels([(p.x, p.y)[axis] for p in piles])
        rows = [
            sorted(
                (p for p in piles if abs((p.x, p.y)[axis] - level) <= _LEVEL_TOL_MM),
                key=lambda p: (p.x, p.y)[1 - axis],
            )
            for level in levels
        ]
        by_axis.append(_PileRows(rows, along_x=axis == 1))
    found = min(by_axis, key=lambda r: len(r.rows))
    if len(found.rows) < 2 or min(len(r) for r in found.rows) < 2:
        return None
    return found


def _row_origins(
    column: Column,
    piles: Sequence[Pile],
    rows: _PileRows,
    reactions: dict[str, float],
) -> list[tuple[float, float, float]]:
    """Isoáreas do pilar (D17): uma faixa por fileira e uma parte por estaca, ∝ às reações.

    As origens são deslocadas da excentricidade da carga, e = Σ R·p / Σ R − centro do pilar, para
    que as componentes horizontais das bielas se equilibrem (Σ H = 0).
    """
    along_x = rows.along_x
    total = sum(reactions[p.id] for p in piles)
    ex = sum(reactions[p.id] * p.x for p in piles) / total - column.x
    ey = sum(reactions[p.id] * p.y for p in piles) / total - column.y
    if abs(ex) > column.bx / 2.0 or abs(ey) > column.by / 2.0:
        raise UnsupportedLayoutError(
            "Excentricidade da carga fora da seção do pilar: fora do escopo das fileiras (D17)"
        )
    across, along = (column.by, column.bx) if along_x else (column.bx, column.by)
    origin: dict[str, tuple[float, float, float]] = {}
    start = -across / 2.0
    for row in rows.rows:
        row_total = sum(reactions[p.id] for p in row)
        height = across * row_total / total
        position = -along / 2.0
        for pile in row:
            width = along * reactions[pile.id] / row_total
            u, v = position + width / 2.0, start + height / 2.0
            ox, oy = (u, v) if along_x else (v, u)
            origin[pile.id] = (column.x + ex + ox, column.y + ey + oy, reactions[pile.id] / total)
            position += width
        start += height
    return [origin[p.id] for p in piles]


def _network_ties(
    piles: Sequence[Pile], pushes: Sequence[tuple[float, float]], fyd: float
) -> tuple[tuple[Tie, ...], float]:
    """Rede triangulada de tirantes com o mínimo de Σ F·l (D17, critério da D12).

    Os candidatos são os lados da triangulação de Delaunay das estacas; tirante fora das direções
    x e y pesa 0,1 % a mais (desempate da D12). Antes, os empuxos recebem a menor correção que
    zera a resultante e o momento em planta (resíduo das isoáreas sob momento); a correção
    relativa ao maior empuxo é devolvida para a trilha de auditoria.
    """
    xy = np.array([(p.x, p.y) for p in piles])
    loads = np.array(pushes, dtype=float).reshape(-1)
    edges = sorted(
        {
            (min(a, b), max(a, b))
            for tri in Delaunay(xy).simplices
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[0], tri[2]))
        }
    )
    # Modos de corpo rígido em planta: translação em x, em y e rotação.
    center = xy.mean(axis=0)
    modes = np.zeros((2 * len(piles), 3))
    modes[0::2, 0] = 1.0
    modes[1::2, 1] = 1.0
    modes[0::2, 2] = -(xy[:, 1] - center[1])
    modes[1::2, 2] = xy[:, 0] - center[0]
    fix = modes @ np.linalg.lstsq(modes, loads, rcond=None)[0]
    loads = loads - fix
    largest = max(math.hypot(hx, hy) for hx, hy in pushes)
    correction = float(np.abs(fix).max()) / largest if largest > 0.0 else 0.0

    matrix = np.zeros((2 * len(piles), len(edges)))
    cost = np.zeros(len(edges))
    units = []
    for k, (a, b) in enumerate(edges):
        length = float(np.linalg.norm(xy[b] - xy[a]))
        ux, uy = (xy[b] - xy[a]) / length
        matrix[2 * a : 2 * a + 2, k] += (ux, uy)
        matrix[2 * b : 2 * b + 2, k] -= (ux, uy)
        on_axis = min(abs(ux), abs(uy)) < _LEVEL_TOL_MM / length
        cost[k] = length * (1.0 if on_axis else 1.0 + OFF_AXIS_TIE_PENALTY)
        units.append((float(ux), float(uy)))
    solution = linprog(cost, A_eq=matrix, b_eq=-loads, bounds=(0.0, None), method="highs")
    if not solution.success:
        raise UnsupportedLayoutError("Tirante comprimido: geometria fora do escopo (D17)")
    forces = _spread_optimum(matrix, -loads, cost, solution.x)
    ties = tuple(
        Tie(piles[a].id, piles[b].id, float(f), float(f) / fyd, ux, uy)
        for (a, b), f, (ux, uy) in zip(edges, forces, units, strict=True)
        if f > _FORCE_TOL * largest
    )
    return ties, correction


def _spread_optimum(
    matrix: np.ndarray, loads: np.ndarray, cost: np.ndarray, start: np.ndarray
) -> np.ndarray:
    """Entre as soluções de mínimo Σ F·l, a de menor Σ F² (única; preserva a simetria)."""
    best = float(cost @ start)
    scale = max(float(np.abs(start).max()), 1.0)
    # Equilíbrio sem as equações redundantes dos modos de corpo rígido.
    basis, singular, _ = np.linalg.svd(matrix, full_matrices=False)
    basis = basis[:, singular > singular[0] * 1e-9]
    matrix, loads = basis.T @ matrix, basis.T @ loads
    result = minimize(
        lambda f: float(f @ f),
        start / scale,
        jac=lambda f: 2.0 * f,
        bounds=[(0.0, None)] * len(start),
        constraints=(
            {"type": "eq", "fun": lambda f: matrix @ f - loads / scale, "jac": lambda _: matrix},
            {
                "type": "ineq",
                "fun": lambda f: best / scale * (1.0 + 1e-9) - cost @ f,
                "jac": lambda _: -cost[None, :],
            },
        ),
        method="SLSQP",
        options={"maxiter": 500, "ftol": 1e-14},
    )
    return (result.x if result.success else start / scale) * scale


def _grid_ties(
    piles: Sequence[Pile], struts: Sequence[Strut], z: float, fyd: float, grid: _PileGrid
) -> tuple[Tie, ...]:
    """Tirantes por linha (x) e por coluna (y) da grade, trecho a trecho (D13).

    A componente horizontal de cada biela empurra a estaca para fora; o trecho entre as estacas k
    e k + 1 equilibra as estacas de um lado ou as do outro, e fica com a maior das duas forças.
    """
    horizontal = {
        pile.id: (s.force_d / z * (pile.x - s.origin_x), s.force_d / z * (pile.y - s.origin_y))
        for pile, s in zip(piles, struts, strict=True)
    }
    lines: list[tuple[list[Pile], int]] = [
        (sorted((p for p in piles if grid.cell[p.id][1] == j), key=lambda p: p.x), 0)
        for j in range(grid.ny)
    ]
    lines += [
        (sorted((p for p in piles if grid.cell[p.id][0] == i), key=lambda p: p.y), 1)
        for i in range(grid.nx)
    ]
    ties = []
    for line, axis in lines:
        pushes = [horizontal[p.id][axis] for p in line]
        for k in range(len(line) - 1):
            force = max(-sum(pushes[: k + 1]), sum(pushes[k + 1 :]))
            if force < -_Y_TOL_MM:
                raise UnsupportedLayoutError("Tirante comprimido: geometria fora do escopo")
            force = max(force, 0.0)
            a, b = line[k], line[k + 1]
            ux, uy = _unit(b.x - a.x, b.y - a.y)
            ties.append(Tie(a.id, b.id, force, force / fyd, ux, uy))
    return tuple(ties)


def _unit(x: float, y: float) -> tuple[float, float]:
    norm = math.hypot(x, y)
    return (x / norm, y / norm)
