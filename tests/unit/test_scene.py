"""Cena 3D do bloco e do modelo de bielas e tirantes (ADR-006)."""

from __future__ import annotations

import pytest

pytest.importorskip("pyvista")

import pyvista as pv

from blococalc import analysis
from blococalc.analysis import analyze, strut_tie_layout
from blococalc.schemas import (
    ColumnLoad,
    DetailingInput,
    LayoutMemberKind,
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
    CUT_OPACITY,
    DIMENSION_COLOR,
    LABEL_COLOR,
    NEUTRAL_COLOR,
    STRESS_BANDS,
    STRUT_COLOR,
    TENSION_COLOR,
    TF,
    TIE_COLOR,
    CapScene,
    StressView,
    TrussLoads,
    cap_scene,
    draw,
    labeled,
    stress_scene,
    value_at,
)
from tests.factories import box_field, four_pile_cap, quadratic_tetra

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
        self.texts: list[str] = []

    def add_mesh(self, mesh: object, **options: object) -> None:
        self.calls[str(options["name"])] = options

    def add_point_labels(self, points: object, labels: object, **options: object) -> None:
        assert isinstance(labels, list)
        self.texts += labels
        self.calls[str(options["name"])] = {"points": points, **options}


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


# --------------------------------------------------------------------------------------
# Ferramentas do visualizador (ADR-013)
# --------------------------------------------------------------------------------------

BOX = box_field(2000.0, 2000.0, 1000.0)  # B1: σ3 = −z/100, uz = −z/1000


def painted(view: StressView) -> pv.DataSet:
    return stress_scene(GEOMETRY, BOX, view).item("tensoes").mesh


def test_box_field_is_a_valid_c3d10_mesh() -> None:
    grid = painted(StressView())
    assert grid.n_cells == 6 * 8
    assert grid.volume == pytest.approx(2000.0 * 2000.0 * 1000.0)
    assert grid.bounds[4:6] == pytest.approx((0.0, 1000.0))


def test_cut_x_keeps_the_side_before_the_plane() -> None:
    grid = painted(StressView(cut_x=500.0))
    assert grid.bounds[0:2] == pytest.approx((-1000.0, 500.0))
    assert grid.bounds[2:4] == pytest.approx((-1000.0, 1000.0))
    assert grid.volume == pytest.approx(1500.0 * 2000.0 * 1000.0, rel=1e-6)


def test_both_cuts_keep_the_corner() -> None:
    scene = stress_scene(GEOMETRY, BOX, StressView(cut_x=0.0, cut_y=-200.0))
    grid = scene.item("tensoes").mesh
    assert grid.bounds[1] == pytest.approx(0.0)
    assert grid.bounds[3] == pytest.approx(-200.0)
    # O que não é cortado fica translúcido para mostrar a face cortada.
    assert scene.item("pilar_P1").opacity == CUT_OPACITY
    assert scene.item("estaca_E1").opacity == CUT_OPACITY
    assert stress_scene(GEOMETRY, BOX).item("estaca_E1").opacity == 1.0


def test_cut_face_shows_the_interior_values() -> None:
    grid = painted(StressView(cut_x=0.0))
    on_face = abs(grid.points[:, 0]) < 1e-6
    assert on_face.sum() > 0
    z = grid.points[on_face, 2]
    assert grid.point_data[COMPRESSION][on_face] == pytest.approx(z / 100.0)


def test_cut_beyond_the_block_keeps_everything_and_cut_before_it_empties() -> None:
    assert painted(StressView(cut_x=5000.0)).n_cells == 48
    scene = stress_scene(GEOMETRY, BOX, StressView(cut_x=-5000.0))
    assert scene.item("tensoes").mesh.n_points == 0
    assert scene.peak == pytest.approx(10.0)  # o pico é do caso, não do que sobrou


def test_deformation_moves_nodes_after_the_cut_and_reports_the_real_displacement() -> None:
    scene = stress_scene(GEOMETRY, BOX, StressView(cut_x=0.0, deformation=100.0))
    grid = scene.item("tensoes").mesh
    assert grid.bounds[1] == pytest.approx(0.0)  # corte na posição original
    assert grid.bounds[5] == pytest.approx(1000.0 - 100.0 * 1.0)  # topo desce 100 × 1 mm
    assert scene.displacement == pytest.approx(1.0)


def test_scale_max_and_opacity() -> None:
    scene = stress_scene(GEOMETRY, BOX, StressView(opacity=0.4, scale_max=5.0))
    item = scene.item("tensoes")
    assert item.clim == (0.0, 5.0)
    assert item.opacity == 0.4
    assert scene.peak == pytest.approx(10.0)


