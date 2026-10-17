"""Detalhamento de blocos rígidos (NBR 6118:2023, 22.7.2.1 e 22.7.4.1).

Recebe os tirantes resolvidos por `blococalc.core.strut_tie` (via protocolo) e devolve:
- largura das faixas sobre as estacas, onde fica mais de 85 % da armadura de flexão;
- armadura de distribuição em malha, 20 % das forças de tração em cada direção;
- verificação da ancoragem de cada tirante sobre a estaca, medida da face interna da estaca;
- alertas de armadura de suspensão e de armadura lateral e superior obrigatórias. Como a malha
  usa 20 %, o gatilho de suspensão por distribuição acima de 25 % (22.7.4.1.3) não ocorre aqui;
- quantidade de barras de cada tirante e se cabem numa camada na faixa (D18, §4.9). Numa linha de
  barras contínua, vale a quantidade do trecho mais carregado, e a ancoragem usa
  As,calc/As,ef dessa linha (9.4.2.5).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from blococalc.schemas import (
    Check,
    CheckStatus,
    DetailingInput,
    GeometryInput,
    MaterialsInput,
    Pile,
    Reference,
)
from blococalc.standards.anchorage import (
    basic_anchorage_length,
    fbd,
    is_good_bond_bottom_bar,
    required_anchorage_length,
)
from blococalc.standards.bars import bar_area, layer_width, tie_bar_count

BAND_WIDTH_FACTOR = 1.2  # 22.7.2.1 a)
DISTRIBUTION_RATIO = 0.20  # 22.7.4.1.2
SUSPENSION_SPACING_FACTOR = 3.0  # 22.7.4.1.3
_PARALLEL_TOL = 1e-9

_ANCHORAGE = Reference(source="NBR 6118:2023", item="22.7.4.1.1 / 9.4.2.5")
_SUSPENSION = Reference(source="NBR 6118:2023", item="22.7.4.1.3")
_BAND = Reference(source="NBR 6118:2023", item="22.7.2.1 a) / 18.3.2.2; D18")


class TieResult(Protocol):
    """Tirante resolvido (`core.strut_tie.Tie` atende a este protocolo)."""

    @property
    def pile_a(self) -> str: ...
    @property
    def pile_b(self) -> str: ...
    @property
    def force_d(self) -> float: ...
    @property
    def dir_x(self) -> float: ...
    @property
    def dir_y(self) -> float: ...


@dataclass(frozen=True)
class Detailing:
    band_widths: dict[str, float]  # largura da faixa sobre cada estaca [mm]
    distribution_area_x: float  # malha de distribuição, barras em x [mm²]
    distribution_area_y: float  # malha de distribuição, barras em y [mm²]
    bar_counts: dict[tuple[str, str], int]  # barras de cada tirante, pelas estacas (D18)
    checks: tuple[Check, ...]
    warnings: tuple[str, ...]


def rigid_cap_detailing(
    geometry: GeometryInput,
    ties: Sequence[TieResult],
    materials: MaterialsInput,
    options: DetailingInput,
    tie_height: float,
) -> Detailing:
    """Detalhamento de bloco rígido para um caso de carga.

    `tie_height` é a altura do eixo do tirante acima da cabeça da estaca [mm], a mesma usada no
    modelo de bielas e tirantes.
    """
    piles = {pile.id: pile for pile in geometry.piles}
    bar_diameter = options.bar_diameter
    fyd = materials.fyk / materials.gamma_s
    runs = _bar_runs(ties)
    # Cada linha de barras (trechos alinhados de uma linha de estacas, D13) entra com o seu
    # trecho mais carregado, que define a armadura da linha inteira.
    tension_x = sum(max(abs(t.force_d * t.dir_x) for t in run) for run in runs)
    tension_y = sum(max(abs(t.force_d * t.dir_y) for t in run) for run in runs)

    cap = geometry.cap
    depth = cap.h - cap.pile_embedment - tie_height
    good = is_good_bond_bottom_bar(cap.h, depth)
    basic = basic_anchorage_length(bar_diameter, fyd, fbd(materials, bar_diameter, good_bond=good))
    hook = options.hooked and cap.cover >= 3.0 * bar_diameter
    one_bar = bar_area(bar_diameter)
    bar_counts: dict[tuple[str, str], int] = {}
    ratios: dict[tuple[str, str], float] = {}
    for run in runs:
        area = max(t.force_d for t in run) / fyd
        count = tie_bar_count(area, bar_diameter)
        for t in run:
            bar_counts[(t.pile_a, t.pile_b)] = count
            ratios[(t.pile_a, t.pile_b)] = area / (count * one_bar)

    checks: list[Check] = []
    for tie in ties:
        key = (tie.pile_a, tie.pile_b)
        band = BAND_WIDTH_FACTOR * min(piles[tie.pile_a].size, piles[tie.pile_b].size)
        width = layer_width(bar_counts[key], bar_diameter, options.max_aggregate_size)
        checks.append(
            Check(
                id=f"faixa_{tie.pile_a}_{tie.pile_b}",
                description=(
                    f"{bar_counts[key]} φ{bar_diameter:g} do tirante {tie.pile_a}–{tie.pile_b} "
                    "numa camada na faixa 1,2·φ"
                ),
                demand=width,
                capacity=band,
                unit="mm",
                status=CheckStatus.OK if width <= band else CheckStatus.FAIL,
                reference=_BAND,
            )
        )

    for tie in ties:
        a, b = piles[tie.pile_a], piles[tie.pile_b]
        required = required_anchorage_length(
            basic, bar_diameter, ratios[(tie.pile_a, tie.pile_b)], hook_alpha=hook
        )
        for end, other in ((a, b), (b, a)):
            if not _run_end(runs, tie, end.id):
                continue  # estaca interna da linha: a barra passa direto
            available = _available_anchorage(geometry, end, other)
            checks.append(
                Check(
                    id=f"ancoragem_{tie.pile_a}_{tie.pile_b}_{end.id}",
                    description=f"Ancoragem do tirante {tie.pile_a}–{tie.pile_b} sobre {end.id}",
                    demand=required,
                    capacity=available,
                    unit="mm",
                    status=CheckStatus.OK if required <= available else CheckStatus.FAIL,
                    reference=_ANCHORAGE,
                )
            )
        spacing = math.hypot(a.x - b.x, a.y - b.y)
        limit = SUSPENSION_SPACING_FACTOR * cap.h
        checks.append(
            Check(
                id=f"suspensao_{tie.pile_a}_{tie.pile_b}",
                description=f"Espaçamento {tie.pile_a}–{tie.pile_b} ≤ 3·h (sem suspensão)",
                demand=spacing,
                capacity=limit,
                unit="mm",
                status=CheckStatus.OK if spacing <= limit else CheckStatus.WARNING,
                reference=_SUSPENSION,
            )
        )

    warnings = []
    if not options.hooked:
        warnings.append(
            "Tirantes sem gancho: a NBR 6118:2023, 22.7.4.1.1 exige gancho nas duas pontas."
        )
    if any(c.id.startswith("suspensao_") and c.status is CheckStatus.WARNING for c in checks):
        warnings.append(
            "Espaçamento entre estacas maior que 3·h: prever armadura de suspensão "
            "(NBR 6118:2023, 22.7.4.1.3). O cálculo dessa armadura ainda não está no programa."
        )
    if _collinear(geometry.piles):
        warnings.append(
            "Estacas em uma única linha: armaduras lateral e superior obrigatórias "
            "(NBR 6118:2023, 22.7.4.1.5)."
        )
    return Detailing(
        band_widths={p.id: BAND_WIDTH_FACTOR * p.size for p in geometry.piles},
        distribution_area_x=DISTRIBUTION_RATIO * tension_x / fyd,
        distribution_area_y=DISTRIBUTION_RATIO * tension_y / fyd,
        bar_counts=bar_counts,
        checks=tuple(checks),
        warnings=tuple(warnings),
    )


def _bar_runs(ties: Sequence[TieResult]) -> list[list[TieResult]]:
    """Agrupa os trechos paralelos que se encadeiam por estacas comuns numa mesma linha."""
    runs: list[list[TieResult]] = []
    for tie in ties:
        joined = [
            run
            for run in runs
            if any(
                {tie.pile_a, tie.pile_b} & {t.pile_a, t.pile_b}
                and abs(tie.dir_x * t.dir_y - tie.dir_y * t.dir_x) < _PARALLEL_TOL
                for t in run
            )
        ]
        merged = [tie] + [t for run in joined for t in run]
        runs = [run for run in runs if all(run is not j for j in joined)] + [merged]
    return runs


def _run_end(runs: Sequence[Sequence[TieResult]], tie: TieResult, pile_id: str) -> bool:
    run = next(r for r in runs if any(t is tie for t in r))
    return sum(pile_id in (t.pile_a, t.pile_b) for t in run) == 1


def _available_anchorage(geometry: GeometryInput, end: Pile, other: Pile) -> float:
    """Da face interna da estaca `end` até a ponta da barra, junto à face do bloco [mm]."""
    length = math.hypot(end.x - other.x, end.y - other.y)
    ux, uy = (end.x - other.x) / length, (end.y - other.y) / length
    to_edge = min(
        (math.copysign(half, u) - coord) / u
        for u, coord, half in ((ux, end.x, geometry.cap.lx / 2), (uy, end.y, geometry.cap.ly / 2))
        if abs(u) > 1e-12
    )
    return to_edge + end.size / 2.0 - geometry.cap.cover


def _collinear(piles: Sequence[Pile]) -> bool:
    p0, p1 = piles[0], piles[1]
    return all(
        abs((p1.x - p0.x) * (p.y - p0.y) - (p1.y - p0.y) * (p.x - p0.x)) < 1e-6 for p in piles[2:]
    )
