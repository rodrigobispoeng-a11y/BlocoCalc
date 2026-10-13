"""Flexão simples de seção retangular com armadura de tração (NBR 6118:2023, 17.2.2 e 17.3.5.2.1).

Cláusulas pinadas em docs/02-metodos.md §2: 8.2.10.1 (ηc), 14.6.4.3 (x/d), 17.2.2 e)
(retângulo de profundidade λx) e 17.3.5.2.1 (armadura mínima). Sem armadura de compressão:
seção que excede o limite de x/d é devolvida como falha.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from blococalc.schemas import MaterialsInput
from blococalc.standards.anchorage import fctm

MIN_RATIO = 0.0015  # 17.3.5.2.1, taxa mínima absoluta
_MIN_MOMENT_FACTOR = 0.8  # Md,mín = 0,8·W0·fctk,sup
_FCTK_SUP_FACTOR = 1.3  # 8.2.5


@dataclass(frozen=True)
class StressBlock:
    """Parâmetros do diagrama retangular (NBR 6118:2023, 17.2.2 e)."""

    lambda_: float
    alpha_c: float
    eta_c: float


@dataclass(frozen=True)
class FlexureDesign:
    area: float  # As necessária, já com o mínimo [mm²]
    area_calc: float  # As do momento solicitante [mm²]
    area_min: float  # As,mín [mm²]
    x_over_d: float  # posição da linha neutra; inf se a seção não resiste sem armadura dupla
    x_over_d_limit: float


def stress_block(fck: float) -> StressBlock:
    """λ, αc (17.2.2 e) e ηc (8.2.10.1).

    λ = 0,8 e αc = 0,85 até fck = 50 MPa; acima, λ = 0,8 − (fck − 50)/400 e
    αc = 0,85·[1 − (fck − 50)/200]. ηc = 1,0 até 40 MPa e (40/fck)^(1/3) acima.
    """
    excess = max(fck - 50.0, 0.0)
    eta_c = 1.0 if fck <= 40.0 else math.pow(40.0 / fck, 1.0 / 3.0)
    return StressBlock(
        lambda_=0.8 - excess / 400.0, alpha_c=0.85 * (1.0 - excess / 200.0), eta_c=eta_c
    )


def neutral_axis_limit(fck: float) -> float:
    """x/d ≤ 0,45 (fck ≤ 50 MPa) ou 0,35 (50 < fck ≤ 90 MPa), NBR 6118:2023, 14.6.4.3."""
    return 0.45 if fck <= 50.0 else 0.35


def tension_area(moment_d: float, width: float, depth: float, materials: MaterialsInput) -> float:
    """As para Md com o retângulo da 17.2.2 e) [mm²]; inf se Md excede a capacidade do concreto.

    Md = σc·b·y·(d − y/2), σc = αc·ηc·fcd, y = λx, logo y = d − √(d² − 2·Md/(σc·b)) e
    As = σc·b·y/fyd.
    """
    if moment_d <= 0.0:
        return 0.0
    sigma = _block_stress(materials)
    radicand = depth * depth - 2.0 * moment_d / (sigma * width)
    if radicand < 0.0:
        return math.inf
    y = depth - math.sqrt(radicand)
    return sigma * width * y / (materials.fyk / materials.gamma_s)


def minimum_area(width: float, height: float, depth: float, materials: MaterialsInput) -> float:
    """As,mín pela 17.3.5.2.1: Md,mín = 0,8·W0·fctk,sup e taxa ≥ 0,15 % de b·h [mm²]."""
    w0 = width * height * height / 6.0
    md_min = _MIN_MOMENT_FACTOR * w0 * _FCTK_SUP_FACTOR * fctm(materials.fck)
    return max(tension_area(md_min, width, depth, materials), MIN_RATIO * width * height)


def design_section(
    moment_d: float, width: float, height: float, depth: float, materials: MaterialsInput
) -> FlexureDesign:
    """Armadura de tração de uma seção retangular e a verificação de dutilidade."""
    area_calc = tension_area(moment_d, width, depth, materials)
    area_min = minimum_area(width, height, depth, materials)
    block = stress_block(materials.fck)
    if math.isinf(area_calc):
        x_over_d = math.inf
    else:
        fyd = materials.fyk / materials.gamma_s
        y = area_calc * fyd / (_block_stress(materials) * width)
        x_over_d = y / block.lambda_ / depth
    return FlexureDesign(
        area=max(area_calc, area_min),
        area_calc=area_calc,
        area_min=area_min,
        x_over_d=x_over_d,
        x_over_d_limit=neutral_axis_limit(materials.fck),
    )


def _block_stress(materials: MaterialsInput) -> float:
    block = stress_block(materials.fck)
    return block.alpha_c * block.eta_c * materials.fck / materials.gamma_c
