"""Cisalhamento e punção de laje sem armadura transversal (NBR 6118:2023, 19.4.1 e 19.5).

Cláusulas pinadas em docs/02-metodos.md §2. Usadas no bloco flexível (22.7.4.2, decisão D9
proposta). Sem protensão: σcp = 0. Funções puras sobre números, sem depender do `core`.
"""

from __future__ import annotations

import itertools
import math
from typing import Protocol

from blococalc.schemas import Check, CheckStatus, Column, MaterialsInput, Reference
from blococalc.standards.anchorage import fctk_inf

MAX_RHO = 0.02  # 19.4.1 e 19.5.3.2
_TAU_RD_FCK_CAP = 60.0  # 19.4.1: τRd limitado ao valor de fck = 60 MPa
_K_TABLE = ((0.5, 0.45), (1.0, 0.60), (2.0, 0.70), (3.0, 0.80))  # Tab. 19.2

_SHEAR = Reference(source="NBR 6118:2023", item="19.4.1")
_PUNCHING_C = Reference(source="NBR 6118:2023", item="19.5.2.2 / 19.5.3.1")
_PUNCHING_C1 = Reference(source="NBR 6118:2023", item="19.5.2.2 / 19.5.3.2")


class ShearDemand(Protocol):
    """Cortante numa seção (`core.flexible_cap.SectionShear` atende a este protocolo)."""

    @property
    def shear_d(self) -> float: ...
    @property
    def depth(self) -> float: ...
    @property
    def width(self) -> float: ...


class PunchingDemand(Protocol):
    """Esforços de punção (`core.flexible_cap.PunchingLoad` atende a este protocolo)."""

    @property
    def force_c(self) -> float: ...
    @property
    def force_c1(self) -> float: ...
    @property
    def moment_x(self) -> float: ...
    @property
    def moment_y(self) -> float: ...


def one_way_shear_resistance(
    width: float, depth: float, rho1: float, materials: MaterialsInput, *, bars_reach: bool = True
) -> float:
    """VRd1 = τRd·k·(1,2 + 40ρ1)·bw·d [N] (NBR 6118:2023, 19.4.1, σcp = 0).

    τRd = 0,25·fctd, fctd = fctk,inf/γc com fck ≤ 60 MPa; ρ1 ≤ 0,02; k = 1,6 − d ≥ 1 (d em m),
    ou k = 1 quando 50 % da armadura inferior não chega ao apoio (`bars_reach=False`).
    """
    tau_rd = 0.25 * fctk_inf(min(materials.fck, _TAU_RD_FCK_CAP)) / materials.gamma_c
    k = max(1.6 - depth / 1000.0, 1.0) if bars_reach else 1.0
    return tau_rd * k * (1.2 + 40.0 * min(rho1, MAX_RHO)) * width * depth


def tau_rd2(materials: MaterialsInput) -> float:
    """τRd2 = 0,27·αv·fcd, αv = 1 − fck/250 [MPa] (NBR 6118:2023, 19.5.3.1)."""
    return 0.27 * (1.0 - materials.fck / 250.0) * materials.fck / materials.gamma_c


def tau_rd1(depth: float, rho: float, fck: float) -> float:
    """τRd1 = 0,13·ke·(100·ρ·fck)^(1/3) [MPa] (NBR 6118:2023, 19.5.3.2, σcp = 0).

    ke = 1 + √(20/d) ≤ 2 com d em cm; ρ = √(ρx·ρy) ≤ 0,02.
    """
    ke = min(1.0 + math.sqrt(20.0 / (depth / 10.0)), 2.0)
    return 0.13 * ke * math.pow(100.0 * min(rho, MAX_RHO) * fck, 1.0 / 3.0)


