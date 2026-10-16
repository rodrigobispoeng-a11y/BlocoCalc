"""Arquivo de projeto `.bloco`: JSON UTF-8 do contrato `Project` (ADR-004).

A gravação é atômica: o JSON vai para um temporário na mesma pasta, que substitui o arquivo
definitivo com `os.replace`, para que uma queda ou a sincronização do OneDrive não deixem um
projeto pela metade.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from blococalc.schemas import Project

EXTENSION = ".bloco"


class ProjectFileError(Exception):
    """Falha ao ler ou gravar um arquivo de projeto, com mensagem para o usuário."""


def save_project(path: Path, project: Project) -> None:
    """Grava o projeto em `path`, substituindo o arquivo existente só no fim."""
    content = project.model_dump_json(indent=2)
    try:
        handle, temporary = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    except OSError as error:
        raise ProjectFileError(f"Não foi possível gravar {path}: {error.strerror}") from error


def load_project(path: Path) -> Project:
    """Lê um projeto; ausência, JSON ou contrato inválidos viram `ProjectFileError`."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ProjectFileError(f"Não foi possível ler {path}: {error}") from error
    try:
        return Project.model_validate_json(content)
    except ValidationError as error:
        raise ProjectFileError(
            f"{path.name} não é um projeto do BlocoCalc válido ({error.error_count()} erro(s))"
        ) from error
