"""Análise completa de um bloco sobre estacas: monta `AnalysisResult` (contratos v3).

É a única camada que combina `core` e `standards`, que não se importam entre si. Sem I/O.

Premissas aprovadas (docs/02-metodos.md §6, registradas na trilha de auditoria):
- D7: peso próprio do bloco = 5 % da força normal de cálculo do caso, no centro do bloco
  (NBR 6122:2019, 5.6, mínimo de 5 % da carga permanente; a favor da segurança porque a
  normal de cálculo inclui as variáveis);
- D8: eixo do tirante a d′ = cobrimento + φ/2 acima da cabeça da estaca;
- D9: bloco flexível pelas seções S1 do CEB-70 com flexão, cisalhamento e punção da NBR 6118
  (docs/02-metodos.md §4.2);
- D10: vários pilares viram um pilar fictício de área equivalente por caso; as reações usam os
  pilares reais e o nó de cada pilar real é verificado à parte.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import replace

from blococalc import __version__
from blococalc.core.flexible_cap import face_shears, punching_load, s1_moments
from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.strut_tie import santos_stucchi
from blococalc.geometry.fictitious_column import fictitious_column
from blococalc.schemas import (
    AnalysisResult,
    AuditTrail,
    Check,
    CheckStatus,
    DetailingInput,
    GeometryInput,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    PileReaction,
    Reference,
    Reinforcement,
    ReinforcementKind,
)
from blococalc.standards.detailing import rigid_cap_detailing
from blococalc.standards.durability import cover_check
from blococalc.standards.flexure import design_section
from blococalc.standards.rigidity import rigidity_checks
from blococalc.standards.slab_shear import one_way_shear_check, punching_checks
from blococalc.standards.strength import strut_tie_strengths
from blococalc.standards.strut_tie_checks import real_column_node_checks, strut_tie_checks

METHOD = "santos-stucchi-2019"
FLEXIBLE_METHOD = "ceb70-nbr6118-flexao"  # ADR-003
SECONDARY_RATIO = 0.20  # CEB-70 §3.2: armadura transversal ≥ 1/5 da principal
SELF_WEIGHT_RATIO = 0.05  # D7

_TIE_REF = Reference(source="NBR 6118:2023", item="22.3.3 / 22.7.4.1.1")
_DISTRIBUTION_REF = Reference(source="NBR 6118:2023", item="22.7.4.1.2")
_SUSPENSION_REF = Reference(source="NBR 6118:2023", item="22.7.4.1.3")
_LATERAL_REF = Reference(source="NBR 6118:2023", item="22.7.4.1.5")
_FLEXURE_REF = Reference(source="CEB-FIP 70 §3 / NBR 6118:2023", item="17.2.2")
_DUCTILITY_REF = Reference(source="NBR 6118:2023", item="14.6.4.3")

_ASSUMPTIONS = (
    "Bloco rígido: reações lineares em planta, estacas de mesma rigidez (M1).",
    "Bielas e tirantes por Santos/Stucchi; y do nó CCC por equilíbrio horizontal (D2, D6).",
    "Pilar retangular tratado por direção com as dimensões reais (D4, provisória).",
    "Peso próprio do bloco = 5 % da normal de cálculo de cada caso (D7).",
    "Eixo do tirante a cobrimento + φ/2 acima da cabeça da estaca (D8).",
    "Ancoragem com As,calc/As,ef = 1 enquanto as barras não são escolhidas.",
)
_FLEXIBLE_ASSUMPTIONS = (
    "Bloco flexível: reações lineares em planta (M1), hipótese do CEB-70 §2.",
    "Flexão nas seções S1 do CEB-70 (0,15·ap para dentro da face), largura total (D9).",
    "Barras em x na camada inferior: dx = h − embutimento − (c + φ/2); dy = dx − φ.",
    "Cortante soma as estacas além da face do pilar, sem redução a/2d (D9).",
    "Punção no pilar como pilar interno (19.5.2.2), sem armadura de punção.",
    "Peso próprio do bloco = 5 % da normal de cálculo de cada caso (D7).",
)
_MULTI_COLUMN_WARNING = (
    "Vários pilares: modelo com pilar fictício de área equivalente (D10). Conferir com a treliça "
    "3D (M7) quando disponível e prever armaduras complementares entre os pilares."
)
_CORNER_PILES_WARNING = (
    "Bloco flexível: punção e cisalhamento junto às estacas de canto e de borda não são "
    "verificados pelo programa (D9); conferir com modelo 3D."
)


def analyze(
    geometry: GeometryInput,
    materials: MaterialsInput,
    loads: LoadsInput,
    detailing: DetailingInput | None = None,
) -> AnalysisResult:
    """Reações, verificações e armaduras de um bloco sobre estacas.

    Bloco rígido por bielas e tirantes (Santos/Stucchi); bloco flexível (NBR 6118:2023, 22.7.1)
    como laje sobre estacas (D9). Vários pilares entram como pilar fictício (D10).
    """
    options = detailing or DetailingInput()
    multiple = len(geometry.columns) > 1
    tie_height = geometry.cap.cover + options.bar_diameter / 2.0
    strengths = strut_tie_strengths(materials)

    checks: list[Check] = [
        *rigidity_checks(geometry.cap, _model_inputs(geometry, loads.cases[0])[0].columns[0]),
        cover_check(geometry.cap, options.aggressiveness_class, options.bar_diameter),
    ]
    rigid = all(c.status is CheckStatus.OK for c in checks[:2])
    warnings: list[str] = [_MULTI_COLUMN_WARNING] if multiple else []
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
            flex_checks, flex_items, flex_warnings = _flexible_case(
                geometry, materials, options, loads.gamma_n, (case, case_reactions)
            )
            checks += _tag(case.id, flex_checks)
            warnings += [w for w in flex_warnings if w not in warnings]
            _merge(envelope, flex_items)
            continue
        model_geometry, _ = _model_inputs(geometry, case)
        model = santos_stucchi(model_geometry, case_reactions, strengths, loads.gamma_n, tie_height)
        result = rigid_cap_detailing(model_geometry, model.ties, materials, options, tie_height)
        checks += _tag(case.id, (*strut_tie_checks(model, strengths), *result.checks))
        if multiple:
            normals = {load.column_id: load.n for load in case.column_loads}
            real = real_column_node_checks(
                model, geometry.columns, normals, loads.gamma_n, strengths
            )
            checks += _tag(case.id, real)
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
        _merge(envelope, items)

    if not rigid:
        warnings.insert(
            0,
            "Bloco flexível pela NBR 6118:2023, 22.7.1 (h < (a − ap)/3): dimensionado como laje "
            "sobre estacas (D9), não por bielas e tirantes.",
        )
        warnings.append(_CORNER_PILES_WARNING)
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
            method=METHOD if rigid else FLEXIBLE_METHOD,
            assumptions=_ASSUMPTIONS if rigid else _FLEXIBLE_ASSUMPTIONS,
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


def _merge(envelope: dict[str, Reinforcement], items: Sequence[Reinforcement]) -> None:
    for item in items:
        current = envelope.get(item.id)
        if current is None or item.area_required > current.area_required:
            envelope[item.id] = item


def _flexible_case(
    geometry: GeometryInput,
    materials: MaterialsInput,
    options: DetailingInput,
    gamma_n: float,
    loading: tuple[LoadCase, Sequence[PileReaction]],
) -> tuple[list[Check], list[Reinforcement], list[str]]:
    """Flexão (S1), cortante e punção de um caso do bloco flexível (D9)."""
    case, reactions = loading
    model_geometry, _ = _model_inputs(geometry, case)
    cap, phi = geometry.cap, options.bar_diameter
    depth_x = cap.h - cap.pile_embedment - (cap.cover + phi / 2.0)
    depths = {"x": depth_x, "y": depth_x - phi}
    widths = {"x": cap.ly, "y": cap.lx}
    fyd = materials.fyk / materials.gamma_s
    checks: list[Check] = []
    area = {"x": 0.0, "y": 0.0}
    for section in s1_moments(model_geometry, reactions, gamma_n, depths["x"], depths["y"]):
        design = design_section(section.moment_d, section.width, cap.h, section.depth, materials)
        area[section.axis] = max(area[section.axis], design.area)
        checks.append(
            Check(
                id=f"dutilidade_{section.axis}{'+' if section.side > 0 else '-'}",
                description=f"Flexão na seção S1 ({section.axis}): x/d ≤ limite",
                demand=design.x_over_d,
                capacity=design.x_over_d_limit,
                unit="-",
                status=CheckStatus.OK
                if design.x_over_d <= design.x_over_d_limit
                else CheckStatus.FAIL,
                reference=_DUCTILITY_REF,
            )
        )
    area = {
        "x": max(area["x"], SECONDARY_RATIO * area["y"]),
        "y": max(area["y"], SECONDARY_RATIO * area["x"]),
    }
    rho = {axis: area[axis] / (widths[axis] * depths[axis]) for axis in area}
    for shear in face_shears(model_geometry, reactions, gamma_n, depths["x"], depths["y"]):
        sign = "+" if shear.side > 0 else "-"
        checks.append(
            one_way_shear_check(
                f"cisalhamento_{shear.axis}{sign}", shear, rho[shear.axis], materials
            )
        )
    depth = (depths["x"] + depths["y"]) / 2.0
    rho_punching = math.sqrt(rho["x"] * rho["y"])
    multiple = len(geometry.columns) > 1
    warnings = []
    loaded = {load.column_id for load in case.column_loads}
    for column in (c for c in geometry.columns if c.id in loaded):
        single = geometry.model_copy(update={"columns": (column,)})
        load = punching_load(single, case, reactions, gamma_n, depth)
        if multiple:
            # Uma estaca pode estar no C′ de mais de um pilar: sem desconto (a favor da segurança).
            load = replace(load, force_c1=load.force_c, piles_inside_c1=())
        c, c1 = punching_checks(load, column, depth, rho_punching, materials)
        suffix = f"_{column.id}" if multiple else ""
        checks.append(c.model_copy(update={"id": c.id + suffix}))
        if load.c1_inside_cap:
            checks.append(c1.model_copy(update={"id": c1.id + suffix}))
        else:
            warnings.append(
                f"Contorno C′ da punção (2d) do pilar {column.id} sai do bloco: verificação em "
                "C′ não feita; conferir com modelo 3D (NBR 6118:2023, 19.5.2.3)."
            )
    items = [
        Reinforcement(
            id=f"flexao_{axis}",
            kind=ReinforcementKind.FLEXURE,
            direction=direction,
            force_d=area[axis] * fyd,
            area_required=area[axis],
            bar_diameter=phi,
            reference=_FLEXURE_REF,
        )
        for axis, direction in (("x", (1.0, 0.0)), ("y", (0.0, 1.0)))
    ]
    return checks, items, warnings


def _model_inputs(geometry: GeometryInput, case: LoadCase) -> tuple[GeometryInput, LoadCase]:
    """Geometria e caso do modelo: com vários pilares, o pilar fictício de área equivalente."""
    if len(geometry.columns) == 1:
        return geometry, case
    column, load = fictitious_column(geometry.columns, case, geometry.cap)
    return (
        geometry.model_copy(update={"columns": (column,)}),
        LoadCase(id=case.id, column_loads=(load,)),
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
