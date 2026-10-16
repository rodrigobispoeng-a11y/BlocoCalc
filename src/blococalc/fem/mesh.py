"""Malha de tetraedros quadráticos do bloco pelo gmsh (D14, docs/02-metodos.md §4.5).

O sólido é o prisma do bloco com a origem no centro em planta e z = 0 no fundo. As áreas das
cabeças das estacas (fundo) e das seções dos pilares (topo) entram como superfícies próprias,
para receber os apoios e as cargas. Unidades: mm.
"""

from __future__ import annotations

from dataclasses import dataclass

import gmsh
import numpy as np
import numpy.typing as npt

from blococalc.schemas import GeometryInput, PileShape

MESH_DIVISIONS = 10  # tamanho máximo = menor dimensão do bloco / 10 (D14)
_TOL_MM = 1e-3

IntArray = npt.NDArray[np.int64]
FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class CapMesh:
    nodes: FloatArray  # (n, 3) coordenadas [mm]
    tets: IntArray  # (m, 10) índices dos nós, ordem do CalculiX (C3D10)
    pile_nodes: dict[str, IntArray]  # nós na área da cabeça de cada estaca
    column_faces: dict[str, IntArray]  # (k, 6) triângulos quadráticos na seção de cada pilar
    size: float  # tamanho máximo dos elementos [mm]


def default_mesh_size(geometry: GeometryInput) -> float:
    cap = geometry.cap
    return min(cap.lx, cap.ly, cap.h) / MESH_DIVISIONS


def mesh_cap(geometry: GeometryInput, size: float | None = None) -> CapMesh:
    """Gera a malha C3D10 do bloco com as estacas e os pilares marcados."""
    cap = geometry.cap
    for pile in geometry.piles:
        half = pile.size / 2
        if abs(pile.x) + half > cap.lx / 2 + _TOL_MM or abs(pile.y) + half > cap.ly / 2 + _TOL_MM:
            raise ValueError(f"estaca {pile.id} fora do fundo do bloco")
    size = size or default_mesh_size(geometry)
    gmsh.initialize(readConfigFiles=False)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        occ = gmsh.model.occ
        box = occ.addBox(-cap.lx / 2, -cap.ly / 2, 0.0, cap.lx, cap.ly, cap.h)
        piles = {}
        for pile in geometry.piles:
            if pile.shape is PileShape.CIRCULAR:
                piles[pile.id] = occ.addDisk(pile.x, pile.y, 0.0, pile.size / 2, pile.size / 2)
            else:
                half = pile.size / 2
                piles[pile.id] = occ.addRectangle(
                    pile.x - half, pile.y - half, 0.0, pile.size, pile.size
                )
        columns = {
            c.id: occ.addRectangle(c.x - c.bx / 2, c.y - c.by / 2, cap.h, c.bx, c.by)
            for c in geometry.columns
        }
        tools = [(2, tag) for tag in (*piles.values(), *columns.values())]
        _, mapping = occ.fragment([(3, box)], tools)
        occ.synchronize()
        surface = {
            tag: [t for d, t in pieces if d == 2]
            for (_, tag), pieces in zip(tools, mapping[1:], strict=True)
        }
        gmsh.option.setNumber("Mesh.MeshSizeMax", size)
        gmsh.option.setNumber("Mesh.ElementOrder", 2)
        gmsh.model.mesh.generate(3)

        tags, coords, _ = gmsh.model.mesh.getNodes()
        index = {int(t): i for i, t in enumerate(tags)}
        nodes = np.asarray(coords, dtype=float).reshape(-1, 3)
        _, _, connectivity = gmsh.model.mesh.getElements(3)
        tets = _to_index(connectivity[0], index).reshape(-1, 10)[:, [0, 1, 2, 3, 4, 5, 6, 7, 9, 8]]
        pile_nodes = {
            pid: np.unique(np.concatenate([_surface_nodes(t, index) for t in surface[tag]]))
            for pid, tag in piles.items()
        }
        column_faces = {
            cid: np.concatenate([_surface_tri6(t, index) for t in surface[tag]])
            for cid, tag in columns.items()
        }
    finally:
        gmsh.finalize()
    return CapMesh(nodes, tets, pile_nodes, column_faces, size)


def _to_index(tags: npt.ArrayLike, index: dict[int, int]) -> IntArray:
    return np.fromiter((index[int(t)] for t in np.asarray(tags)), dtype=np.int64)


def _surface_nodes(tag: int, index: dict[int, int]) -> IntArray:
    tags, _, _ = gmsh.model.mesh.getNodes(2, tag, includeBoundary=True)
    return _to_index(tags, index)


def _surface_tri6(tag: int, index: dict[int, int]) -> IntArray:
    _, _, connectivity = gmsh.model.mesh.getElements(2, tag)
    return _to_index(connectivity[0], index).reshape(-1, 6)
