"""Cobrimento nominal (NBR 6118:2023, 7.4.7 e Tabela 7.2)."""

from __future__ import annotations

import pytest

from blococalc.schemas import AggressivenessClass, Cap, CheckStatus
from blococalc.standards.durability import cover_check, nominal_cover


@pytest.mark.parametrize(
    ("aggressiveness", "expected"),
    [
        (AggressivenessClass.I, 30.0),
        (AggressivenessClass.II, 30.0),
        (AggressivenessClass.III, 40.0),
        (AggressivenessClass.IV, 50.0),
    ],
)
def test_soil_contact_cover(aggressiveness: AggressivenessClass, expected: float) -> None:
    assert nominal_cover(aggressiveness, 16.0) == expected


def test_cover_not_smaller_than_bar() -> None:
    assert nominal_cover(AggressivenessClass.I, 32.0) == 32.0


def test_cover_check() -> None:
    cap = Cap(lx=2000.0, ly=2000.0, h=1000.0, cover=40.0)
    assert cover_check(cap, AggressivenessClass.III, 16.0).status is CheckStatus.OK
    assert cover_check(cap, AggressivenessClass.IV, 16.0).status is CheckStatus.FAIL
