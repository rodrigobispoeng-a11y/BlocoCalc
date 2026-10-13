"""Reações nas estacas de bloco rígido por equilíbrio estático (método M1, docs/02-metodos.md §4).

Premissas (registradas na trilha de auditoria pelo chamador):
- bloco infinitamente rígido e estacas verticais de mesma rigidez axial, de modo que a reação
  varia linearmente em planta: R(x, y) = a + b·x + c·y;
- convenção de sinais: compressão positiva; `my` comprime o lado +x e `mx` comprime o lado +y;
- forças horizontais atuam no topo do bloco e geram momento com braço igual à distância do topo
  do bloco ao plano das cabeças das estacas (h − embutimento). A força horizontal em si não é
  distribuída às estacas aqui;
- as cargas recebidas já são de cálculo (majoradas por γf). O coeficiente adicional γn é
  aplicado pelas verificações estruturais, não aqui.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from blococalc.schemas import GeometryInput, LoadCase, PileReaction

_REL_TOL = 1e-9
_COINCIDENT_MM2 = 1e-6  # dispersão abaixo disso: estacas no mesmo ponto


class UnbalancedMomentError(ValueError):
    """O estaqueamento não consegue equilibrar o momento aplicado sem elementos adicionais."""


@dataclass(frozen=True)
class AppliedResultant:
    """Resultante das ações em relação à origem do bloco.

    fz: força vertical total [N]; sx = Σ F·x + momentos que comprimem +x [N·mm];
    sy = Σ F·y + momentos que comprimem +y [N·mm].
    """

    fz: float
    sx: float
    sy: float


def applied_resultant(
    geometry: GeometryInput, case: LoadCase, self_weight: float = 0.0
) -> AppliedResultant:
    """Reduz as ações de um caso de carga à origem do bloco.

    `self_weight` é o peso próprio de cálculo do bloco [N], aplicado no centro do bloco
    (NBR 6122:2019, 5.6). Seu valor é calculado pelo chamador.
    """
    columns = {column.id: column for column in geometry.columns}
    arm = geometry.cap.h - geometry.cap.pile_embedment
    fz, sx, sy = self_weight, 0.0, 0.0
    for load in case.column_loads:
        column = columns.get(load.column_id)
        if column is None:
            raise ValueError(f"Caso {case.id}: pilar {load.column_id} não existe na geometria")
        fz += load.n
        sx += load.n * column.x + load.my + load.hx * arm
        sy += load.n * column.y + load.mx + load.hy * arm
    return AppliedResultant(fz=fz, sx=sx, sy=sy)


def rigid_cap_reactions(
    geometry: GeometryInput, case: LoadCase, self_weight: float = 0.0
) -> tuple[PileReaction, ...]:
    """Reações de cálculo nas estacas de um bloco rígido [N], compressão positiva.

    Resolve ΣR = Fz, ΣR·x = Sx e ΣR·y = Sy com R linear em planta. Estacas alinhadas só
    equilibram momento na direção do alinhamento; momento na direção perpendicular gera
    `UnbalancedMomentError` (ver NBR 6122:2019, 8.5.6.1: vigas de travamento).
    """
    resultant = applied_resultant(geometry, case, self_weight)
    xs = [pile.x for pile in geometry.piles]
    ys = [pile.y for pile in geometry.piles]
    forces = _linear_distribution(xs, ys, resultant)
    return tuple(
        PileReaction(pile_id=pile.id, case_id=case.id, force=force)
        for pile, force in zip(geometry.piles, forces, strict=True)
    )


def _linear_distribution(
    xs: Sequence[float], ys: Sequence[float], resultant: AppliedResultant
) -> list[float]:
    n = len(xs)
    xc, yc = sum(xs) / n, sum(ys) / n
    dx = [x - xc for x in xs]
    dy = [y - yc for y in ys]
    # Momentos de primeira ordem em relação ao centroide do estaqueamento.
    mx = resultant.sx - resultant.fz * xc
    my = resultant.sy - resultant.fz * yc
    ixx = sum(d * d for d in dx)
    iyy = sum(d * d for d in dy)
    ixy = sum(a * b for a, b in zip(dx, dy, strict=True))
    det = ixx * iyy - ixy * ixy
    scale = ixx + iyy
    mean = resultant.fz / n

    if scale < _COINCIDENT_MM2:
        _require_zero(math.hypot(mx, my), resultant.fz, 1.0, "estaca única")
        return [mean] * n

    if det > _REL_TOL * scale * scale:
        b = (mx * iyy - my * ixy) / det
        c = (my * ixx - mx * ixy) / det
        return [mean + b * u + c * v for u, v in zip(dx, dy, strict=True)]

    # Estacas alinhadas: direção do alinhamento pelo maior autovetor do tensor de inércia.
    angle = 0.5 * math.atan2(2.0 * ixy, ixx - iyy)
    ux, uy = math.cos(angle), math.sin(angle)
    t = [u * ux + v * uy for u, v in zip(dx, dy, strict=True)]
    itt = sum(value * value for value in t)
    _require_zero(-mx * uy + my * ux, resultant.fz, math.sqrt(itt / n), "estacas alinhadas")
    m_along = mx * ux + my * uy
    return [mean + m_along * value / itt for value in t]


def _require_zero(moment: float, force: float, length: float, layout: str) -> None:
    if abs(moment) > _REL_TOL * max(abs(force), 1.0) * max(length, 1.0):
        raise UnbalancedMomentError(
            f"Momento de {moment:.6g} N·mm sem rigidez para equilibrá-lo ({layout}). "
            "Preveja vigas de travamento (NBR 6122:2019, 8.5.6.1) ou altere o estaqueamento."
        )