@pytest.mark.parametrize(
    "view",
    [{"opacity": 0.05}, {"opacity": 1.5}, {"scale_max": 0.0}, {"deformation": -1.0}],
)
def test_invalid_view_is_refused(view: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        StressView(**view)


def test_value_at_returns_the_nearest_node_in_original_position() -> None:
    scene = stress_scene(GEOMETRY, BOX, StressView(deformation=100.0))
    # Topo deformado está em z = 900; o clique ali acha o nó original do topo.
    probe = value_at(scene, (1000.0, 1000.0, 905.0))
    assert probe is not None
    assert probe.position == pytest.approx((1000.0, 1000.0, 1000.0))
    assert probe.sigma3 == pytest.approx(-10.0)
    assert probe.compression == pytest.approx(10.0)
    assert probe.displacement == pytest.approx(1.0)
    assert probe.text() == (
        "σ3 = -10.00 MPa (compressão 10.00 MPa), u = 1.000 mm em x = 1000, y = 1000, z = 1000 mm"
    )


def test_value_at_without_field_or_with_everything_cut() -> None:
    assert value_at(cap_scene(GEOMETRY, REACTIONS, None), (0.0, 0.0, 0.0)) is None
    empty = stress_scene(GEOMETRY, BOX, StressView(cut_x=-5000.0))
    assert value_at(empty, (0.0, 0.0, 0.0)) is None


def test_value_at_in_tension_says_so() -> None:
    scene = stress_scene(GEOMETRY, quadratic_tetra((0.5,) * 10))
    probe = value_at(scene, (0.0, 0.0, 0.0))
    assert probe is not None
    assert probe.compression == 0.0
    assert probe.text().startswith("σ3 = 0.50 MPa (tração)")


# --------------------------------------------------------------------------------------
# Rótulos da treliça (ADR-014)
# --------------------------------------------------------------------------------------


def b1_labels(unit: str = "kN", nk: float | None = 700e3) -> tuple[CapScene, StrutTieLayout]:
    loads = LoadsInput(
        cases=(LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=980e3, nk=nk),)),)
    )
    materials = MaterialsInput(fck=35.0)
    project = Project(
        name="B1",
        geometry=GEOMETRY,
        materials=materials,
        loads=loads,
        result=analyze(GEOMETRY, materials, loads, DetailingInput()),
    )
    layout = strut_tie_layout(project, "C1")
    assert layout is not None and project.result is not None
    rk = analysis.characteristic_reactions(project, "C1")
    truss = TrussLoads(loads.cases[0], loads.gamma_n, project.result.reactions, rk)
    scene = cap_scene(GEOMETRY, project.result.reactions, layout)
    return labeled(scene, GEOMETRY, truss, layout, unit), layout


def texts(scene: CapScene) -> list[str]:
    return [label.text for label in scene.labels]


def test_every_member_gets_its_design_force_in_its_color() -> None:
    scene, layout = b1_labels()
    members = [label for label in scene.labels if label.color in (STRUT_COLOR, TIE_COLOR)]
    assert len(members) == len(layout.members)
    strut = next(m for m in layout.members if m.kind is LayoutMemberKind.STRUT)
    assert f"{strut.force_d / 1e3:.1f} kN" in texts(scene)
    nodes = {n.id: n for n in layout.nodes}
    a, b = nodes[strut.start], nodes[strut.end]
    middle = ((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2)
    assert any(label.position == pytest.approx(middle) for label in members)


def test_column_and_pile_labels_show_characteristic_and_design_values() -> None:
    # B1: Fd = 980 kN, Nd = 1,2 × 980 = 1176 kN; Rd = 980 × 1,05 / 4 = 257,25 kN (D7);
    # Rk = 700 × 1,05 / 4 = 183,75 kN.
    scene, _ = b1_labels()
    assert "P1\nNk = 700.0 kN\nFd = 980.0 kN\nNd = 1176.0 kN" in texts(scene)
    assert "E1\nRk = 183.8 kN\nRd = 257.2 kN" in texts(scene)
    without, _ = b1_labels(nk=None)
    assert "P1\nFd = 980.0 kN\nNd = 1176.0 kN" in texts(without)
    assert "E1\nRd = 257.2 kN" in texts(without)


def test_forces_in_tf() -> None:
    scene, _ = b1_labels("tf")
    assert f"P1\nNk = {700e3 / TF:.1f} tf\nFd = 99.9 tf\nNd = 119.9 tf" in texts(scene)
    with pytest.raises(ValueError, match="unidade"):
        b1_labels("kgf")


def test_dimensions_h_d_and_d_prime() -> None:
    scene, layout = b1_labels()
    d_prime = min(n.z for n in layout.nodes if n.id.startswith("estaca_"))
    assert "h = 1000 mm" in texts(scene)
    assert f"d' = {d_prime:.0f} mm" in texts(scene)
    assert f"d = {1000.0 - d_prime:.0f} mm" in texts(scene)
    line = scene.item("cota_d").mesh
    assert line.bounds[4:6] == pytest.approx((d_prime, 1000.0))
    assert line.bounds[0] > 1000.0  # fora do bloco, na aresta da frente da isométrica


def test_flexible_cap_has_loads_reactions_and_h_only() -> None:
    loads = TrussLoads(LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=980e3),)),
                       1.2, REACTIONS)  # fmt: skip
    scene = labeled(cap_scene(GEOMETRY, REACTIONS, None), GEOMETRY, loads, None)
    assert [t.split(" =")[0] for t in texts(scene) if " mm" in t] == ["h"]
    assert {i.name for i in scene.items} >= {"cota_h"}
    assert not any(i.name == "cota_d" for i in scene.items)


def test_draw_groups_labels_by_color() -> None:
    plotter = RecordingPlotter()
    scene, _ = b1_labels()
    draw(plotter, scene)
    groups = {k: v for k, v in plotter.calls.items() if k.startswith("rotulos_")}
    assert {v["text_color"] for v in groups.values()} == {
        STRUT_COLOR,
        TIE_COLOR,
        LABEL_COLOR,
        DIMENSION_COLOR,
    }
    assert sorted(plotter.texts) == sorted(texts(scene))
    assert all(v["always_visible"] for v in groups.values())
