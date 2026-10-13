"""Testes dos contratos (v2, com leitura da v1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from blococalc.schemas import (
    AggressivenessClass,
    AnalysisResult,
    Cap,
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Pile,
)
from tests.factories import four_pile_cap


def test_valid_geometry_round_trips_through_json() -> None:
    geometry = four_pile_cap()
    assert GeometryInput.model_validate_json(geometry.model_dump_json()) == geometry


def test_contracts_are_immutable() -> None:
    geometry = four_pile_cap()
    with pytest.raises(ValidationError):
        geometry.cap.h = 500.0  # type: ignore[misc]


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Cap.model_validate({"lx": 1.0, "ly": 1.0, "h": 1.0, "unidade": "cm"})


def test_duplicate_pile_ids_are_rejected() -> None:
    geometry = four_pile_cap()
    with pytest.raises(ValidationError, match="repetidos"):
        GeometryInput(
            cap=geometry.cap,
            piles=(geometry.piles[0], geometry.piles[0]),
            columns=geometry.columns,
        )


def test_pile_outside_cap_is_rejected() -> None:
    geometry = four_pile_cap()
    far = Pile(id="E9", x=5000.0, y=0.0, size=400.0)
    with pytest.raises(ValidationError, match="fora da projeção"):
        GeometryInput(cap=geometry.cap, piles=(far,), columns=geometry.columns)


def test_embedment_must_be_smaller_than_cap_height() -> None:
    geometry = four_pile_cap()
    with pytest.raises(ValidationError, match="Embutimento"):
        GeometryInput(
            cap=Cap(lx=2000.0, ly=2000.0, h=100.0, pile_embedment=100.0),
            piles=geometry.piles,
            columns=geometry.columns,
        )


def test_defaults_follow_approved_decisions() -> None:
    loads = LoadsInput(
        cases=(LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=980e3),)),)
    )
    assert loads.gamma_n == 1.2
    materials = MaterialsInput(fck=35.0)
    assert (materials.gamma_c, materials.gamma_s, materials.fyk) == (1.4, 1.15, 500.0)


def test_v1_documents_are_read_as_v2() -> None:
    data = four_pile_cap().model_dump(mode="json")
    data["schema_version"] = "1"
    assert GeometryInput.model_validate(data).schema_version == "2"
    v1_result = {
        "schema_version": "1",
        "rigid": True,
        "reactions": [],
        "checks": [],
        "audit": {"app_version": "0.1.0", "method": "m", "input_hash": "x"},
    }
    assert AnalysisResult.model_validate(v1_result).reinforcement == ()


def test_unknown_schema_version_is_rejected() -> None:
    data = four_pile_cap().model_dump(mode="json")
    data["schema_version"] = "3"
    with pytest.raises(ValidationError):
        GeometryInput.model_validate(data)


def test_detailing_defaults() -> None:
    options = DetailingInput()
    assert options.bar_diameter == 16.0
    assert options.aggressiveness_class is AggressivenessClass.II
    assert options.hooked is True
