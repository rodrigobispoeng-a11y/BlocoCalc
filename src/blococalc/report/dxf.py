"""Desenhos de forma e de armação em DXF R12 para o CAD (ADR-011).

Reaproveita as folhas de `drawings` (as mesmas do memorial), com texto de altura fixa, e grava
cada primitiva na sua camada. Um arquivo por análise: forma na primeira fila, armação e tabela
de aço na segunda. Unidade em mm, escala 1:1 no espaço do modelo. Sem Qt e sem I/O.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from blococalc.report.drawings import (
    DIMENSION_LAYER,
    FORM_LAYER,
    MESH_LAYER,
    PILE_LAYER,
    TEXT_LAYER,
    TIE_LAYER,
    Circle,
    Line,
    Mask,
    Path,
    Primitive,
    Sheet,
    Text,
    form_plan_sheet,
    form_section_sheet,
    reinforcement_plan_sheet,
    reinforcement_section_sheet,
)
from blococalc.report.memorial import (
    STEEL_SCHEDULE_HEAD,
    STEEL_SUMMARY_HEAD,
    steel_schedule,
    steel_summary,
    tie_axis_height,
)
from blococalc.schemas import Project

SCALE = 25  # escala de plotagem que fixa a altura dos textos
TEXT_HEIGHT = 2.5 * SCALE  # mm no modelo: 2,5 mm no papel
_TITLE = 1.4  # altura dos títulos, em alturas de texto
_GAP = 10.0 * TEXT_HEIGHT  # espaço entre desenhos
_CELL_CHAR = 0.9  # largura de caractere nas tabelas, folgada para as fontes do CAD
# Cor ACI de cada camada (ADR-011, item 2).
LAYER_COLORS = {
    FORM_LAYER: 7,
    PILE_LAYER: 8,
    TIE_LAYER: 5,
    MESH_LAYER: 3,
    DIMENSION_LAYER: 1,
    TEXT_LAYER: 7,
}


@dataclass(frozen=True)
class _Placed:
    title: str
    sheet: Sheet


def cap_drawing(project: Project) -> bytes:
    """Arquivo DXF R12 (ANSI 1252) com a forma, a armação e a tabela de aço do projeto."""
    result = project.result
    if result is None:
        raise ValueError("Calcule o bloco antes de exportar os desenhos.")
    g, positions, h = project.geometry, result.bar_positions, TEXT_HEIGHT
    tie = tie_axis_height(project)
    rows = [
        [
            _Placed("PLANTA DE FORMA", form_plan_sheet(g, h)),
            _Placed("CORTE A-A", form_section_sheet(g, "x", tie, h)),
            _Placed("CORTE B-B", form_section_sheet(g, "y", tie, h)),
        ]
    ]
    if positions:
        rows.append(
            [
                _Placed("ARMAÇÃO INFERIOR", reinforcement_plan_sheet(g, positions, h)),
                _Placed("ARMAÇÃO - CORTE A-A", reinforcement_section_sheet(g, positions, "x", h)),
                _Placed("ARMAÇÃO - CORTE B-B", reinforcement_section_sheet(g, positions, "y", h)),
                _Placed("", _steel_tables(project)),
            ]
        )
    entities = list(_layout(rows))
    xs = [v for e in entities for c, v in e if c in {10, 11} and isinstance(v, float)]
    ys = [v for e in entities for c, v in e if c in {20, 21} and isinstance(v, float)]
    out = _Writer()
    out.section("HEADER")
    out.pair(9, "$ACADVER")
    out.pair(1, "AC1009")
    out.pair(9, "$DWGCODEPAGE")
    out.pair(3, "ANSI_1252")
    for name, x, y in (("$EXTMIN", min(xs), min(ys)), ("$EXTMAX", max(xs), max(ys))):
        out.pair(9, name)
        out.point(10, x, y)
    out.end()
    out.section("TABLES")
    out.table("LTYPE", 1)
    out.pairs(("0", "LTYPE"), (2, "CONTINUOUS"), (70, 0), (3, "Solid line"), (72, 65), (73, 0))
    out.pair(40, 0.0)
    out.pair(0, "ENDTAB")
    out.table("LAYER", len(LAYER_COLORS))
    for name, color in LAYER_COLORS.items():
        out.pairs((0, "LAYER"), (2, name), (70, 0), (62, color), (6, "CONTINUOUS"))
    out.pair(0, "ENDTAB")
    out.end()
    out.section("ENTITIES")
    for entity in entities:
        out.pairs(*entity)
    out.end()
    out.pair(0, "EOF")
    return out.data()


def _steel_tables(project: Project) -> Sheet:
    """Tabela e resumo de aço como textos em colunas, iguais aos do memorial (D19)."""
    positions = project.result.bar_positions if project.result else ()
    sheet = Sheet(1.0, TEXT_HEIGHT)
    v = 0.0
    for title, head, rows in (
        ("TABELA DE AÇO", STEEL_SCHEDULE_HEAD, steel_schedule(positions)),
        ("RESUMO DE AÇO", STEEL_SUMMARY_HEAD, steel_summary(positions)),
    ):
        table: list[tuple[str, ...]] = [head, *rows]
        widths = [
            (max(len(r[k]) for r in table) + 2) * _CELL_CHAR * TEXT_HEIGHT for k in range(len(head))
        ]
        sheet.text(sum(widths) / 2, v, title, scale=_TITLE)
        v -= 2.0 * TEXT_HEIGHT
        for k, row in enumerate(table):
            u = 0.0
            for width, cell in zip(widths, row, strict=True):
                sheet.text(u + width / 2, v, cell)
                u += width
            if k == 0:
                rule = v - 0.9 * TEXT_HEIGHT
                sheet.line((0.0, rule), (u, rule), layer=TEXT_LAYER)
            v -= 1.8 * TEXT_HEIGHT
        v -= 2.0 * TEXT_HEIGHT
    return sheet


Pair = tuple[int | str, str | float]


def _layout(rows: Sequence[Sequence[_Placed]]) -> Iterator[tuple[Pair, ...]]:
    """Desenhos em grade, alinhados pelo topo da fila e centrados na coluna, com título."""
    columns = max(len(r) for r in rows)
    widths = [max(_width(r[k].sheet) for r in rows if k < len(r)) for k in range(columns)]
    top = 0.0
    for row in rows:
        u = 0.0
        for width, placed in zip(widths, row, strict=False):
            left, right, _, high = _bounds(placed.sheet)
            dx, dy = u + width / 2 - (left + right) / 2, top - high
            if placed.title:
                at = (u + width / 2, top + 2.0 * TEXT_HEIGHT)
                title = Text(at, f"{placed.title} - ESC. 1:{SCALE}", "", _TITLE * TEXT_HEIGHT,
                             False, TEXT_LAYER)  # fmt: skip
                yield from _entities(title, 0.0, 0.0)
            for item in placed.sheet.items:
                yield from _entities(item, dx, dy)
            u += width + _GAP
        top -= max(_bounds(p.sheet)[3] - _bounds(p.sheet)[2] for p in row) + _GAP


def _entities(item: Primitive, dx: float, dy: float) -> Iterator[tuple[Pair, ...]]:
    def at(code: int, point: tuple[float, float]) -> tuple[Pair, ...]:
        return (code, point[0] + dx), (code + 10, point[1] + dy), (code + 20, 0.0)

    match item:
        case Line(a, b, _, _, _, layer):
            yield ("0", "LINE"), (8, layer), *at(10, a), *at(11, b)
        case Path(points, _, _, closed, layer):
            yield ("0", "POLYLINE"), (8, layer), (66, 1), *at(10, (-dx, -dy)), (70, int(closed))
            for point in points:
                yield ("0", "VERTEX"), (8, layer), *at(10, point)
            yield ("0", "SEQEND"), (8, layer)
        case Circle((u, v), radius, _, True, layer):
            # Seção de barra: polilinha fechada de dois arcos com largura igual ao raio.
            yield (("0", "POLYLINE"), (8, layer), (66, 1), *at(10, (-dx, -dy)), (70, 1),
                   (40, radius), (41, radius))  # fmt: skip
            for side in (-1, 1):
                yield ("0", "VERTEX"), (8, layer), *at(10, (u + side * radius / 2, v)), (42, 1.0)
            yield ("0", "SEQEND"), (8, layer)
        case Circle(center, radius, _, False, layer):
            yield ("0", "CIRCLE"), (8, layer), *at(10, center), (40, radius)
        case Text(point, label, _, size, vertical, layer):
            yield (("0", "TEXT"), (8, layer), *at(10, point), (40, size),
                   (1, label.replace("φ", "%%c")), (50, 90.0 if vertical else 0.0), (72, 4),
                   *at(11, point))  # fmt: skip
        case Mask():
            return


def _bounds(sheet: Sheet) -> tuple[float, float, float, float]:
    us, vs = [p[0] for p in sheet.points], [p[1] for p in sheet.points]
    return min(us), max(us), min(vs), max(vs)


def _width(sheet: Sheet) -> float:
    left, right, _, _ = _bounds(sheet)
    return right - left


class _Writer:
    """Pares de código de grupo do DXF ASCII, com CRLF como o AutoCAD grava."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def pair(self, code: int | str, value: str | float) -> None:
        text = f"{value:.3f}" if isinstance(value, float) else str(value)
        self.lines += [f"{int(code):>3}", text]

    def pairs(self, *items: Pair) -> None:
        for code, value in items:
            self.pair(code, value)

    def point(self, code: int, x: float, y: float) -> None:
        self.pairs((code, x), (code + 10, y), (code + 20, 0.0))

    def section(self, name: str) -> None:
        self.pairs((0, "SECTION"), (2, name))

    def table(self, name: str, count: int) -> None:
        self.pairs((0, "TABLE"), (2, name), (70, count))

    def end(self) -> None:
        self.pair(0, "ENDSEC")

    def data(self) -> bytes:
        return "".join(f"{line}\r\n" for line in self.lines).encode("cp1252", errors="replace")
