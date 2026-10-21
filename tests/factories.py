"""Geometrias de teste reutilizáveis (mm)."""

from __future__ import annotations

import math

from blococalc.schemas import Cap, Column, FemField, GeometryInput, Pile, PileShape


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


def grid_cap(
    nx: int, ny: int, spacing: float = 1500.0, column: tuple[float, float] = (2090.0, 300.0)
) -> GeometryInput:
    """Estacas φ600 em grade nx × ny centrada na origem, bloco com 450 mm de borda (D13).

    Com nx = 4, ny = 2 e os padrões, é o B2 (planilha "Bloco Sobre N estacas"): bloco 540×240×140
    cm, pilar 209×30, espaçamento de 150 cm deduzido da planilha (2,5φ).
    """
    piles = tuple(
        Pile(
            id=f"E{j * nx + i + 1}",
            x=(i - (nx - 1) / 2.0) * spacing,
            y=(j - (ny - 1) / 2.0) * spacing,
            size=600.0,
        )
        for j in range(ny)
        for i in range(nx)
    )
    return GeometryInput(
        cap=Cap(
            lx=(nx - 1) * spacing + 900.0,
            ly=(ny - 1) * spacing + 900.0,
            h=1400.0,
            pile_embedment=100.0,
        ),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=column[0], by=column[1]),),
    )


def quincunx_cap() -> GeometryInput:
    """B7: bloco B05P01 de Bavaresco (2016), 420×420×210 cm, 5 estacas 60×60 em quincôncio."""
    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    piles = (
        *(
            Pile(id=f"E{i + 1}", x=sx * 1600.0, y=sy * 1600.0, size=600.0, shape=PileShape.SQUARE)
            for i, (sx, sy) in enumerate(corners)
        ),
        Pile(id="E5", x=0.0, y=0.0, size=600.0, shape=PileShape.SQUARE),
    )
    return GeometryInput(
        cap=Cap(lx=4200.0, ly=4200.0, h=2100.0, pile_embedment=100.0),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=1000.0, by=1000.0),),
    )


def polygon_cap(n: int, radius: float = 1000.0, center: bool = False) -> GeometryInput:
    """Estacas φ400 nos vértices de um polígono regular (a primeira em +x), pilar 400×400 (D15)."""
    piles = tuple(
        Pile(
            id=f"E{i + 1}",
            x=radius * math.cos(2.0 * math.pi * i / n),
            y=radius * math.sin(2.0 * math.pi * i / n),
            size=400.0,
        )
        for i in range(n)
    )
    if center:
        piles += (Pile(id=f"E{n + 1}", x=0.0, y=0.0, size=400.0),)
    side = 2.0 * radius + 1000.0
    return GeometryInput(
        cap=Cap(lx=side, ly=side, h=1300.0, pile_embedment=100.0),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=400.0, by=400.0),),
    )


def staggered_cap(
    rows: tuple[int, ...],
    column: tuple[float, float] = (800.0, 800.0),
    h: float = 1500.0,
    spacing: float = 1500.0,
) -> GeometryInput:
    """Estacas φ600 em fileiras desencontradas paralelas a x, em triângulo equilátero (D17).

    `rows` dá o número de estacas de cada fileira, de baixo para cima; cada fileira é centrada em
    x e as fileiras ficam a spacing·√3/2. Bloco com 750 mm de borda e pilar no centroide.
    """
    pitch = spacing * math.sqrt(3.0) / 2.0
    points = [
        ((i - (n - 1) / 2.0) * spacing, (j - (len(rows) - 1) / 2.0) * pitch)
        for j, n in enumerate(rows)
        for i in range(n)
    ]
    cy = sum(y for _, y in points) / len(points)
    return GeometryInput(
        cap=Cap(
            lx=(max(rows) - 1) * spacing + 1500.0,
            ly=(len(rows) - 1) * pitch + 1500.0,
            h=h,
            pile_embedment=100.0,
        ),
        piles=tuple(Pile(id=f"E{k + 1}", x=x, y=y, size=600.0) for k, (x, y) in enumerate(points)),
        columns=(Column(id="P1", x=0.0, y=cy, bx=column[0], by=column[1]),),
    )


def quadratic_tetra(sigma3: tuple[float, ...], case_id: str = "C1") -> FemField:
    """Campo do MEF com um único tetraedro quadrático (C3D10) de 1 m de aresta."""
    corners = [(0.0, 0.0, 0.0), (1000.0, 0.0, 0.0), (0.0, 1000.0, 0.0), (0.0, 0.0, 1000.0)]
    edges = [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]  # ordem do C3D10
    mids = [
        tuple((a + b) / 2 for a, b in zip(corners[i], corners[j], strict=True)) for i, j in edges
    ]
    nodes = [c for point in (*corners, *mids) for c in point]
    return FemField(
        case_id=case_id,
        nodes=tuple(nodes),
        tetrahedra=tuple(range(10)),
        displacements=(0.0,) * 30,
        sigma3=sigma3,
    )
