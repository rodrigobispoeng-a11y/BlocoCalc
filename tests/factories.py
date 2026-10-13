"""Geometrias de teste reutilizáveis (mm)."""

from __future__ import annotations

from blococalc.schemas import Cap, Column, GeometryInput, Pile


def four_pile_cap(h: float = 1000.0) -> GeometryInput:
    """Bloco de 4 estacas do benchmark B1 (Macedo 2022, §6.1)."""
    piles = tuple(
        Pile(id=f"E{i + 1}", x=sx * 600.0, y=sy * 600.0, size=400.0)
        for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)))
    )
    return GeometryInput(
        cap=Cap(lx=2000.0, ly=2000.0, h=h, pile_embedment=100.0),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=200.0, by=650.0),),
    )


def two_pile_cap() -> GeometryInput:
    return GeometryInput(
        cap=Cap(lx=2000.0, ly=800.0, h=900.0, pile_embedment=100.0),
        piles=(
            Pile(id="E1", x=-600.0, y=0.0, size=400.0),
            Pile(id="E2", x=600.0, y=0.0, size=400.0),
        ),
        columns=(Column(id="P1", x=0.0, y=0.0, bx=400.0, by=400.0),),
    )


def node_depth(d: float, width: float, k: float) -> float:
    """Profundidade `y` do nó CCC por D6 com a face espraiada a 45° (D13), sem passar pelo código.

    Resolve (b + 2y)·y·(d − y/2) = k por bissecção, com k = ΣR·lproj/fcd1 na direção e b a
    largura da face do pilar que a compressão atravessa. O lado esquerdo cresce em [0, d].
    """
    low, high = 0.0, d
    for _ in range(200):
        mid = (low + high) / 2.0
        if (width + 2.0 * mid) * mid * (d - mid / 2.0) < k:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0
