"""Cisalhamento de laje (19.4.1) e punção (19.5) da NBR 6118:2023, valores recalculados à mão."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from blococalc.schemas import CheckStatus, Column, MaterialsInput
from blococalc.standards.slab_shear import (
    moment_factor,
    one_way_shear_check,
    one_way_shear_resistance,
    plastic_modulus,
    punching_checks,
    punching_stress,
    tau_rd1,
    tau_rd2,
)

C30 = MaterialsInput(fck=30.0)
COLUMN = Column(id="P1", x=0.0, y=0.0, bx=400.0, by=400.0)


@dataclass(frozen=True)
class Shear:
    shear_d: float
    depth: float
    width: float


@dataclass(frozen=True)
class Punching:
    force_c: float
    force_c1: float
    moment_x: float
    moment_y: float


@pytest.mark.golden
def test_one_way_shear_resistance() -> None:
    # fctk,inf = 0,7·0,3·30^(2/3) = 2,0276; τRd = 0,25·2,0276/1,4 = 0,3621; k = 1,6 − 0,442.
    tau_rd = 0.25 * 0.7 * 0.3 * 30.0 ** (2.0 / 3.0) / 1.4
    expected = tau_rd * 1.158 * (1.2 + 40.0 * 0.005) * 3000.0 * 442.0
    assert one_way_shear_resistance(3000.0, 442.0, 0.005, C30) == pytest.approx(expected)
    assert expected == pytest.approx(778.3e3, abs=0.1e3)


def test_one_way_shear_limits() -> None:
    base = one_way_shear_resistance(1000.0, 1200.0, 0.03, C30)  # k = 1 e ρ1 = 0,02
    tau_rd = 0.25 * 0.7 * 0.3 * 30.0 ** (2.0 / 3.0) / 1.4
    assert base == pytest.approx(tau_rd * 2.0 * 1000.0 * 1200.0)
    no_reach = one_way_shear_resistance(1000.0, 400.0, 0.01, C30, bars_reach=False)
    assert no_reach == pytest.approx(tau_rd * 1.6 * 1000.0 * 400.0)
    # τRd limitado ao valor de fck = 60 MPa.
    c70 = one_way_shear_resistance(1000.0, 1200.0, 0.0, MaterialsInput(fck=70.0))
    assert c70 == pytest.approx(0.25 * 0.7 * 2.12 * math.log(7.8) / 1.4 * 1.2 * 1000.0 * 1200.0)


def test_one_way_shear_check() -> None:
    ok = one_way_shear_check("v", Shear(700e3, 442.0, 3000.0), 0.005, C30)
    assert ok.status is CheckStatus.OK
    fail = one_way_shear_check("v", Shear(800e3, 442.0, 3000.0), 0.005, C30)
    assert fail.status is CheckStatus.FAIL
    assert fail.reference.item == "19.4.1"


@pytest.mark.golden
def test_punching_resistances() -> None:
    assert tau_rd2(C30) == pytest.approx(0.27 * 0.88 * 30.0 / 1.4)
    ke = 1.0 + math.sqrt(20.0 / 43.4)
    assert tau_rd1(434.0, 0.005, 30.0) == pytest.approx(0.13 * ke * 15.0 ** (1.0 / 3.0))
    assert tau_rd1(434.0, 0.005, 30.0) == pytest.approx(0.5383, abs=1e-4)
    # ke ≤ 2 para d < 20 cm e ρ ≤ 0,02.
    assert tau_rd1(100.0, 0.05, 30.0) == pytest.approx(0.13 * 2.0 * 60.0 ** (1.0 / 3.0))


@pytest.mark.parametrize(
    ("ratio", "k"), [(0.25, 0.45), (0.5, 0.45), (1.5, 0.65), (2.5, 0.75), (3.0, 0.8), (4.0, 0.8)]
)
def test_moment_factor_table(ratio: float, k: float) -> None:
    assert moment_factor(ratio * 400.0, 400.0) == pytest.approx(k)


def test_plastic_modulus() -> None:
    assert plastic_modulus(400.0, 400.0, 0.0) == pytest.approx(240000.0)
    d = 434.0
    expected = 240000.0 + 4 * 400 * d + 16 * d * d + 2 * math.pi * d * 400
    assert plastic_modulus(400.0, 400.0, d) == pytest.approx(expected)


@pytest.mark.golden
def test_punching_stresses_and_checks() -> None:
    d, f, m = 434.0, 2400e3, 60e6
    tau_c = f / (1600.0 * d) + 0.6 * m / (240000.0 * d)
    u1 = 1600.0 + 4.0 * math.pi * d
    tau_c1 = f / (u1 * d) + 0.6 * m / (plastic_modulus(400.0, 400.0, d) * d)
    assert punching_stress(f, (0.0, m), COLUMN, d, at_c1=False) == pytest.approx(tau_c)
    assert punching_stress(f, (m, 0.0), COLUMN, d, at_c1=True) == pytest.approx(tau_c1)

    c, c1 = punching_checks(Punching(f, f, 0.0, m), COLUMN, d, 0.005, C30)
    assert c.demand == pytest.approx(3.802, abs=1e-3)
    assert c.status is CheckStatus.OK  # τRd2 = 5,09 MPa
    assert c1.demand == pytest.approx(0.8004, abs=1e-4)
    assert c1.status is CheckStatus.FAIL  # τRd1 = 0,538 MPa
    _, relieved = punching_checks(Punching(f, 0.0, 0.0, 0.0), COLUMN, d, 0.005, C30)
    assert relieved.status is CheckStatus.OK
