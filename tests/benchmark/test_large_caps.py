"""Blocos grandes pela análise completa (D13): B2 e B6 (docs/02-metodos.md §4.4 e §5)."""

from __future__ import annotations

import pytest

from blococalc.analysis import analyze
from blococalc.schemas import (
    Cap,
    CheckStatus,
    Column,
    ColumnLoad,
    DetailingInput,
    GeometryInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    Pile,
)
from tests.factories import grid_cap

C35 = MaterialsInput(fck=35.0)
TF = 9.80665e3  # N


@pytest.mark.benchmark
def test_b2_full_analysis() -> None:
    # Planilha "Bloco Sobre N estacas": 8 × 113,96 tf, γf = 1,4, φ25, cobrimento 50 (d′ = 62,5).
    case = LoadCase(id="C1", column_loads=(ColumnLoad(column_id="P1", n=1.4 * 8 * 113.96 * TF),))
    result = analyze(
        grid_cap(4, 2),
        C35,
        LoadsInput(cases=(case,), include_cap_self_weight=False),
        DetailingInput(bar_diameter=25.0),
    )

    assert result.rigid
    areas = {r.id: r.area_required for r in result.reinforcement}
    assert areas["tirante_E2_E3"] == pytest.approx(8014.0, rel=0.02)  # 80,14 cm², §4.4
    assert areas["tirante_E1_E2"] == pytest.approx(6010.0, rel=0.02)
    # Tirante em y na 2ª camada (D20): 27,67 cm² com o d′ da 1ª camada, 28,75 cm² com φ acima.
    assert areas["tirante_E1_E5"] == pytest.approx(2875.0, rel=0.02)
    assert areas["malha_x"] == pytest.approx(0.2 * 2 * areas["tirante_E2_E3"])
    failed = {c.id for c in result.checks if c.status is CheckStatus.FAIL}
    # Ancoragem: 450 mm de borda, φ32 pela D18. D20: as bielas saem da 2ª camada (z menor), e o
    # nó das estacas de canto passa de fcd3 (15,77 > 15,48 MPa); θ < 45° e y/d = 0,31 só ficam
    # fora das recomendações dos autores.
    corners = ("E1", "E4", "E5", "E8")
    assert {f for f in failed if not f.startswith("C1:ancoragem_")} == {
        f"C1:no_estaca_{e}" for e in corners
    }


def b6() -> tuple[GeometryInput, LoadsInput]:
    """Macedo 2022, §6.2, pela figura (Fig. 5.1/6.6): bloco 330×300×140 cm, grade 4×3, φ30.

    O texto do §6.2 fala em 200×200 cm e 16 estacas, o que não bate com a figura. Coordenadas a
    partir do canto superior esquerdo da figura, convertidas para o centro do bloco (y para cima).
    """
    xs, ys = (500.0, 1266.7, 2033.3, 2800.0), (500.0, 1500.0, 2500.0)
    piles = tuple(
        Pile(id=f"E{j * 4 + i + 1}", x=x - 1650.0, y=1500.0 - y, size=300.0)
        for j, y in enumerate(ys)
        for i, x in enumerate(xs)
    )
    columns = (
        Column(id="P1", x=0.0, y=1000.0, bx=800.0, by=300.0),
        Column(id="P2", x=1150.0, y=-500.0, bx=300.0, by=800.0),
        Column(id="P3", x=-1150.0, y=-500.0, bx=250.0, by=500.0),
    )
    geometry = GeometryInput(
        cap=Cap(lx=3300.0, ly=3000.0, h=1400.0, pile_embedment=100.0),
        piles=piles,
        columns=columns,
    )
    case = LoadCase(
        id="C1",
        column_loads=tuple(
            ColumnLoad(column_id=c, n=1.4 * n)
            for c, n in (("P1", 1100e3), ("P2", 900e3), ("P3", 200e3))
        ),
    )
    return geometry, LoadsInput(cases=(case,))


@pytest.mark.benchmark
def test_b6_fictitious_column_is_on_the_safe_side_of_the_space_truss() -> None:
    # D10 pede o confronto com a treliça 3D: o pilar fictício deve dar mais tração que o M7.
    geometry, cases = b6()
    result = analyze(geometry, C35, cases, DetailingInput(bar_diameter=20.0))

    assert result.rigid
    m7 = {c.id: c for c in result.checks if "m7_tracao" in c.id}
    assert set(m7) == {"C1:m7_tracao_x", "C1:m7_tracao_y"}
    for check in m7.values():
        assert check.status is CheckStatus.OK
        assert 0.0 < check.demand < check.capacity
