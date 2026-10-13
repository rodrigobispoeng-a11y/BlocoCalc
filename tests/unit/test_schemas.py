"""Testes dos contratos v1."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from blococalc.schemas import (
    Cap,
    Column,
    ColumnLoad,
    GeometryInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Pile,
)


def four_pile_cap() -> GeometryInput:
    """Bloco de 4 estacas do exemplo B1 (Macedo 2022, §6.1), em mm."""
    piles = tuple(
        Pile(id=f"E{i + 1}", x=sx * 600.0, y=sy * 600.0, size=400.0)
        for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)))
    )
    return GeometryInput(
        cap=Cap(lx=2000.0, ly=2000.0, h=1000.0, pile_embedment=100.0),
        piles=piles,
        columns=(Column(id="P1", x=0.0, y=0.0, bx=200.0, by=650.0),),
    )


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
