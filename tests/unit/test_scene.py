"""Cena 3D do bloco e do modelo de bielas e tirantes (ADR-006)."""

from __future__ import annotations

import pytest

pytest.importorskip("pyvista")

import pyvista as pv

from blococalc.analysis import strut_tie_layout
from blococalc.schemas import (
    ColumnLoad,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    PileReaction,
    PileShape,
    Project,
    StrutTieLayout,
)
from blococalc.viz.scene import (
    CAP_OPACITY,
    COLUMN_COLOR,
    COMPRESSION,
    COMPRESSION_COLOR,
    NEUTRAL_COLOR,
    STRESS_BANDS,
    STRUT_COLOR,
    TENSION_COLOR,
    TIE_COLOR,
    cap_scene,
    draw,
    stress_scene,
)
from tests.factories import four_pile_cap, quadratic_tetra

GEOMETRY = four_pile_cap()
REACTIONS = tuple(
    PileReaction(pile_id=pile_id, case_id="C1", force=force)
    for pile_id, force in (("E1", 300e3), ("E2", 200e3), ("E3", 100e3), ("E4", -50e3))
)


def b1_layout() -> StrutTieLayout:
    case = LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=980e3),))
    saved = Project(
        name="B1",
        geometry=GEOMETRY,
        materials=MaterialsInput(fck=35.0),
        loads=LoadsInput(cases=(case,)),
    )
    layout = strut_tie_layout(saved, "C1")
    assert layout is not None
    return layout


def test_cap_columns_and_piles_follow_the_geometry() -> None:
    scene = cap_scene(GEOMETRY, REACTIONS, None)
    cap = scene.item("bloco")
    assert cap.mesh.bounds == pytest.approx((-1000.0, 1000.0, -1000.0, 1000.0, 0.0, 1000.0))
    assert cap.opacity == CAP_OPACITY < 1.0
    pile = scene.item("estaca_E1").mesh.bounds
    assert pile[:4] == pytest.approx((-800.0, -400.0, -800.0, -400.0), abs=1.0)
    assert pile[5] == pytest.approx(100.0)  # cabeça no embutimento
    column = scene.item("pilar_P1").mesh.bounds
    assert column[:4] == pytest.approx((-100.0, 100.0, -325.0, 325.0))
    assert column[4] == pytest.approx(1000.0)


def test_piles_are_colored_by_reaction() -> None:
    scene = cap_scene(GEOMETRY, REACTIONS, None)
    colors = {i: scene.item(f"estaca_{i}").color for i in ("E1", "E2", "E3", "E4")}
    assert colors["E1"] == pytest.approx(COMPRESSION_COLOR)
    assert colors["E4"] != pytest.approx(NEUTRAL_COLOR)
    assert colors["E4"] == pytest.approx(
        tuple(n + (t - n) * 50 / 300 for n, t in zip(NEUTRAL_COLOR, TENSION_COLOR, strict=True))
    )
    assert colors["E2"] == pytest.approx(
        tuple(n + (c - n) * 2 / 3 for n, c in zip(NEUTRAL_COLOR, COMPRESSION_COLOR, strict=True))
    )


def test_piles_without_reaction_are_neutral() -> None:
    scene = cap_scene(GEOMETRY, (), None)
    assert scene.item("estaca_E1").color == pytest.approx(NEUTRAL_COLOR)


def test_without_layout_there_are_no_members() -> None:
    names = [item.name for item in cap_scene(GEOMETRY, REACTIONS, None).items]
    assert not [n for n in names if n.startswith(("biela_", "tirante_"))]


def test_struts_and_ties_join_their_nodes() -> None:
    layout = b1_layout()
    scene = cap_scene(GEOMETRY, REACTIONS, layout)
    nodes = {n.id: n for n in layout.nodes}
    struts = [i for i in scene.items if i.name.startswith("biela_")]
    ties = [i for i in scene.items if i.name.startswith("tirante_")]
    assert len(struts) == 4 and len(ties) == 4
    assert all(i.color == STRUT_COLOR for i in struts)
    assert all(i.color == TIE_COLOR for i in ties)
    bounds = scene.item("biela_E2").mesh.bounds
    top, pile = nodes["topo_E2"], nodes["estaca_E2"]
    radius = scene.radius("biela_E2")
    assert bounds[4] == pytest.approx(pile.z, abs=radius)
    assert bounds[5] == pytest.approx(top.z, abs=radius)
    assert bounds[1] == pytest.approx(pile.x, abs=radius)


