"""Tela principal: formulário, resultado do B1 e menu Arquivo com projetos `.bloco` (ADR-004)."""

from __future__ import annotations

import functools
import os
import sys
import time
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QWidget  # noqa: E402

from blococalc.analysis import (  # noqa: E402
    FEM_METHOD,
    analyze,
    fem_verification,
    refresh_project,
)
from blococalc.app import __main__ as entry  # noqa: E402
from blococalc.app import main_window, view3d  # noqa: E402
from blococalc.app.main_window import KN, MainWindow, _append_row, _check_rows  # noqa: E402
from blococalc.app.view3d import View3D  # noqa: E402
from blococalc.persistence.project import load_project, save_project  # noqa: E402
from blococalc.schemas import (  # noqa: E402
    AnalysisResult,
    Check,
    CheckStatus,
    CombinationType,
    MaterialsInput,
    PileShape,
    Project,
    Reference,
)
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


def test_square_piles_round_trip_without_warning(app: object, tmp_path: Path) -> None:
    # B7 tem estacas quadradas: a tela agora mostra a forma e não perde nada ao salvar.
    window = MainWindow()
    project = window.project().model_copy(update={"geometry": quincunx_cap()})
    save_project(tmp_path / "b7.bloco", project)
    assert window.open_path(tmp_path / "b7.bloco")
    assert window.inputs()[0] == quincunx_cap()
    assert window.status.text() == f"Projeto aberto: {tmp_path / 'b7.bloco'}."


def test_open_warns_about_values_the_screen_rounds(app: object, tmp_path: Path) -> None:
    window = MainWindow()
    geometry = window.inputs()[0]
    cap = geometry.cap.model_copy(update={"h": 1000.04})
    project = window.project().model_copy(
        update={"geometry": geometry.model_copy(update={"cap": cap})}
    )
    save_project(tmp_path / "b1.bloco", project)
    assert window.open_path(tmp_path / "b1.bloco")
    assert "arredonda" in window.status.text()


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


def wait_fem(window: MainWindow) -> None:
    deadline = time.monotonic() + 120.0
    while window.fem_running:
        assert time.monotonic() < deadline, "MEF não terminou"
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)


def fake_fem(*inputs: Any) -> AnalysisResult:
    result = analyze(*inputs)
    return result.model_copy(
        update={"audit": result.audit.model_copy(update={"method": FEM_METHOD})}
    )


