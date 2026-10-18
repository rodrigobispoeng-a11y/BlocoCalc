"""Geometria do modelo de bielas e tirantes para a visualização 3D (ADR-006)."""

from __future__ import annotations

import math

import pytest

from blococalc.analysis import analyze, strut_tie_layout
from blococalc.geometry.fictitious_column import fictitious_column
from blococalc.schemas import (
    Column,
    ColumnLoad,
    LayoutMemberKind,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Project,
)
from blococalc.standards.strength import strut_tie_strengths
from tests.factories import four_pile_cap, node_depth

C35 = MaterialsInput(fck=35.0)


def project(*normals: float) -> Project:
    loads = LoadsInput(
        cases=tuple(
            LoadCase(id=f"C{i + 1}", column_loads=(ColumnLoad(column_id="P1", n=n),))
            for i, n in enumerate(normals)
        )
    )
    return Project(name="B1", geometry=four_pile_cap(), materials=C35, loads=loads)


@pytest.mark.golden
def test_b1_layout_places_nodes_and_forces() -> None:
    # Mesmos números do golden de analyze(): Rd = 1,2·1,05·245 kN. D20: as bielas saem da camada
    # mais alta (tirantes em y, d′ = 58 + 16 = 74, d = 826), e o nó da estaca fica nela.
    layout = strut_tie_layout(project(980e3), "C1")
    assert layout is not None
    rd, d = 1.2 * 257.25e3, 826.0
    y = node_depth(d, 200.0, 2.0 * rd * 437.5 / strut_tie_strengths(C35).fcd1)
    z = d - y / 2.0
    nodes = {n.id: n for n in layout.nodes}
    members = {m.id: m for m in layout.members}

    assert layout.case_id == "C1"
    pile = nodes["estaca_E2"]
    assert (pile.x, pile.y, pile.z) == pytest.approx((600.0, -600.0, 100.0 + 74.0))
    top = nodes["topo_E2"]
    # Biela parte do centroide do quadrante do pilar 200×650 voltado para a estaca (D13).
    assert (top.x, top.y, top.z) == pytest.approx((50.0, -162.5, 1000.0 - y / 2.0))
    assert top.z - pile.z == pytest.approx(z)

    strut = members["biela_E2"]
    assert strut.kind is LayoutMemberKind.STRUT
    assert (strut.start, strut.end) == ("topo_E2", "estaca_E2")
    length = math.dist((top.x, top.y, top.z), (pile.x, pile.y, pile.z))
    assert strut.force_d == pytest.approx(rd * length / z, rel=1e-6)

    tie = members["tirante_E1_E2"]  # em x, na 1ª camada: d = 842
    z1 = 842.0 - node_depth(842.0, 200.0, 2.0 * rd * 437.5 / strut_tie_strengths(C35).fcd1) / 2.0
    assert tie.kind is LayoutMemberKind.TIE
    assert tie.force_d == pytest.approx(rd * 550.0 / z1, rel=1e-6)
    assert members["tirante_E2_E3"].force_d == pytest.approx(rd * 437.5 / z, rel=1e-6)
    assert len([m for m in layout.members if m.kind is LayoutMemberKind.STRUT]) == 4
    assert len([m for m in layout.members if m.kind is LayoutMemberKind.TIE]) == 4


def test_tie_forces_match_the_design_result() -> None:
    saved = project(980e3)
    layout = strut_tie_layout(saved, "C1")
    assert layout is not None
    design = analyze(saved.geometry, saved.materials, saved.loads, saved.detailing)
    items = {r.id: r.force_d for r in design.reinforcement}
    for member in layout.members:
        if member.kind is LayoutMemberKind.TIE:
            assert member.force_d == pytest.approx(items[member.id])


def test_each_case_has_its_own_forces() -> None:
    saved = project(980e3, 490e3)
    first, second = strut_tie_layout(saved, "C1"), strut_tie_layout(saved, "C2")
    assert first is not None and second is not None
    assert second.case_id == "C2"
    assert {n.id for n in first.nodes} == {n.id for n in second.nodes}
    assert second.members[0].force_d < first.members[0].force_d


def test_every_member_joins_existing_nodes() -> None:
    layout = strut_tie_layout(project(980e3), "C1")
    assert layout is not None
    ids = {n.id for n in layout.nodes}
    assert all({m.start, m.end} <= ids for m in layout.members)


def test_flexible_cap_has_no_layout() -> None:
    saved = project(980e3)
    shallow = saved.geometry.model_copy(
        update={"cap": saved.geometry.cap.model_copy(update={"h": 400.0})}
    )
    assert strut_tie_layout(saved.model_copy(update={"geometry": shallow}), "C1") is None


def test_several_columns_use_the_fictitious_column() -> None:
    saved = project(800e3)
    columns = (
        Column(id="P1", x=-300.0, y=0.0, bx=200.0, by=200.0),
        Column(id="P2", x=300.0, y=0.0, bx=200.0, by=200.0),
    )
    case = LoadCase(
        id="C1",
        column_loads=(ColumnLoad(column_id="P1", n=500e3), ColumnLoad(column_id="P2", n=300e3)),
    )
    several = saved.model_copy(
        update={
            "geometry": saved.geometry.model_copy(update={"columns": columns}),
            "loads": LoadsInput(cases=(case,)),
        }
    )
    layout = strut_tie_layout(several, "C1")
    assert layout is not None
    column, _ = fictitious_column(columns, case, several.geometry.cap)
    tops = [n for n in layout.nodes if n.id.startswith("topo_")]
    # As bielas partem de dentro do pilar fictício, deslocado para P1 (mais carregado).
    assert column.x < 0.0
    for top in tops:
        assert abs(top.x - column.x) <= column.bx / 2.0
        assert abs(top.y - column.y) <= column.by / 2.0


def test_unknown_case_raises() -> None:
    with pytest.raises(ValueError, match="X9"):
        strut_tie_layout(project(980e3), "X9")
