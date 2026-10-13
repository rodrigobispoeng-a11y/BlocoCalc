"""Esforços de cálculo do bloco flexível (docs/02-metodos.md §4.2, decisão D9 proposta).

O bloco flexível é tratado como laje sobre estacas:
- flexão nas seções de referência S1 do CEB-FIP 70 (Boletim 73, Apêndice 4, §3.1 e §3.2):
  plano a 0,15·ap para dentro da face do pilar, largura igual à do bloco, momento das reações das
  estacas do lado não cruzado pelo eixo do pilar e altura útil limitada a 1,5 vez a distância de
  S1 à estaca mais afastada;
- cortante de uma direção junto à face do pilar: a NBR 6118:2023, 19.4.1 toma VSd a d da face,
  mas aqui as estacas entre a face e essa seção contam inteiras (a favor da segurança, sem a
  redução a/2d); estaca cortada pela face entra com parcela linear;
- força de punção no pilar para os contornos C e C′ (NBR 6118:2023, 19.5.2.1 e 19.5.2.2): em C′
  descontam-se as reações das estacas com eixo dentro do contorno.

Todos os esforços saem multiplicados por γn (NBR 6118:2023, 22.2, decisão D3). Funções puras.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from blococalc.schemas import Column, GeometryInput, LoadCase, Pile, PileReaction

S1_OFFSET_RATIO = 0.15  # CEB-70 §3.1
S1_DEPTH_LIMIT = 1.5  # CEB-70 §3.1
C1_DISTANCE = 2.0  # contorno C′ a 2d da face (19.5.1)


@dataclass(frozen=True)
class SectionMoment:
    """Momento de cálculo numa seção S1.

    `axis` é a direção das barras ("x" ou "y"); a seção é perpendicular a ela. `side` = +1 ou −1
    indica o lado do pilar. `depth` já está limitada pelo CEB-70 §3.1.
    """

    axis: str
    side: int
    moment_d: float  # [N·mm]
    depth: float  # [mm]
    width: float  # [mm]


@dataclass(frozen=True)
class SectionShear:
    """Cortante de cálculo de uma direção junto à face do pilar."""

    axis: str
    side: int
    shear_d: float  # [N]
    depth: float  # [mm]
    width: float  # [mm]


@dataclass(frozen=True)
class PunchingLoad:
    """Esforços de punção no pilar (NBR 6118:2023, 19.5.2)."""

    force_c: float  # FSd no contorno C [N]
    force_c1: float  # FSd no contorno C′, descontadas as estacas internas [N]
    moment_x: float  # MSd em torno de x [N·mm]
    moment_y: float  # MSd em torno de y [N·mm]
    piles_inside_c1: tuple[str, ...]
    c1_inside_cap: bool


def s1_moments(
    geometry: GeometryInput,
    reactions: Sequence[PileReaction],
    gamma_n: float,
    depth_x: float,
    depth_y: float,
) -> tuple[SectionMoment, ...]:
    """Momentos nas quatro seções S1 (dois lados em cada direção), CEB-70 §3.1 e §3.2."""
    column = _single_column(geometry)
    forces = _forces(geometry, reactions)
    result = []
    for axis, center, size, depth, width in _axes(geometry, column, depth_x, depth_y):
        for side in (1, -1):
            section = center + side * (size / 2.0 - S1_OFFSET_RATIO * size)
            arms = [(side * (_coord(p, axis) - section), force) for p, force in forces]
            beyond = [(arm, force) for arm, force in arms if arm > 0.0]
            moment = gamma_n * sum(arm * force for arm, force in beyond)
            farthest = max((arm for arm, _ in beyond), default=math.inf)
            result.append(
                SectionMoment(
                    axis=axis,
                    side=side,
                    moment_d=moment,
                    depth=min(depth, S1_DEPTH_LIMIT * farthest),
                    width=width,
                )
            )
    return tuple(result)


def face_shears(
    geometry: GeometryInput,
    reactions: Sequence[PileReaction],
    gamma_n: float,
    depth_x: float,
    depth_y: float,
) -> tuple[SectionShear, ...]:
    """Cortante de cada lado do pilar, somando as estacas além da face (parcela linear)."""
    column = _single_column(geometry)
    forces = _forces(geometry, reactions)
    result = []
    for axis, center, size, depth, width in _axes(geometry, column, depth_x, depth_y):
        for side in (1, -1):
            face = center + side * size / 2.0
            shear = sum(
                force * _share(side * (_coord(p, axis) - face), p.size) for p, force in forces
            )
            result.append(
                SectionShear(
                    axis=axis, side=side, shear_d=gamma_n * shear, depth=depth, width=width
                )
            )
    return tuple(result)


def punching_load(
    geometry: GeometryInput,
    case: LoadCase,
    reactions: Sequence[PileReaction],
    gamma_n: float,
    depth: float,
) -> PunchingLoad:
    """Força e momentos de punção no pilar; `depth` = (dx + dy)/2 (19.5.2.1)."""
    column = _single_column(geometry)
    (load,) = (item for item in case.column_loads if item.column_id == column.id)
    reach = C1_DISTANCE * depth
    inside = [
        (pile, force)
        for pile, force in _forces(geometry, reactions)
        if _distance_to_rectangle(pile, column) <= reach
    ]
    cap = geometry.cap
    fits = (
        abs(column.x) + column.bx / 2.0 + reach <= cap.lx / 2.0
        and abs(column.y) + column.by / 2.0 + reach <= cap.ly / 2.0
    )
    return PunchingLoad(
        force_c=gamma_n * load.n,
        force_c1=gamma_n * (load.n - sum(force for _, force in inside)),
        moment_x=gamma_n * load.mx,
        moment_y=gamma_n * load.my,
        piles_inside_c1=tuple(pile.id for pile, _ in inside),
        c1_inside_cap=fits,
    )


def _single_column(geometry: GeometryInput) -> Column:
    if len(geometry.columns) != 1:
        raise ValueError("O bloco flexível aceita um único pilar por bloco")
    return geometry.columns[0]


def _forces(geometry: GeometryInput, reactions: Sequence[PileReaction]) -> list[tuple[Pile, float]]:
    by_id = {r.pile_id: r.force for r in reactions}
    return [(pile, by_id[pile.id]) for pile in geometry.piles]


def _axes(
    geometry: GeometryInput, column: Column, depth_x: float, depth_y: float
) -> tuple[tuple[str, float, float, float, float], ...]:
    cap = geometry.cap
    return (
        ("x", column.x, column.bx, depth_x, cap.ly),
        ("y", column.y, column.by, depth_y, cap.lx),
    )


def _coord(pile: Pile, axis: str) -> float:
    return pile.x if axis == "x" else pile.y


def _share(offset: float, size: float) -> float:
    """Fração da estaca além da seção: 0 a 1, linear quando o eixo está a menos de size/2."""
    return min(1.0, max(0.0, 0.5 + offset / size))


def _distance_to_rectangle(pile: Pile, column: Column) -> float:
    gap_x = max(0.0, abs(pile.x - column.x) - column.bx / 2.0)
    gap_y = max(0.0, abs(pile.y - column.y) - column.by / 2.0)
    return math.hypot(gap_x, gap_y)
