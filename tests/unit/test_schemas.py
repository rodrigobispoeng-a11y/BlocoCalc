"""Testes dos contratos (v2, com leitura da v1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from blococalc.schemas import (
    AggressivenessClass,
    AnalysisResult,
    BarPosition,
    Cap,
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    HookShape,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Pile,
    Reference,
    Reinforcement,
    ReinforcementKind,
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


@pytest.mark.parametrize("old", ["1", "2", "3", "4", "5", "6"])
def test_older_documents_are_read_as_v7(old: str) -> None:
    data = four_pile_cap().model_dump(mode="json")
    data["schema_version"] = old
    for pile in data["piles"]:
        del pile["axial_stiffness"]
    geometry = GeometryInput.model_validate(data)
    assert geometry.schema_version == "7"
    assert all(p.axial_stiffness is None for p in geometry.piles)
    detailing = DetailingInput.model_validate({"schema_version": old, "bar_diameter": 20.0})
    assert detailing.max_aggregate_size == 19.0
    v1_result = {
        "schema_version": "1",
        "rigid": True,
        "reactions": [],
        "checks": [],
        "audit": {"app_version": "0.1.0", "method": "m", "input_hash": "x"},
    }
    assert AnalysisResult.model_validate(v1_result).reinforcement == ()
    assert AnalysisResult.model_validate(v1_result).bar_positions == ()


def test_reinforcement_bars_are_optional() -> None:
    # ADR-009: armaduras sem barras (suspensão, lateral) e resultados da v5 ficam com None.
    bare = Reinforcement(
        id="suspensao",
        kind=ReinforcementKind.SUSPENSION,
        direction=(0.0, 0.0),
        force_d=0.0,
        area_required=0.0,
        bar_diameter=16.0,
        reference=Reference(source="NBR 6118:2023", item="22.7.4.1.3"),
    )
    assert (bare.bar_count, bare.spacing, bare.area_provided) == (None, None, None)
    tie = bare.model_copy(update={"bar_count": 3, "area_provided": 603.2})
    assert Reinforcement.model_validate(tie.model_dump()).bar_count == 3
    with pytest.raises(ValidationError):
        Reinforcement.model_validate({**bare.model_dump(), "bar_count": 0})
    with pytest.raises(ValidationError):
        DetailingInput(max_aggregate_size=0.0)


def test_unknown_schema_version_is_rejected() -> None:
    data = four_pile_cap().model_dump(mode="json")
    data["schema_version"] = "8"
    with pytest.raises(ValidationError):
        GeometryInput.model_validate(data)


def test_detailing_defaults() -> None:
    options = DetailingInput()
    assert options.bar_diameter == 16.0
    assert options.aggressiveness_class is AggressivenessClass.II
    assert options.hooked is True


def test_flexure_reinforcement_kind() -> None:
    item = Reinforcement(
        id="flexao_x",
        kind="flexure",
        direction=(1.0, 0.0),
        force_d=0.0,
        area_required=6358.5,
        bar_diameter=16.0,
        reference=Reference(source="NBR 6118:2023", item="17.2.2"),
    )
    assert item.kind is ReinforcementKind.FLEXURE


def test_pile_stiffness_is_optional_and_positive() -> None:
    # ADR-007: rigidez axial da estaca para o MEF (D16); vazia = apoio rígido.
    pile = four_pile_cap().piles[0]
    assert pile.axial_stiffness is None
    assert pile.model_copy(update={"axial_stiffness": 720e3}).axial_stiffness == 720e3
    for invalid in (0.0, -1.0):
        with pytest.raises(ValidationError):
            Pile(id="E1", x=0.0, y=0.0, size=400.0, axial_stiffness=invalid)


def test_bar_position_contract() -> None:
    # ADR-010: posição de armação com as extremidades de cada barra em planta.
    position = BarPosition(
        id="N1",
        bar_diameter=16.0,
        count=2,
        length=2220.0,
        hook=HookShape.RIGHT_ANGLE,
        layer=1,
        reinforcement_ids=("tirante_E1_E2",),
        bars=(((-950.0, -600.0), (950.0, -600.0)), ((-950.0, -561.2), (950.0, -561.2))),
    )
    assert not position.variable_length
    assert BarPosition.model_validate(position.model_dump()) == position
    with pytest.raises(ValidationError, match="count"):
        position.model_validate({**position.model_dump(), "count": 3})
    with pytest.raises(ValidationError):
        BarPosition.model_validate({**position.model_dump(), "layer": 0})
