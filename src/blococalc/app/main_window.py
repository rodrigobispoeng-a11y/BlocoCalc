"""Primeira tela: entrada de um bloco com um pilar e um caso de carga, e tabelas de resultado.

Conversões de unidade só aqui (CLAUDE.md §4): a tela usa kN e kN·m; o motor, N e N·mm.
A tela só conhece `blococalc.analysis` e `blococalc.schemas`.
"""

from __future__ import annotations

from collections.abc import Sequence

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


def _spin(value: float, maximum: float, decimals: int = 1, minimum: float = 0.0) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setValue(value)
    return box


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
        self.column = {
            "x": _spin(0.0, 10000.0, minimum=-10000.0),
            "y": _spin(0.0, 10000.0, minimum=-10000.0),
            "bx": _spin(200.0, 5000.0),
            "by": _spin(650.0, 5000.0),
        }
        self.materials = {"fck": _spin(35.0, 90.0), "fyk": _spin(500.0, 600.0)}
        self.loads = {
            "n": _spin(980.0, 1e6, minimum=-1e6),
            "mx": _spin(0.0, 1e6, minimum=-1e6),
            "my": _spin(0.0, 1e6, minimum=-1e6),
            "hx": _spin(0.0, 1e6, minimum=-1e6),
            "hy": _spin(0.0, 1e6, minimum=-1e6),
        }
        self.gamma_n = _spin(1.2, 2.0, decimals=2, minimum=1.0)
        self.bar_diameter = _spin(16.0, 40.0)
        self.aggressiveness = QComboBox()
        self.aggressiveness.addItems([c.value for c in AggressivenessClass])
        self.aggressiveness.setCurrentText(AggressivenessClass.II.value)
        self.piles = QTableWidget(0, len(_PILE_HEADERS))
        self.piles.setHorizontalHeaderLabels(_PILE_HEADERS)
        self.piles.setMinimumHeight(180)
        self.piles.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for pile_id, x, y in _DEFAULT_PILES:
            self._append_pile(pile_id, x, y, 400.0)

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
            ("Pilar [mm]", self.column, ("x", "y", "bx", "by")),
            ("Materiais [MPa]", self.materials, ("fck", "fyk")),
            ("Caso de cálculo", self.loads,
             ("Nd [kN]", "Mxd [kN·m]", "Myd [kN·m]", "Hxd [kN]", "Hyd [kN]")),
        )  # fmt: skip
        for title, fields, labels in groups:
            box = QGroupBox(title)
            layout = QFormLayout(box)
            for label, widget in zip(labels, fields.values(), strict=True):
                layout.addRow(label, widget)
            if fields is self.loads:
                layout.addRow("γn", self.gamma_n)
            form.addWidget(box)
        detailing = QGroupBox("Detalhamento")
        detailing_layout = QFormLayout(detailing)
        detailing_layout.addRow("φ dos tirantes [mm]", self.bar_diameter)
        detailing_layout.addRow("Classe de agressividade", self.aggressiveness)
        form.addWidget(detailing)

        piles_box = QGroupBox("Estacas")
        piles_layout = QVBoxLayout(piles_box)
        piles_layout.addWidget(self.piles)
        buttons = QHBoxLayout()
        add, remove = QPushButton("Adicionar"), QPushButton("Remover")
        add.clicked.connect(lambda: self._append_pile(f"E{self.piles.rowCount() + 1}", 0, 0, 400))
        remove.clicked.connect(lambda: self.piles.removeRow(self.piles.rowCount() - 1))
        buttons.addWidget(add)
        buttons.addWidget(remove)
        piles_layout.addLayout(buttons)
        form.addWidget(piles_box)
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

    def _append_pile(self, pile_id: str, x: float, y: float, size: float) -> None:
        row = self.piles.rowCount()
        self.piles.insertRow(row)
        for column, value in enumerate((pile_id, x, y, size)):
            self.piles.setItem(row, column, QTableWidgetItem(str(value)))

    def _read_piles(self) -> tuple[Pile, ...]:
        rows = []
        for row in range(self.piles.rowCount()):
            cells = [self.piles.item(row, c) for c in range(len(_PILE_HEADERS))]
            pile_id, x, y, size = (cell.text() if cell else "" for cell in cells)
            rows.append(Pile(id=pile_id, x=float(x), y=float(y), size=float(size)))
        return tuple(rows)

    def inputs(self) -> tuple[GeometryInput, MaterialsInput, LoadsInput, DetailingInput]:
        """Lê o formulário e converte para os contratos (N, mm, MPa)."""
        value = {name: box.value() for name, box in self.cap.items()}
        geometry = GeometryInput(
            cap=Cap(**value),
            piles=self._read_piles(),
            columns=(Column(id="P1", **{k: b.value() for k, b in self.column.items()}),),
        )
        materials = MaterialsInput(**{k: b.value() for k, b in self.materials.items()})
        loads = self.loads
        case = LoadCase(
            id="ELU1",
            column_loads=(
                ColumnLoad(
                    column_id="P1",
                    n=loads["n"].value() * KN,
                    mx=loads["mx"].value() * KNM,
                    my=loads["my"].value() * KNM,
                    hx=loads["hx"].value() * KN,
                    hy=loads["hy"].value() * KN,
                ),
            ),
        )
        detailing = DetailingInput(
            bar_diameter=self.bar_diameter.value(),
            aggressiveness_class=AggressivenessClass(self.aggressiveness.currentText()),
        )
        return (
            geometry,
            materials,
            LoadsInput(cases=(case,), gamma_n=self.gamma_n.value()),
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
