"""Tração, aderência e ancoragem (NBR 6118:2023, 8.2.5, 9.3 e 9.4.2)."""

from __future__ import annotations

import pytest

from blococalc.schemas import MaterialsInput
from blococalc.standards.anchorage import (
    basic_anchorage_length,
    eta1,
    fbd,
    fctk_inf,
    fctm,
    is_good_bond_bottom_bar,
    required_anchorage_length,
)

C35 = MaterialsInput(fck=35.0)
FYD = 500.0 / 1.15


@pytest.mark.golden
def test_tensile_strength() -> None:
    # 0,3·35^(2/3) = 3,20996; acima de 50 MPa: 2,12·ln(1 + 0,1·68) = 2,12·ln 7,8.
    assert fctm(35.0) == pytest.approx(3.20996, rel=1e-5)
    assert fctm(60.0) == pytest.approx(2.12 * 2.054124, rel=1e-6)
    assert fctk_inf(35.0) == pytest.approx(0.7 * 3.20996, rel=1e-5)


@pytest.mark.golden
def test_bond_strength_c35_ca50() -> None:
    # fbd = 2,25·1,0·1,0·(0,7·3,20996/1,4) = 3,61121 MPa.
    assert fbd(C35, 16.0) == pytest.approx(3.61121, rel=1e-5)
    assert fbd(C35, 16.0, good_bond=False) == pytest.approx(0.7 * 3.61121, rel=1e-5)
    assert fbd(C35, 32.0) == pytest.approx(3.61121, rel=1e-5)  # η3 = (132 − 32)/100 = 1
    assert fbd(C35, 40.0) == pytest.approx(0.92 * 3.61121, rel=1e-5)


def test_eta1_by_steel_category() -> None:
    assert eta1(500.0) == 2.25
    assert eta1(600.0) == 1.0
    with pytest.raises(ValueError, match="CA-25, CA-50 ou CA-60"):
        eta1(400.0)


@pytest.mark.golden
def test_basic_anchorage_length() -> None:
    # φ16: 16/4·434,78/3,61121 = 481,59 mm (> 25φ = 400).
    assert basic_anchorage_length(16.0, FYD, 3.61121) == pytest.approx(481.59, abs=0.01)
    # Aderência alta: prevalece 25φ.
    assert basic_anchorage_length(10.0, FYD, 6.0) == pytest.approx(250.0)


def test_required_anchorage_length() -> None:
    assert required_anchorage_length(481.59, 16.0, 1.0, hook_alpha=True) == pytest.approx(337.113)
    assert required_anchorage_length(481.59, 16.0, 1.0, hook_alpha=False) == pytest.approx(481.59)
    # 0,7·481,59·0,2 = 67,4 < ℓb,mín = máx(144,5; 160; 100).
    assert required_anchorage_length(481.59, 16.0, 0.2, hook_alpha=True) == pytest.approx(160.0)


@pytest.mark.parametrize(
    ("h", "depth", "good"),
    [(1000.0, 850.0, True), (1000.0, 200.0, False), (500.0, 300.0, True), (500.0, 100.0, False)],
)
def test_good_bond_position(h: float, depth: float, good: bool) -> None:
    assert is_good_bond_bottom_bar(h, depth) is good
