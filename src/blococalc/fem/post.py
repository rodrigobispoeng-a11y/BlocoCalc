"""Pós-processamento do MEF para conferir o M5 (D14, docs/02-metodos.md §4.5).

As tensões nodais do CalculiX são interpoladas linearmente (triangulação de Delaunay dos nós)
e integradas em grades regulares: tração em planos verticais e médias da tensão principal de
compressão nos volumes dos nós. Tensões em MPa, forças em N, comprimentos em mm.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from scipy.interpolate import LinearNDInterpolator

from blococalc.fem.ccx import FemResult
from blococalc.fem.mesh import CapMesh, FloatArray
from blococalc.schemas import FemField

_CELLS = 10  # pontos por direção nas médias de volume


class StressField:
    """Tensões normais σxx, σyy e a principal mínima σ3 em qualquer ponto do bloco."""

    def __init__(self, mesh: CapMesh, result: FemResult) -> None:
        s = result.stresses
        self._interpolate = LinearNDInterpolator(
            mesh.nodes, np.column_stack([s[:, 0], s[:, 1], minimum_principal(s)])
        )

    def __call__(self, points: FloatArray) -> FloatArray:
        """(k, 3) colunas σxx, σyy e σ3 [MPa]; NaN fora do bloco."""
        values: FloatArray = self._interpolate(points)
        return values


def minimum_principal(stresses: FloatArray) -> FloatArray:
    """σ3, a menor tensão principal de cada linha xx, yy, zz, xy, yz, zx [MPa]."""
    s = stresses
    tensors = np.stack(
        [
            np.stack([s[:, 0], s[:, 3], s[:, 5]], axis=1),
            np.stack([s[:, 3], s[:, 1], s[:, 4]], axis=1),
            np.stack([s[:, 5], s[:, 4], s[:, 2]], axis=1),
        ],
        axis=1,
    )
    sigma3: FloatArray = np.linalg.eigvalsh(tensors)[:, 0]
    return sigma3


def fem_field(mesh: CapMesh, result: FemResult, case_id: str) -> FemField:
    """Contrato do campo de um caso para a aba 3D (ADR-012)."""
    return FemField(
        case_id=case_id,
        nodes=tuple(mesh.nodes.ravel().tolist()),
        tetrahedra=tuple(mesh.tets.ravel().tolist()),
        displacements=tuple(result.displacements.ravel().tolist()),
        sigma3=tuple(minimum_principal(result.stresses).tolist()),
    )


def pile_reactions(
    mesh: CapMesh, result: FemResult, stiffness: Mapping[str, float] | None = None
) -> dict[str, float]:
    """Reação vertical de cada estaca, positiva em compressão [N].

    Apoio rígido: soma das reações nodais da cabeça. Mola (D16): −k·uz da cabeça rígida, porque
    o CalculiX não devolve reação nos nós ligados por equação.
    """
    springs = stiffness or {}
    return {
        pid: (
            -springs[pid] * float(result.displacements[nodes, 2].mean())
            if pid in springs
            else float(result.reactions[nodes, 2].sum())
        )
        for pid, nodes in mesh.pile_nodes.items()
    }


def section_tension(
    field: StressField, axis: int, coordinate: float, extent: tuple[float, float], cell: float
) -> float:
    """Resultante de tração no plano vertical `axis` = `coordinate` (0: x, 1: y) [N].

    Soma das tensões normais positivas ao plano em toda a seção do bloco (`extent` = largura ×
    altura), em células de lado ≈ `cell` (Bavaresco 2016, §3.4).
    """
    width, height = extent
    nt, nz = max(int(np.ceil(width / cell)), 1), max(int(np.ceil(height / cell)), 1)
    t = (np.arange(nt) + 0.5) * width / nt - width / 2.0
    z = (np.arange(nz) + 0.5) * height / nz
    tt, zz = np.meshgrid(t, z)
    points = np.zeros((tt.size, 3))
    points[:, axis] = coordinate
    points[:, 1 - axis] = tt.ravel()
    points[:, 2] = zz.ravel()
    normal = field(points)[:, axis]
    return float(np.nansum(np.clip(normal, 0.0, None)) * (width / nt) * (height / nz))


def mean_compression(
    field: StressField,
    center: tuple[float, float],
    half: tuple[float, float],
    z_range: tuple[float, float],
    circular: bool = False,
) -> float:
    """Média de −σ3 (compressão positiva) no prisma ou cilindro dado [MPa]."""
    u = (np.arange(_CELLS) + 0.5) / _CELLS * 2.0 - 1.0
    w = (np.arange(_CELLS) + 0.5) / _CELLS
    gu, gv, gw = (a.ravel() for a in np.meshgrid(u, u, w))
    if circular:
        inside = gu**2 + gv**2 <= 1.0
        gu, gv, gw = gu[inside], gv[inside], gw[inside]
    points = np.column_stack(
        [
            center[0] + gu * half[0],
            center[1] + gv * half[1],
            z_range[0] + gw * (z_range[1] - z_range[0]),
        ]
    )
    return float(-np.nanmean(field(points)[:, 2]))
