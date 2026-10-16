"""Adaptadores do MEF: malha gmsh e cargas dos pilares (D14, docs/02-metodos.md §4.5)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("gmsh")

from blococalc.fem.loads import column_nodal_forces
from blococalc.fem.mesh import CapMesh, default_mesh_size, mesh_cap
from blococalc.schemas import Cap, ColumnLoad, GeometryInput, PileShape
from tests.factories import four_pile_cap

COARSE = 200.0


@pytest.fixture(scope="module")
def b1() -> tuple[GeometryInput, CapMesh]:
    geometry = four_pile_cap()
    return geometry, mesh_cap(geometry, COARSE)


def face_area(mesh: CapMesh, column_id: str) -> float:
    xyz = mesh.nodes[mesh.column_faces[column_id][:, :3]]
    return float(
        0.5 * np.linalg.norm(np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0]), axis=1).sum()
    )


def test_mesh_marks_piles_and_column(b1: tuple[GeometryInput, CapMesh]) -> None:
    geometry, mesh = b1
    assert default_mesh_size(geometry) == 100.0
    assert mesh.tets.shape[1] == 10
    for pile in geometry.piles:
        xyz = mesh.nodes[mesh.pile_nodes[pile.id]]
        assert np.allclose(xyz[:, 2], 0.0)
        assert np.hypot(xyz[:, 0] - pile.x, xyz[:, 1] - pile.y).max() <= pile.size / 2 + 1e-6
    faces = mesh.nodes[mesh.column_faces["P1"]]
    assert np.allclose(faces[..., 2], 1000.0)
    assert face_area(mesh, "P1") == pytest.approx(200.0 * 650.0, rel=1e-9)


def test_tets_follow_calculix_order(b1: tuple[GeometryInput, CapMesh]) -> None:
    # C3D10: nós 8, 9 e 10 no meio das arestas 1-4, 2-4 e 3-4.
    _, mesh = b1
    xyz = mesh.nodes[mesh.tets[:50]]
    for mid, corner in ((7, 0), (8, 1), (9, 2)):
        assert np.allclose(xyz[:, mid], (xyz[:, corner] + xyz[:, 3]) / 2, atol=1e-6)


def test_pile_outside_cap_bottom_is_rejected() -> None:
    geometry = four_pile_cap()
    narrow = geometry.model_copy(
        update={"cap": Cap(lx=1300.0, ly=1300.0, h=1000.0, pile_embedment=100.0)}
    )
    with pytest.raises(ValueError, match="estaca"):
        mesh_cap(narrow, COARSE)


def test_column_forces_match_load_resultants(b1: tuple[GeometryInput, CapMesh]) -> None:
    geometry, mesh = b1
    load = ColumnLoad(column_id="P1", n=1e6, mx=40e6, my=-25e6, hx=30e3, hy=-20e3)
    forces = column_nodal_forces(mesh, {"P1": geometry.columns[0]}, [load], 1.26)
    total = forces.sum(axis=0)
    assert total == pytest.approx(1.26 * np.array([30e3, -20e3, -1e6]))
    x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]
    # my comprime o lado +x e mx o lado +y (convenção do M1): Σ(−fz)·x = my e Σ(−fz)·y = mx.
    assert float(-(forces[:, 2] * x).sum()) == pytest.approx(1.26 * -25e6, rel=1e-9)
    assert float(-(forces[:, 2] * y).sum()) == pytest.approx(1.26 * 40e6, rel=1e-9)


def test_square_piles_are_meshed() -> None:
    geometry = four_pile_cap()
    square = geometry.model_copy(
        update={
            "piles": tuple(p.model_copy(update={"shape": PileShape.SQUARE}) for p in geometry.piles)
        }
    )
    mesh = mesh_cap(square, 250.0)
    xyz = mesh.nodes[mesh.pile_nodes["E1"]]
    assert np.abs(xyz[:, :2] - (-600.0, -600.0)).max() == pytest.approx(200.0)
