"""Desenhos do bloco em SVG para o memorial (ADR-008).

Planta e cortes de forma, e o modelo de bielas e tirantes de um caso em planta e em corte,
em escala, a partir dos contratos de `schemas`. Coordenadas do desenho em mm (as do bloco),
com o eixo vertical invertido para o SVG; cotas em cm e forças em kN. Sem Qt e sem I/O.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from html import escape
from typing import Literal

from blococalc.schemas import (
    BarPosition,
    GeometryInput,
    HookShape,
    LayoutMemberKind,
    PileReaction,
    PileShape,
    Point,
    StrutTieLayout,
)

Axis = Literal["x", "y"]
STRUT_COLOR = "#c0392b"
TIE_COLOR = "#1f4e9c"
MESH_COLOR = "#4f7f3a"
_HOOK_TAIL = 8.0  # φ (D19)
_CHAR_WIDTH = 0.6  # largura média de um caractere, em altura de fonte (sans-serif)
_LINE = "#000000"
_LIGHT = "#9a9a9a"
_SECTION_TEXT = 0.07  # cortes saem menores na página que as plantas
_PIXELS = 2400  # maior lado da imagem; o memorial reduz na página (cerca de 380 ppi)
KN = 1e3  # N
# Camadas de CAD (ADR-011); a cor do traço dá a camada quando o desenho não diz outra.
FORM_LAYER = "FORMA"
PILE_LAYER = "ESTACAS"
TIE_LAYER = "ARM-TIRANTE"
MESH_LAYER = "ARM-MALHA"
DIMENSION_LAYER = "COTAS"
TEXT_LAYER = "TEXTOS"
MODEL_LAYER = "MODELO"  # bielas e tirantes do modelo: só no memorial
_LAYERS = {
    _LINE: FORM_LAYER,
    _LIGHT: FORM_LAYER,
    TIE_COLOR: TIE_LAYER,
    MESH_COLOR: MESH_LAYER,
    STRUT_COLOR: MODEL_LAYER,
}


@dataclass(frozen=True)
class Line:
    a: tuple[float, float]
    b: tuple[float, float]
    color: str
    width: float
    dash: str
    layer: str


@dataclass(frozen=True)
class Path:
    points: tuple[tuple[float, float], ...]
    color: str
    fill: str
    closed: bool
    layer: str


@dataclass(frozen=True)
class Circle:
    center: tuple[float, float]
    radius: float
    color: str
    filled: bool  # seção de barra: cheio e sem contorno
    layer: str


@dataclass(frozen=True)
class Text:
    at: tuple[float, float]
    label: str
    color: str
    size: float
    vertical: bool
    layer: str


@dataclass(frozen=True)
class Mask:
    """Fundo branco sob uma etiqueta; só faz sentido na imagem (ADR-011)."""

    at: tuple[float, float]  # canto inferior esquerdo
    width: float
    height: float


Primitive = Line | Path | Circle | Text | Mask


class Sheet:
    """Folha com coordenadas do bloco (u para a direita, v para cima) em mm.

    Guarda primitivas neutras, cada uma com a camada de CAD (ADR-011); `render` gera o SVG.
    """

    def __init__(self, size: float, text: float = 0.032) -> None:
        self.text_size = text * size
        self.stroke = size / 500.0
        self.items: list[Primitive] = []
        self.points: list[tuple[float, float]] = []

    def line(  # noqa: PLR0913, PLR0917 - extremos, cor, estilo e camada
        self, a: tuple[float, float], b: tuple[float, float], color: str = _LINE,
        width: float = 1.0, dash: str = "", layer: str = "",
    ) -> None:  # fmt: skip
        self.points += [a, b]
        self.items.append(Line(a, b, color, width, dash, layer or _LAYERS[color]))

    def polyline(self, points: Sequence[tuple[float, float]], color: str = _LINE,
                 fill: str = "none", closed: bool = False, layer: str = "") -> None:  # fmt: skip
        self.points += points
        self.items.append(Path(tuple(points), color, fill, closed, layer or _LAYERS[color]))

    def rect(  # noqa: PLR0913, PLR0917 - retângulo, cor, preenchimento e camada
        self, u: float, v: float, width: float, height: float, color: str = _LINE,
        fill: str = "none", layer: str = "",
    ) -> None:  # fmt: skip
        corners = [(u, v), (u + width, v), (u + width, v + height), (u, v + height)]
        self.polyline(corners, color, fill, closed=True, layer=layer)

    def circle(  # noqa: PLR0913, PLR0917 - centro, raio, cor e estilo
        self, u: float, v: float, radius: float, color: str = _LINE, filled: bool = False,
        layer: str = "",
    ) -> None:  # fmt: skip
        if not filled:  # a seção de barra não mexe nos limites, como antes
            self.points += [(u - radius, v - radius), (u + radius, v + radius)]
        self.items.append(Circle((u, v), radius, color, filled, layer or _LAYERS[color]))

    def mask(self, u: float, v: float, width: float, height: float) -> None:
        self.items.append(Mask((u, v), width, height))

    def text(  # noqa: PLR0913, PLR0917 - posição, texto e estilo
        self, u: float, v: float, label: str, color: str = _LINE, scale: float = 1.0,
        vertical: bool = False, layer: str = TEXT_LAYER,
    ) -> None:  # fmt: skip
        size = self.text_size * scale
        half = max(size, _CHAR_WIDTH * size * len(label) / 2)
        reach = (size, half) if vertical else (half, size)
        self.points += [(u - reach[0], v - reach[1]), (u + reach[0], v + reach[1])]
        self.items.append(Text((u, v), label, color, size, vertical, layer))

    def dimension(self, a: float, b: float, at: float, horizontal: bool) -> None:
        """Cota de `a` a `b` [mm] na linha `at`, com o valor em cm no meio."""
        if b - a < 1.0:
            return
        tick = 0.6 * self.text_size

        def point(s: float, t: float) -> tuple[float, float]:
            return (s, t) if horizontal else (t, s)

        self.line(point(a, at), point(b, at), width=0.6, layer=DIMENSION_LAYER)
        for s in (a, b):
            ends = point(s - tick / 2, at - tick / 2), point(s + tick / 2, at + tick / 2)
            self.line(*ends, layer=DIMENSION_LAYER)
        offset = 0.8 * self.text_size
        if horizontal or b - a > 3.0 * self.text_size:
            u, v = point((a + b) / 2, at + offset if horizontal else at - offset)
            self.text(u, v, _cm(b - a), scale=0.85, vertical=not horizontal, layer=DIMENSION_LAYER)
        else:  # cota curta: valor deitado ao lado da linha
            outward = 1.6 * self.text_size if at >= 0 else -1.6 * self.text_size
            self.text(at + outward, (a + b) / 2, _cm(b - a), scale=0.85, layer=DIMENSION_LAYER)

    def render(self) -> str:
        us, vs = [p[0] for p in self.points], [p[1] for p in self.points]
        pad = 1.5 * self.text_size
        left, right = min(us) - pad, max(us) + pad
        bottom, top = min(vs) - pad, max(vs) + pad
        width, height = right - left, top - bottom
        scale = _PIXELS / max(width, height)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * scale:.0f}" '
            f'height="{height * scale:.0f}" viewBox="{left:.1f} {-top:.1f} {width:.1f} '
            f'{height:.1f}"><rect x="{left:.1f}" y="{-top:.1f}" width="{width:.1f}" '
            f'height="{height:.1f}" fill="#ffffff"/>'
            + "".join(self._svg(item) for item in self.items)
            + "</svg>"
        )

    def _svg(self, item: Primitive) -> str:
        match item:
            case Line(a, b, color, width, dash):
                style = f' stroke-dasharray="{dash}"' if dash else ""
                return (
                    f'<line x1="{a[0]:.1f}" y1="{-a[1]:.1f}" x2="{b[0]:.1f}" y2="{-b[1]:.1f}" '
                    f'stroke="{color}" stroke-width="{width * self.stroke:.2f}"{style}/>'
                )
            case Path(points, color, fill, closed):
                tag = "polygon" if closed else "polyline"
                coords = " ".join(f"{u:.1f},{-v:.1f}" for u, v in points)
                return (
                    f'<{tag} points="{coords}" fill="{fill}" stroke="{color}" '
                    f'stroke-width="{self.stroke:.2f}"/>'
                )
            case Circle((u, v), radius, color, True):
                return (
                    f'<circle cx="{u:.1f}" cy="{-v:.1f}" r="{radius:.1f}" '
                    f'fill="{color}" stroke="none"/>'
                )
            case Circle((u, v), radius, color, False):
                return (
                    f'<circle cx="{u:.1f}" cy="{-v:.1f}" r="{radius:.1f}" fill="none" '
                    f'stroke="{color}" stroke-width="{self.stroke:.2f}"/>'
                )
            case Text((u, v), label, color, size, vertical):
                turn = f' transform="rotate(-90 {u:.1f} {-v:.1f})"' if vertical else ""
                # Linha de base abaixo do centro: o renderizador da Qt ignora dominant-baseline.
                return (
                    f'<text x="{u:.1f}" y="{-v + 0.35 * size:.1f}" font-size="{size:.1f}" '
                    f'font-family="sans-serif" text-anchor="middle" fill="{color}"{turn}>'
                    f"{escape(label)}</text>"
                )
            case Mask((u, v), width, height):
                return (
                    f'<rect x="{u:.1f}" y="{-v - height:.1f}" width="{width:.1f}" '
                    f'height="{height:.1f}" fill="#ffffff" stroke="none"/>'
                )
        raise TypeError(item)


def form_plan(geometry: GeometryInput) -> str:
    """Planta de forma: bloco, estacas e pilares, com cotas totais e das estacas [cm]."""
    return form_plan_sheet(geometry).render()


def form_plan_sheet(geometry: GeometryInput) -> Sheet:
    """Folha de `form_plan`, com as primitivas e as camadas para o DXF (ADR-011)."""
    cap = geometry.cap
    hx, hy = cap.lx / 2, cap.ly / 2
    sheet = Sheet(max(cap.lx, cap.ly))
    gap = 2.5 * sheet.text_size
    sheet.rect(-hx, -hy, cap.lx, cap.ly)
    _piles_and_columns(sheet, geometry, _LINE)
    xs = _stations(-hx, hx, (p.x for p in geometry.piles))
    ys = _stations(-hy, hy, (p.y for p in geometry.piles))
    for a, b in itertools.pairwise(xs):
        sheet.dimension(a, b, -hy - gap, horizontal=True)
    sheet.dimension(-hx, hx, -hy - 2 * gap, horizontal=True)
    for a, b in itertools.pairwise(ys):
        sheet.dimension(a, b, -hx - gap, horizontal=False)
    sheet.dimension(-hy, hy, -hx - 2 * gap, horizontal=False)
    return sheet


def form_section(geometry: GeometryInput, axis: Axis, tie_height: float) -> str:
    """Corte pelo centro na direção `axis`: altura, embutimento e eixo do tirante (D8) [cm]."""
    return form_section_sheet(geometry, axis, tie_height).render()


def form_section_sheet(geometry: GeometryInput, axis: Axis, tie_height: float) -> Sheet:
    """Folha de `form_section`, com as primitivas e as camadas para o DXF (ADR-011)."""
    cap = geometry.cap
    length = cap.lx if axis == "x" else cap.ly
    half, h = length / 2, cap.h
    sheet = Sheet(max(length, 1.6 * h), _SECTION_TEXT)
    gap = 2.5 * sheet.text_size
    stub = 0.3 * h
    sheet.rect(-half, 0.0, length, h)
    for u, size in _projected(((p.x, p.y, p.size) for p in geometry.piles), axis):
        a, b = u - size / 2, u + size / 2
        outline = [(a, -stub), (a, cap.pile_embedment), (b, cap.pile_embedment), (b, -stub)]
        sheet.polyline(outline, layer=PILE_LAYER)
    for c in geometry.columns:
        u, width = (c.x, c.bx) if axis == "x" else (c.y, c.by)
        sheet.polyline([(u - width / 2, h + stub), (u - width / 2, h),
                        (u + width / 2, h), (u + width / 2, h + stub)])  # fmt: skip
    tie = cap.pile_embedment + tie_height
    dash = f"{4 * sheet.stroke} {sheet.stroke}"
    sheet.line((-half, tie), (half, tie), TIE_COLOR, dash=dash, layer=DIMENSION_LAYER)
    sheet.dimension(0.0, h, half + 2 * gap, horizontal=False)
    sheet.dimension(0.0, cap.pile_embedment, half + gap, horizontal=False)
    sheet.dimension(cap.pile_embedment, tie, -half - gap, horizontal=False)  # do outro lado
    sheet.dimension(-half, half, -stub - gap, horizontal=True)
    return sheet


def model_plan(
    geometry: GeometryInput, layout: StrutTieLayout, reactions: Sequence[PileReaction]
) -> str:
    """Bielas (vermelho) e tirantes (azul) em planta, com as forças e as reações [kN]."""
    cap = geometry.cap
    sheet = Sheet(max(cap.lx, cap.ly))
    sheet.rect(-cap.lx / 2, -cap.ly / 2, cap.lx, cap.ly, _LIGHT)
    _piles_and_columns(sheet, geometry, _LIGHT, labels=False)
    nodes = {n.id: (n.x, n.y) for n in layout.nodes}
    # Tirantes primeiro; as bielas tracejadas por cima, porque em planta podem coincidir com
    # tirantes diagonais. Rótulos no meio, de lados opostos da barra.
    members = sorted(layout.members, key=lambda m: m.kind is LayoutMemberKind.STRUT)
    for member in members:
        a, b = nodes[member.start], nodes[member.end]
        strut = member.kind is LayoutMemberKind.STRUT
        color = STRUT_COLOR if strut else TIE_COLOR
        dash = f"{6 * sheet.stroke} {3 * sheet.stroke}" if strut else ""
        sheet.line(a, b, color, width=2.0, dash=dash)
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length > 1.0:
            label = _kn(member.force_d)
            nx, ny = -(b[1] - a[1]) / length, (b[0] - a[0]) / length
            if ny < -1e-9 or (abs(ny) <= 1e-9 and nx < 0):
                nx, ny = -nx, -ny  # normal sempre para cima (ou para a direita)
            # Afasta o centro do texto da barra pela meia largura (ou meia altura) do rótulo.
            size = 0.85 * sheet.text_size
            reach = abs(nx) * 0.3 * size * len(label) + abs(ny) * 0.5 * size + 0.3 * size
            side = reach if strut else -reach
            u, v = (a[0] + b[0]) / 2 + side * nx, (a[1] + b[1]) / 2 + side * ny
            sheet.text(u, v, label, color, 0.85)
    forces = {r.pile_id: r.force for r in reactions}
    for pile in geometry.piles:
        if pile.id in forces:
            below = pile.y - pile.size / 2 - 0.9 * sheet.text_size
            sheet.text(pile.x, below, f"{pile.id}: {_kn(forces[pile.id])}", scale=0.85)
    return sheet.render()


def model_section(geometry: GeometryInput, layout: StrutTieLayout, axis: Axis) -> str:
    """Bielas e tirantes projetados no plano vertical da direção `axis`, com o braço z [cm]."""
    cap = geometry.cap
    length = cap.lx if axis == "x" else cap.ly
    sheet = Sheet(max(length, 1.6 * cap.h), _SECTION_TEXT)
    sheet.rect(-length / 2, 0.0, length, cap.h, _LIGHT)
    nodes = {n.id: ((n.x if axis == "x" else n.y), n.z) for n in layout.nodes}
    drawn: set[tuple[LayoutMemberKind, tuple[float, ...]]] = set()
    for member in layout.members:
        a, b = sorted((nodes[member.start], nodes[member.end]))
        key = (member.kind, tuple(round(c) for c in (*a, *b)))
        if key not in drawn:
            drawn.add(key)
            color = STRUT_COLOR if member.kind is LayoutMemberKind.STRUT else TIE_COLOR
            sheet.line(a, b, color, width=2.0)
    heights = [z for _, z in nodes.values()]
    gap = 2.5 * sheet.text_size
    sheet.dimension(min(heights), max(heights), length / 2 + gap, horizontal=False)
    return sheet.render()


def reinforcement_plan(geometry: GeometryInput, positions: Sequence[BarPosition]) -> str:
    """Armação inferior em planta: todas as barras e o chamado de cada posição (D19)."""
    return reinforcement_plan_sheet(geometry, positions).render()


def reinforcement_plan_sheet(geometry: GeometryInput, positions: Sequence[BarPosition]) -> Sheet:
    """Folha de `reinforcement_plan`, com as primitivas e as camadas para o DXF (ADR-011)."""
    cap = geometry.cap
    sheet = Sheet(max(cap.lx, cap.ly))
    sheet.rect(-cap.lx / 2, -cap.ly / 2, cap.lx, cap.ly)
    _piles_and_columns(sheet, geometry, _LIGHT, labels=False)
    for position in positions:
        color = _color(position)
        for a, b in position.bars:
            sheet.line(a, b, color, width=1.0 if color == TIE_COLOR else 0.6)
    # Etiqueta de cada posição numa fração diferente do comprimento da barra, para não se
    # sobreporem; os chamados completos ficam na legenda abaixo da planta.
    for k, position in enumerate(positions):
        a, b = position.bars[0]
        t = (k + 0.5) / len(positions)
        _tag(sheet, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])), position)
    for k, position in enumerate(positions):
        v = -cap.ly / 2 - (2.0 + 1.3 * k) * sheet.text_size
        sheet.text(0.0, v, call_out(position), _color(position), 0.85)
    return sheet


def reinforcement_section(
    geometry: GeometryInput, positions: Sequence[BarPosition], axis: Axis
) -> str:
    """Corte pela primeira linha de estacas na direção `axis`: barras paralelas em elevação, com
    os ganchos, e as que cruzam o corte em seção (D19)."""
    return reinforcement_section_sheet(geometry, positions, axis).render()


def reinforcement_section_sheet(
    geometry: GeometryInput, positions: Sequence[BarPosition], axis: Axis
) -> Sheet:
    """Folha de `reinforcement_section`, com as primitivas e as camadas para o DXF (ADR-011)."""
    cap = geometry.cap
    across = 1 if axis == "x" else 0  # coordenada constante no plano do corte
    at = min(p.y if axis == "x" else p.x for p in geometry.piles)
    reach = max(p.size for p in geometry.piles) / 2
    length = cap.lx if axis == "x" else cap.ly
    sheet = Sheet(max(length, 1.6 * cap.h), _SECTION_TEXT)
    sheet.rect(-length / 2, 0.0, length, cap.h, _LIGHT)
    for u, size in _projected(((p.x, p.y, p.size) for p in geometry.piles), axis):
        height = 0.3 * cap.h + cap.pile_embedment
        sheet.rect(u - size / 2, -0.3 * cap.h, size, height, _LIGHT, layer=PILE_LAYER)
    heights = _layer_heights(geometry, positions)
    for k, position in enumerate(positions):
        z = heights[position.layer] + position.bar_diameter / 2
        color = _color(position)
        near = [b for b in position.bars if _parallel(b, across)]
        near = [b for b in near if abs(b[0][across] - at) <= reach]
        if near:
            a, b = min(near, key=lambda bar: abs(bar[0][across] - at))
            u0, u1 = sorted((a[1 - across], b[1 - across]))
            leg = (
                _HOOK_TAIL * position.bar_diameter if position.hook is HookShape.RIGHT_ANGLE else 0
            )
            sheet.polyline([(u0, z + leg), (u0, z), (u1, z), (u1, z + leg)], color)
            t = (k + 0.5) / len(positions)
            sheet.text(u0 + t * (u1 - u0), z + 1.2 * sheet.text_size, position.id, color, 0.85)
            continue
        for a, b in position.bars:
            if (a[across] - at) * (b[across] - at) < 0:
                t = (at - a[across]) / (b[across] - a[across])
                u = a[1 - across] + t * (b[1 - across] - a[1 - across])
                sheet.circle(u, z, position.bar_diameter / 2, color, filled=True)
    return sheet


def call_out(position: BarPosition) -> str:
    """Chamado da posição: "N1: 6 φ16 C=220" (comprimento em cm, "var." se variável)."""
    phi = f"{position.bar_diameter:g}".replace(".", ",")
    length = "var." if position.variable_length else _cm(position.length)
    return f"{position.id}: {position.count} φ{phi} C={length}"


def _tag(sheet: Sheet, at: Point, position: BarPosition) -> None:
    """Número da posição sobre um fundo branco, legível no meio das barras."""
    size = 0.85 * sheet.text_size
    width = _CHAR_WIDTH * size * len(position.id) + 0.4 * size
    sheet.mask(at[0] - width / 2, at[1] - 0.6 * size, width, 1.2 * size)
    sheet.text(at[0], at[1], position.id, _color(position), 0.85)


def _color(position: BarPosition) -> str:
    return TIE_COLOR if _is_tie(position) else MESH_COLOR


def _is_tie(position: BarPosition) -> bool:
    return any(i.startswith("tirante_") for i in position.reinforcement_ids)


def _parallel(bar: tuple[tuple[float, float], tuple[float, float]], across: int) -> bool:
    return abs(bar[0][across] - bar[1][across]) < 1.0


def _layer_heights(geometry: GeometryInput, positions: Sequence[BarPosition]) -> dict[int, float]:
    """Face inferior de cada camada: cobrimento sobre a estaca e a camada de baixo (D19)."""
    thickest = {
        layer: max((p.bar_diameter for p in positions if p.layer == layer), default=0.0)
        for layer in (1, 2, 3)
    }
    base = geometry.cap.pile_embedment + geometry.cap.cover
    return {1: base, 2: base + thickest[1], 3: base + thickest[1] + thickest[2]}


def _piles_and_columns(
    sheet: Sheet, geometry: GeometryInput, color: str, labels: bool = True
) -> None:
    # Pilares antes das estacas, para a estaca sob o pilar (D15) continuar visível.
    for c in geometry.columns:
        sheet.rect(c.x - c.bx / 2, c.y - c.by / 2, c.bx, c.by, color, fill="#e6e6e6")
        if labels:
            sheet.text(c.x, c.y + c.by / 2 - sheet.text_size, c.id, scale=0.85)
    for p in geometry.piles:
        if p.shape is PileShape.CIRCULAR:
            sheet.circle(p.x, p.y, p.size / 2, color, layer=PILE_LAYER)
        else:
            sheet.rect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size, color, layer=PILE_LAYER)
        if labels:
            sheet.text(p.x, p.y, p.id, scale=0.85)


def _stations(start: float, end: float, positions: Iterable[float]) -> list[float]:
    """Pontos da cadeia de cotas: bordas do bloco e eixos das estacas, sem repetir."""
    return sorted({round(start, 1), round(end, 1), *(round(p, 1) for p in positions)})


def _projected(
    items: Iterable[tuple[float, float, float]], axis: Axis
) -> list[tuple[float, float]]:
    """Posição ao longo do corte e largura, uma vez por posição (estacas alinhadas)."""
    widths: dict[float, float] = {}
    for x, y, size in items:
        u = round(x if axis == "x" else y, 1)
        widths[u] = max(widths.get(u, 0.0), size)
    return sorted(widths.items())


def _cm(length: float) -> str:
    return f"{length / 10:.1f}".removesuffix(".0")


def _kn(force: float) -> str:
    return f"{force / KN:.0f} kN"
