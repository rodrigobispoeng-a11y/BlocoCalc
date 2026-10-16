"""Cargas dos pilares como pressão na seção (D14, docs/02-metodos.md §4.5).

Em cada pilar, a normal vira pressão com distribuição linear (Navier) pelos momentos, e as forças
horizontais viram tração tangencial uniforme. As forças nodais são as consistentes com os
triângulos quadráticos, integradas por quadratura de grau 5 (exata para pressão linear).
"""

from __future__ import annotations

import numpy as np

from blococalc.fem.mesh import CapMesh, FloatArray
from blococalc.schemas import Column, ColumnLoad

# Quadratura de 7 pontos em triângulo (Dunavant, grau 5): coordenadas de área e pesos.
_A, _B = 0.059715871789770, 0.470142064105115
_C, _D = 0.797426985353087, 0.101286507323456
_POINTS = np.array(
    [
        (1 / 3, 1 / 3, 1 / 3),
        (_A, _B, _B),
        (_B, _A, _B),
        (_B, _B, _A),
        (_C, _D, _D),
        (_D, _C, _D),
        (_D, _D, _C),
    ]
)
_WEIGHTS = np.array([0.225, *([0.132394152788506] * 3), *([0.125939180544827] * 3)])


def _tri6_shape(l1: float, l2: float, l3: float) -> FloatArray:
    return np.array(
        [
            l1 * (2 * l1 - 1),
            l2 * (2 * l2 - 1),
            l3 * (2 * l3 - 1),
            4 * l1 * l2,
            4 * l2 * l3,
            4 * l3 * l1,
        ]
    )


def column_nodal_forces(
    mesh: CapMesh, columns: dict[str, Column], loads: list[ColumnLoad], factor: float
) -> FloatArray:
    """Forças nodais (n, 3) [N] das cargas dos pilares, multiplicadas por `factor` (γn, D7).

    Convenções do M1: compressão positiva em `n`; `my` comprime o lado +x e `mx` o lado +y;
    z do modelo aponta para cima.
    """
    forces = np.zeros_like(mesh.nodes)
    for load in loads:
        column = columns[load.column_id]
        area = column.bx * column.by
        ix, iy = column.by * column.bx**3 / 12, column.bx * column.by**3 / 12

        shear = np.array([load.hx, load.hy]) / area
        for tri in mesh.column_faces[column.id]:
            xyz = mesh.nodes[tri]
            corners = xyz[:3]
            jac = 0.5 * np.linalg.norm(np.cross(corners[1] - corners[0], corners[2] - corners[0]))
            for (l1, l2, l3), weight in zip(_POINTS, _WEIGHTS, strict=True):
                shape = _tri6_shape(l1, l2, l3)
                x, y, _ = l1 * corners[0] + l2 * corners[1] + l3 * corners[2]
                da = weight * jac
                pressure = (
                    load.n / area + load.my * (x - column.x) / ix + load.mx * (y - column.y) / iy
                )
                forces[tri, 2] -= factor * pressure * shape * da
                forces[tri, 0] += factor * shear[0] * shape * da
                forces[tri, 1] += factor * shear[1] * shape * da
    return forces
