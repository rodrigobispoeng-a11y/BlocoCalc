"""Resistências de cálculo usadas no método de bielas e tirantes."""

from __future__ import annotations

from dataclasses import dataclass

from blococalc.schemas import MaterialsInput


@dataclass(frozen=True)
class StrutTieStrengths:
    """Tensões resistentes de cálculo [MPa]."""

    fcd: float
    alpha_v2: float
    fcd1: float
    fcd2: float
    fcd3: float
    fyd: float


def alpha_v2(fck: float) -> float:
    """αv2 = 1 − fck/250, fck em MPa (NBR 6118:2023, 17.4.2.2 e 19.5.3.1)."""
    return 1.0 - fck / 250.0


def strut_tie_strengths(materials: MaterialsInput) -> StrutTieStrengths:
    """Parâmetros de NBR 6118:2023, 22.3.2 (bielas e nós) e 22.3.3 (tirantes).

    fcd = fck/γc (12.3.3); fcd1 = 0,85·αv2·fcd (nós CCC); fcd2 = 0,60·αv2·fcd (nós CTT/TTT);
    fcd3 = 0,72·αv2·fcd (nós CCT); fyd = fyk/γs.
    """
    fcd = materials.fck / materials.gamma_c
    av2 = alpha_v2(materials.fck)
    return StrutTieStrengths(
        fcd=fcd,
        alpha_v2=av2,
        fcd1=0.85 * av2 * fcd,
        fcd2=0.60 * av2 * fcd,
        fcd3=0.72 * av2 * fcd,
        fyd=materials.fyk / materials.gamma_s,
    )
