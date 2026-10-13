"""Resistências de cálculo de bielas, nós e tirantes (NBR 6118:2023, 22.3.2 e 22.3.3)."""

from __future__ import annotations

import pytest

from blococalc.schemas import MaterialsInput
from blococalc.standards.strength import alpha_v2, strut_tie_strengths


@pytest.mark.golden
def test_c35_ca50() -> None:
    # B1: fcd = 35/1,4 = 25; αv2 = 1 − 35/250 = 0,86; fyd = 500/1,15.
    s = strut_tie_strengths(MaterialsInput(fck=35.0))
    assert s.fcd == pytest.approx(25.0)
    assert s.alpha_v2 == pytest.approx(0.86)
    assert s.fcd1 == pytest.approx(18.275)
    assert s.fcd2 == pytest.approx(12.9)
    assert s.fcd3 == pytest.approx(15.48)
    assert s.fyd == pytest.approx(434.7826, rel=1e-6)


def test_alpha_v2_decreases_with_fck() -> None:
    assert alpha_v2(20.0) == pytest.approx(0.92)
    assert alpha_v2(50.0) == pytest.approx(0.80)
