"""Detalhamento de bloco rígido (NBR 6118:2023, 22.7.2.1 e 22.7.4.1)."""

from __future__ import annotations

import pytest

from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.strut_tie import Tie, santos_stucchi
from blococalc.schemas import (
    CheckStatus,
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    LoadCase,
    MaterialsInput,
)
from blococalc.standards.detailing import rigid_cap_detailing
from blococalc.standards.strength import strut_tie_strengths
from tests.factories import four_pile_cap, grid_cap, two_pile_cap

C35 = MaterialsInput(fck=35.0)
FYD = 500.0 / 1.15
PHI16 = DetailingInput(bar_diameter=16.0)


def ties(geometry: GeometryInput, n: float) -> tuple[Tie, ...]:
    case = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=n),))
    reactions = rigid_cap_reactions(geometry, case)
    return santos_stucchi(geometry, reactions, strut_tie_strengths(C35), 1.2, 50.0).ties


@pytest.mark.golden
def test_b1_detailing() -> None:
    model_ties = ties(four_pile_cap(), 980e3)
    result = rigid_cap_detailing(four_pile_cap(), model_ties, C35, PHI16, 50.0)

    assert result.band_widths == {f"E{i}": pytest.approx(480.0) for i in range(1, 5)}
    # 20 % da soma das forças nos dois tirantes de cada direção.
    total_x = sum(t.force_d for t in model_ties if t.dir_y == 0.0)
    assert result.distribution_area_x == pytest.approx(0.2 * total_x / FYD)
    assert result.distribution_area_x == pytest.approx(180.89, abs=0.01)  # 184,49 antes da D13
    # Ancoragem: φ16 com gancho, ℓb,nec = 0,7·481,59 = 337,1 mm; disponível da face interna da
    # estaca (x = 400) até a face do bloco menos o cobrimento: 1000 − 50 − 400 = 550 mm.
    anchorage = [c for c in result.checks if c.id.startswith("ancoragem_")]
    assert len(anchorage) == 8
    assert {round(c.demand, 1) for c in anchorage} == {337.1}
    assert [c.capacity for c in anchorage] == pytest.approx([550.0] * 8)
    assert all(c.status is CheckStatus.OK for c in result.checks)
    assert result.warnings == ()


def test_short_overhang_fails_anchorage() -> None:
    base = four_pile_cap()
    tight = base.model_copy(update={"cap": base.cap.model_copy(update={"lx": 1500.0})})
    result = rigid_cap_detailing(tight, ties(base, 980e3), C35, PHI16, 50.0)
    x_ends = [c for c in result.checks if c.id in ("ancoragem_E1_E2_E1", "ancoragem_E1_E2_E2")]
    # 750 − 600 + 200 − 50 = 300 mm < 337,1 mm.
    assert [c.capacity for c in x_ends] == pytest.approx([300.0, 300.0])
    assert all(c.status is CheckStatus.FAIL for c in x_ends)


def test_wide_spacing_requires_suspension() -> None:
    base = four_pile_cap()
    shallow = four_pile_cap(h=390.0)  # 3·h = 1170 < 1200
    result = rigid_cap_detailing(shallow, ties(base, 980e3), C35, PHI16, 50.0)
    suspension = [c for c in result.checks if c.id.startswith("suspensao_")]
    assert all(c.status is CheckStatus.WARNING for c in suspension)
    assert any("suspensão" in w for w in result.warnings)


def test_piles_in_one_line_require_lateral_and_top_bars() -> None:
    result = rigid_cap_detailing(two_pile_cap(), ties(two_pile_cap(), 1000e3), C35, PHI16, 50.0)
    assert result.distribution_area_y == 0.0
    assert any("22.7.4.1.5" in w for w in result.warnings)


def test_straight_bars_need_longer_anchorage_and_warn() -> None:
    options = DetailingInput(bar_diameter=16.0, hooked=False)
    result = rigid_cap_detailing(four_pile_cap(), ties(four_pile_cap(), 980e3), C35, options, 50.0)
    anchorage = [c for c in result.checks if c.id.startswith("ancoragem_")]
    assert anchorage[0].demand == pytest.approx(481.59, abs=0.01)  # α = 1,0
    assert any("gancho" in w for w in result.warnings)


def test_grid_rows_anchor_at_the_ends_and_size_the_mesh_by_the_worst_segment() -> None:
    # B2 (D13): cada linha em x tem 3 trechos; a barra é contínua, com a armadura do trecho
    # central, e só ancora sobre as estacas das pontas.
    geometry = grid_cap(4, 2)
    model_ties = ties(geometry, 15e6)
    result = rigid_cap_detailing(geometry, model_ties, C35, PHI16, 50.0)

    x_ties = [t for t in model_ties if t.dir_x != 0.0]
    worst = max(t.force_d for t in x_ties)
    assert worst > min(t.force_d for t in x_ties)
    assert result.distribution_area_x == pytest.approx(0.2 * 2 * worst / FYD)
    x_prefixes = tuple(f"ancoragem_{t.pile_a}_{t.pile_b}_" for t in x_ties)
    anchored = {c.id.rsplit("_", 1)[1] for c in result.checks if c.id.startswith(x_prefixes)}
    assert anchored == {"E1", "E4", "E5", "E8"}
    anchors = [c for c in result.checks if c.id.startswith("ancoragem_")]
    assert len(anchors) == 2 * 2 + 4 * 2  # pontas das 2 linhas em x e das 4 colunas em y
