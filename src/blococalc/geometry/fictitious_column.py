"""Pilar fictício de área equivalente para blocos com vários pilares (M8, decisão D10 proposta).

Regra proposta (docs/02-metodos.md, M8):
- área do pilar fictício = soma das áreas dos pilares reais, para não diluir a tensão no nó;
- proporção dos lados pelos momentos de segunda ordem da área do grupo em relação ao seu
  centroide: para um retângulo, S = A·b²/12, logo bx/by = √(Sx/Sy);
- posição na resultante das forças normais do caso, para não criar excentricidade falsa entre a
  carga e o pilar; os momentos e as forças horizontais dos pilares são somados;
- lados limitados às dimensões do bloco.

A referência (Macedo, Pilares Associados, eq. 5.7) escreve η = Ix/Iy para a proporção dos lados;
dimensionalmente a razão entre lados é √(Ix/Iy), que é o que se usa aqui.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from blococalc.schemas import Cap, Column, ColumnLoad, LoadCase

FICTITIOUS_ID = "PF"


def fictitious_column(
    columns: Sequence[Column], case: LoadCase, cap: Cap
) -> tuple[Column, ColumnLoad]:
    """Pilar fictício e sua carga de cálculo para um caso; um único pilar volta inalterado."""
    loads = {load.column_id: load for load in case.column_loads}
    if len(columns) == 1:
        column = columns[0]
        return column, loads[column.id]
    area = sum(c.bx * c.by for c in columns)
    xg = sum(c.bx * c.by * c.x for c in columns) / area
    yg = sum(c.bx * c.by * c.y for c in columns) / area
    sx = sum(c.bx * c.by * (c.bx**2 / 12.0 + (c.x - xg) ** 2) for c in columns)
    sy = sum(c.bx * c.by * (c.by**2 / 12.0 + (c.y - yg) ** 2) for c in columns)
    bx = min(math.sqrt(area * math.sqrt(sx / sy)), cap.lx)
    by = min(area / bx, cap.ly)

    acting = [(c, loads[c.id]) for c in columns if c.id in loads]
    n = sum(load.n for _, load in acting)
    if n <= 0.0:
        raise ValueError(f"Caso {case.id}: resultante normal dos pilares ≤ 0")
    x = sum(load.n * c.x for c, load in acting) / n
    y = sum(load.n * c.y for c, load in acting) / n
    load = ColumnLoad(
        column_id=FICTITIOUS_ID,
        n=n,
        mx=sum(item.mx for _, item in acting),
        my=sum(item.my for _, item in acting),
        hx=sum(item.hx for _, item in acting),
        hy=sum(item.hy for _, item in acting),
    )
    return Column(id=FICTITIOUS_ID, x=x, y=y, bx=bx, by=by), load