def moment_factor(c1: float, c2: float) -> float:
    """K da Tabela 19.2 (NBR 6118:2023, 19.5.2.2).

    Interpolação linear entre os pontos da tabela e valores constantes fora dela: premissa nossa,
    registrada em docs/02-metodos.md.
    """
    ratio = c1 / c2
    if ratio <= _K_TABLE[0][0]:
        return _K_TABLE[0][1]
    for (r0, k0), (r1, k1) in itertools.pairwise(_K_TABLE):
        if ratio <= r1:
            return k0 + (k1 - k0) * (ratio - r0) / (r1 - r0)
    return _K_TABLE[-1][1]


def plastic_modulus(c1: float, c2: float, depth: float) -> float:
    """Wp = C1²/2 + C1·C2 + 4·C2·d + 16·d² + 2π·d·C1 [mm²], pilar retangular (19.5.2.2).

    Fórmula do contorno C′; com d = 0 dá o Wp do contorno C, C1²/2 + C1·C2.
    """
    d = depth
    return c1 * c1 / 2.0 + c1 * c2 + 4.0 * c2 * d + 16.0 * d * d + 2.0 * math.pi * d * c1


def punching_stress(
    force: float, moments: tuple[float, float], column: Column, depth: float, *, at_c1: bool
) -> float:
    """τSd = FSd/(u·d) + Σ K·MSd/(Wp·d) [MPa] (NBR 6118:2023, 19.5.2.1 e 19.5.2.2).

    `moments` = (MSd,x, MSd,y); MSd,y é excêntrico em x (C1 = bx) e MSd,x em y (C1 = by).
    Somar as duas parcelas é a favor da segurança para momento nas duas direções.
    """
    contour_depth = depth if at_c1 else 0.0
    moment_x, moment_y = moments
    bx, by = column.bx, column.by
    perimeter = 2.0 * (bx + by) + 4.0 * math.pi * contour_depth  # C′ a 2d: arcos de raio 2d
    stress = force / (perimeter * depth)
    for moment, c1, c2 in ((moment_y, bx, by), (moment_x, by, bx)):
        wp = plastic_modulus(c1, c2, contour_depth)
        stress += moment_factor(c1, c2) * abs(moment) / (wp * depth)
    return stress


def one_way_shear_check(
    check_id: str, shear: ShearDemand, rho1: float, materials: MaterialsInput
) -> Check:
    capacity = one_way_shear_resistance(shear.width, shear.depth, rho1, materials)
    return Check(
        id=check_id,
        description="Cortante de laje sem estribos VSd ≤ VRd1",
        demand=shear.shear_d,
        capacity=capacity,
        unit="N",
        status=CheckStatus.OK if shear.shear_d <= capacity else CheckStatus.FAIL,
        reference=_SHEAR,
    )


def punching_checks(
    load: PunchingDemand, column: Column, depth: float, rho: float, materials: MaterialsInput
) -> tuple[Check, Check]:
    """Contorno C (compressão diagonal) e C′ a 2d (tração diagonal), sem armadura de punção.

    Em C′ a força já vem descontada das estacas internas; o momento é mantido inteiro.
    """
    moments = (load.moment_x, load.moment_y)
    stress_c = punching_stress(load.force_c, moments, column, depth, at_c1=False)
    stress_c1 = punching_stress(load.force_c1, moments, column, depth, at_c1=True)
    return (
        _stress_check(
            "puncao_C",
            "Punção no contorno C: τSd ≤ τRd2",
            stress_c,
            tau_rd2(materials),
            _PUNCHING_C,
        ),
        _stress_check(
            "puncao_C1",
            "Punção no contorno C′ (2d): τSd ≤ τRd1",
            stress_c1,
            tau_rd1(depth, rho, materials.fck),
            _PUNCHING_C1,
        ),
    )


def _stress_check(
    check_id: str, description: str, demand: float, capacity: float, reference: Reference
) -> Check:
    return Check(
        id=check_id,
        description=description,
        demand=demand,
        capacity=capacity,
        unit="MPa",
        status=CheckStatus.OK if demand <= capacity else CheckStatus.FAIL,
        reference=reference,
    )
