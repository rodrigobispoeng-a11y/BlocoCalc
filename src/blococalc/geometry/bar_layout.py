"""Posições de armação em planta (D19, docs/02-metodos.md §4.10; ADR-010).

Barras dos tirantes na faixa sobre as estacas, paralelas à linha das estacas e centradas nela,
de face a face do bloco menos o cobrimento; malha e flexão em toda a largura. Comprimento pela
linha de centro: trecho reto entre as pernas dos ganchos, arcos e pontas de 8φ (9.4.2.3,
gancho a 90° escolhido na D19), arredondado para cima de 1 em 1 cm. Barras iguais formam uma
posição; uma linha de barras com comprimentos diferentes (diagonais) forma uma posição de
comprimento variável.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from blococalc.schemas import BarPosition, Cap, HookShape, Point

_HOOK_TAIL = 8.0  # ponta reta do gancho a 90°, em φ (9.4.2.3 c)
_LARGE_BAR = 20.0  # mm, Tab. 9.1
_PIN_FACTORS = {250.0: (4.0, 5.0), 500.0: (5.0, 8.0), 600.0: (6.0, 6.0)}  # Tab. 9.1
_ROUND = 10.0  # mm
_AXIS_TOL = 1e-9
_SAME_LENGTH = 10.0  # mm: barras da mesma linha com diferença maior têm comprimento variável

# Chave da posição: (0 tirante | 1 malha, φ, camada, comprimentos da linha).
_Key = tuple[int, float, int, tuple[float, ...]]
_Bar = tuple[Point, Point]
_Groups = dict[_Key, list[tuple[tuple[str, ...], list[_Bar]]]]


@dataclass(frozen=True)
class BarRun:
    """Linha de barras de um tirante (D13): `count` barras de φ a `spacing` entre eixos."""

    reinforcement_ids: tuple[str, ...]
    origin: Point  # um ponto da linha das estacas [mm]
    direction: Point  # vetor unitário
    count: int
    bar_diameter: float
    spacing: float


@dataclass(frozen=True)
class MeshBars:
    """Malha de distribuição ou flexão: barras na direção `direction` a `spacing` [mm]."""

    reinforcement_id: str
    direction: Point
    bar_diameter: float
    spacing: float


def bend_diameter(phi: float, fyk: float) -> float:
    """Diâmetro do pino de dobramento [mm] (NBR 6118:2023, 9.4.2.3, Tabela 9.1)."""
    small, large = _PIN_FACTORS[fyk]
    return (small if phi < _LARGE_BAR else large) * phi


def hooked_length(straight: float, phi: float, fyk: float, hook: HookShape) -> float:
    """Comprimento da barra pela linha de centro, arredondado para cima de 1 cm [mm].

    `straight`: distância em planta entre as pernas dos ganchos (ou entre as pontas, sem
    gancho). Com gancho a 90°: straight − 2r + π·r + 2·8φ, r = D/2 + φ/2 (9.4.2.3).
    """
    length = straight
    if hook is HookShape.RIGHT_ANGLE:
        radius = bend_diameter(phi, fyk) / 2.0 + phi / 2.0
        length += -2.0 * radius + math.pi * radius + 2.0 * _HOOK_TAIL * phi
    return math.ceil(length / _ROUND - 1e-9) * _ROUND


def bar_positions(
    cap: Cap,
    runs: Sequence[BarRun],
    meshes: Sequence[MeshBars],
    hook: HookShape,
    fyk: float,
) -> tuple[BarPosition, ...]:
    """Posições numeradas: tirantes (maior φ primeiro) e depois malha, por camada."""
    groups: _Groups = {}
    for run in runs:
        bars = [
            _clipped(cap, hook, run.bar_diameter, _offset(run.origin, run.direction, offset),
                     run.direction)
            for offset in _offsets(run.count, run.spacing)
        ]  # fmt: skip
        _add(groups, (0, run.bar_diameter, bar_layer(run.direction)), run.reinforcement_ids, bars,
             hook, fyk)  # fmt: skip
    for mesh in meshes:
        normal = (-mesh.direction[1], mesh.direction[0])
        inset = cap.cover + mesh.bar_diameter / 2.0
        width = (cap.ly if abs(mesh.direction[0]) > _AXIS_TOL else cap.lx) - 2.0 * inset
        count = math.floor(width / mesh.spacing + 1e-9) + 1
        bars = [
            _clipped(cap, hook, mesh.bar_diameter, _offset((0.0, 0.0), normal, offset, along=False),
                     mesh.direction)
            for offset in _offsets(count, mesh.spacing)
        ]  # fmt: skip
        _add(groups, (1, mesh.bar_diameter, bar_layer(mesh.direction)), (mesh.reinforcement_id,),
             bars, hook, fyk)  # fmt: skip

    def order(key: _Key) -> tuple[int, float, int, float]:
        kind, phi, layer, lengths = key
        return (kind, -phi, layer, -max(lengths))

    positions = []
    for number, key in enumerate(sorted(groups, key=order), start=1):
        _, phi, layer, lengths = key
        members = groups[key]
        bars = [bar for _, run_bars in members for bar in run_bars]
        each = [hooked_length(math.dist(*bar), phi, fyk, hook) for bar in bars]
        positions.append(
            BarPosition(
                id=f"N{number}",
                bar_diameter=phi,
                count=len(bars),
                length=sum(each) / len(each),
                variable_length=len(lengths) > 1,
                hook=hook,
                layer=layer,
                reinforcement_ids=tuple(i for ids, _ in members for i in ids),
                bars=tuple(bars),
            )
        )
    return tuple(positions)


def _add(  # noqa: PLR0913, PLR0917 - grupo, linha e regra do comprimento
    groups: _Groups,
    kind: tuple[int, float, int],
    ids: tuple[str, ...],
    bars: list[_Bar],
    hook: HookShape,
    fyk: float,
) -> None:
    """Agrupa pelo conjunto de comprimentos da linha: linhas iguais formam uma só posição."""
    lengths = sorted({hooked_length(math.dist(*b), kind[1], fyk, hook) for b in bars})
    if lengths[-1] - lengths[0] <= _SAME_LENGTH:
        lengths = [lengths[-1]]
    groups.setdefault((*kind, tuple(lengths)), []).append((ids, bars))


def bar_layer(direction: Point) -> int:
    """Camada: 1 para x, 2 para y, 3 para as diagonais (D19)."""
    if abs(direction[1]) <= _AXIS_TOL:
        return 1
    return 2 if abs(direction[0]) <= _AXIS_TOL else 3


def _offsets(count: int, spacing: float) -> list[float]:
    return [(k - (count - 1) / 2.0) * spacing for k in range(count)]


def _offset(origin: Point, direction: Point, offset: float, along: bool = True) -> Point:
    """Ponto deslocado de `offset` na normal de `direction` (ou ao longo dela, se `along`
    for falso, quando `direction` já é a normal)."""
    nx, ny = (-direction[1], direction[0]) if along else direction
    return (origin[0] + offset * nx, origin[1] + offset * ny)


def _clipped(cap: Cap, hook: HookShape, phi: float, point: Point, direction: Point) -> _Bar:
    """Barra pela reta `point` + t·`direction`, entre as faces do bloco menos o cobrimento.

    Com gancho, as extremidades ficam no eixo das pernas (cobrimento + φ/2 da face).
    """
    inset = cap.cover + (phi / 2.0 if hook is HookShape.RIGHT_ANGLE else 0.0)
    low, high = -math.inf, math.inf
    for coord, step, half in (
        (point[0], direction[0], cap.lx / 2.0 - inset),
        (point[1], direction[1], cap.ly / 2.0 - inset),
    ):
        if abs(step) <= _AXIS_TOL:
            continue
        a, b = (-half - coord) / step, (half - coord) / step
        low, high = max(low, min(a, b)), min(high, max(a, b))
    start = (point[0] + low * direction[0], point[1] + low * direction[1])
    end = (point[0] + high * direction[0], point[1] + high * direction[1])
    return start, end
