"""Cena 3D do bloco e do modelo de bielas e tirantes (ADR-006).

Monta as malhas PyVista sem janela e sem Qt; a tela (`blococalc.app`) só as desenha.
Origem no centro do bloco em planta e na face inferior; z para cima; mm.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pyvista as pv

from blococalc.schemas import (
    FemField,
    GeometryInput,
    LayoutMemberKind,
    PileReaction,
    PileShape,
    StrutTieLayout,
)

Color = tuple[float, float, float]

CAP_COLOR: Color = (0.75, 0.75, 0.72)
CAP_OPACITY = 0.25
COLUMN_COLOR: Color = (0.55, 0.55, 0.55)
NEUTRAL_COLOR: Color = (0.85, 0.85, 0.85)
COMPRESSION_COLOR: Color = (0.93, 0.55, 0.13)
TENSION_COLOR: Color = (0.55, 0.25, 0.70)
STRUT_COLOR: Color = (0.80, 0.15, 0.15)
TIE_COLOR: Color = (0.15, 0.35, 0.80)
LEGEND: tuple[tuple[str, Color], ...] = (
    ("Biela (compressão)", STRUT_COLOR),
    ("Tirante (tração)", TIE_COLOR),
    ("Estaca mais comprimida", COMPRESSION_COLOR),
    ("Estaca tracionada", TENSION_COLOR),
)

_MAX_RADIUS = 0.04  # raio da barra mais forte, fração do menor lado do bloco
_MIN_RADIUS = 0.2  # raio mínimo, fração do raio máximo, para a barra não sumir
_PILE_LENGTH = 1.5  # trecho de estaca desenhado abaixo do bloco, em alturas do bloco
_COLUMN_LENGTH = 1.5  # trecho de pilar desenhado acima do bloco, em maiores lados do pilar
COMPRESSION = "compressao_MPa"  # −σ3 sem a tração, nos nós (ADR-012)
STRESS_BANDS = 12
STRESS_PALETTE = "jet"  # azul (zero) ao vermelho (máximo), como nos programas de MEF


@dataclass(frozen=True)
class SceneItem:
    name: str
    mesh: pv.DataSet
    color: Color
    opacity: float = 1.0
    radius: float = 0.0  # barras do modelo [mm]
    scalars: str = ""  # dado nodal que pinta a malha no lugar de `color`
    clim: tuple[float, float] | None = None
    bands: int = 0  # faixas de cor (0 = contínuo)


@dataclass(frozen=True)
class CapScene:
    items: tuple[SceneItem, ...]
    legend: tuple[tuple[str, Color], ...] = LEGEND
    peak: float = 0.0  # maior valor pintado (compressão máxima no campo do MEF) [MPa]

    def item(self, name: str) -> SceneItem:
        for item in self.items:
            if item.name == name:
                return item
        raise KeyError(name)

    def radius(self, name: str) -> float:
        return self.item(name).radius


def cap_scene(
    geometry: GeometryInput,
    reactions: Sequence[PileReaction],
    layout: StrutTieLayout | None,
) -> CapScene:
    """Bloco translúcido, pilares, estacas coloridas pela reação e, com `layout`, as barras.

    `reactions` são as de um caso; estaca sem reação fica neutra. A espessura das barras
    representa a força: área proporcional, com a barra mais forte em 4 % do menor lado.
    """
    cap = geometry.cap
    items = [
        SceneItem(
            "bloco",
            pv.Box((-cap.lx / 2, cap.lx / 2, -cap.ly / 2, cap.ly / 2, 0.0, cap.h)),
            CAP_COLOR,
            CAP_OPACITY,
        )
    ]
    forces = {r.pile_id: r.force for r in reactions}
    largest = max((abs(f) for f in forces.values()), default=0.0)
    items += _columns_and_piles(
        geometry, lambda pid: _reaction_color(forces.get(pid, 0.0), largest)
    )
    if layout is not None:
        items += _members(layout, _MAX_RADIUS * min(cap.lx, cap.ly))
    return CapScene(tuple(items))


def stress_scene(geometry: GeometryInput, field: FemField) -> CapScene:
    """Bloco pintado pela compressão do MEF (−σ3, sem a tração) em faixas (ADR-012).

    Malha C3D10 como célula quadrática do VTK (mesma ordem de nós), 12 faixas de 0 ao máximo do
    caso; pilares e estacas em cinza, sem a treliça.
    """
    points = np.asarray(field.nodes, dtype=float).reshape(-1, 3)
    tets = np.asarray(field.tetrahedra, dtype=np.int64).reshape(-1, 10)
    cells = np.hstack([np.full((len(tets), 1), 10, dtype=np.int64), tets]).ravel()
    grid = pv.UnstructuredGrid(
        cells, np.full(len(tets), pv.CellType.QUADRATIC_TETRA, dtype=np.uint8), points
    )
    compression = np.clip(-np.asarray(field.sigma3, dtype=float), 0.0, None)
    grid.point_data[COMPRESSION] = compression
    peak = float(compression.max(initial=0.0))
    painted = SceneItem(
        "tensoes",
        grid,
        NEUTRAL_COLOR,
        scalars=COMPRESSION,
        clim=(0.0, peak if peak > 0 else 1.0),
        bands=STRESS_BANDS,
    )
    gray = _columns_and_piles(geometry, lambda _: NEUTRAL_COLOR)
    return CapScene((painted, *gray), legend=(), peak=peak)


class Plotter(Protocol):
    def add_mesh(self, mesh: pv.DataSet, **options: object) -> object: ...


def draw(plotter: Plotter, scene: CapScene) -> None:
    """Desenha a cena num plotter do PyVista (na tela ou fora dela)."""
    for item in scene.items:
        options: dict[str, object] = {"name": item.name, "opacity": item.opacity}
        if item.scalars:
            options |= {
                "scalars": item.scalars,
                "cmap": STRESS_PALETTE,
                "n_colors": item.bands or 256,
                "clim": item.clim,
                "scalar_bar_args": {"title": "Compressão [MPa]", "n_labels": 7, "fmt": "%.1f"},
            }
        else:
            options["color"] = item.color
        plotter.add_mesh(item.mesh, **options)


def _columns_and_piles(
    geometry: GeometryInput, pile_color: Callable[[str], Color]
) -> list[SceneItem]:
    """Pilares acima do bloco e estacas cortadas abaixo dele, até o embutimento."""
    cap = geometry.cap
    items: list[SceneItem] = []
    for column in geometry.columns:
        height = _COLUMN_LENGTH * max(column.bx, column.by)
        bounds = (
            column.x - column.bx / 2,
            column.x + column.bx / 2,
            column.y - column.by / 2,
            column.y + column.by / 2,
            cap.h,
            cap.h + height,
        )
        items.append(SceneItem(f"pilar_{column.id}", pv.Box(bounds), COLUMN_COLOR))

    bottom = -_PILE_LENGTH * cap.h
    for pile in geometry.piles:
        if pile.shape is PileShape.SQUARE:
            half = pile.size / 2
            mesh = pv.Box(
                (
                    pile.x - half,
                    pile.x + half,
                    pile.y - half,
                    pile.y + half,
                    bottom,
                    cap.pile_embedment,
                )
            )
        else:
            length = cap.pile_embedment - bottom
            mesh = pv.Cylinder(
                center=(pile.x, pile.y, bottom + length / 2),
                direction=(0.0, 0.0, 1.0),
                radius=pile.size / 2,
                height=length,
                resolution=48,
            )
        items.append(SceneItem(f"estaca_{pile.id}", mesh, pile_color(pile.id)))

    return items


def _members(layout: StrutTieLayout, max_radius: float) -> list[SceneItem]:
    nodes = {n.id: (n.x, n.y, n.z) for n in layout.nodes}
    strongest = max((m.force_d for m in layout.members), default=0.0)
    items = []
    for member in layout.members:
        start, end = nodes[member.start], nodes[member.end]
        share = math.sqrt(member.force_d / strongest) if strongest > 0 else 0.0
        radius = max_radius * max(share, _MIN_RADIUS)
        axis = tuple(b - a for a, b in zip(start, end, strict=True))
        mesh = pv.Cylinder(
            center=tuple((a + b) / 2 for a, b in zip(start, end, strict=True)),
            direction=axis,
            radius=radius,
            height=math.hypot(*axis),
            resolution=24,
        )
        color = STRUT_COLOR if member.kind is LayoutMemberKind.STRUT else TIE_COLOR
        items.append(SceneItem(member.id, mesh, color, radius=radius))
    return items


def _reaction_color(force: float, largest: float) -> Color:
    """Do neutro à cor da compressão (ou da tração) na proporção da maior reação em módulo."""
    if largest <= 0:
        return NEUTRAL_COLOR
    target = COMPRESSION_COLOR if force >= 0 else TENSION_COLOR
    share = abs(force) / largest
    r, g, b = (n + (t - n) * share for n, t in zip(NEUTRAL_COLOR, target, strict=True))
    return (r, g, b)
