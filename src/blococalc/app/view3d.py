"""Aba 3D: bloco, estacas e modelo de bielas e tirantes de um caso (ADR-006).

A cena vem pronta de `blococalc.viz.scene`; aqui só se escolhe o caso e se desenha. Sem
PyVista instalado ou sem OpenGL, a aba mostra o motivo e o resto da tela segue funcionando.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blococalc.analysis import strut_tie_layout
from blococalc.schemas import Project

_NO_RESULT = "Calcule o bloco para ver o modelo em 3D."
_FLEXIBLE = "Bloco flexível (D9): sem bielas e tirantes; estacas coloridas pela reação."


class Plotter(Protocol):
    """O que a aba usa do `pyvistaqt.QtInteractor` (permite trocar por um falso nos testes)."""

    def add_mesh(self, mesh: Any, **options: Any) -> Any: ...
    def clear(self) -> None: ...
    def view_isometric(self) -> None: ...
    def view_xy(self) -> None: ...
    def view_xz(self) -> None: ...
    def view_yz(self) -> None: ...


PlotterFactory = Callable[[QWidget], tuple[QWidget, Plotter]]


def interactor(parent: QWidget) -> tuple[QWidget, Plotter]:
    """`QtInteractor` do pyvistaqt; erro com o motivo quando não dá para desenhar."""
    if QGuiApplication.platformName() in ("offscreen", "minimal"):
        raise RuntimeError("esta sessão não tem tela (OpenGL indisponível)")
    try:
        from pyvistaqt import QtInteractor  # noqa: PLC0415 - extra opcional `viz`
    except ImportError as error:
        raise RuntimeError(
            'PyVista não instalado; instale com python -m pip install -e ".[viz]"'
        ) from error
    widget: Any = QtInteractor(parent)  # QWidget e Plotter ao mesmo tempo
    return widget, widget


class View3D(QWidget):
    def __init__(self, factory: PlotterFactory = interactor) -> None:
        super().__init__()
        self.project: Project | None = None
        self.scene: Any = None  # viz.scene.CapScene; Any porque o extra `viz` é opcional
        self.case_box = QComboBox()
        self.case_box.currentTextChanged.connect(self._draw)
        self.note = QLabel(_NO_RESULT)
        self.note.setWordWrap(True)
        self.plotter: Plotter | None = None
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Caso"))
        bar.addWidget(self.case_box, 1)
        self.view_buttons: dict[str, QPushButton] = {}
        try:
            widget, self.plotter = factory(self)
        except RuntimeError as error:
            self.note.setText(f"Visualização 3D indisponível: {error}.")
            layout.addLayout(bar)
            layout.addWidget(self.note)
            layout.addStretch(1)
            return
        plotter = self.plotter
        for label, action in (
            ("Isométrica", plotter.view_isometric),
            ("Planta", plotter.view_xy),
            ("Frente", plotter.view_xz),
            ("Lateral", plotter.view_yz),
        ):
            button = QPushButton(label)
            button.clicked.connect(action)
            bar.addWidget(button)
            self.view_buttons[label] = button
        layout.addLayout(bar)
        layout.addWidget(widget, 1)
        layout.addWidget(self.note)

    @property
    def available(self) -> bool:
        return self.plotter is not None

    def show_project(self, project: Project | None) -> None:
        """Refaz a cena para o projeto calculado; sem resultado, limpa e pede o cálculo."""
        self.project = project if project is not None and project.result is not None else None
        current = self.case_box.currentText()
        self.case_box.blockSignals(True)
        self.case_box.clear()
        if self.project is not None:
            ids = [case.id for case in self.project.loads.cases]
            self.case_box.addItems(ids)
            if current in ids:
                self.case_box.setCurrentText(current)
        self.case_box.blockSignals(False)
        self._draw()

    def _draw(self, *_: object) -> None:
        if self.plotter is not None:
            self.plotter.clear()
        project, case_id = self.project, self.case_box.currentText()
        self.scene = None
        if project is None or project.result is None or not case_id:
            self._tell(_NO_RESULT)
            return
        try:
            from blococalc.viz.scene import cap_scene  # noqa: PLC0415 - extra opcional `viz`
        except ImportError:  # pragma: no cover - o CI instala o extra `viz`
            self._tell('Visualização 3D indisponível: instale o extra ".[viz]".')
            return
        try:
            layout = strut_tie_layout(project, case_id)
        except ValueError as error:
            layout, message = None, f"Modelo de bielas e tirantes indisponível: {error}"
        else:
            message = _FLEXIBLE if layout is None else _legend()
        reactions = [r for r in project.result.reactions if r.case_id == case_id]
        self.scene = cap_scene(project.geometry, reactions, layout)
        self._tell(message)
        if self.plotter is None:
            return
        for item in self.scene.items:
            self.plotter.add_mesh(item.mesh, color=item.color, opacity=item.opacity, name=item.name)
        self.plotter.view_isometric()

    def _tell(self, message: str) -> None:
        """Sem desenho, a nota continua explicando por que a aba está indisponível."""
        if self.available:
            self.note.setText(message)


def _legend() -> str:
    from blococalc.viz.scene import LEGEND  # noqa: PLC0415 - extra opcional `viz`

    parts = []
    for label, (r, g, b) in LEGEND:
        color = f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"
        parts.append(f'<span style="color:{color}">&#9632;</span> {label}')
    return "&nbsp;&nbsp;".join(parts) + "&nbsp;&nbsp;(espessura proporcional à força)"
