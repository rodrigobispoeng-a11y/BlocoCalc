"""Desenhos SVG do memorial (ADR-008): conferidos como texto, sem renderizar."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from blococalc.analysis import analyze, strut_tie_layout
from blococalc.report.drawings import (
    DIMENSION_LAYER,
    FORM_LAYER,
    MESH_COLOR,
    MESH_LAYER,
    PILE_LAYER,
    STRUT_COLOR,
    TEXT_LAYER,
    TIE_COLOR,
    TIE_LAYER,
    Circle,
    Line,
    Mask,
    Text,
    form_plan,
    form_plan_sheet,
    form_section,
    form_section_sheet,
    model_plan,
    model_section,
    reinforcement_plan,
    reinforcement_plan_sheet,
    reinforcement_section,
    reinforcement_section_sheet,
)
from blococalc.schemas import (
    ColumnLoad,
    DetailingInput,
    LayoutMemberKind,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Project,
    StrutTieLayout,
)
from tests.factories import four_pile_cap, quincunx_cap

SVG = "{http://www.w3.org/2000/svg}"


def b1() -> tuple[Project, StrutTieLayout]:
    geometry, materials = four_pile_cap(), MaterialsInput(fck=35.0)
    loads = LoadsInput(
        cases=(LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=980e3),)),)
    )
    result = analyze(geometry, materials, loads, DetailingInput())
    project = Project(name="B1", geometry=geometry, materials=materials, loads=loads, result=result)
    layout = strut_tie_layout(project, "ELU1")
    assert layout is not None
    return project, layout


def texts(svg: str) -> list[str]:
    return [t.text or "" for t in ET.fromstring(svg).iter(f"{SVG}text")]


def test_form_plan_is_to_scale_with_dimensions_in_cm() -> None:
    # B1: bloco 200 × 200 cm, estacas φ40 a 60 cm do centro: cadeia 40 + 120 + 40 cm.
    svg = form_plan(four_pile_cap())
    root = ET.fromstring(svg)
    circles = [(float(c.get("cx", 0)), float(c.get("cy", 0)), float(c.get("r", 0)))
               for c in root.iter(f"{SVG}circle")]  # fmt: skip
    assert sorted(circles) == sorted(
        (x, -y, 200.0) for x, y in ((-600, -600), (600, -600), (600, 600), (-600, 600))
    )
    labels = texts(svg)
    assert {"E1", "E2", "E3", "E4", "P1"} <= set(labels)
    assert labels.count("200") == 2  # totais em x e em y
    assert labels.count("40") == 4 and labels.count("120") == 2
    assert max(int(root.get("width", 0)), int(root.get("height", 0))) == 2400


def test_square_piles_are_drawn_as_squares() -> None:
    svg = form_plan(quincunx_cap())
    assert "<circle" not in svg
    assert {"420", "160", "50"} <= set(texts(svg))  # 420 cm, eixos a 160 cm, borda a 50 cm


@pytest.mark.parametrize("axis", ["x", "y"])
def test_form_section_shows_height_embedment_and_tie_axis(axis: str) -> None:
    # B1: h = 100 cm, embutimento 10 cm, eixo do tirante 5,8 cm acima da estaca (D8, φ16).
    svg = form_section(four_pile_cap(), axis, tie_height=58.0)  # type: ignore[arg-type]
    labels = texts(svg)
    assert {"100", "10", "5.8", "200"} <= set(labels)
    assert TIE_COLOR in svg
    assert len(re.findall("<polyline", svg)) == 2 + 1  # duas linhas de estacas e o pilar


def test_model_plan_labels_every_member_and_reaction() -> None:
    project, layout = b1()
    assert project.result is not None
    svg = model_plan(project.geometry, layout, project.result.reactions)
    labels = texts(svg)
    for member in layout.members:
        assert f"{member.force_d / 1e3:.0f} kN" in labels
    assert "E1: 257 kN" in labels  # (980 + 5 %) × 1,0 / 4, sem γn na reação do M1
    struts = sum(m.kind is LayoutMemberKind.STRUT for m in layout.members)
    assert svg.count(f'stroke="{STRUT_COLOR}" stroke-width') == struts
    assert svg.count(f'stroke="{TIE_COLOR}" stroke-width') == len(layout.members) - struts
    assert svg.count("stroke-dasharray") == struts  # bielas tracejadas por cima dos tirantes


def test_model_section_draws_each_projection_once_with_lever_arm() -> None:
    project, layout = b1()
    svg = model_section(project.geometry, layout, "x")
    # Em x, as 4 bielas se projetam em 2 linhas e os 4 tirantes em 1 linha e 2 pontos.
    assert svg.count(f'stroke="{STRUT_COLOR}"') == 2
    assert svg.count(f'stroke="{TIE_COLOR}"') == 3
    top = max(n.z for n in layout.nodes)
    bottom = min(n.z for n in layout.nodes)
    assert f"{(top - bottom) / 10:.1f}".removesuffix(".0") in texts(svg)


# Armação (D19, §4.10).


def lines(svg: str) -> list[ET.Element]:
    return list(ET.fromstring(svg).iter(f"{SVG}line"))


def test_reinforcement_plan_draws_every_bar_and_calls_each_position() -> None:
    project, _ = b1()
    positions = project.result.bar_positions  # type: ignore[union-attr]
    svg = reinforcement_plan(project.geometry, positions)
    bars = [e for e in lines(svg) if e.get("stroke") in (TIE_COLOR, MESH_COLOR)]
    assert len(bars) == sum(p.count for p in positions)
    labels = texts(svg)
    assert "N1: 6 φ16 C=220" in labels
    assert "N3: 10 φ6,3 C=202" in labels


def test_variable_length_is_called_var() -> None:
    geometry = quincunx_cap()
    loads = LoadsInput(
        cases=(LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=8000e3),)),)
    )
    result = analyze(geometry, MaterialsInput(fck=25.0), loads, DetailingInput())
    labels = texts(reinforcement_plan(geometry, result.bar_positions))
    assert any(label.endswith("C=var.") for label in labels)


@pytest.mark.parametrize("axis", ["x", "y"])
def test_reinforcement_section_shows_hooks_and_crossing_bars(axis: str) -> None:
    project, _ = b1()
    positions = project.result.bar_positions  # type: ignore[union-attr]
    svg = reinforcement_section(project.geometry, positions, axis)  # type: ignore[arg-type]
    # Corte pela primeira linha de estacas: a posição paralela aparece com os dois ganchos
    # (polilinha) e as barras que cruzam o corte, como pontos.
    assert len(ET.fromstring(svg).findall(f"{SVG}polyline")) >= 1
    dots = [c for c in ET.fromstring(svg).iter(f"{SVG}circle") if c.get("fill") != "none"]
    assert dots
    parallel = "N1" if axis == "x" else "N2"
    assert parallel in texts(svg)


def test_form_drawings_put_each_primitive_on_its_cad_layer() -> None:
    # ADR-011: forma, estacas, cotas e textos em camadas separadas para o DXF.
    plan = form_plan_sheet(four_pile_cap())
    assert {i.layer for i in plan.items if isinstance(i, Circle)} == {PILE_LAYER}
    assert {i.layer for i in plan.items if isinstance(i, Line)} == {DIMENSION_LAYER}
    values = {i.label for i in plan.items if isinstance(i, Text) and i.layer == DIMENSION_LAYER}
    assert values == {"40", "120", "200"}
    assert {i.label for i in plan.items if isinstance(i, Text) and i.layer == TEXT_LAYER} == {
        "P1", "E1", "E2", "E3", "E4"
    }  # fmt: skip
    section = form_section_sheet(four_pile_cap(), "x", 100.0)
    layers = {i.layer for i in section.items if not isinstance(i, (Text, Mask))}
    assert layers == {FORM_LAYER, PILE_LAYER, DIMENSION_LAYER}


def test_reinforcement_drawings_put_ties_and_mesh_on_their_layers() -> None:
    project, _ = b1()
    positions = project.result.bar_positions  # type: ignore[union-attr]
    plan = reinforcement_plan_sheet(project.geometry, positions)
    bars = [i for i in plan.items if isinstance(i, Line)]
    ties = sum(p.count for p in positions if p.id in {"N1", "N2"})
    assert sum(i.layer == TIE_LAYER for i in bars) == ties
    assert sum(i.layer == MESH_LAYER for i in bars) == sum(p.count for p in positions) - ties
    section = reinforcement_section_sheet(project.geometry, positions, "x")
    dots = [i for i in section.items if isinstance(i, Circle) and i.filled]
    assert dots
    assert {i.layer for i in dots} <= {TIE_LAYER, MESH_LAYER}