def test_thickness_grows_with_force() -> None:
    layout = b1_layout()
    scene = cap_scene(GEOMETRY, REACTIONS, layout)
    forces = {m.id: m.force_d for m in layout.members}
    # Tirante em x (E1-E2) é mais forte que em y (E2-E3) no B1; área proporcional à força.
    assert forces["tirante_E1_E2"] > forces["tirante_E2_E3"]
    ratio = scene.radius("tirante_E1_E2") / scene.radius("tirante_E2_E3")
    assert ratio == pytest.approx((forces["tirante_E1_E2"] / forces["tirante_E2_E3"]) ** 0.5)
    strongest = max(forces, key=lambda k: forces[k])
    assert scene.radius(strongest) == pytest.approx(0.04 * 2000.0)


def test_unknown_item_raises() -> None:
    with pytest.raises(KeyError, match="nada"):
        cap_scene(GEOMETRY, REACTIONS, None).item("nada")


def test_square_pile_is_a_prism() -> None:
    square = GEOMETRY.piles[0].model_copy(update={"shape": PileShape.SQUARE})
    geometry = GEOMETRY.model_copy(update={"piles": (square, *GEOMETRY.piles[1:])})
    bounds = cap_scene(geometry, REACTIONS, None).item("estaca_E1").mesh.bounds
    assert bounds == pytest.approx((-800.0, -400.0, -800.0, -400.0, -1500.0, 100.0))


def test_members_without_force_keep_the_minimum_radius() -> None:
    layout = b1_layout()
    idle = layout.model_copy(
        update={"members": tuple(m.model_copy(update={"force_d": 0.0}) for m in layout.members)}
    )
    scene = cap_scene(GEOMETRY, REACTIONS, idle)
    assert scene.radius("biela_E1") == pytest.approx(0.2 * 0.04 * 2000.0)


def test_stress_scene_paints_compression_in_bands() -> None:
    # ADR-012: compressão = −σ3 sem a tração, 12 faixas de 0 ao máximo do caso.
    sigma3 = (-8.0, -2.0, 1.5, 0.0, -4.0, -1.0, 0.5, -3.0, -6.0, -0.5)
    scene = stress_scene(GEOMETRY, quadratic_tetra(sigma3))
    item = scene.item("tensoes")
    grid = item.mesh
    assert isinstance(grid, pv.UnstructuredGrid)
    assert grid.n_cells == 1
    assert grid.celltypes[0] == pv.CellType.QUADRATIC_TETRA
    assert item.scalars == COMPRESSION
    assert list(grid.point_data[COMPRESSION]) == pytest.approx(
        [8.0, 2.0, 0.0, 0.0, 4.0, 1.0, 0.0, 3.0, 6.0, 0.5]
    )
    assert item.clim == (0.0, 8.0)
    assert item.bands == STRESS_BANDS == 12
    assert scene.peak == 8.0
    # Pilares e estacas em cinza, sem treliça e sem bloco translúcido.
    assert scene.item("pilar_P1").color == COLUMN_COLOR
    assert scene.item("estaca_E1").color == NEUTRAL_COLOR
    assert {i.name for i in scene.items} == {"tensoes", "pilar_P1", "estaca_E1", "estaca_E2",
                                             "estaca_E3", "estaca_E4"}  # fmt: skip


def test_field_without_compression_keeps_a_valid_range() -> None:
    scene = stress_scene(GEOMETRY, quadratic_tetra((1.0,) * 10))
    assert scene.peak == 0.0
    assert scene.item("tensoes").clim == (0.0, 1.0)


class RecordingPlotter:
    def __init__(self) -> None:
        self.calls: dict[str, dict[str, object]] = {}

    def add_mesh(self, mesh: object, **options: object) -> None:
        self.calls[str(options["name"])] = options


def test_draw_paints_scalars_and_colors_the_rest() -> None:
    plotter = RecordingPlotter()
    draw(plotter, stress_scene(GEOMETRY, quadratic_tetra((-8.0,) * 10)))
    painted = plotter.calls["tensoes"]
    assert painted["scalars"] == COMPRESSION
    assert painted["n_colors"] == 12
    assert painted["clim"] == (0.0, 8.0)
    assert "color" not in painted
    assert plotter.calls["estaca_E1"]["color"] == NEUTRAL_COLOR
    draw(plotter, cap_scene(GEOMETRY, REACTIONS, None))
    assert plotter.calls["bloco"]["opacity"] == CAP_OPACITY
    assert "scalars" not in plotter.calls["bloco"]
