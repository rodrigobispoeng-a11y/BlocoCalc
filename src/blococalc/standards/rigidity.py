"""Classificação do bloco em rígido ou flexível.

NBR 6118:2023, 22.7.1: blocos podem ser considerados rígidos ou flexíveis por critério análogo
ao definido para sapatas. NBR 6118:2023, 22.6.1: a sapata é rígida quando h ≥ (a − ap)/3 nas
duas direções.

Decisões de interpretação (docs/02-metodos.md §6):
- D1: este critério governa; critérios da literatura entram só como alertas;
- D4: em cada direção usa-se a dimensão do pilar naquela direção;
- D5: `a` é a dimensão do bloco na direção considerada.
"""

from __future__ import annotations

from blococalc.schemas import Cap, Check, CheckStatus, Column, Reference

_REFERENCE = Reference(source="NBR 6118:2023", item="22.7.1 / 22.6.1")


def required_rigid_height(cap_dimension: float, column_dimension: float) -> float:
    """Altura mínima para bloco rígido numa direção: (a − ap)/3 [mm]."""
    return max(cap_dimension - column_dimension, 0.0) / 3.0


def rigidity_checks(cap: Cap, column: Column) -> tuple[Check, Check]:
    """Verificação h ≥ (a − ap)/3 nas direções x e y para um pilar."""
    return (
        _check("x", cap.h, required_rigid_height(cap.lx, column.bx)),
        _check("y", cap.h, required_rigid_height(cap.ly, column.by)),
    )


def is_rigid(cap: Cap, column: Column) -> bool:
    return all(check.status is CheckStatus.OK for check in rigidity_checks(cap, column))


def _check(direction: str, height: float, required: float) -> Check:
    return Check(
        id=f"rigidez_{direction}",
        description=f"Bloco rígido na direção {direction}: h ≥ (a − ap)/3",
        demand=required,
        capacity=height,
        unit="mm",
        status=CheckStatus.OK if height >= required else CheckStatus.FAIL,
        reference=_REFERENCE,
    )
