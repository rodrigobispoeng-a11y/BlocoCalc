"""Resistência à tração, aderência e ancoragem de armaduras passivas.

Cláusulas pinadas em docs/02-metodos.md §2: NBR 6118:2023, 8.2.5, 9.3.1, 9.3.2.1 (Tab. 8.2),
9.4.2.4 e 9.4.2.5.
"""

from __future__ import annotations

import math

from blococalc.schemas import MaterialsInput

_ETA1_BY_FYK = {250.0: 1.0, 500.0: 2.25, 600.0: 1.0}  # CA-25, CA-50, CA-60 (Tab. 8.2)
_HOOK_ALPHA = 0.7
_GOOD_BOND_HEIGHT_MM = 600.0
_GOOD_BOND_OFFSET_MM = 300.0


def fctm(fck: float) -> float:
    """Resistência média à tração direta [MPa] (NBR 6118:2023, 8.2.5).

    fctm = 0,3·fck^(2/3) para fck ≤ 50 MPa; fctm = 2,12·ln[1 + 0,1·(fck + 8)] acima disso.
    """
    if fck <= 50.0:
        return 0.3 * math.pow(fck, 2.0 / 3.0)
    return 2.12 * math.log(1.0 + 0.1 * (fck + 8.0))


def fctk_inf(fck: float) -> float:
    """fctk,inf = 0,7·fctm [MPa] (NBR 6118:2023, 8.2.5)."""
    return 0.7 * fctm(fck)


def eta1(fyk: float) -> float:
    """Coeficiente de conformação superficial η1 (NBR 6118:2023, Tabela 8.2)."""
    try:
        return _ETA1_BY_FYK[fyk]
    except KeyError:
        raise ValueError(f"fyk = {fyk} MPa não corresponde a CA-25, CA-50 ou CA-60") from None


def is_good_bond_bottom_bar(h: float, depth_from_top: float) -> bool:
    """Barra horizontal inferior em boa situação de aderência (NBR 6118:2023, 9.3.1 b).

    h < 60 cm: até 30 cm acima da face inferior; h ≥ 60 cm: pelo menos 30 cm abaixo da face
    superior. `depth_from_top` é a distância do topo do bloco ao eixo da barra [mm].
    """
    if h < _GOOD_BOND_HEIGHT_MM:
        return h - depth_from_top <= _GOOD_BOND_OFFSET_MM
    return depth_from_top >= _GOOD_BOND_OFFSET_MM


def fbd(materials: MaterialsInput, bar_diameter: float, *, good_bond: bool = True) -> float:
    """Resistência de aderência de cálculo [MPa] (NBR 6118:2023, 9.3.2.1).

    fbd = η1·η2·η3·fctd, fctd = fctk,inf/γc; η2 = 1,0 (boa aderência) ou 0,7 (má);
    η3 = 1,0 para φ < 32 mm e (132 − φ)/100 para φ ≥ 32 mm.
    """
    eta2 = 1.0 if good_bond else 0.7
    eta3 = 1.0 if bar_diameter < 32.0 else (132.0 - bar_diameter) / 100.0
    return eta1(materials.fyk) * eta2 * eta3 * fctk_inf(materials.fck) / materials.gamma_c


def basic_anchorage_length(bar_diameter: float, fyd: float, bond_strength: float) -> float:
    """ℓb = (φ/4)·(fyd/fbd) ≥ 25φ [mm] (NBR 6118:2023, 9.4.2.4)."""
    return max(bar_diameter / 4.0 * fyd / bond_strength, 25.0 * bar_diameter)


def required_anchorage_length(
    basic_length: float, bar_diameter: float, area_ratio: float, *, hook_alpha: bool
) -> float:
    """ℓb,nec = α·ℓb·As,calc/As,ef ≥ ℓb,mín [mm] (NBR 6118:2023, 9.4.2.5).

    `area_ratio` = As,calc/As,ef. `hook_alpha`: barra com gancho e cobrimento no plano normal
    ao gancho ≥ 3φ (α = 0,7); sem isso, α = 1,0. ℓb,mín = máx(0,3·ℓb; 10φ; 100 mm).
    """
    alpha = _HOOK_ALPHA if hook_alpha else 1.0
    minimum = max(0.3 * basic_length, 10.0 * bar_diameter, 100.0)
    return max(alpha * basic_length * area_ratio, minimum)
