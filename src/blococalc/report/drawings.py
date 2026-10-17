"""Desenhos do bloco em SVG para o memorial (ADR-008).

Planta e cortes de forma, e o modelo de bielas e tirantes de um caso em planta e em corte,
em escala, a partir dos contratos de `schemas`. Coordenadas do desenho em mm (as do bloco),
com o eixo vertical invertido para o SVG; cotas em cm e forças em kN. Sem Qt e sem I/O.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Sequence
from html import escape
from typing import Literal

from blococalc.schemas import (
    GeometryInput,
    LayoutMemberKind,
    PileReaction,
    PileShape,
    StrutTieLayout,
)

Axis = Literal["x", "y"]
STRUT_COLOR = "#c0392b"
TIE_COLOR = "#1f4e9c"
_LINE = "#000000"
_LIGHT = "#9a9a9a"
_SECTION_TEXT = 0.07  # cortes saem menores na página que as plantas
_PIXELS = 2400  # maior lado da imagem; o memorial reduz na página (cerca de 380 ppi)
KN = 1e3  # N


class _Sheet:
    """Folha com coordenadas do bloco (u para a direita, v para cima) em mm."""

    def __init__(self, size: float, text: float = 0.032) -> None:
        self.text_size = text * size
        self.stroke = size / 500.0
        self.items: list[str] = []
        self.points: list[tuple[float, float]] = []

    def line(self, a: tuple[float, float], b: tuple[float, float], color: str = _LINE,
             width: float = 1.0, dash: str = "") -> None:  # fmt: skip
        self.points += [a, b]
        style = f' stroke-dasharray="{dash}"' if dash else ""
        self.items.append(
            f'<line x1="{a[0]:.1f}" y1="{-a[1]:.1f}" x2="{b[0]:.1f}" y2="{-b[1]:.1f}" '
            f'stroke="{color}" stroke-width="{width * self.stroke:.2f}"{style}/>'
        )

    def polyline(self, points: Sequence[tuple[float, float]], color: str = _LINE,
                 fill: str = "none", closed: bool = False) -> None:  # fmt: skip
        self.points += points
        tag = "polygon" if closed else "polyline"
        coords = " ".join(f"{u:.1f},{-v:.1f}" for u, v in points)
        self.items.append(
            f'<{tag} points="{coords}" fill="{fill}" stroke="{color}" '
            f'stroke-width="{self.stroke:.2f}"/>'
        )

    def rect(  # noqa: PLR0913, PLR0917 - retângulo, cor e preenchimento
        self, u: float, v: float, width: float, height: float, color: str = _LINE,
        fill: str = "none",
    ) -> None:  # fmt: skip
        corners = [(u, v), (u + width, v), (u + width, v + height), (u, v + height)]
        self.polyline(corners, color, fill, closed=True)

    def circle(self, u: float, v: float, radius: float, color: str = _LINE) -> None:
        self.points += [(u - radius, v - radius), (u + radius, v + radius)]
        self.items.append(
            f'<circle cx="{u:.1f}" cy="{-v:.1f}" r="{radius:.1f}" fill="none" '
            f'stroke="{color}" stroke-width="{self.stroke:.2f}"/>'
        )

    def text(  # noqa: PLR0913, PLR0917 - posição, texto e estilo
        self, u: float, v: float, label: str, color: str = _LINE, scale: float = 1.0,
        vertical: bool = False,
    ) -> None:  # fmt: skip
        size = self.text_size * scale
        self.points += [(u - size, v - size), (u + size, v + size)]
        turn = f' transform="rotate(-90 {u:.1f} {-v:.1f})"' if vertical else ""
        # Linha de base abaixo do centro: o renderizador da Qt ignora dominant-baseline.
        self.items.append(
            f'<text x="{u:.1f}" y="{-v + 0.35 * size:.1f}" font-size="{size:.1f}" '
            f'font-family="sans-serif" text-anchor="middle" fill="{color}"{turn}>'
            f"{escape(label)}</text>"
        )

    def dimension(self, a: float, b: float, at: float, horizontal: bool) -> None:
        """Cota de `a` a `b` [mm] na linha `at`, com o valor em cm no meio."""
        if b - a < 1.0:
            return
        tick = 0.6 * self.text_size

        def point(s: float, t: float) -> tuple[float, float]:
            return (s, t) if horizontal else (t, s)

        self.line(point(a, at), point(b, at), width=0.6)
        for s in (a, b):
            self.line(point(s - tick / 2, at - tick / 2), point(s + tick / 2, at + tick / 2))
        offset = 0.8 * self.text_size
        if horizontal or b - a > 3.0 * self.text_size:
            u, v = point((a + b) / 2, at + offset if horizontal else at - offset)
            self.text(u, v, _cm(b - a), scale=0.85, vertical=not horizontal)
        else:  # cota curta: valor deitado ao lado da linha
            outward = 1.6 * self.text_size if at >= 0 else -1.6 * self.text_size
            self.text(at + outward, (a + b) / 2, _cm(b - a), scale=0.85)

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
            f'height="{height:.1f}" fill="#ffffff"/>' + "".join(self.items) + "</svg>"
        )


def form_plan(geometry: GeometryInput) -> str:
    """Planta de forma: bloco, estacas e pilares, com cotas totais e das estacas [cm]."""
    cap = geometry.cap
    hx, hy = cap.lx / 2, cap.ly / 2
    sheet = _Sheet(max(cap.lx, cap.ly))
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
    return sheet.render()


def form_section(geometry: GeometryInput, axis: Axis, tie_height: float) -> str:
    """Corte pelo centro na direção `axis`: altura, embutimento e eixo do tirante (D8) [cm]."""
    cap = geometry.cap
    length = cap.lx if axis == "x" else cap.ly
    half, h = length / 2, cap.h
    sheet = _Sheet(max(length, 1.6 * h), _SECTION_TEXT)
    gap = 2.5 * sheet.text_size
    stub = 0.3 * h
    sheet.rect(-half, 0.0, length, h)
    for u, size in _projected(((p.x, p.y, p.size) for p in geometry.piles), axis):
        a, b = u - size / 2, u + size / 2
        sheet.polyline([(a, -stub), (a, cap.pile_embedment), (b, cap.pile_embedment), (b, -stub)])
    for c in geometry.columns:
        u, width = (c.x, c.bx) if axis == "x" else (c.y, c.by)
        sheet.polyline([(u - width / 2, h + stub), (u - width / 2, h),
                        (u + width / 2, h), (u + width / 2, h + stub)])  # fmt: skip
    tie = cap.pile_embedment + tie_height
    sheet.line((-half, tie), (half, tie), TIE_COLOR, dash=f"{4 * sheet.stroke} {sheet.stroke}")
    sheet.dimension(0.0, h, half + 2 * gap, horizontal=False)
    sheet.dimension(0.0, cap.pile_embedment, half + gap, horizontal=False)
    sheet.dimension(cap.pile_embedment, tie, -half - gap, horizontal=False)  # do outro lado
    sheet.dimension(-half, half, -stub - gap, horizontal=True)
    return sheet.render()


def model_plan(
    geometry: GeometryInput, layout: StrutTieLayout, reactions: Sequence[PileReaction]
) -> str:
    """Bielas (vermelho) e tirantes (azul) em planta, com as forças e as reações [kN]."""
    cap = geometry.cap
    sheet = _Sheet(max(cap.lx, cap.ly))
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
    sheet = _Sheet(max(length, 1.6 * cap.h), _SECTION_TEXT)
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


def _piles_and_columns(
    sheet: _Sheet, geometry: GeometryInput, color: str, labels: bool = True
) -> None:
    # Pilares antes das estacas, para a estaca sob o pilar (D15) continuar visível.
    for c in geometry.columns:
        sheet.rect(c.x - c.bx / 2, c.y - c.by / 2, c.bx, c.by, color, fill="#e6e6e6")
        if labels:
            sheet.text(c.x, c.y + c.by / 2 - sheet.text_size, c.id, scale=0.85)
    for p in geometry.piles:
        if p.shape is PileShape.CIRCULAR:
            sheet.circle(p.x, p.y, p.size / 2, color)
        else:
            sheet.rect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size, color)
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
