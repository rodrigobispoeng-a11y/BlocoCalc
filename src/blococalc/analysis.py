"""Análise completa de um bloco sobre estacas: monta `AnalysisResult` (contratos v5).

É a única camada que combina `core` e `standards`, que não se importam entre si. Sem I/O.

Premissas aprovadas (docs/02-metodos.md §6, registradas na trilha de auditoria):
- D7: peso próprio do bloco = 5 % da força normal de cálculo do caso, no centro do bloco
  (NBR 6122:2019, 5.6, mínimo de 5 % da carga permanente; a favor da segurança porque a
  normal de cálculo inclui as variáveis);
- D8: eixo do tirante a d′ = cobrimento + φ/2 acima da cabeça da estaca;
- D9: bloco flexível pelas seções S1 do CEB-70 com flexão, cisalhamento e punção da NBR 6118
  (docs/02-metodos.md §4.2);
- D10: vários pilares viram um pilar fictício de área equivalente por caso; as reações usam os
  pilares reais e o nó de cada pilar real é verificado à parte;
- D12: no bloco rígido com vários pilares, a treliça 3D de menor energia (M7) com os pilares
  reais confronta as trações no fundo do modelo de pilar fictício (docs/02-metodos.md §4.3);
- D14: sob demanda, `fem_verification` confere o M5 por MEF linear (docs/02-metodos.md §4.5).
  O pacote `fem` (gmsh e CalculiX) só é importado dentro dessa função.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

from blococalc import __version__
from blococalc.core.cap_truss import cap_truss
from blococalc.core.flexible_cap import face_shears, punching_load, s1_moments
from blococalc.core.reactions import rigid_cap_reactions
from blococalc.core.strut_tie import StrutTieModel, santos_stucchi
from blococalc.geometry.fictitious_column import fictitious_column
from blococalc.schemas import (
    AnalysisResult,
    AuditTrail,
    Check,
    CheckStatus,
    DetailingInput,
    GeometryInput,
    LayoutMember,
    LayoutMemberKind,
    LayoutNode,
    LoadCase,
    LoadsInput,
    MaterialsInput,
    PileReaction,
    PileShape,
    Project,
    Reference,
    Reinforcement,
    ReinforcementKind,
    StrutTieLayout,
)
from blococalc.standards.detailing import rigid_cap_detailing
from blococalc.standards.durability import cover_check
from blococalc.standards.flexure import design_section
from blococalc.standards.rigidity import rigidity_checks
from blococalc.standards.slab_shear import one_way_shear_check, punching_checks
from blococalc.standards.strength import StrutTieStrengths, strut_tie_strengths
from blococalc.standards.strut_tie_checks import real_column_node_checks, strut_tie_checks

if TYPE_CHECKING:
    from blococalc.fem.post import StressField

METHOD = "santos-stucchi-2019"
FLEXIBLE_METHOD = "ceb70-nbr6118-flexao"  # ADR-003
SECONDARY_RATIO = 0.20  # CEB-70 §3.2: armadura transversal ≥ 1/5 da principal
SELF_WEIGHT_RATIO = 0.05  # D7
_HASH_FORMAT = "4"  # ADR-007: formato do hash das entradas, igual ao da v4
_M7_TOLERANCE = 0.01  # diferença numérica aceita no confronto D10 × M7

_TIE_REF = Reference(source="NBR 6118:2023", item="22.3.3 / 22.7.4.1.1")
_DISTRIBUTION_REF = Reference(source="NBR 6118:2023", item="22.7.4.1.2")
_SUSPENSION_REF = Reference(source="NBR 6118:2023", item="22.7.4.1.3")
_LATERAL_REF = Reference(source="NBR 6118:2023", item="22.7.4.1.5")
_FLEXURE_REF = Reference(source="CEB-FIP 70 §3 / NBR 6118:2023", item="17.2.2")
_DUCTILITY_REF = Reference(source="NBR 6118:2023", item="14.6.4.3")
_M7_REF = Reference(source="Gomes (2015) / docs/02-metodos.md", item="eq. 3.7; D10, D12")

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
    "Vários pilares: modelo com pilar fictício de área equivalente (D10), confrontado com a "
    "treliça 3D dos pilares reais (M7, D12); prever armaduras complementares entre os pilares."
)
_STIFFNESS_WARNING = (
    "Estacas com rigidez diferente (D16): as reações do M1 supõem estacas iguais; a rigidez só "
    "entra na conferência por MEF."
)
_M7_ASSUMPTION = (
    "Vários pilares: treliça 3D de menor Σ Ft·lt (M7) com os pilares reais em quatro nós cada, "
    "planos do M5 e peso próprio nos pilares, só para confronto (D12)."
)
FEM_METHOD = "mef-linear-d14"
_FEM_REACTION_LIMIT = 0.01  # D14: validade do modelo
_FEM_TIE_LIMIT = 0.10  # D14: alerta de tirante
_FEM_REF = Reference(source="docs/02-metodos.md", item="§4.5, D14")
_FEM_NODE_REF = Reference(source="NBR 6118:2023", item="22.3.2; D14")
_FEM_ASSUMPTIONS = (
    "Sólido elástico linear sem armadura, C3D10 (gmsh + CalculiX), Ecs e ν = 0,2 (8.2.8, 8.2.9).",
    "Estacas como apoios verticais rígidos na área da cabeça, no fundo do bloco; vinculação "
    "horizontal isostática (D14).",
    "Cargas dos pilares reais × γn·(1 + D7) como pressão (Navier) e cisalhamento uniforme.",
    "Tração: tensões normais positivas em planos verticais entre linhas de estacas vizinhas.",
    "Nós: média de −σ3 no prisma pilar × y do M5 (fcd1) e no volume estaca × 2·d′ (fcd3).",
    "Comparação apenas: o dimensionamento continua pelo M5.",
)
_FEM_SPRING_LIMIT = 0.10  # D16: alerta de reação com molas
_FEM_SPRING_REF = Reference(source="docs/02-metodos.md", item="§4.7, D16")
_FEM_SPRING_ASSUMPTION = (
    "Estacas com rigidez: cabeça rígida sobre mola axial k (D16); sem rigidez: apoio vertical "
    "rígido na área da cabeça; vinculação horizontal isostática (D14)."
)
_MIXED_SUPPORTS_WARNING = (
    "Estacas com e sem rigidez no MEF (D16): as sem rigidez ficam como apoio rígido e tendem a "
    "concentrar carga."
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

    rigidity = rigidity_checks(geometry.cap, _model_inputs(geometry, loads.cases[0])[0].columns[0])
    checks: list[Check] = [
        *rigidity,
        cover_check(geometry.cap, options.aggressiveness_class, options.bar_diameter),
    ]
    rigid = all(c.status is CheckStatus.OK for c in rigidity)
    warnings: list[str] = [_MULTI_COLUMN_WARNING] if multiple else []
    if len({p.axial_stiffness for p in geometry.piles}) > 1:
        warnings.append(_STIFFNESS_WARNING)
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
            ratio = SELF_WEIGHT_RATIO if loads.include_cap_self_weight else 0.0
            m7_checks, m7_warnings = _space_truss_comparison(
                geometry, case, loads.gamma_n, ratio, model
            )
            checks += _tag(case.id, m7_checks)
            warnings += m7_warnings
        warnings += [w for w in result.warnings if w not in warnings]
        if model.interior_piles:
            interior = _interior_pile_warning(model.interior_piles)
            warnings += [interior] if interior not in warnings else []
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
            assumptions=(
                (*_ASSUMPTIONS, *((_M7_ASSUMPTION,) if multiple else ()))
                if rigid
                else _FLEXIBLE_ASSUMPTIONS
            ),
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


def fem_verification(  # noqa: PLR0913 - mesmas entradas de analyze() mais as opções do MEF
    geometry: GeometryInput,
    materials: MaterialsInput,
    loads: LoadsInput,
    detailing: DetailingInput | None = None,
    *,
    mesh_size: float | None = None,
    ccx: str | None = None,
) -> AnalysisResult:
    """Confere o M5 de um bloco rígido por MEF linear (D14, docs/02-metodos.md §4.5).

    Chamada separada de `analyze()`, sob demanda: exige o extra `fem` (gmsh) e o executável do
    CalculiX (`ccx`, parâmetro, BLOCOCALC_CCX ou PATH). As reações devolvidas são as do MEF.
    """
    from blococalc.fem import ccx as solver  # noqa: PLC0415 (extra opcional)
    from blococalc.fem import post  # noqa: PLC0415
    from blococalc.fem.loads import column_nodal_forces  # noqa: PLC0415
    from blococalc.fem.mesh import mesh_cap  # noqa: PLC0415

    options = detailing or DetailingInput()
    tie_height = geometry.cap.cover + options.bar_diameter / 2.0
    strengths = strut_tie_strengths(materials)
    ratio = SELF_WEIGHT_RATIO if loads.include_cap_self_weight else 0.0
    checks = list(
        rigidity_checks(geometry.cap, _model_inputs(geometry, loads.cases[0])[0].columns[0])
    )
    rigid = all(c.status is CheckStatus.OK for c in checks)
    parameters: dict[str, float | str | bool] = {
        "gamma_n": loads.gamma_n,
        "tie_height_mm": tie_height,
        "self_weight_ratio": ratio,
        "Ecs_MPa": solver.secant_modulus(materials.fck),
        "poisson": solver.POISSON,
    }
    stiffness = {p.id: p.axial_stiffness for p in geometry.piles if p.axial_stiffness is not None}
    parameters |= {f"k_{pid}_N_mm": k for pid, k in stiffness.items()}
    warnings: list[str] = []
    if stiffness and len(stiffness) < len(geometry.piles):
        warnings.append(_MIXED_SUPPORTS_WARNING)
    reactions: list[PileReaction] = []
    if not rigid:
        warnings.append(
            "Bloco flexível pela NBR 6118:2023, 22.7.1: o MEF da D14 só confere o M5 de blocos "
            "rígidos; nada foi calculado."
        )
    else:
        mesh = mesh_cap(geometry, mesh_size)
        parameters |= {"mesh_size_mm": mesh.size, "mesh_nodes": len(mesh.nodes)}
        columns = {c.id: c for c in geometry.columns}
        factor = loads.gamma_n * (1.0 + ratio)
        for case in loads.cases:
            forces = column_nodal_forces(mesh, columns, list(case.column_loads), factor)
            result = solver.solve(mesh, forces, materials.fck, ccx, stiffness)
            field = post.StressField(mesh, result)
            fem = post.pile_reactions(mesh, result, stiffness)
            reactions += [PileReaction(pile_id=k, case_id=case.id, force=v) for k, v in fem.items()]
            # M1 com a mesma carga do MEF (D7 junto com os pilares) para validar o modelo.
            m1 = {r.pile_id: factor * r.force for r in rigid_cap_reactions(geometry, case)}
            model_geometry, _ = _model_inputs(geometry, case)
            model = santos_stucchi(
                model_geometry,
                rigid_cap_reactions(geometry, case, ratio * sum(x.n for x in case.column_loads)),
                strengths,
                loads.gamma_n,
                tie_height,
            )
            reaction_checks = (
                _fem_spring_checks(fem, m1) if stiffness else _fem_reaction_checks(fem, m1)
            )
            case_checks = [*reaction_checks, *_fem_tie_checks(geometry, model, field)]
            case_checks += _fem_node_checks(geometry, model, field, strengths, tie_height)
            checks += _tag(case.id, case_checks)
            warnings += [
                _fem_warning(case.id, c, bool(stiffness))
                for c in case_checks
                if c.status is not CheckStatus.OK
            ]
    return AnalysisResult(
        rigid=rigid,
        reactions=tuple(reactions),
        checks=tuple(checks),
        warnings=tuple(warnings),
        audit=AuditTrail(
            app_version=__version__,
            method=FEM_METHOD,
            assumptions=_fem_assumptions(bool(stiffness)),
            parameters=parameters,
            input_hash=_input_hash(geometry, materials, loads, options),
        ),
    )


def refresh_project(project: Project) -> tuple[Project, tuple[str, ...]]:
    """Descarta os resultados salvos que não valem para as entradas do projeto (ADR-004).

    Um resultado só vale se o hash das entradas e a versão do programa forem os da gravação.
    O de `analyze()` é recalculado; o do MEF é descartado sem rodar o MEF de novo.
    """
    current = _input_hash(project.geometry, project.materials, project.loads, project.detailing)
    updates: dict[str, AnalysisResult | None] = {}
    warnings: list[str] = []
    result = project.result
    if result is not None and (reason := _stale_reason(result, current)):
        updates["result"] = analyze(
            project.geometry, project.materials, project.loads, project.detailing
        )
        warnings.append(f"Resultado salvo {reason}; recalculado com as entradas do projeto.")
    fem = project.fem_result
    if fem is not None and (reason := _stale_reason(fem, current)):
        updates["fem_result"] = None
        warnings.append(f"Resultado do MEF salvo {reason}; descartado, rode o MEF de novo.")
    return project.model_copy(update=updates), tuple(warnings)


def strut_tie_layout(project: Project, case_id: str) -> StrutTieLayout | None:
    """Nós e barras do modelo M5 de um caso, para a visualização 3D (ADR-006).

    Refaz o mesmo modelo de `analyze()` (Santos/Stucchi, D13, D15; pilar fictício D10 com
    vários pilares). z a partir da face inferior: nó da estaca na altura do tirante (D8), nó
    superior de cada biela a y/2 do topo. Bloco flexível (D9) não tem treliça: devolve None.
    """
    geometry, loads = project.geometry, project.loads
    case = next((c for c in loads.cases if c.id == case_id), None)
    if case is None:
        raise ValueError(f"Caso de cálculo {case_id} não existe no projeto.")
    model_geometry, _ = _model_inputs(geometry, loads.cases[0])
    rigidity = rigidity_checks(geometry.cap, model_geometry.columns[0])
    if any(c.status is not CheckStatus.OK for c in rigidity):
        return None
    tie_height = geometry.cap.cover + project.detailing.bar_diameter / 2.0
    self_weight = (
        SELF_WEIGHT_RATIO * sum(load.n for load in case.column_loads)
        if loads.include_cap_self_weight
        else 0.0
    )
    reactions = rigid_cap_reactions(geometry, case, self_weight)
    model_geometry, _ = _model_inputs(geometry, case)
    model = santos_stucchi(
        model_geometry,
        reactions,
        strut_tie_strengths(project.materials),
        loads.gamma_n,
        tie_height,
    )
    pile_z = geometry.cap.pile_embedment + tie_height
    top_z = geometry.cap.h - model.y / 2.0
    nodes = [LayoutNode(id=f"estaca_{p.id}", x=p.x, y=p.y, z=pile_z) for p in geometry.piles]
    members: list[LayoutMember] = []
    for strut in model.struts:
        nodes.append(
            LayoutNode(id=f"topo_{strut.pile_id}", x=strut.origin_x, y=strut.origin_y, z=top_z)
        )
        members.append(
            LayoutMember(
                id=f"biela_{strut.pile_id}",
                kind=LayoutMemberKind.STRUT,
                start=f"topo_{strut.pile_id}",
                end=f"estaca_{strut.pile_id}",
                force_d=strut.force_d * math.hypot(strut.l_proj, model.z) / model.z,
            )
        )
    members += [
        LayoutMember(
            id=f"tirante_{t.pile_a}_{t.pile_b}",
            kind=LayoutMemberKind.TIE,
            start=f"estaca_{t.pile_a}",
            end=f"estaca_{t.pile_b}",
            force_d=t.force_d,
        )
        for t in model.ties
    ]
    return StrutTieLayout(case_id=case.id, nodes=tuple(nodes), members=tuple(members))


def _stale_reason(result: AnalysisResult, input_hash: str) -> str | None:
    if result.audit.input_hash != input_hash:
        return "não corresponde às entradas"
    if result.audit.app_version != __version__:
        return f"foi calculado pela versão {result.audit.app_version}"
    return None


def _fem_reaction_checks(fem: dict[str, float], m1: dict[str, float]) -> list[Check]:
    """Validade do modelo: reação do MEF a menos de 1 % da do M1 em cada estaca (D14)."""
    scale = max(abs(v) for v in m1.values())
    return [
        _fem_check(
            f"mef_reacao_{pid}",
            f"Reação da estaca {pid}: |MEF − M1| ≤ 1 % do M1",
            abs(fem[pid] - m1[pid]) / max(abs(m1[pid]), 1e-9 * scale),
            _FEM_REACTION_LIMIT,
            "-",
            _FEM_REF,
        )
        for pid in m1
    ]


def _fem_spring_checks(fem: dict[str, float], m1: dict[str, float]) -> list[Check]:
    """Com molas, a reação do MEF é comparação: alerta acima de 1,10 × M1 (D16)."""
    return [
        _fem_check(
            f"mef_reacao_{pid}",
            f"Reação da estaca {pid} com molas: MEF ≤ 1,10 × M1",
            fem[pid],
            m1[pid] + _FEM_SPRING_LIMIT * abs(m1[pid]),
            "N",
            _FEM_SPRING_REF,
        )
        for pid in m1
    ]


def _fem_warning(case_id: str, check: Check, springs: bool) -> str:
    if springs and check.id.startswith("mef_reacao_"):
        pid = check.id.removeprefix("mef_reacao_")
        return (
            f"Caso {case_id}: M1 subestima a reação da estaca {pid} ({check.demand / 1e3:.0f} kN "
            f"pelo MEF com molas, limite {check.capacity / 1e3:.0f} kN = 1,10 × M1; D16)."
        )
    return (
        f"Caso {case_id}: {check.description} não atendida pelo MEF "
        f"({check.demand:.4g} contra {check.capacity:.4g} {check.unit})."
    )


def _fem_assumptions(springs: bool) -> tuple[str, ...]:
    if not springs:
        return _FEM_ASSUMPTIONS
    first, _supports, *rest = _FEM_ASSUMPTIONS
    return (first, _FEM_SPRING_ASSUMPTION, *rest)


def _fem_tie_checks(
    geometry: GeometryInput, model: StrutTieModel, field: StressField
) -> list[Check]:
    """Tração do MEF em cada plano entre linhas de estacas ≤ 1,10 × tirantes do M5 (D14)."""
    from blococalc.fem.post import section_tension  # noqa: PLC0415

    cap = geometry.cap
    piles = {p.id: (p.x, p.y) for p in geometry.piles}
    cell = min(cap.lx, cap.ly, cap.h) / 50.0
    checks = []
    for axis, name, width in ((0, "x", cap.ly), (1, "y", cap.lx)):
        lines = sorted({round(xy[axis], 3) for xy in piles.values()})
        for a, b in itertools.pairwise(lines):
            plane = (a + b) / 2.0
            m5 = sum(
                t.force_d * abs((t.dir_x, t.dir_y)[axis])
                for t in model.ties
                if min(piles[t.pile_a][axis], piles[t.pile_b][axis])
                < plane
                < max(piles[t.pile_a][axis], piles[t.pile_b][axis])
            )
            checks.append(
                _fem_check(
                    f"mef_tracao_{name}_{plane:.0f}",
                    f"Tração no plano {name} = {plane:.0f} mm: MEF ≤ 1,10 × tirantes do M5",
                    section_tension(field, axis, plane, (width, cap.h), cell),
                    (1.0 + _FEM_TIE_LIMIT) * m5,
                    "N",
                    _FEM_REF,
                )
            )
    return checks


def _fem_node_checks(
    geometry: GeometryInput,
    model: StrutTieModel,
    field: StressField,
    strengths: StrutTieStrengths,
    tie_height: float,
) -> list[Check]:
    """Média de −σ3 nos nós: pilar × y do M5 contra fcd1, estaca × 2·d′ contra fcd3 (D14)."""
    from blococalc.fem.post import mean_compression  # noqa: PLC0415

    h = geometry.cap.h
    checks = [
        _fem_check(
            f"mef_no_pilar_{c.id}",
            f"Nó do pilar {c.id}: média de −σ3 no MEF ≤ fcd1",
            mean_compression(field, (c.x, c.y), (c.bx / 2, c.by / 2), (h - model.y, h)),
            strengths.fcd1,
            "MPa",
            _FEM_NODE_REF,
        )
        for c in geometry.columns
    ]
    checks += [
        _fem_check(
            f"mef_no_estaca_{p.id}",
            f"Nó da estaca {p.id}: média de −σ3 no MEF ≤ fcd3",
            mean_compression(
                field,
                (p.x, p.y),
                (p.size / 2, p.size / 2),
                (0.0, 2.0 * tie_height),
                circular=p.shape is PileShape.CIRCULAR,
            ),
            strengths.fcd3,
            "MPa",
            _FEM_NODE_REF,
        )
        for p in geometry.piles
    ]
    return checks


def _fem_check(  # noqa: PLR0913, PLR0917 - campos do Check
    check_id: str, description: str, demand: float, capacity: float, unit: str, ref: Reference
) -> Check:
    return Check(
        id=check_id,
        description=description,
        demand=demand,
        capacity=capacity,
        unit=unit,
        status=CheckStatus.OK if demand <= capacity else CheckStatus.WARNING,
        reference=ref,
    )


def _space_truss_comparison(
    geometry: GeometryInput,
    case: LoadCase,
    gamma_n: float,
    self_weight_ratio: float,
    model: StrutTieModel,
) -> tuple[list[Check], list[str]]:
    """Trações no fundo: treliça 3D dos pilares reais (M7) × pilar fictício (D10, D12).

    Se o pilar fictício dá menos tração que o M7 numa direção, a verificação fica como alerta.
    """
    try:
        truss = cap_truss(geometry, case, gamma_n, self_weight_ratio, (model.y / 2.0, model.d))
    except ValueError as error:
        return [], [
            f"Caso {case.id}: treliça 3D (M7) sem solução, confronto D10 não feito: {error}"
        ]
    checks, warnings = [], []
    for axis, m7, index in (("x", truss.tension_x, 0), ("y", truss.tension_y, 1)):
        fictitious = sum(t.force_d * abs((t.dir_x, t.dir_y)[index]) for t in model.ties)
        ok = m7 <= fictitious * (1.0 + _M7_TOLERANCE)
        checks.append(
            Check(
                id=f"m7_tracao_{axis}",
                description=f"Tração no fundo em {axis}: treliça 3D (M7) ≤ pilar fictício (D10)",
                demand=m7,
                capacity=fictitious,
                unit="N",
                status=CheckStatus.OK if ok else CheckStatus.WARNING,
                reference=_M7_REF,
            )
        )
        if not ok:
            excess = 100.0 * (m7 / fictitious - 1.0) if fictitious > 0.0 else math.inf
            warnings.append(
                f"Caso {case.id}: a treliça 3D dos pilares reais (M7) pede {excess:.0f} % mais "
                f"tração em {axis} que o pilar fictício (D10); revisar os tirantes nessa direção."
            )
    if truss.inclined_struts:
        warnings.append(
            f"Caso {case.id}: bielas da treliça 3D (M7) fora de 0,57 ≤ tg θ ≤ 2 "
            f"(NBR 6118:2023, 22.3.1): {', '.join(truss.inclined_struts)}."
        )
    if truss.crossing_struts:
        pairs = "; ".join(f"{a} × {b}" for a, b in truss.crossing_struts)
        warnings.append(
            f"Caso {case.id}: bielas da treliça 3D (M7) se cruzam fora dos nós: {pairs}."
        )
    return checks, warnings


def _interior_pile_warning(pile_ids: Sequence[str]) -> str:
    """D15: a reação das estacas internas pelo M1 subestima a real (docs/02-metodos.md §4.6)."""
    return (
        f"Estacas internas sob o pilar ({', '.join(pile_ids)}): reação pelo M1, com estacas de "
        "mesma rigidez; no MEF de Bavaresco (2016) a estaca central recebeu 39 % acima da média. "
        "O nó dessas estacas é verificado com 1,4 × R (D15); conferir também a capacidade "
        "geotécnica delas."
    )


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
    """SHA-256 das entradas sem os campos vazios e com a versão fixa do formato do hash.

    ADR-007: campos novos e opcionais (como a rigidez das estacas) e a troca da versão do
    contrato não invalidam os resultados salvos de entradas que não os usam.
    """
    digest = hashlib.sha256()
    for item in inputs:
        data = item.model_dump(mode="json", exclude_none=True)
        data["schema_version"] = _HASH_FORMAT
        digest.update(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return digest.hexdigest()
