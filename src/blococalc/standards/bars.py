"""Escolha de barras (D18, docs/02-metodos.md §4.9).

Série de diâmetros CA-50 da NBR 7480; espaçamento livre da NBR 6118:2023, 18.3.2.2; espaçamento
máximo de lajes da 20.1. O espaçamento mínimo de 100 mm da malha é um padrão prático nosso (D18),
não da norma.
"""

from __future__ import annotations

import math

BAR_SERIES = (6.3, 8.0, 10.0, 12.5, 16.0, 20.0, 25.0, 32.0, 40.0)  # mm, NBR 7480 (D18)
MIN_MESH_SPACING = 100.0  # mm, padrão prático (D18)
_SPACING_STEP = 10.0  # mm
_MIN_CLEAR = 20.0  # mm, 18.3.2.2
_AGGREGATE_FACTOR = 1.2  # 18.3.2.2 a), direção horizontal
_SLAB_MAX_SPACING = 200.0  # mm, 20.1
_LARGE_BAR = 20.0  # mm, 20.1
_LARGE_BAR_FACTOR = 15.0  # 20.1


def bar_area(phi: float) -> float:
    """Área da seção de uma barra [mm²]."""
    return math.pi * phi * phi / 4.0


def clear_spacing(phi: float, max_aggregate: float) -> float:
    """Espaçamento livre horizontal mínimo entre barras [mm] (NBR 6118:2023, 18.3.2.2 a)).

    ah ≥ máx(20 mm; φ; 1,2·dmáx).
    """
    return max(_MIN_CLEAR, phi, _AGGREGATE_FACTOR * max_aggregate)


def tie_bar_count(area: float, phi: float) -> int:
    """Quantidade de barras de um tirante: n = ⌈As / Aφ⌉, pelo menos uma (NBR 6118:2023, 22.3.3)."""
    return max(1, math.ceil(area / bar_area(phi) - 1e-9))


def layer_width(count: int, phi: float, max_aggregate: float) -> float:
    """Largura ocupada por `count` barras numa camada: n·φ + (n − 1)·ah [mm] (18.3.2.2)."""
    return count * phi + (count - 1) * clear_spacing(phi, max_aggregate)


def max_slab_spacing(h: float, phi: float) -> float:
    """Espaçamento máximo da armadura principal de flexão [mm] (NBR 6118:2023, 20.1).

    mín(2h; 200 mm); para φ ≥ 20 mm, 15φ.
    """
    if phi >= _LARGE_BAR:
        return _LARGE_BAR_FACTOR * phi
    return min(2.0 * h, _SLAB_MAX_SPACING)


def mesh_spacing(area: float, width: float, h: float, phi: float) -> float:
    """Espaçamento de barras φ para `area` [mm²] em `width` [mm] (D18).

    Arredondado para baixo de 10 em 10 mm e limitado pela 20.1; abaixo de 10 mm, sem arredondar.
    """
    exact = bar_area(phi) * width / area if area > 0.0 else math.inf
    spacing = min(max_slab_spacing(h, phi), exact)
    if spacing >= _SPACING_STEP:
        spacing = math.floor(spacing / _SPACING_STEP + 1e-9) * _SPACING_STEP
    return spacing


def mesh_bars(area: float, width: float, h: float, phi_min: float) -> tuple[float, float]:
    """Diâmetro e espaçamento de uma malha com `area` [mm²] distribuída em `width` [mm] (D18).

    Menor φ da série, a partir de `phi_min`, cujo espaçamento (`mesh_spacing`) fica em pelo menos
    100 mm. Se nenhum servir, devolve φ40 com o espaçamento que ele exige, abaixo do mínimo,
    para quem chama avisar.
    """
    for phi in (phi_min, *(p for p in BAR_SERIES if p > phi_min)):
        spacing = mesh_spacing(area, width, h, phi)
        if spacing >= MIN_MESH_SPACING:
            break
    return phi, spacing
