"""Treliça 3D sobre o bloco para o confronto D10 × M7 (D12; docs/02-metodos.md §4.3)."""

from __future__ import annotations

import numpy as np
import pytest

from blococalc.core.cap_truss import _segments_cross, cap_truss
from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.strut_tie import santos_stucchi
from blococalc.schemas import Column, ColumnLoad, LoadCase, MaterialsInput
from blococalc.standards.strength import strut_tie_strengths
from tests.factories import four_pile_cap


def case(n: float, my: float = 0.0) -> LoadCase:
    return LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=n, my=my),))


@pytest.mark.golden
def test_single_column_reproduces_santos_stucchi_ties() -> None:
    # Com um só pilar, os quatro nós nos quadrantes são as origens das bielas do M5 (D6):
    # as trações no fundo devem ser as do M5 no B1 (peso próprio de 5 % nos dois modelos).
    geometry = four_pile_cap()
    reactions = rigid_cap_reactions(geometry, case(980e3), 0.05 * 980e3)
    strengths = strut_tie_strengths(MaterialsInput(fck=35.0))
    model = santos_stucchi(geometry, reactions, strengths, 1.2, 58.0)
    truss = cap_truss(geometry, case(980e3), 1.2, 0.05, (model.y / 2.0, model.d))
    m5_x = sum(t.force_d * abs(t.dir_x) for t in model.ties)
    m5_y = sum(t.force_d * abs(t.dir_y) for t in model.ties)
    assert truss.tension_x == pytest.approx(m5_x, rel=1e-6)
    assert truss.tension_y == pytest.approx(m5_y, rel=1e-6)
    assert truss.inclined_struts == ()
    assert truss.crossing_struts == ()


def test_large_moment_creates_vertical_ties() -> None:
    # my = 900 kN·m sobre 980 kN: quadrantes do lado −x e estacas do lado −x tracionados.
    truss = cap_truss(four_pile_cap(), case(980e3, my=900e6), 1.2, 0.0, (50.0, 842.0))
    vertical_ties = {
        frozenset((m.start, m.end))
        for m in truss.truss.members
        if m.force > 0 and abs(abs(m.direction[2]) - 1.0) < 1e-9
    }
    assert frozenset(("P1a", "P1a_fundo")) in vertical_ties
    assert frozenset(("E1", "E1_topo")) in vertical_ties


def test_struts_outside_the_inclination_limits_are_listed() -> None:
    # Pilares nas diagonais, a 300 mm do centro: bielas quase verticais até as estacas próximas.
    columns = (
        Column(id="P1", x=-300.0, y=-300.0, bx=200.0, by=200.0),
        Column(id="P2", x=300.0, y=300.0, bx=200.0, by=200.0),
    )
    geometry = four_pile_cap().model_copy(update={"columns": columns})
    loads = tuple(ColumnLoad(column_id=c.id, n=600e3) for c in columns)
    truss = cap_truss(geometry, LoadCase(id="C1", column_loads=loads), 1.2, 0.0, (50.0, 842.0))
    assert truss.inclined_struts


def test_segment_crossing() -> None:
    o = np.zeros(3)
    assert _segments_cross(
        o, np.array([2.0, 2.0, 0.0]), np.array([0.0, 2.0, 0.0]), np.array([2.0, 0.0, 0.0])
    )
    assert not _segments_cross(
        o, np.array([1.0, 0.0, 0.0]), np.array([2.0, 1.0, 0.0]), np.array([2.0, -1.0, 0.0])
    )
    assert not _segments_cross(
        o, np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([1.0, 1.0, 0.0])
    )
    assert not _segments_cross(
        o, np.array([1.0, 1.0, 0.0]), np.array([0.0, 1.0, 1.0]), np.array([1.0, 0.0, 1.0])
    )
