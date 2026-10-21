"""Campo de tensões do MEF para a aba 3D (ADR-012): contrato, σ3 nodal e saída da análise."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from blococalc.schemas import FemField


def tetra(**update: object) -> FemField:
    nodes = (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0) * 2 + (0.0,) * 6
    data: dict[str, object] = {
        "case_id": "C1",
        "nodes": nodes,  # 10 nós (4 cantos repetidos + 2 extras) só para a forma
        "tetrahedra": tuple(range(10)),
        "displacements": (0.0,) * 30,
        "sigma3": (-1.0,) * 10,
    }
    return FemField.model_validate(data | update)


def test_field_counts_nodes_and_elements() -> None:
    field = tetra()
    assert field.node_count == 10
    assert field.element_count == 1


@pytest.mark.parametrize(
    "update",
    [
        {"nodes": (0.0,) * 29},  # coordenadas não múltiplas de 3
        {"tetrahedra": tuple(range(9))},  # elemento incompleto
        {"tetrahedra": (*range(9), 10)},  # índice fora da malha
        {"sigma3": (-1.0,) * 9},  # um valor por nó
        {"displacements": (0.0,) * 27},  # três por nó
    ],
)
def test_inconsistent_field_is_refused(update: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        tetra(**update)


def test_minimum_principal_stress() -> None:
    pytest.importorskip("scipy")
    from blococalc.fem.post import minimum_principal  # noqa: PLC0415

    # Linhas xx, yy, zz, xy, yz, zx: compressão uniaxial, cisalhamento puro e tração pura.
    stresses = np.array(
        [
            [0.0, 0.0, -5.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 3.0, 0.0, 0.0],
            [2.0, 1.0, 4.0, 0.0, 0.0, 0.0],
        ]
    )
    assert minimum_principal(stresses) == pytest.approx([-5.0, -3.0, 1.0])
