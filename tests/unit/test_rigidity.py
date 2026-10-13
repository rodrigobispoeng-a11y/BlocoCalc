"""Classificação rígido × flexível (NBR 6118:2023, 22.7.1 / 22.6.1; decisões D4 e D5)."""

from __future__ import annotations

import pytest

from blococalc.schemas import CheckStatus
from blococalc.standards.rigidity import is_rigid, required_rigid_height, rigidity_checks
from tests.factories import four_pile_cap


def test_required_height_uses_cap_and_column_dimension() -> None:
    assert required_rigid_height(2000.0, 200.0) == pytest.approx(600.0)
    assert required_rigid_height(300.0, 400.0) == 0.0


def test_b1_cap_is_rigid_in_both_directions() -> None:
    geometry = four_pile_cap()
    check_x, check_y = rigidity_checks(geometry.cap, geometry.columns[0])
    assert (check_x.demand, check_y.demand) == pytest.approx((600.0, 450.0))
    assert check_x.status is CheckStatus.OK and check_y.status is CheckStatus.OK
    assert check_x.reference.item == "22.7.1 / 22.6.1"


def test_thin_cap_is_flexible_in_the_direction_of_the_narrow_column_side() -> None:
    geometry = four_pile_cap(h=500.0)
    check_x, check_y = rigidity_checks(geometry.cap, geometry.columns[0])
    assert check_x.status is CheckStatus.FAIL  # (2000 − 200)/3 = 600 > 500
    assert check_y.status is CheckStatus.OK  # (2000 − 650)/3 = 450 ≤ 500
    assert not is_rigid(geometry.cap, geometry.columns[0])
