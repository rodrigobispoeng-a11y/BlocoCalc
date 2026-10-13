"""Primeira tela: lê o formulário, converte unidades e mostra o resultado do B1."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from blococalc.app import __main__ as entry  # noqa: E402
from blococalc.app.main_window import KN, MainWindow, _append_row  # noqa: E402


@pytest.fixture(scope="module")
def app() -> Iterator[object]:
    """Encerra o Qt antes da saída do interpretador: no Windows, destruir widgets durante o
    encerramento do Python faz o processo terminar com código de erro mesmo com testes OK."""
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield application
    for widget in QtWidgets.QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QtWidgets.QApplication.processEvents()
    application.shutdown()


def test_defaults_reproduce_b1(app: object) -> None:
    window = MainWindow()
    geometry, materials, loads, detailing = window.inputs()
    assert len(geometry.piles) == 4
    assert materials.fck == 35.0
    assert loads.cases[0].column_loads[0].n == pytest.approx(980.0 * KN)
    assert detailing.bar_diameter == 16.0

    window.calculate()

    assert window.result is not None
    assert window.result.rigid
    # B1: Rd = (980 + 5 %)/4 = 257,25 kN por estaca (tests/unit/test_analysis.py).
    cell = window.reactions_table.item(0, 2)
    assert cell is not None
    assert cell.text() == "257.25"
    assert window.checks_table.rowCount() == len(window.result.checks)
    assert window.reinforcement_table.rowCount() == len(window.result.reinforcement)
    assert "rígido" in window.summary.toPlainText()
    assert window.status.text() == window.result.disclaimer


def test_invalid_input_shows_message(app: object) -> None:
    window = MainWindow()
    cell = window.piles.item(0, 3)
    assert cell is not None
    cell.setText("abc")
    window.calculate()
    assert window.result is None
    assert window.status.text().startswith("Não foi possível calcular")


def test_add_and_remove_rows(app: object) -> None:
    window = MainWindow()
    for table in (window.columns, window.piles, window.loads):
        box = table.parentWidget()
        assert box is not None
        buttons = {b.text(): b for b in box.findChildren(QtWidgets.QPushButton)}
        rows = table.rowCount()
        buttons["Adicionar"].click()
        assert table.rowCount() == rows + 1
        buttons["Remover"].click()
        assert table.rowCount() == rows


def test_two_columns_and_two_cases(app: object) -> None:
    window = MainWindow()
    window.columns.setRowCount(0)
    window.loads.setRowCount(0)
    for column in (("P1", -300, 0, 200, 200), ("P2", 300, 0, 200, 200)):
        _append_row(window.columns, column)
    for load in (("ELU1", "P1", 500, 0, 0, 0, 0), ("ELU1", "P2", 300, 0, 0, 0, 0),
                 ("ELU2", "P1", 400, 0, 0, 0, 0)):  # fmt: skip
        _append_row(window.loads, load)

    geometry, _, loads, _ = window.inputs()
    assert [c.id for c in geometry.columns] == ["P1", "P2"]
    assert [c.id for c in loads.cases] == ["ELU1", "ELU2"]
    assert [cl.n for cl in loads.cases[0].column_loads] == pytest.approx([500 * KN, 300 * KN])

    window.calculate()
    assert window.result is not None
    assert window.result.warnings[0].startswith("Vários pilares")
    assert window.reactions_table.rowCount() == 8


def test_no_load_rows_shows_message(app: object) -> None:
    window = MainWindow()
    window.loads.setRowCount(0)
    window.calculate()
    assert window.result is None
    assert "caso de cálculo" in window.status.text()


def test_entry_point_opens_window(app: object, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeApplication:
        def __init__(self, argv: list[str]) -> None:
            self.argv = argv

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(entry, "QApplication", FakeApplication)
    assert entry.main() == 0
