"""Desenhos SVG do memorial (ADR-008): conferidos como texto, sem renderizar."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from blococalc.analysis import analyze, strut_tie_layout
from blococalc.report.drawings import (
    STRUT_COLOR,
    TIE_COLOR,
    form_plan,
    form_section,
    model_plan,
    model_section,
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
