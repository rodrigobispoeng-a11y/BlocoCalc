"""Desenhos em DXF R12 (ADR-011): conferidos lendo os pares de código de grupo, sem CAD."""

from __future__ import annotations

from collections import Counter

import pytest

from blococalc.analysis import analyze
from blococalc.report.dxf import TEXT_HEIGHT, cap_drawing
from blococalc.schemas import (
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Project,
)
from tests.factories import four_pile_cap, quincunx_cap

Entity = dict[str, list[str]]


def project(geometry: GeometryInput | None = None, n: float = 980e3, fck: float = 35.0) -> Project:
    geometry = geometry or four_pile_cap()
    materials = MaterialsInput(fck=fck)
    loads = LoadsInput(cases=(LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=n),)),))
    result = analyze(geometry, materials, loads, DetailingInput())
    return Project(name="B1", geometry=geometry, materials=materials, loads=loads, result=result)


def pairs(dxf: bytes) -> list[tuple[str, str]]:
    lines = dxf.decode("cp1252").split("\r\n")
    assert lines[-1] == ""
    return [(lines[i].strip(), lines[i + 1]) for i in range(0, len(lines) - 1, 2)]


def section(dxf: bytes, name: str) -> list[Entity]:
    """Entidades (ou registros de tabela) de uma seção, cada uma com os valores por código."""
    items: list[Entity] = []
    inside = False
    for code, value in pairs(dxf):
        if code == "2" and not items and value == name:
            inside = True
            continue
        if not inside:
            continue
        if code == "0":
            if value == "ENDSEC":
                break
            items.append({"0": [value]})
        else:
            items[-1].setdefault(code, []).append(value)
    return items


def on(entities: list[Entity], kind: str, layer: str) -> list[Entity]:
    return [e for e in entities if e["0"] == [kind] and e.get("8") == [layer]]


def test_file_is_r12_ascii_in_mm_and_ends_with_eof() -> None:
    dxf = cap_drawing(project())
    assert dxf.startswith(b"  0\r\nSECTION\r\n")
    header = dict(pairs(dxf)[:12])
    assert ("1", "AC1009") in pairs(dxf)
    assert ("3", "ANSI_1252") in pairs(dxf)
    assert header
    assert pairs(dxf)[-1] == ("0", "EOF")


def test_layers_have_the_cad_colors_of_the_adr() -> None:
    layers = {
        e["2"][0]: int(e["62"][0])
        for e in section(cap_drawing(project()), "TABLES")
        if e["0"] == ["LAYER"]
    }
    assert layers == {
        "FORMA": 7,
        "ESTACAS": 8,
        "ARM-TIRANTE": 5,
        "ARM-MALHA": 3,
        "COTAS": 1,
        "TEXTOS": 7,
    }


def test_plan_has_every_bar_on_its_layer() -> None:
    # B1: N1 6 φ16 + N2 4 φ16 nos tirantes, malha N3/N4 10 + 10 φ6,3 (D19).
    entities = section(cap_drawing(project()), "ENTITIES")
    assert len(on(entities, "LINE", "ARM-TIRANTE")) == 10
    assert len(on(entities, "LINE", "ARM-MALHA")) == 20
    lengths = Counter(
        round(
            abs(float(e["11"][0]) - float(e["10"][0])) + abs(float(e["21"][0]) - float(e["20"][0]))
        )
        for e in on(entities, "LINE", "ARM-TIRANTE")
    )
    # Eixo da barra: 2000 menos dois cobrimentos de 50 e dois meios φ16 (D19).
    assert lengths == Counter({1884: 10})


def test_call_outs_use_the_cad_diameter_symbol() -> None:
    texts = [e["1"][0] for e in section(cap_drawing(project()), "ENTITIES") if e["0"] == ["TEXT"]]
    assert "N1: 6 %%c16 C=220" in texts
    assert "N3: 10 %%c6,3 C=202" in texts
    assert "φ" not in "".join(texts)


def test_texts_share_one_height_scale() -> None:
    # ADR-011: 2,5 mm na escala 1:25; rótulos menores na mesma proporção do memorial.
    entities = section(cap_drawing(project()), "ENTITIES")
    heights = {round(float(e["40"][0]), 3) for e in entities if e["0"] == ["TEXT"]}
    assert pytest.approx(62.5) == TEXT_HEIGHT
    assert heights <= {62.5, 53.125, 87.5}
    titles = [e["1"][0] for e in entities if e["0"] == ["TEXT"] and e["1"][0].endswith("1:25")]
    assert "PLANTA DE FORMA - ESC. 1:25" in titles
    assert "ARMAÇÃO INFERIOR - ESC. 1:25" in titles


def test_steel_schedule_and_summary_match_the_memorial() -> None:
    # Golden do memorial (test_report): φ16 22,00 m = 34,7 kg; φ6,3 40,40 m = 9,9 kg.
    texts = [e["1"][0] for e in section(cap_drawing(project()), "ENTITIES") if e["0"] == ["TEXT"]]
    for value in ("TABELA DE AÇO", "RESUMO DE AÇO", "22.00", "34.7", "40.40", "9.9", "44.6"):
        assert value in texts


def test_bar_sections_are_filled_donuts() -> None:
    entities = section(cap_drawing(project()), "ENTITIES")
    donuts = [
        e for e in entities if e["0"] == ["POLYLINE"] and "41" in e and e["8"][0].startswith("ARM")
    ]
    assert donuts
    assert all(e["40"] == e["41"] for e in donuts)
    assert {e["40"][0] for e in donuts} <= {"8.000", "3.150"}  # largura = raio da barra


def test_drawings_do_not_overlap() -> None:
    entities = section(cap_drawing(project(quincunx_cap(), 8000e3, 25.0)), "ENTITIES")
    titles = [
        (float(e["11"][0]), float(e["21"][0]))
        for e in entities
        if e["0"] == ["TEXT"] and "ESC." in e["1"][0]
    ]
    assert len(titles) == 6
    assert len({round(t[0]) for t in titles}) == 3  # três desenhos por fila
    assert len({round(t[1]) for t in titles}) == 2  # duas filas


def test_cap_without_bar_positions_exports_the_forms_only() -> None:
    p = project()
    p = p.model_copy(update={"result": p.result.model_copy(update={"bar_positions": ()})})  # type: ignore[union-attr]
    entities = section(cap_drawing(p), "ENTITIES")
    assert not [e for e in entities if e.get("8", [""])[0].startswith("ARM")]
    texts = [e["1"][0] for e in entities if e["0"] == ["TEXT"]]
    assert "PLANTA DE FORMA - ESC. 1:25" in texts
    assert "TABELA DE AÇO" not in texts


def test_project_without_result_is_refused() -> None:
    p = project().model_copy(update={"result": None})
    with pytest.raises(ValueError, match="Calcule"):
        cap_drawing(p)
