"""Primeira tela: entrada de um bloco com pilares, estacas e casos de carga em tabelas.

Conversões de unidade só aqui (CLAUDE.md §4): a tela usa kN e kN·m; o motor, N e N·mm.
A tela só conhece `blococalc.analysis` e `blococalc.schemas`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from blococalc.analysis import analyze
from blococalc.schemas import (
    AggressivenessClass,
    AnalysisResult,
    Cap,
    Column,
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Pile,
)

KN = 1e3  # N
KNM = 1e6  # N·mm

# Exemplo inicial: benchmark B1 (Macedo 2022, §6.1), Fd = 980 kN.
_DEFAULT_PILES = (("E1", -600.0, -600.0), ("E2", 600.0, -600.0), ("E3", 600.0, 600.0),
                  ("E4", -600.0, 600.0))  # fmt: skip
_PILE_HEADERS = ("Estaca", "x [mm]", "y [mm]", "φ [mm]")
_COLUMN_HEADERS = ("Pilar", "x [mm]", "y [mm]", "bx [mm]", "by [mm]")
_LOAD_HEADERS = ("Caso", "Pilar", "Nd [kN]", "Mxd [kN·m]", "Myd [kN·m]", "Hxd [kN]", "Hyd [kN]")


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
        self.setWindowTitle("BlocoCalc — bloco sobre estacas (NBR 6118:2023)")
        self.result: AnalysisResult | None = None

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
        self._build_layout()

    def _build_layout(self) -> None:
        form = QVBoxLayout()
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

        tabs = QTabWidget()
        tabs.addTab(self.summary, "Resumo")
        tabs.addTab(self.reactions_table, "Reações")
        tabs.addTab(self.checks_table, "Verificações")
        tabs.addTab(self.reinforcement_table, "Armaduras")
        right = QVBoxLayout()
        right.addWidget(tabs)
        right.addWidget(self.status)

        form_widget = QWidget()
        form_widget.setLayout(form)
        scroll = QScrollArea()
        scroll.setWidget(form_widget)
        scroll.setWidgetResizable(True)
        root = QHBoxLayout()
        root.addWidget(scroll, 1)
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
        result = self.result
        self.status.setText(result.disclaimer)
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


def _fill(table: QTableWidget, headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            table.setItem(i, j, QTableWidgetItem(text))
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
