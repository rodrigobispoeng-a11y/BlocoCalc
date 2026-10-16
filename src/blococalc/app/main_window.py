"""Primeira tela: entrada de um bloco com pilares, estacas e casos de carga em tabelas.

Conversões de unidade só aqui (CLAUDE.md §4): a tela usa kN e kN·m; o motor, N e N·mm.
A tela só conhece `blococalc.analysis`, `blococalc.persistence` e `blococalc.schemas`.
O menu Arquivo grava e abre projetos `.bloco` (ADR-004). A conferência por MEF (D14) roda em
segundo plano, com o formulário bloqueado até terminar.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from blococalc.analysis import analyze, fem_verification, refresh_project
from blococalc.persistence.project import EXTENSION, ProjectFileError, load_project, save_project
from blococalc.schemas import (
    AggressivenessClass,
    AnalysisResult,
    Cap,
    CheckStatus,
    Column,
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Pile,
    Project,
)

KN = 1e3  # N
KNM = 1e6  # N·mm

# Exemplo inicial: benchmark B1 (Macedo 2022, §6.1), Fd = 980 kN.
_DEFAULT_PILES = (("E1", -600.0, -600.0), ("E2", 600.0, -600.0), ("E3", 600.0, 600.0),
                  ("E4", -600.0, 600.0))  # fmt: skip
_PILE_HEADERS = ("Estaca", "x [mm]", "y [mm]", "φ [mm]")
_COLUMN_HEADERS = ("Pilar", "x [mm]", "y [mm]", "bx [mm]", "by [mm]")
_LOAD_HEADERS = ("Caso", "Pilar", "Nd [kN]", "Mxd [kN·m]", "Myd [kN·m]", "Hxd [kN]", "Hyd [kN]")
_NEW_NAME = "Novo projeto"
_FILTER = f"Projetos BlocoCalc (*{EXTENSION})"


def _spin(value: float, maximum: float, decimals: int = 1, minimum: float = 0.0) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setValue(value)
    return box


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setMinimumHeight(150)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    for row in rows:
        _append_row(table, row)
    return table


def _append_row(table: QTableWidget, values: Sequence[object]) -> None:
    row = table.rowCount()
    table.insertRow(row)
    for column, value in enumerate(values):
        table.setItem(row, column, QTableWidgetItem(str(value)))


class _FemRunner(QObject):
    """Roda `fem_verification` numa thread e entrega o resultado (ou a falha) na thread da tela."""

    finished = Signal(object)

    def start(
        self, inputs: tuple[GeometryInput, MaterialsInput, LoadsInput, DetailingInput]
    ) -> None:
        threading.Thread(target=self._run, args=(inputs,), daemon=True).start()

    def _run(
        self, inputs: tuple[GeometryInput, MaterialsInput, LoadsInput, DetailingInput]
    ) -> None:
        try:
            outcome: AnalysisResult | Exception = fem_verification(*inputs)
        except Exception as error:  # qualquer falha do MEF vai para a tela
            outcome = error
        self.finished.emit(outcome)


def _rows(table: QTableWidget) -> list[list[str]]:
    """Texto das células; célula vazia vira "" e falha na conversão com mensagem na tela."""
    cells = (
        [table.item(row, c) for c in range(table.columnCount())] for row in range(table.rowCount())
    )
    return [[cell.text().strip() if cell else "" for cell in row] for row in cells]


class MainWindow(QMainWindow):
    """Formulário de entrada à esquerda e resultados em abas à direita."""

    def __init__(self) -> None:
        super().__init__()
        self.result: AnalysisResult | None = None
        self.fem_result: AnalysisResult | None = None
        self.path: Path | None = None
        self.modified = False
        self._loading = False
        self.name = QLineEdit(_NEW_NAME)
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(80)

        self.cap = {
            "lx": _spin(2000.0, 20000.0),
            "ly": _spin(2000.0, 20000.0),
            "h": _spin(1000.0, 5000.0),
            "pile_embedment": _spin(100.0, 500.0),
            "cover": _spin(50.0, 200.0),
        }
        self.columns = _table(_COLUMN_HEADERS, [("P1", 0.0, 0.0, 200.0, 650.0)])
        self.materials = {"fck": _spin(35.0, 90.0), "fyk": _spin(500.0, 600.0)}
        self.loads = _table(_LOAD_HEADERS, [("ELU1", "P1", 980.0, 0.0, 0.0, 0.0, 0.0)])
        self.gamma_n = _spin(1.2, 2.0, decimals=2, minimum=1.0)
        self.bar_diameter = _spin(16.0, 40.0)
        self.aggressiveness = QComboBox()
        self.aggressiveness.addItems([c.value for c in AggressivenessClass])
        self.aggressiveness.setCurrentText(AggressivenessClass.II.value)
        self.piles = _table(_PILE_HEADERS, [(*pile, 400.0) for pile in _DEFAULT_PILES])
        self.summary = QPlainTextEdit(readOnly=True)
        self.reactions_table = QTableWidget()
        self.checks_table = QTableWidget()
        self.reinforcement_table = QTableWidget()
        self.status = QLabel()
        self.status.setWordWrap(True)

        self.calculate_button = QPushButton("Calcular")
        self.calculate_button.clicked.connect(self.calculate)
        self.fem_button = QPushButton("Conferir por MEF")
        self.fem_button.clicked.connect(self.run_fem)
        self.fem_summary = QPlainTextEdit(readOnly=True)
        self.fem_table = QTableWidget()
        self.fem_running = False
        self._fem_runner = _FemRunner(self)
        self._fem_runner.finished.connect(self._fem_finished)
        self._build_layout()
        self._build_menu()
        self._watch_changes()
        self._blank = self.project()
        self._update_title()

    def _build_layout(self) -> None:
        form = QVBoxLayout()
        project = QGroupBox("Projeto")
        project_layout = QFormLayout(project)
        project_layout.addRow("Nome", self.name)
        project_layout.addRow("Observações", self.notes)
        form.addWidget(project)
        groups = (
            ("Bloco [mm]", self.cap, ("Lx", "Ly", "h", "Embutimento da estaca", "Cobrimento")),
            ("Materiais [MPa]", self.materials, ("fck", "fyk")),
        )
        for title, fields, labels in groups:
            box = QGroupBox(title)
            layout = QFormLayout(box)
            for label, widget in zip(labels, fields.values(), strict=True):
                layout.addRow(label, widget)
            form.addWidget(box)
        detailing = QGroupBox("Detalhamento")
        detailing_layout = QFormLayout(detailing)
        detailing_layout.addRow("γn", self.gamma_n)
        detailing_layout.addRow("φ dos tirantes [mm]", self.bar_diameter)
        detailing_layout.addRow("Classe de agressividade", self.aggressiveness)
        form.addWidget(detailing)

        tables = (
            ("Pilares", self.columns, lambda n: (f"P{n}", 0.0, 0.0, 200.0, 200.0)),
            ("Estacas", self.piles, lambda n: (f"E{n}", 0.0, 0.0, 400.0)),
            ("Casos de cálculo (um pilar por linha)", self.loads,
             lambda n: ("ELU1", f"P{n}", 0.0, 0.0, 0.0, 0.0, 0.0)),
        )  # fmt: skip
        for title, table, default in tables:
            form.addWidget(self._table_box(title, table, default))
        form.addWidget(self.calculate_button)
        form.addWidget(self.fem_button)

        tabs = QTabWidget()
        tabs.addTab(self.summary, "Resumo")
        tabs.addTab(self.reactions_table, "Reações")
        tabs.addTab(self.checks_table, "Verificações")
        tabs.addTab(self.reinforcement_table, "Armaduras")
        fem_tab = QWidget()
        fem_layout = QVBoxLayout(fem_tab)
        fem_layout.addWidget(self.fem_summary, 1)
        fem_layout.addWidget(self.fem_table, 2)
        tabs.addTab(fem_tab, "MEF")
        right = QVBoxLayout()
        right.addWidget(tabs)
        right.addWidget(self.status)

        form_widget = QWidget()
        form_widget.setLayout(form)
        self.form_area = QScrollArea()
        self.form_area.setWidget(form_widget)
        self.form_area.setWidgetResizable(True)
        root = QHBoxLayout()
        root.addWidget(self.form_area, 1)
        root.addLayout(right, 2)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

    @staticmethod
    def _table_box(
        title: str, table: QTableWidget, default: Callable[[int], Sequence[object]]
    ) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(table)
        buttons = QHBoxLayout()
        add, remove = QPushButton("Adicionar"), QPushButton("Remover")
        add.clicked.connect(lambda: _append_row(table, default(table.rowCount() + 1)))
        remove.clicked.connect(lambda: table.removeRow(table.rowCount() - 1))
        buttons.addWidget(add)
        buttons.addWidget(remove)
        layout.addLayout(buttons)
        return box

    def inputs(self) -> tuple[GeometryInput, MaterialsInput, LoadsInput, DetailingInput]:
        """Lê o formulário e converte para os contratos (N, mm, MPa).

        Linhas de carga com o mesmo caso formam um `LoadCase`, na ordem em que aparecem.
        """
        geometry = GeometryInput(
            cap=Cap(**{name: box.value() for name, box in self.cap.items()}),
            piles=tuple(
                Pile(id=i, x=float(x), y=float(y), size=float(d))
                for i, x, y, d in _rows(self.piles)
            ),
            columns=tuple(
                Column(id=i, x=float(x), y=float(y), bx=float(bx), by=float(by))
                for i, x, y, bx, by in _rows(self.columns)
            ),
        )
        materials = MaterialsInput(**{k: b.value() for k, b in self.materials.items()})
        cases: dict[str, list[ColumnLoad]] = {}
        for case_id, column_id, n, mx, my, hx, hy in _rows(self.loads):
            cases.setdefault(case_id, []).append(
                ColumnLoad(
                    column_id=column_id,
                    n=float(n) * KN,
                    mx=float(mx) * KNM,
                    my=float(my) * KNM,
                    hx=float(hx) * KN,
                    hy=float(hy) * KN,
                )
            )
        if not cases:
            raise ValueError("informe ao menos um caso de cálculo")
        detailing = DetailingInput(
            bar_diameter=self.bar_diameter.value(),
            aggressiveness_class=AggressivenessClass(self.aggressiveness.currentText()),
        )
        return (
            geometry,
            materials,
            LoadsInput(
                cases=tuple(LoadCase(id=k, column_loads=tuple(v)) for k, v in cases.items()),
                gamma_n=self.gamma_n.value(),
            ),
            detailing,
        )

    def calculate(self) -> None:
        """Roda a análise; erro de entrada ou de modelo aparece na linha de estado."""
        try:
            self.result = analyze(*self.inputs())
        except ValueError as error:
            self.result = None
            self.status.setText(f"Não foi possível calcular: {error}")
            return
        self._mark_modified()
        self._show(self.result)
        self.status.setText(self.result.disclaimer)

    def _show(self, result: AnalysisResult | None) -> None:
        if result is None:
            self.summary.clear()
            for table in (self.reactions_table, self.checks_table, self.reinforcement_table):
                table.clear()
                table.setRowCount(0)
            return
        lines = [
            f"Bloco {'rígido' if result.rigid else 'flexível'} (NBR 6118:2023, 22.7.1)",
            f"Método: {result.audit.method}",
            "",
            "Alertas:",
            *(f"- {w}" for w in result.warnings or ("nenhum",)),
            "",
            "Premissas:",
            *(f"- {a}" for a in result.audit.assumptions),
        ]
        self.summary.setPlainText("\n".join(lines))
        reactions = [(r.pile_id, r.case_id, f"{r.force / KN:.2f}") for r in result.reactions]
        _fill(self.reactions_table, ("Estaca", "Caso", "Rd [kN]"), reactions)
        _fill(
            self.checks_table,
            ("Verificação", "Solicitante", "Resistente", "Unidade", "Situação", "Item"),
            [
                (c.description, f"{c.demand:.3f}", f"{c.capacity:.3f}", c.unit,
                 c.status.value, f"{c.reference.source}, {c.reference.item}")
                for c in result.checks
            ],
        )  # fmt: skip
        _fill(
            self.reinforcement_table,
            ("Armadura", "Tipo", "As [cm²]", "φ [mm]", "Item"),
            [
                (r.id, r.kind.value, f"{r.area_required / 100:.2f}", f"{r.bar_diameter:.0f}",
                 r.reference.item)
                for r in result.reinforcement
            ],
        )  # fmt: skip

    # ----------------------------------------------------------------------------------
    # Projeto e menu Arquivo (ADR-004)
    # ----------------------------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&Arquivo")
        key = QKeySequence.StandardKey
        entries: tuple[tuple[str, QKeySequence.StandardKey, Callable[[], object]], ...] = (
            ("&Novo", key.New, self.new_project),
            ("&Abrir...", key.Open, self.open_project),
            ("&Salvar", key.Save, self.save),
            ("Salvar &como...", key.SaveAs, self.save_as),
            ("Sai&r", key.Quit, self.close),
        )
        for text, shortcut, slot in entries:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda _=False, slot=slot: slot())
            menu.addAction(action)

    def _watch_changes(self) -> None:
        spins = (*self.cap.values(), *self.materials.values(), self.gamma_n, self.bar_diameter)
        for box in spins:
            box.valueChanged.connect(self._inputs_changed)
        self.aggressiveness.currentTextChanged.connect(self._inputs_changed)
        self.name.textChanged.connect(self._mark_modified)
        self.notes.textChanged.connect(self._mark_modified)
        for table in (self.columns, self.piles, self.loads):
            table.itemChanged.connect(self._inputs_changed)
            table.model().rowsInserted.connect(self._inputs_changed)
            table.model().rowsRemoved.connect(self._inputs_changed)

    def _inputs_changed(self, *_: object) -> None:
        """Entrada alterada: o resultado do MEF deixa de valer e sai da tela."""
        if self._loading:
            return
        self._mark_modified()
        if self.fem_result is not None:
            self.fem_result = None
            self._show_fem(None)
            self.status.setText("Entradas alteradas: o resultado do MEF foi descartado.")

    def _mark_modified(self, *_: object) -> None:
        if not self._loading:
            self.modified = True
            self._update_title()

    def _update_title(self) -> None:
        name = self.name.text().strip() or _NEW_NAME
        self.setWindowTitle(f"{name}[*] — BlocoCalc (NBR 6118:2023)")
        self.setWindowModified(self.modified)

    def project(self) -> Project:
        """Projeto com as entradas da tela e os últimos resultados, como estão."""
        geometry, materials, loads, detailing = self.inputs()
        return Project(
            name=self.name.text().strip() or _NEW_NAME,
            notes=self.notes.toPlainText(),
            geometry=geometry,
            materials=materials,
            loads=loads,
            detailing=detailing,
            result=self.result,
            fem_result=self.fem_result,
        )

    def set_project(self, project: Project) -> None:
        """Preenche a tela com o projeto (kN e kN·m) e mostra o resultado salvo."""
        self._loading = True
        try:
            self.name.setText(project.name)
            self.notes.setPlainText(project.notes)
            for name, box in self.cap.items():
                box.setValue(getattr(project.geometry.cap, name))
            for name, box in self.materials.items():
                box.setValue(getattr(project.materials, name))
            self.gamma_n.setValue(project.loads.gamma_n)
            self.bar_diameter.setValue(project.detailing.bar_diameter)
            self.aggressiveness.setCurrentText(project.detailing.aggressiveness_class.value)
            rows: tuple[tuple[QTableWidget, list[tuple[object, ...]]], ...] = (
                (self.piles, [(p.id, p.x, p.y, p.size) for p in project.geometry.piles]),
                (
                    self.columns,
                    [(c.id, c.x, c.y, c.bx, c.by) for c in project.geometry.columns],
                ),
                (self.loads, _load_rows(project.loads)),
            )
            for table, values in rows:
                table.setRowCount(0)
                for row in values:
                    _append_row(table, row)
            self.result, self.fem_result = project.result, project.fem_result
            self._show(project.result)
            self._show_fem(project.fem_result)
        finally:
            self._loading = False

    def save(self) -> bool:
        return self.save_as() if self.path is None else self.save_to(self.path)

    def save_as(self) -> bool:
        start = str(self.path or Path(self.name.text().strip() or _NEW_NAME))
        name, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", start, _FILTER)
        if not name:
            return False
        path = Path(name)
        if path.suffix.lower() != EXTENSION:
            path = path.with_name(path.name + EXTENSION)
        return self.save_to(path)

    def save_to(self, path: Path) -> bool:
        """Grava o projeto; antes descarta ou recalcula resultados desatualizados."""
        try:
            project, warnings = refresh_project(self.project())
            save_project(path, project)
        except (ValueError, ProjectFileError) as error:
            self.status.setText(f"Não foi possível salvar: {error}")
            return False
        self.result, self.fem_result = project.result, project.fem_result
        self._show(project.result)
        self._show_fem(project.fem_result)
        self.path, self.modified = path, False
        self._update_title()
        self.status.setText(" ".join((f"Projeto salvo em {path}.", *warnings)))
        return True

    def open_project(self) -> None:
        if not self._confirm_discard():
            return
        start = str(self.path.parent) if self.path else ""
        name, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", start, _FILTER)
        if name:
            self.open_path(Path(name))

    def open_path(self, path: Path) -> bool:
        """Abre o projeto e avisa sobre resultados descartados e dados fora da tela."""
        try:
            project, warnings = refresh_project(load_project(path))
        except (ValueError, ProjectFileError) as error:
            self.status.setText(f"Não foi possível abrir: {error}")
            return False
        self.set_project(project)
        self.path, self.modified = path, False
        self._update_title()
        shown = self.inputs()
        saved = (project.geometry, project.materials, project.loads, project.detailing)
        if not all(_same(a.model_dump(mode="json"), b.model_dump(mode="json"))
                   for a, b in zip(shown, saved, strict=True)):  # fmt: skip
            warnings = (
                *warnings,
                "O projeto tem dados que a tela não mostra ou arredonda (ex.: estaca quadrada); "
                "ao salvar, valem os valores da tela.",
            )
        self.status.setText(" ".join((f"Projeto aberto: {path}.", *warnings)))
        return True

    def new_project(self) -> None:
        if self._confirm_discard():
            self.set_project(self._blank)
            self.path, self.modified = None, False
            self._update_title()
            self.status.clear()

    def _confirm_discard(self) -> bool:
        """Pergunta se salva as alterações pendentes; False cancela a ação."""
        if not self.modified:
            return True
        button = QMessageBox.StandardButton
        answer = QMessageBox.question(
            self,
            "BlocoCalc",
            f"Salvar as alterações em {self.name.text().strip() or _NEW_NAME}?",
            button.Save | button.Discard | button.Cancel,
        )
        if answer == button.Save:
            return self.save()
        return answer == button.Discard

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - nome do Qt
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    # ----------------------------------------------------------------------------------
    # Conferência por MEF (D14)
    # ----------------------------------------------------------------------------------

    def run_fem(self) -> None:
        """Roda o MEF em segundo plano; o formulário fica bloqueado até o fim."""
        try:
            inputs = self.inputs()
        except ValueError as error:
            self.status.setText(f"Não foi possível rodar o MEF: {error}")
            return
        self.fem_running = True
        self.form_area.setEnabled(False)
        self.status.setText("Rodando o MEF (gmsh e CalculiX); pode levar alguns minutos...")
        self._fem_runner.start(inputs)

    def _fem_finished(self, outcome: object) -> None:
        self.fem_running = False
        self.form_area.setEnabled(True)
        if not isinstance(outcome, AnalysisResult):
            hint = " Instale o extra fem (gmsh)." if isinstance(outcome, ImportError) else ""
            self.status.setText(f"Não foi possível rodar o MEF: {outcome}.{hint}")
            return
        self.fem_result = outcome
        self._show_fem(outcome)
        self._mark_modified()
        failed = sum(c.status is not CheckStatus.OK for c in outcome.checks)
        self.status.setText(
            f"MEF concluído: {failed} verificação(ões) não atendida(s). Veja a aba MEF."
            if failed
            else "MEF concluído: todas as verificações atendidas. Veja a aba MEF."
        )

    def _show_fem(self, result: AnalysisResult | None) -> None:
        if result is None:
            self.fem_summary.clear()
            self.fem_table.clear()
            self.fem_table.setRowCount(0)
            return
        lines = [
            f"Método: {result.audit.method}",
            *(f"Malha: {v:g}" for k, v in result.audit.parameters.items() if k == "mesh_size_mm"),
            "",
            "Reações do MEF:",
            *(f"- {r.pile_id} ({r.case_id}): {r.force / KN:.2f} kN" for r in result.reactions),
            "",
            "Alertas:",
            *(f"- {w}" for w in result.warnings or ("nenhum",)),
            "",
            "Premissas:",
            *(f"- {a}" for a in result.audit.assumptions),
            "",
            result.disclaimer,
        ]
        self.fem_summary.setPlainText("\n".join(lines))
        _fill(
            self.fem_table,
            ("Verificação", "Solicitante", "Referência", "Unidade", "Situação", "Item"),
            [
                (c.description, f"{c.demand:.4g}", f"{c.capacity:.4g}", c.unit,
                 c.status.value, f"{c.reference.source}, {c.reference.item}")
                for c in result.checks
            ],
        )  # fmt: skip


def _load_rows(loads: LoadsInput) -> list[tuple[object, ...]]:
    """Linhas da tabela de casos em kN e kN·m, um pilar por linha."""
    return [
        (case.id, c.column_id, c.n / KN, c.mx / KNM, c.my / KNM, c.hx / KN, c.hy / KN)
        for case in loads.cases
        for c in case.column_loads
    ]


def _same(a: object, b: object) -> bool:
    """Igualdade de JSON com tolerância nos números (kN ↔ N e arredondamento da tela)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(map(_same, a, b))
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    return a == b


def _fill(table: QTableWidget, headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            table.setItem(i, j, QTableWidgetItem(text))
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
