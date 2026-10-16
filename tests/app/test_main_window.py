"""Tela principal: formulário, resultado do B1 e menu Arquivo com projetos `.bloco` (ADR-004)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from blococalc.analysis import refresh_project  # noqa: E402
from blococalc.app import __main__ as entry  # noqa: E402
from blococalc.app import main_window  # noqa: E402
from blococalc.app.main_window import KN, MainWindow, _append_row  # noqa: E402
from blococalc.persistence.project import load_project, save_project  # noqa: E402
from blococalc.schemas import MaterialsInput, Project  # noqa: E402
from tests.factories import quincunx_cap  # noqa: E402

Button = QtWidgets.QMessageBox.StandardButton


@pytest.fixture(scope="module")
def app() -> Iterator[object]:
    """Encerra o Qt antes da saída do interpretador: no Windows, destruir widgets durante o
    encerramento do Python faz o processo terminar com código de erro mesmo com testes OK."""
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield application
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, MainWindow):
            widget.modified = False  # sem a pergunta de salvar no encerramento
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


class FakeDialogs:
    """Substitui QMessageBox e QFileDialog: devolve respostas fixas sem abrir janela."""

    StandardButton = Button

    def __init__(self, answer: object = Button.Discard, file: str = "") -> None:
        self.answer, self.file, self.asked = answer, file, 0

    def question(self, *_: object) -> object:
        self.asked += 1
        return self.answer

    def getSaveFileName(self, *_: object) -> tuple[str, str]:  # noqa: N802 - nome do Qt
        return self.file, ""

    def getOpenFileName(self, *_: object) -> tuple[str, str]:  # noqa: N802 - nome do Qt
        return self.file, ""


@pytest.fixture
def dialogs(monkeypatch: pytest.MonkeyPatch) -> FakeDialogs:
    fake = FakeDialogs()
    monkeypatch.setattr(main_window, "QMessageBox", fake)
    monkeypatch.setattr(main_window, "QFileDialog", fake)
    return fake


def test_title_marks_unsaved_changes(app: object) -> None:
    window = MainWindow()
    assert not window.isWindowModified()
    assert window.windowTitle().startswith("Novo projeto")
    window.cap["h"].setValue(1200.0)
    assert window.isWindowModified()
    window.name.setText("Bloco P12")
    assert window.windowTitle().startswith("Bloco P12")


def test_save_and_open_round_trip(app: object, tmp_path: Path) -> None:
    window = MainWindow()
    window.name.setText("B1")
    window.calculate()
    path = tmp_path / "b1.bloco"
    assert window.save_to(path)
    assert not window.modified
    assert load_project(path).result == window.result

    other = MainWindow()
    assert other.open_path(path)
    assert other.inputs() == window.inputs()
    assert other.result == window.result
    assert other.reactions_table.rowCount() == 4
    assert other.windowTitle().startswith("B1")
    assert not other.isWindowModified()
    assert other.status.text() == f"Projeto aberto: {path}."


def test_save_recomputes_result_of_edited_inputs(app: object, tmp_path: Path) -> None:
    window = MainWindow()
    window.calculate()
    window.materials["fck"].setValue(30.0)
    assert window.save_to(tmp_path / "b1.bloco")
    saved = load_project(tmp_path / "b1.bloco")
    assert saved.materials.fck == 30.0
    assert window.result == saved.result
    assert refresh_project(saved) == (saved, ())  # o resultado gravado vale para as entradas
    assert "recalculado" in window.status.text()


def test_open_warns_about_data_the_screen_does_not_show(app: object, tmp_path: Path) -> None:
    window = MainWindow()
    project = window.project().model_copy(update={"geometry": quincunx_cap()})
    save_project(tmp_path / "b7.bloco", project)
    assert window.open_path(tmp_path / "b7.bloco")
    assert len(window.inputs()[0].piles) == 5
    assert "não mostra" in window.status.text()


def test_open_invalid_file_keeps_window(app: object, tmp_path: Path) -> None:
    path = tmp_path / "ruim.bloco"
    path.write_text("{}", encoding="utf-8")
    window = MainWindow()
    assert not window.open_path(path)
    assert window.path is None
    assert window.status.text().startswith("Não foi possível abrir")


def test_save_as_adds_extension(app: object, dialogs: FakeDialogs, tmp_path: Path) -> None:
    dialogs.file = str(tmp_path / "obra")
    window = MainWindow()
    assert window.save()
    assert window.path == tmp_path / "obra.bloco"
    assert window.path.exists()
    dialogs.file = ""
    window.cap["h"].setValue(1100.0)
    assert window.save()  # já tem caminho: não abre o diálogo
    assert load_project(tmp_path / "obra.bloco").geometry.cap.h == 1100.0


def test_unsaved_changes_ask_before_discarding(app: object, dialogs: FakeDialogs) -> None:
    window = MainWindow()
    window.new_project()
    assert dialogs.asked == 0  # nada a perder
    window.materials["fck"].setValue(40.0)
    dialogs.answer = Button.Cancel
    window.new_project()
    assert window.materials["fck"].value() == 40.0
    dialogs.answer = Button.Discard
    window.new_project()
    assert window.materials["fck"].value() == 35.0
    assert not window.modified


def test_close_with_changes_can_be_cancelled(app: object, dialogs: FakeDialogs) -> None:
    window = MainWindow()
    window.show()
    window.cap["h"].setValue(1300.0)
    dialogs.answer = Button.Cancel
    assert not window.close()
    assert window.isVisible()
    dialogs.answer = Button.Discard
    assert window.close()


def test_open_from_menu(app: object, dialogs: FakeDialogs, tmp_path: Path) -> None:
    path = tmp_path / "b1.bloco"
    window = MainWindow()
    save_project(path, window.project().model_copy(update={"materials": MaterialsInput(fck=45.0)}))
    dialogs.file = str(path)
    menu = window.menuBar().findChild(QtWidgets.QMenu)
    assert menu is not None
    actions = {a.text(): a for a in menu.actions()}
    assert set(actions) >= {"&Novo", "&Abrir...", "&Salvar", "Salvar &como...", "Sai&r"}
    actions["&Abrir..."].trigger()
    assert window.materials["fck"].value() == 45.0
    assert isinstance(window.project(), Project)
