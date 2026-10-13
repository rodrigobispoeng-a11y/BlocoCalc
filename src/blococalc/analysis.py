"""Análise completa de um bloco rígido: monta `AnalysisResult` (contratos v2, ADR-002).

É a única camada que combina `core` e `standards`, que não se importam entre si. Sem I/O.

Premissas provisórias (docs/02-metodos.md §6, registradas na trilha de auditoria):
- D7: peso próprio do bloco = 5 % da força normal de cálculo do caso, no centro do bloco
  (NBR 6122:2019, 5.6, mínimo de 5 % da carga permanente; a favor da segurança porque a
  normal de cálculo inclui as variáveis);
- D8: eixo do tirante a d′ = cobrimento + φ/2 acima da cabeça da estaca.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from blococalc import __version__
from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.strut_tie import santos_stucchi
from blococalc.schemas import (
    AnalysisResult,
    AuditTrail,
    Check,
    CheckStatus,
    DetailingInput,
    GeometryInput,
    LoadsInput,
    MaterialsInput,
    PileReaction,
    Reference,
    Reinforcement,
    ReinforcementKind,
)
from blococalc.standards.detailing import rigid_cap_detailing
from blococalc.standards.durability import cover_check
from blococalc.standards.rigidity import rigidity_checks
from blococalc.standards.strength import strut_tie_strengths
from blococalc.standards.strut_tie_checks import strut_tie_checks

METHOD = "santos-stucchi-2019"
SELF_WEIGHT_RATIO = 0.05  # D7

_TIE_REF = Reference(source="NBR 6118:2023", item="22.3.3 / 22.7.4.1.1")
_DISTRIBUTION_REF = Reference(source="NBR 6118:2023", item="22.7.4.1.2")
_SUSPENSION_REF = Reference(source="NBR 6118:2023", item="22.7.4.1.3")
_LATERAL_REF = Reference(source="NBR 6118:2023", item="22.7.4.1.5")

_ASSUMPTIONS = (
    "Bloco rígido: reações lineares em planta, estacas de mesma rigidez (M1).",
    "Bielas e tirantes por Santos/Stucchi; y do nó CCC por equilíbrio horizontal (D2, D6).",
    "Pilar retangular tratado por direção com as dimensões reais (D4, provisória).",
    "Peso próprio do bloco = 5 % da normal de cálculo de cada caso (D7, provisória).",
    "Eixo do tirante a cobrimento + φ/2 acima da cabeça da estaca (D8, provisória).",
    "Ancoragem com As,calc/As,ef = 1 enquanto as barras não são escolhidas.",
)


def analyze(
    geometry: GeometryInput,
    materials: MaterialsInput,
    loads: LoadsInput,
    detailing: DetailingInput | None = None,
) -> AnalysisResult:
    """Reações, verificações e armaduras de um bloco sobre estacas com um pilar.

    Bloco classificado como flexível (NBR 6118:2023, 22.7.1) devolve só a classificação e as
    reações, com alerta: o modelo rígido fica bloqueado (CLAUDE.md §8).
    """
    options = detailing or DetailingInput()
    if len(geometry.columns) != 1:
        raise ValueError("A análise v1 aceita um único pilar por bloco")
    tie_height = geometry.cap.cover + options.bar_diameter / 2.0
    strengths = strut_tie_strengths(materials)

    checks: list[Check] = [
        *rigidity_checks(geometry.cap, geometry.columns[0]),
        cover_check(geometry.cap, options.aggressiveness_class, options.bar_diameter),
    ]
    rigid = all(c.status is CheckStatus.OK for c in checks[:2])
    warnings: list[str] = []
    reactions: list[PileReaction] = []
    envelope: dict[str, Reinforcement] = {}

    for case in loads.cases:
        self_weight = (
            SELF_WEIGHT_RATIO * sum(load.n for load in case.column_loads)
            if loads.include_cap_self_weight
            else 0.0
        )
        case_reactions = rigid_cap_reactions(geometry, case, self_weight)
        reactions += case_reactions
        if not rigid:
            continue
        model = santos_stucchi(geometry, case_reactions, strengths, loads.gamma_n, tie_height)
        result = rigid_cap_detailing(geometry, model.ties, materials, options, tie_height)
        checks += _tag(case.id, (*strut_tie_checks(model, strengths), *result.checks))
        warnings += [w for w in result.warnings if w not in warnings]
        phi = options.bar_diameter
        items = [
            Reinforcement(
                id=f"tirante_{t.pile_a}_{t.pile_b}",
                kind=ReinforcementKind.TIE,
                direction=(t.dir_x, t.dir_y),
                force_d=t.force_d,
                area_required=t.area_required,
                bar_diameter=phi,
                reference=_TIE_REF,
            )
            for t in model.ties
        ]
        for axis, area, direction in (
            ("x", result.distribution_area_x, (1.0, 0.0)),
            ("y", result.distribution_area_y, (0.0, 1.0)),
        ):
            items.append(
                Reinforcement(
                    id=f"malha_{axis}",
                    kind=ReinforcementKind.DISTRIBUTION,
                    direction=direction,
                    force_d=area * strengths.fyd,
                    area_required=area,
                    bar_diameter=phi,
                    reference=_DISTRIBUTION_REF,
                )
            )
        for item in items:
            current = envelope.get(item.id)
            if current is None or item.area_required > current.area_required:
                envelope[item.id] = item

    if not rigid:
        warnings.append(
            "Bloco flexível pela NBR 6118:2023, 22.7.1 (h < (a − ap)/3): o modelo de bloco "
            "rígido foi bloqueado. Blocos flexíveis ainda não estão no programa."
        )
    reinforcement = list(envelope.values())
    reinforcement += _flagged(warnings, options.bar_diameter)
    return AnalysisResult(
        rigid=rigid,
        reactions=tuple(reactions),
        checks=tuple(checks),
        reinforcement=tuple(reinforcement),
        warnings=tuple(warnings),
        audit=AuditTrail(
            app_version=__version__,
            method=METHOD,
            assumptions=_ASSUMPTIONS,
            parameters={
                "gamma_n": loads.gamma_n,
                "tie_height_mm": tie_height,
                "bar_diameter_mm": options.bar_diameter,
                "self_weight_ratio": SELF_WEIGHT_RATIO if loads.include_cap_self_weight else 0.0,
                "aggressiveness_class": options.aggressiveness_class.value,
            },
            input_hash=_input_hash(geometry, materials, loads, options),
        ),
    )


def _tag(case_id: str, checks: Sequence[Check]) -> list[Check]:
    return [c.model_copy(update={"id": f"{case_id}:{c.id}"}) for c in checks]


def _flagged(warnings: Sequence[str], phi: float) -> list[Reinforcement]:
    """Armaduras exigidas pela norma mas ainda sem método de cálculo pinado: área zero."""
    flags = (
        ("suspensao", ReinforcementKind.SUSPENSION, "22.7.4.1.3", _SUSPENSION_REF),
        ("lateral_superior", ReinforcementKind.LATERAL_TOP, "22.7.4.1.5", _LATERAL_REF),
    )
    return [
        Reinforcement(
            id=name,
            kind=kind,
            direction=(0.0, 0.0),
            force_d=0.0,
            area_required=0.0,
            bar_diameter=phi,
            reference=reference,
        )
        for name, kind, clause, reference in flags
        if any(clause in w for w in warnings)
    ]


def _input_hash(*inputs: GeometryInput | MaterialsInput | LoadsInput | DetailingInput) -> str:
    digest = hashlib.sha256()
    for item in inputs:
        digest.update(item.model_dump_json().encode("utf-8"))
    return digest.hexdigest()