def test_fem_runs_in_background_and_is_saved(
    app: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(main_window, "fem_verification", fake_fem)
    window = MainWindow()
    window.fem_button.click()
    assert not window.form_area.isEnabled()
    wait_fem(window)
    assert window.form_area.isEnabled()
    assert window.fem_result is not None
    assert window.fem_table.rowCount() == len(window.fem_result.checks)
    assert FEM_METHOD in window.fem_summary.toPlainText()
    assert window.status.text().startswith("MEF concluído")
    assert window.isWindowModified()

    assert window.save_to(tmp_path / "b1.bloco")
    other = MainWindow()
    assert other.open_path(tmp_path / "b1.bloco")
    assert other.fem_result == window.fem_result
    assert other.fem_table.rowCount() == len(window.fem_result.checks)


def test_fem_failure_is_shown(app: object, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_ccx(*_: object) -> AnalysisResult:
        # Mesma mensagem de blococalc.fem.ccx.FemError, sem exigir o gmsh nos testes da tela.
        raise RuntimeError("CalculiX não encontrado (parâmetro, BLOCOCALC_CCX ou PATH)")

    monkeypatch.setattr(main_window, "fem_verification", missing_ccx)
    window = MainWindow()
    window.run_fem()
    wait_fem(window)
    assert window.fem_result is None
    assert window.form_area.isEnabled()
    assert "BLOCOCALC_CCX" in window.status.text()


def test_editing_inputs_discards_fem_result(app: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_window, "fem_verification", fake_fem)
    window = MainWindow()
    window.run_fem()
    wait_fem(window)
    window.name.setText("Outro nome")  # nome não muda o cálculo
    assert window.fem_result is not None
    window.cap["h"].setValue(1100.0)
    assert window.fem_result is None
    assert window.fem_table.rowCount() == 0
    assert "MEF foi descartado" in window.status.text()


@pytest.mark.fem
def test_real_fem_from_the_screen(app: object, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("gmsh")
    from blococalc.fem.ccx import find_ccx  # noqa: PLC0415 - exige o gmsh

    if find_ccx() is None:
        pytest.skip("CalculiX (ccx) não instalado")
    monkeypatch.setattr(
        main_window, "fem_verification", functools.partial(fem_verification, mesh_size=300.0)
    )
    window = MainWindow()
    window.run_fem()
    wait_fem(window)
    assert window.fem_result is not None, window.status.text()
    assert window.fem_result.audit.method == FEM_METHOD
    assert len(window.fem_result.reactions) == 4


def test_defaults_match_contract_defaults(app: object) -> None:
    geometry, materials, loads, detailing = MainWindow().inputs()
    assert {p.shape for p in geometry.piles} == {PileShape.CIRCULAR}
    assert geometry.columns[0].reinforcement_ratio == pytest.approx(0.02)
    assert loads.cases[0].combination is CombinationType.NORMAL
    assert loads.include_cap_self_weight
    assert (materials.gamma_c, materials.gamma_s) == (1.4, 1.15)
    assert detailing.hooked


def test_all_contract_fields_are_editable(app: object) -> None:
    window = MainWindow()
    window.piles.setRowCount(0)
    _append_row(window.piles, ("E1", -600, 0, 400, "quadrada"))
    _append_row(window.piles, ("E2", 600, 0, 400, "circular"))
    window.columns.setRowCount(0)
    _append_row(window.columns, ("P1", 0, 0, 400, 400, 1.5))
    window.loads.setRowCount(0)
    _append_row(window.loads, ("ELU1", "P1", 900, 0, 0, 0, 0, "especial"))
    window.materials["gamma_c"].setValue(1.2)
    window.materials["gamma_s"].setValue(1.0)
    window.hooked.setChecked(False)
    window.self_weight.setChecked(False)

    geometry, materials, loads, detailing = window.inputs()
    assert [p.shape for p in geometry.piles] == [PileShape.SQUARE, PileShape.CIRCULAR]
    assert geometry.columns[0].reinforcement_ratio == pytest.approx(0.015)
    assert loads.cases[0].combination is CombinationType.SPECIAL
    assert not loads.include_cap_self_weight
    assert (materials.gamma_c, materials.gamma_s) == (1.2, 1.0)
    assert not detailing.hooked

    window.set_project(window.project())
    assert window.inputs() == (geometry, materials, loads, detailing)


def test_unknown_pile_shape_is_reported(app: object) -> None:
    window = MainWindow()
    cell = window.piles.item(0, 4)
    assert cell is not None
    cell.setText("oval")
    window.calculate()
    assert window.result is None
    assert "circular ou quadrada" in window.status.text()


def test_forces_are_shown_in_kn() -> None:
    check = Check(
        id="mef_tracao_x_0",
        description="Tração",
        demand=433_700.0,
        capacity=459_300.0,
        unit="N",
        status=CheckStatus.OK,
        reference=Reference(source="docs/02-metodos.md", item="§4.5"),
    )
    assert _check_rows((check,))[0][1:4] == ("433.7", "459.3", "kN")


def test_report_is_written_as_pdf(app: object, tmp_path: Path) -> None:
    window = MainWindow()
    window.calculate()
    path = tmp_path / "b1 - memorial.pdf"
    assert window.write_report(path)
    content = path.read_bytes()
    assert content.startswith(b"%PDF")
    assert len(content) > 5_000
    assert window.status.text() == f"Memorial salvo em {path}."


def test_report_recomputes_stale_result(app: object, tmp_path: Path) -> None:
    window = MainWindow()
    window.calculate()
    window.materials["fck"].setValue(30.0)
    assert window.write_report(tmp_path / "m.pdf")
    assert window.result is not None
    assert window.result == analyze(*window.inputs())
    assert "recalculado" in window.status.text()


def test_report_needs_calculation(app: object, tmp_path: Path) -> None:
    window = MainWindow()
    assert not window.write_report(tmp_path / "m.pdf")
    assert not (tmp_path / "m.pdf").exists()
    assert "Calcule" in window.status.text()


def test_report_from_menu_adds_extension(app: object, dialogs: FakeDialogs, tmp_path: Path) -> None:
    window = MainWindow()
    window.calculate()
    dialogs.file = str(tmp_path / "memorial")
    menu = window.menuBar().findChild(QtWidgets.QMenu)
    assert menu is not None
    action = next(a for a in menu.actions() if a.text() == "Gerar &memorial (PDF)...")
    action.trigger()
    assert (tmp_path / "memorial.pdf").read_bytes().startswith(b"%PDF")


# --------------------------------------------------------------------------------------
# Aba 3D (ADR-006)
# --------------------------------------------------------------------------------------


class FakePlotter(QWidget):
    """Faz o papel do QtInteractor sem OpenGL: guarda o que seria desenhado."""

    def __init__(self, parent: object = None) -> None:
        super().__init__()
        self.meshes: dict[str, dict[str, Any]] = {}
        self.views: list[str] = []
        self.cleared = 0

    def add_mesh(self, mesh: Any, **options: Any) -> None:
        self.meshes[options["name"]] = {"mesh": mesh, **options}

    def clear(self) -> None:
        self.meshes.clear()
        self.cleared += 1

    def view_isometric(self) -> None:
        self.views.append("iso")

    def view_xy(self) -> None:
        self.views.append("xy")

    def view_xz(self) -> None:
        self.views.append("xz")

    def view_yz(self) -> None:
        self.views.append("yz")


def fake_factory(parent: object) -> tuple[FakePlotter, FakePlotter]:
    plotter = FakePlotter(parent)
    return plotter, plotter


def calculated(h: float = 1000.0, cases: int = 2) -> Project:
    window = MainWindow()
    window.cap["h"].setValue(h)
    for _ in range(cases - 1):
        _append_row(window.loads, ("ELU2", "P1", 490.0, 0.0, 0.0, 0.0, 0.0, "normal"))
    window.calculate()
    window.modified = False
    project = window.project()
    window.close()
    return project


def test_3d_tab_without_display_explains_and_still_builds_the_scene(app: object) -> None:
    window = MainWindow()
    assert not window.view3d.available
    assert window.view3d.note.text().startswith("Visualização 3D indisponível: esta sessão")
    window.calculate()
    assert window.view3d.case_box.count() == 1
    assert window.view3d.scene is not None
    names = {item.name for item in window.view3d.scene.items}
    assert {"bloco", "pilar_P1", "estaca_E1", "biela_E1", "tirante_E1_E2"} <= names
    assert window.view3d.note.text().startswith("Visualização 3D indisponível")


def test_3d_tab_draws_the_selected_case(app: object) -> None:
    view = View3D(fake_factory)
    plotter = view.plotter
    assert isinstance(plotter, FakePlotter)
    view.show_project(calculated())
    assert [view.case_box.itemText(i) for i in range(2)] == ["ELU1", "ELU2"]
    assert "biela_E1" in plotter.meshes
    assert plotter.meshes["bloco"]["opacity"] < 1.0
    assert "Biela" in view.note.text()
    first, cleared = view.scene, plotter.cleared
    view.case_box.setCurrentText("ELU2")
    assert plotter.cleared == cleared + 1
    assert view.scene is not first
    assert "biela_E1" in plotter.meshes
    for label in ("Planta", "Frente", "Lateral", "Isométrica"):
        view.view_buttons[label].click()
    assert plotter.views[-4:] == ["xy", "xz", "yz", "iso"]


def test_3d_tab_keeps_the_case_and_clears_without_result(app: object) -> None:
    view = View3D(fake_factory)
    project = calculated()
    view.show_project(project)
    view.case_box.setCurrentText("ELU2")
    view.show_project(project)
    assert view.case_box.currentText() == "ELU2"
    view.show_project(project.model_copy(update={"result": None}))
    assert view.scene is None
    assert view.case_box.count() == 0
    assert view.note.text() == "Calcule o bloco para ver o modelo em 3D."


def test_3d_tab_on_a_flexible_cap_shows_only_reactions(app: object) -> None:
    view = View3D(fake_factory)
    view.show_project(calculated(h=400.0, cases=1))
    assert view.note.text().startswith("Bloco flexível (D9)")
    assert view.scene is not None
    assert not [i for i in view.scene.items if i.name.startswith("biela_")]


def test_3d_tab_reports_model_errors(app: object, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(project: Project, case_id: str) -> None:
        raise ValueError("estaqueamento fora do escopo")

    monkeypatch.setattr(view3d, "strut_tie_layout", broken)
    view = View3D(fake_factory)
    view.show_project(calculated(cases=1))
    assert view.note.text().endswith("estaqueamento fora do escopo")
    assert view.scene is not None


def test_interactor_needs_a_screen_and_pyvistaqt(
    app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = QtWidgets.QWidget()
    with pytest.raises(RuntimeError, match="não tem tela"):
        view3d.interactor(parent)
    monkeypatch.setattr(QGuiApplication, "platformName", staticmethod(lambda: "windows"))
    monkeypatch.setitem(sys.modules, "pyvistaqt", None)
    with pytest.raises(RuntimeError, match="PyVista não instalado"):
        view3d.interactor(parent)
    monkeypatch.setitem(sys.modules, "pyvistaqt", types.SimpleNamespace(QtInteractor=FakePlotter))
    widget, plotter = view3d.interactor(parent)
    assert id(widget) == id(plotter)
    assert isinstance(widget, FakePlotter)


def test_3d_tab_is_cleared_when_the_form_is_invalid(
    app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    window.calculate()
    assert window.result is not None

    def invalid() -> Project:
        raise ValueError("tabela vazia")

    monkeypatch.setattr(window, "project", invalid)
    window._show(window.result)
    assert window.view3d.scene is None
