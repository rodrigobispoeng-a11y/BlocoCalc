"""Verificação do M5 por MEF (D14, docs/02-metodos.md §4.5).

O pós-processamento é conferido com campos de tensão analíticos; o B1 completo roda o CalculiX
(marcado `fem`, pulado onde ele não existe) e reproduz o protótipo da §4.5.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pytest

pytest.importorskip("gmsh")

from blococalc.analysis import FEM_METHOD, _fem_tie_checks, fem_verification
from blococalc.core.strut_tie import StrutTieModel, Tie
from blococalc.fem.ccx import find_ccx
from blococalc.fem.mesh import FloatArray
from blococalc.fem.post import StressField, mean_compression, section_tension
from blococalc.schemas import (
    Cap,
    CheckStatus,
    ColumnLoad,
    LoadCase,
    LoadsInput,
    MaterialsInput,
)
from tests.factories import four_pile_cap, quincunx_cap

needs_ccx = pytest.mark.skipif(find_ccx() is None, reason="CalculiX (ccx) não instalado")


class LinearField:
    """σxx = σyy = a + b·z e σ3 = −(c + x/1000), no lugar do campo interpolado do MEF."""

    def __init__(self, a: float, b: float, c: float) -> None:
        self.a, self.b, self.c = a, b, c

    def __call__(self, points: FloatArray) -> FloatArray:
        normal = self.a + self.b * points[:, 2]
        return np.column_stack([normal, normal, -(self.c + points[:, 0] / 1000.0)])


def field(a: float = 0.0, b: float = 0.0, c: float = 0.0) -> StressField:
    return cast(StressField, LinearField(a, b, c))


def loads(n: float = 980e3) -> LoadsInput:
    case = LoadCase(id="ELU1", column_loads=(ColumnLoad(column_id="P1", n=n),))
    return LoadsInput(cases=(case,), include_cap_self_weight=False)


def test_section_tension_integrates_only_tension() -> None:
    # σ = 2 − 4·z/1000 em 2000 × 1000: tração só em z < 500, resultante 2000·(2·500/2) = 1e6 N.
    tension = section_tension(field(2.0, -4e-3), 0, 0.0, (2000.0, 1000.0), 10.0)
    assert tension == pytest.approx(1e6, rel=1e-3)
    assert section_tension(field(-1.0), 1, 0.0, (2000.0, 1000.0), 50.0) == 0.0


def test_mean_compression_over_prism_and_cylinder() -> None:
    # −σ3 = 5 + x/1000: média = 5 + x do centro/1000 em volumes simétricos.
    prism = mean_compression(field(c=5.0), (100.0, 0.0), (100.0, 325.0), (900.0, 1000.0))
    assert prism == pytest.approx(5.1)
    cylinder = mean_compression(field(c=5.0), (-600.0, 0.0), (200.0, 200.0), (0.0, 116.0), True)
    assert cylinder == pytest.approx(4.4)


def test_tie_check_warns_above_ten_percent() -> None:
    geometry = four_pile_cap()
    ties = (
        Tie("E1", "E2", 400e3, 0.0, 1.0, 0.0),
        Tie("E4", "E3", 400e3, 0.0, 1.0, 0.0),
        Tie("E1", "E4", 300e3, 0.0, 0.0, 1.0),
        Tie("E2", "E3", 300e3, 0.0, 0.0, 1.0),
    )
    model = StrutTieModel(d=900.0, y=55.0, z=870.0, struts=(), ties=ties)
    # σ = 0,43 MPa constante: 0,43·2000·1000 = 860 kN, abaixo de 1,10 × 800 kN em x e acima de
    # 1,10 × 600 kN em y.
    checks = {c.id: c for c in _fem_tie_checks(geometry, model, field(0.43))}
    assert set(checks) == {"mef_tracao_x_0", "mef_tracao_y_0"}
    assert checks["mef_tracao_x_0"].capacity == pytest.approx(880e3)
    assert checks["mef_tracao_x_0"].demand == pytest.approx(860e3, rel=1e-9)
    assert checks["mef_tracao_x_0"].status is CheckStatus.OK
    assert checks["mef_tracao_y_0"].status is CheckStatus.WARNING


def test_flexible_cap_is_not_analysed() -> None:
    flexible = four_pile_cap().model_copy(
        update={"cap": Cap(lx=2000.0, ly=2000.0, h=500.0, pile_embedment=100.0)}
    )
    result = fem_verification(flexible, MaterialsInput(fck=25.0), loads(), ccx="ccx-inexistente")
    assert not result.rigid
    assert result.reactions == ()
    assert "só confere o M5 de blocos rígidos" in result.warnings[0]
    assert result.audit.method == FEM_METHOD


def test_mixed_supports_warn() -> None:
    # D16: estacas com e sem rigidez no mesmo bloco; o aviso sai antes de qualquer cálculo.
    geometry = four_pile_cap()
    piles = (geometry.piles[0].model_copy(update={"axial_stiffness": 500e3}), *geometry.piles[1:])
    flexible = geometry.model_copy(
        update={"piles": piles, "cap": Cap(lx=2000.0, ly=2000.0, h=500.0, pile_embedment=100.0)}
    )
    result = fem_verification(flexible, MaterialsInput(fck=25.0), loads(), ccx="ccx-inexistente")
    assert any("com e sem rigidez" in w for w in result.warnings)
    assert result.audit.parameters["k_E1_N_mm"] == 500e3
    assert "k_E2_N_mm" not in result.audit.parameters


@pytest.mark.fem
@needs_ccx
def test_b7_with_springs_compares_reactions_with_m1() -> None:
    # §4.7: com k = 720 kN/mm a estaca central leva cerca de 4 % a mais que o M1 (2000 kN sem
    # γn); com γn e D7 em ambos os lados, a razão se mantém. A soma bate com a carga.
    base = quincunx_cap()
    piles = tuple(p.model_copy(update={"axial_stiffness": 720e3}) for p in base.piles)
    geometry = base.model_copy(update={"piles": piles})
    result = fem_verification(geometry, MaterialsInput(fck=30.0), loads(10_000e3), mesh_size=300.0)
    factor = 1.2
    forces = {r.pile_id: r.force for r in result.reactions}
    assert sum(forces.values()) == pytest.approx(factor * 10_000e3, rel=1e-6)
    assert forces["E5"] / (factor * 2000e3) == pytest.approx(1.04, abs=0.015)
    checks = {c.id.removeprefix("ELU1:"): c for c in result.checks}
    reaction = checks["mef_reacao_E5"]
    assert reaction.unit == "N"
    assert reaction.capacity == pytest.approx(1.1 * factor * 2000e3)
    assert reaction.status is CheckStatus.OK
    assert not any("subestima" in w for w in result.warnings)
    assert result.audit.parameters["k_E5_N_mm"] == 720e3
    assert any("mola" in a for a in result.audit.assumptions)


@pytest.mark.fem
@needs_ccx
def test_stiff_springs_warn_that_m1_underestimates() -> None:
    # k = 20 000 kN/mm: quase rígido, a estaca central passa o M1 em mais de 10 %.
    base = quincunx_cap()
    piles = tuple(p.model_copy(update={"axial_stiffness": 20e6}) for p in base.piles)
    geometry = base.model_copy(update={"piles": piles})
    result = fem_verification(geometry, MaterialsInput(fck=30.0), loads(10_000e3), mesh_size=300.0)
    assert any("M1 subestima a reação da estaca E5" in w for w in result.warnings)


@pytest.mark.fem
@needs_ccx
def test_b1_matches_prototype() -> None:
    # Protótipo da §4.5 (malha 100 mm): tração 412,4 kN em x e 331,7 kN em y. Malha de 150 mm
    # aqui para o teste ser rápido (412,3 kN em x na convergência).
    result = fem_verification(four_pile_cap(), MaterialsInput(fck=25.0), loads(), mesh_size=150.0)
    checks = {c.id.removeprefix("ELU1:"): c for c in result.checks}
    assert all(c.status is CheckStatus.OK for c in result.checks)
    assert result.warnings == ()
    assert [r.force for r in result.reactions] == pytest.approx([294e3] * 4, rel=0.002)
    assert checks["mef_tracao_x_0"].demand == pytest.approx(412.3e3, rel=0.01)
    assert checks["mef_tracao_y_0"].demand == pytest.approx(331.7e3, rel=0.01)
    # M5 com φ16: em x (d′ = 58 mm) a tração do MEF fica 3 a 10 % acima; em y o M5 já usa a
    # 2ª camada (D20, d′ = 74 mm) e a folga cai para 1 a 10 %.
    for axis, low in (("x", 1.03), ("y", 1.01)):
        check = checks[f"mef_tracao_{axis}_0"]
        assert low < 1.1 * check.demand / check.capacity < 1.10
    assert checks["mef_no_pilar_P1"].demand == pytest.approx(8.0, abs=0.4)
    assert result.audit.parameters["mesh_size_mm"] == 150.0
