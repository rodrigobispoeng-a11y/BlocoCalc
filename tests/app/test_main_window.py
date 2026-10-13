"""Primeira tela: lê o formulário, converte unidades e mostra o resultado do B1."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from blococalc.app import __main__ as entry  # noqa: E402
from blococalc.app.main_window import KN, MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app() -> object:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


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


def test_add_and_remove_piles(app: object) -> None:
    window = MainWindow()
    buttons = {b.text(): b for b in window.findChildren(QtWidgets.QPushButton)}
    buttons["Adicionar"].click()
    assert window.piles.rowCount() == 5
    buttons["Remover"].click()
    assert window.piles.rowCount() == 4


def test_entry_point_opens_window(app: object, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeApplication:
        def __init__(self, argv: list[str]) -> None:
            self.argv = argv

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(entry, "QApplication", FakeApplication)
    assert entry.main() == 0
