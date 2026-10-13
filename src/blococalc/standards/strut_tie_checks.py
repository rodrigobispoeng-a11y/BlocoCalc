"""Verificações do modelo de bielas e tirantes (docs/02-metodos.md §4.1).

Recebe o resultado de `blococalc.core.strut_tie.santos_stucchi` e devolve `Check` por biela.
As recomendações dos autores (y/d ≤ 0,3 e θ ≥ 45°) são alertas, não reprovações.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from blococalc.schemas import Check, CheckStatus, Reference
from blococalc.standards.strength import StrutTieStrengths

TAN_THETA_MIN = 0.57
TAN_THETA_MAX = 2.0
TAN_THETA_RECOMMENDED = 1.0  # θ ≥ 45°, Santos, Carvalho e Stucchi (2019)
DUCTILITY_RATIO_MAX = 0.3  # y/d, Santos, Carvalho e Stucchi (2019), §3.5

_ANGLE = Reference(source="NBR 6118:2023", item="22.3.1")
_NODES = Reference(source="NBR 6118:2023", item="22.3.2")
_AUTHORS = Reference(source="Santos, Carvalho e Stucchi (2019)", item="§3.5")


class StrutResult(Protocol):
    """Biela resolvida (`core.strut_tie.Strut` atende a este protocolo)."""

    @property
    def pile_id(self) -> str: ...
    @property
    def tan_theta(self) -> float: ...
    @property
    def sigma_column_node(self) -> float: ...
    @property
    def sigma_pile_node(self) -> float: ...


class StrutTieResult(Protocol):
    """Modelo resolvido (`core.strut_tie.StrutTieModel` atende a este protocolo)."""

    @property
    def d(self) -> float: ...
    @property
    def y(self) -> float: ...
    @property
    def struts(self) -> Sequence[StrutResult]: ...


def strut_tie_checks(model: StrutTieResult, strengths: StrutTieStrengths) -> tuple[Check, ...]:
    """Inclinação das bielas (22.3.1), tensões nos nós CCC e CCT (22.3.2) e ductilidade.

    Em cada `Check`, demanda ≤ capacidade significa atendido.
    """
    rows: list[tuple[str, str, float, float, str, Reference, CheckStatus]] = []
    for strut in model.struts:
        tag, tan_t = strut.pile_id, strut.tan_theta
        sc, sp = strut.sigma_column_node, strut.sigma_pile_node
        rows += [
            (f"tg_theta_min_{tag}", f"Biela {tag}: tg θ ≥ 0,57",
             TAN_THETA_MIN, tan_t, "-", _ANGLE, CheckStatus.FAIL),
            (f"tg_theta_max_{tag}", f"Biela {tag}: tg θ ≤ 2",
             tan_t, TAN_THETA_MAX, "-", _ANGLE, CheckStatus.FAIL),
            (f"theta_45_{tag}", f"Biela {tag}: θ ≥ 45° (recomendação)",
             TAN_THETA_RECOMMENDED, tan_t, "-", _AUTHORS, CheckStatus.WARNING),
            (f"no_pilar_{tag}", f"Nó CCC sob o pilar, biela {tag}: σcd,c ≤ fcd1",
             sc, strengths.fcd1, "MPa", _NODES, CheckStatus.FAIL),
            (f"no_estaca_{tag}", f"Nó CCT sobre a estaca {tag}: σcd,p ≤ fcd3",
             sp, strengths.fcd3, "MPa", _NODES, CheckStatus.FAIL),
        ]  # fmt: skip
    rows.append(
        ("ductilidade", "Profundidade do nó: y/d ≤ 0,3 (recomendação)",
         model.y / model.d, DUCTILITY_RATIO_MAX, "-", _AUTHORS, CheckStatus.WARNING)
    )  # fmt: skip
    return tuple(
        Check(
            id=check_id,
            description=description,
            demand=demand,
            capacity=capacity,
            unit=unit,
            status=CheckStatus.OK if demand <= capacity else failure,
            reference=reference,
        )
        for check_id, description, demand, capacity, unit, reference, failure in rows
    )
