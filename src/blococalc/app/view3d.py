"""Aba 3D: bloco, estacas e modelo de bielas e tirantes de um caso (ADR-006), ou o bloco
pintado pela compressão do MEF quando ele rodou nesta sessão (ADR-012), com cortes,
opacidade, deformada, topo da escala e valor no ponto clicado (ADR-013).

A cena vem pronta de `blococalc.viz.scene`; aqui só se escolhe o caso e se desenha. Sem
PyVista instalado ou sem OpenGL, a aba mostra o motivo e o resto da tela segue funcionando.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from blococalc.analysis import strut_tie_layout
from blococalc.schemas import FemField, MaterialsInput, Project
from blococalc.standards.strength import strut_tie_strengths

_NO_RESULT = "Calcule o bloco para ver o modelo em 3D."
MODEL, STRESSES = "modelo de bielas e tirantes", "tensões do MEF"
_NO_FIELD = "Sem campo de tensões do MEF para o caso {case} (bloco flexível não tem)."
_FLEXIBLE = "Bloco flexível (D9): sem bielas e tirantes; estacas coloridas pela reação."


class Plotter(Protocol):
    """O que a aba usa do `pyvistaqt.QtInteractor` (permite trocar por um falso nos testes)."""

    def add_mesh(self, mesh: Any, **options: Any) -> Any: ...
    def add_point_labels(self, points: Any, labels: Any, **options: Any) -> Any: ...
    def clear(self) -> None: ...
    def view_isometric(self) -> None: ...
    def view_xy(self) -> None: ...
    def view_xz(self) -> None: ...
    def view_yz(self) -> None: ...
    def enable_point_picking(self, callback: Callable[[Any], None], **options: Any) -> Any: ...


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
        self.fields: dict[str, FemField] = {}
        self.fem_project: Project | None = None
        self.display_box = QComboBox()
        self.display_box.addItems([MODEL, STRESSES])
        self.display_box.setEnabled(False)
        self.display_box.setToolTip('Tensões do MEF: rode "Conferir por MEF" nesta sessão.')
        self.display_box.currentTextChanged.connect(self._draw)
        self.note = QLabel(_NO_RESULT)
        self.note.setWordWrap(True)
        self.probe = QLabel()
        self.tools = self._build_tools()
        self.plotter: Plotter | None = None
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Caso"))
        bar.addWidget(self.case_box, 1)
        bar.addWidget(QLabel("Exibir"))
        bar.addWidget(self.display_box, 1)
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
        plotter.enable_point_picking(
            self._picked, left_clicking=True, show_message=False, show_point=True
        )
        layout.addLayout(bar)
        layout.addWidget(self.tools)
        layout.addWidget(widget, 1)
        layout.addWidget(self.probe)
        layout.addWidget(self.note)

    def _build_tools(self) -> QWidget:
        """Controles do modo "tensões do MEF" (ADR-013); mudar um deles só refaz a cena."""
        tools = QWidget()
        row = QHBoxLayout(tools)
        row.setContentsMargins(0, 0, 0, 0)
        self.cuts: dict[str, tuple[QCheckBox, QSlider]] = {}
        for axis in ("x", "y"):
            box, slider = QCheckBox(f"Corte {axis}"), QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)  # % da face negativa à positiva do bloco
            slider.setValue(50)
            slider.setToolTip("Posição do plano: retira a parte do bloco além dele.")
            box.toggled.connect(self._redraw)
            slider.valueChanged.connect(self._redraw)
            row.addWidget(box)
            row.addWidget(slider, 1)
            self.cuts[axis] = (box, slider)
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(10, 100)
        self.opacity.setValue(100)
        self.opacity.valueChanged.connect(self._redraw)
        self.deformation = QDoubleSpinBox()
        self.deformation.setRange(0.0, 10000.0)
        self.deformation.setSingleStep(100.0)
        self.deformation.setDecimals(0)
        self.deformation.setSpecialValueText("sem")
        self.deformation.valueChanged.connect(self._redraw)
        self.scale_max = QDoubleSpinBox()
        self.scale_max.setRange(0.0, 200.0)
        self.scale_max.setDecimals(1)
        self.scale_max.setSpecialValueText("pico")
        self.scale_max.setToolTip("Topo das faixas de cor; acima dele a cor satura.")
        self.scale_max.valueChanged.connect(self._redraw)
        for label, control, stretch in (
            ("Opacidade", self.opacity, 1),
            ("Deformada ×", self.deformation, 0),
            ("Escala até [MPa]", self.scale_max, 0),
        ):
            row.addWidget(QLabel(label))
            row.addWidget(control, stretch)
        tools.setHidden(True)
        return tools

    def stress_view(self) -> Any:
        """`viz.scene.StressView` com os controles da barra, no bloco do campo mostrado."""
        from blococalc.viz.scene import StressView  # noqa: PLC0415 - extra opcional `viz`

        cap = self.fem_project.geometry.cap if self.fem_project is not None else None
        cut: dict[str, float | None] = {}
        for axis, (box, slider) in self.cuts.items():
            size = 0.0 if cap is None else cap.lx if axis == "x" else cap.ly
            cut[axis] = size * (slider.value() / 100.0 - 0.5) if box.isChecked() else None
        return StressView(
            cut_x=cut["x"],
            cut_y=cut["y"],
            opacity=self.opacity.value() / 100.0,
            deformation=self.deformation.value(),
            scale_max=self.scale_max.value() or None,
        )

    @property
    def available(self) -> bool:
        return self.plotter is not None

    def show_project(self, project: Project | None) -> None:
        """Refaz a cena para o projeto calculado; sem resultado, limpa e pede o cálculo."""
        self.project = project if project is not None and project.result is not None else None
        current = self.case_box.currentText()
        self.case_box.blockSignals(True)
        self.case_box.clear()
        source = self.project or self.fem_project
        if source is not None:
            ids = [case.id for case in source.loads.cases]
            self.case_box.addItems(ids)
            if current in ids:
                self.case_box.setCurrentText(current)
        self.case_box.blockSignals(False)
        self._draw()

    def show_fields(self, project: Project | None, fields: tuple[FemField, ...]) -> None:
        """Guarda os campos do MEF desta sessão (ADR-012); sem campos, volta ao modelo."""
        self.fem_project = project if fields else None
        self.fields = {field.case_id: field for field in fields}
        self.display_box.blockSignals(True)
        self.display_box.setEnabled(bool(fields))
        if not fields:
            self.display_box.setCurrentText(MODEL)
        self.display_box.blockSignals(False)
        self.show_project(self.project)

    def _redraw(self, *_: object) -> None:
        """Controle da barra mudou: refaz a cena sem mexer na câmera."""
        self._draw(reset_camera=False)

    def _draw(self, *_: object, reset_camera: bool = True) -> None:
        if self.plotter is not None:
            self.plotter.clear()
        self.scene = None
        self.probe.clear()
        stresses = self.display_box.currentText() == STRESSES and self.fem_project is not None
        self.tools.setHidden(not stresses)
        try:
            from blococalc.viz import scene  # noqa: PLC0415 - extra opcional `viz`
        except ImportError:  # pragma: no cover - o CI instala o extra `viz`
            self._tell('Visualização 3D indisponível: instale o extra ".[viz]".')
            return
        if stresses and self.fem_project is not None:
            self._draw_stresses(self.fem_project, self.case_box.currentText(), reset_camera)
            return
        project, case_id = self.project, self.case_box.currentText()
        if project is None or project.result is None or not case_id:
            self._tell(_NO_RESULT)
            return
        try:
            layout = strut_tie_layout(project, case_id)
        except ValueError as error:
            layout, message = None, f"Modelo de bielas e tirantes indisponível: {error}"
        else:
            message = _FLEXIBLE if layout is None else _legend()
        reactions = [r for r in project.result.reactions if r.case_id == case_id]
        self.scene = scene.cap_scene(project.geometry, reactions, layout)
        self._tell(message)
        self._paint(reset_camera)

    def _draw_stresses(self, project: Project, case_id: str, reset_camera: bool) -> None:
        from blococalc.viz.scene import stress_scene  # noqa: PLC0415 - extra opcional `viz`

        field = self.fields.get(case_id)
        if field is None:
            self._tell(_NO_FIELD.format(case=case_id))
            return
        view = self.stress_view()
        self.scene = stress_scene(project.geometry, field, view)
        note = _stress_note(case_id, self.scene.peak, project.materials)
        if view.deformation:
            note += (
                f" Deformada ampliada {view.deformation:.0f} vezes; deslocamento máximo real "
                f"{self.scene.displacement:.3f} mm."
            )
        self._tell(note)
        self._paint(reset_camera)

    def _paint(self, reset_camera: bool) -> None:
        if self.plotter is None or self.scene is None:
            return
        from blococalc.viz.scene import draw  # noqa: PLC0415 - extra opcional `viz`

        draw(self.plotter, self.scene)
        if reset_camera:
            self.plotter.view_isometric()

    def _picked(self, point: Any) -> None:
        """Clique sobre o desenho: valor do MEF no nó mais próximo (ADR-013, item 5)."""
        if self.scene is None or self.display_box.currentText() != STRESSES:
            self.probe.clear()
            return
        from blococalc.viz.scene import value_at  # noqa: PLC0415 - extra opcional `viz`

        x, y, z = (float(c) for c in point)
        probed = value_at(self.scene, (x, y, z))
        self.probe.setText("" if probed is None else f"Ponto clicado: {probed.text()}")

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


def _stress_note(case_id: str, peak: float, materials: MaterialsInput) -> str:
    """Pico do caso e, só como referência, os limites do método (ADR-012, item 4)."""
    strengths = strut_tie_strengths(materials)
    return (
        f"Compressão do MEF no caso {case_id}: máxima {peak:.1f} MPa. Referência do método "
        f"(NBR 6118:2023, 22.3.2): fcd1 = {strengths.fcd1:.1f} MPa, "
        f"fcd3 = {strengths.fcd3:.1f} MPa. O pico sob o pilar é concentração do modelo "
        "elástico, não verificação: quem verifica é o método e as médias da aba MEF."
    )
