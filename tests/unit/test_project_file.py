"""Arquivo de projeto `.bloco` (ADR-004): gravação, leitura e resultados desatualizados."""

from __future__ import annotations

from pathlib import Path

import pytest

from blococalc import analysis
from blococalc.analysis import analyze, refresh_project
from blococalc.persistence.project import ProjectFileError, load_project, save_project
from blococalc.schemas import (
    ColumnLoad,
    DetailingInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Project,
)
from tests.factories import four_pile_cap

LOADS = LoadsInput(
    cases=(LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=980e3),)),)
)


def project(with_result: bool = True) -> Project:
    geometry, materials = four_pile_cap(), MaterialsInput(fck=25.0)
    result = analyze(geometry, materials, LOADS, DetailingInput()) if with_result else None
    return Project(
        name="Bloco B1", geometry=geometry, materials=materials, loads=LOADS, result=result
    )


def test_round_trip_keeps_inputs_and_result(tmp_path: Path) -> None:
    path = tmp_path / "b1.bloco"
    original = project()
    save_project(path, original)
    assert load_project(path) == original
    assert '"schema_version": "4"' in path.read_text(encoding="utf-8")
    assert [p.name for p in tmp_path.iterdir()] == ["b1.bloco"]  # sem temporário esquecido


def test_save_replaces_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "b1.bloco"
    save_project(path, project(with_result=False))
    save_project(path, project().model_copy(update={"notes": "revisão 2"}))
    assert load_project(path).notes == "revisão 2"


@pytest.mark.parametrize(
    ("content", "message"),
    [("{não é json", "não é um projeto"), ('{"name": "x"}', "não é um projeto")],
)
def test_invalid_files_raise_project_error(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "ruim.bloco"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ProjectFileError, match=message):
        load_project(path)


def test_missing_file_raises_project_error(tmp_path: Path) -> None:
    with pytest.raises(ProjectFileError, match="Não foi possível ler"):
        load_project(tmp_path / "inexistente.bloco")


def test_current_result_is_kept() -> None:
    saved = project()
    refreshed, warnings = refresh_project(saved)
    assert refreshed == saved
    assert warnings == ()


def test_result_for_other_inputs_is_recomputed() -> None:
    saved = project()
    edited = saved.model_copy(update={"materials": MaterialsInput(fck=30.0)})
    refreshed, warnings = refresh_project(edited)
    assert refreshed.result is not None
    assert refreshed.result != saved.result
    assert refreshed.result == analyze(edited.geometry, edited.materials, LOADS, DetailingInput())
    assert "recalculado" in warnings[0]


def test_result_from_other_version_is_recomputed(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = project()
    monkeypatch.setattr(analysis, "__version__", "9.9.9")
    refreshed, warnings = refresh_project(saved)
    assert refreshed.result is not None
    assert refreshed.result.audit.app_version == "9.9.9"
    assert "0.1.0" in warnings[0]


def test_stale_fem_result_is_dropped_without_running_fem() -> None:
    saved = project()
    assert saved.result is not None
    stale = saved.result.model_copy(
        update={"audit": saved.result.audit.model_copy(update={"input_hash": "outro"})}
    )
    refreshed, warnings = refresh_project(saved.model_copy(update={"fem_result": stale}))
    assert refreshed.fem_result is None
    assert refreshed.result == saved.result
    assert any("MEF" in w for w in warnings)


def test_project_without_result_stays_without_result() -> None:
    saved = project(with_result=False)
    assert refresh_project(saved) == (saved, ())


def test_save_failure_raises_project_error_and_leaves_nothing(tmp_path: Path) -> None:
    with pytest.raises(ProjectFileError, match="Não foi possível gravar"):
        save_project(tmp_path / "pasta-inexistente" / "b1.bloco", project())
    assert list(tmp_path.iterdir()) == []
