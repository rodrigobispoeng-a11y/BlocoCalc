"""Memorial de cálculo em HTML simples (ADR-005).

Títulos, parágrafos, tabelas e desenhos em SVG embutido (ADR-008), para o `QTextDocument`
da tela imprimir em PDF. Unidades da tela: kN, kN·m, mm, MPa e cm². Recebe o projeto já
conferido por `analysis.refresh_project` e os modelos de bielas e tirantes de cada caso; não
recalcula nada.
"""

from __future__ import annotations

import base64
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from html import escape

from blococalc.report.drawings import (
    form_plan,
    form_section,
    model_plan,
    model_section,
    reinforcement_plan,
    reinforcement_section,
)
from blococalc.schemas import (
    AnalysisResult,
    BarPosition,
    Check,
    CheckStatus,
    Project,
    Reinforcement,
    StrutTieLayout,
)

KN = 1e3  # N
KNM = 1e6  # N·mm
_SHAPES = {"circular": "circular", "square": "quadrada"}
_COMBINATIONS = {"normal": "normal", "special": "especial", "exceptional": "excepcional"}
_STYLE = (
    "body{font-family:sans-serif;font-size:9pt}h1{font-size:15pt}h2{font-size:12pt}"
    "table{border-collapse:collapse}th,td{border:1px solid #888;padding:2px 4px}"
    "th{background:#ddd}.falha{background:#f6c6c6}.desenho td{border:none}"
)
_STEEL_DENSITY = 7850.0  # kg/m³, NBR 6118:2023, 8.3.3
STEEL_SCHEDULE_HEAD = ("Posição", "φ [mm]", "Quantidade", "C unitário [cm]", "C total [m]")
STEEL_SUMMARY_HEAD = ("φ [mm]", "C total [m]", "Massa [kg]")
_PLAN_WIDTH = 420  # largura dos desenhos na página (o PDF reduz a imagem de 2400 px)
_SECTION_WIDTH = 270


def calculation_report(
    project: Project,
    issued: date,
    layouts: Mapping[str, StrutTieLayout] | None = None,
    *,
    drawings: bool = True,
) -> str:
    """Memorial com entradas, método, resultados e trilha de auditoria (ADR-005, item 2).

    Com `drawings`, a seção 1 traz a forma e a seção 3 o modelo de bielas e tirantes de cada
    caso presente em `layouts` (ADR-008); blocos flexíveis não têm modelo.
    """
    result = project.result
    if result is None:
        raise ValueError("Calcule o bloco antes de gerar o memorial.")
    parts = [
        f"<html><head><meta charset='utf-8'><style>{_STYLE}</style></head><body>",
        f"<h1>Memorial de cálculo: {escape(project.name)}</h1>",
        _paragraph(f"Emitido em {issued:%d/%m/%Y} pelo BlocoCalc {result.audit.app_version}."),
        _paragraph(project.notes) if project.notes else "",
        f"<p><b>{escape(result.disclaimer)}</b></p>",
        *_inputs(project, drawings),
        "<h2>3. Método</h2>",
        _paragraph(
            f"Bloco {'rígido' if result.rigid else 'flexível'} pela NBR 6118:2023, 22.7.1. "
            f"Método: {result.audit.method}."
        ),
        _list(result.audit.assumptions),
        *(_model_drawings(project, result, layouts or {}) if drawings else ()),
        *_results(result, 4),
        *(_reinforcement_drawings(project, result) if drawings else ()),
    ]
    if project.fem_result is not None:
        parts += ["<h2>8. Conferência por MEF (D14)</h2>", *_results(project.fem_result, None)]
    parts += ["<h2>9. Trilha de auditoria</h2>", _audit("Análise", result)]
    if project.fem_result is not None:
        parts.append(_audit("MEF", project.fem_result))
    parts.append("</body></html>")
    return "\n".join(p for p in parts if p)


def _inputs(project: Project, drawings: bool) -> list[str]:
    g, m, loads, d = project.geometry, project.materials, project.loads, project.detailing
    cap = g.cap
    tie_height = tie_axis_height(project)
    # ADR-014: a coluna Nk só aparece quando algum pilar tem a carga característica.
    characteristic = any(c.nk is not None for case in loads.cases for c in case.column_loads)
    forms = [
        "<h3>Forma (cotas em cm)</h3>",
        _figure(form_plan(g), _PLAN_WIDTH, "Planta de forma"),
        _pair(
            (form_section(g, "x", tie_height), "Corte A-A (plano y = 0)"),
            (form_section(g, "y", tie_height), "Corte B-B (plano x = 0)"),
        ),
        _paragraph("Linha azul tracejada: eixo dos tirantes, a cobrimento + φ/2 da estaca (D8)."),
    ]
    return [
        "<h2>1. Entradas</h2>",
        _table(
            ("Bloco", "Lx [mm]", "Ly [mm]", "h [mm]", "Embutimento [mm]", "Cobrimento [mm]"),
            [("", _n(cap.lx), _n(cap.ly), _n(cap.h), _n(cap.pile_embedment), _n(cap.cover))],
        ),
        _table(
            ("fck [MPa]", "fyk [MPa]", "γc", "γs", "γn", "Peso próprio (D7)"),
            [
                (
                    _n(m.fck),
                    _n(m.fyk),
                    _n(m.gamma_c, 2),
                    _n(m.gamma_s, 2),
                    _n(loads.gamma_n, 2),
                    "sim" if loads.include_cap_self_weight else "não",
                )
            ],
        ),
        _table(
            ("Estaca", "x [mm]", "y [mm]", "φ ou lado [mm]", "Forma", "k [kN/mm]"),
            [
                (
                    p.id,
                    _n(p.x),
                    _n(p.y),
                    _n(p.size),
                    _SHAPES[p.shape.value],
                    "rígida" if p.axial_stiffness is None else _n(p.axial_stiffness / KN),
                )
                for p in g.piles
            ],
        ),
        _table(
            ("Pilar", "x [mm]", "y [mm]", "bx [mm]", "by [mm]", "ρ [%]"),
            [
                (c.id, _n(c.x), _n(c.y), _n(c.bx), _n(c.by), _n(100 * c.reinforcement_ratio, 2))
                for c in g.columns
            ],
        ),
        *(forms if drawings else ()),
        "<h2>2. Casos de cálculo e detalhamento</h2>",
        _table(
            (
                "Caso",
                "Combinação",
                "Pilar",
                "Nd [kN]",
                "Mxd [kN·m]",
                "Myd [kN·m]",
                "Hxd [kN]",
                "Hyd [kN]",
                *(("Nk [kN]",) if characteristic else ()),
            ),
            [
                (
                    case.id,
                    _COMBINATIONS[case.combination.value],
                    c.column_id,
                    _n(c.n / KN, 2),
                    _n(c.mx / KNM, 2),
                    _n(c.my / KNM, 2),
                    _n(c.hx / KN, 2),
                    _n(c.hy / KN, 2),
                    *((("—" if c.nk is None else _n(c.nk / KN, 2)),) if characteristic else ()),
                )
                for case in loads.cases
                for c in case.column_loads
            ],
        ),
        _paragraph(
            f"Tirantes φ {_n(d.bar_diameter)} mm, classe de agressividade "
            f"{d.aggressiveness_class.value}, {'com' if d.hooked else 'sem'} ganchos nas pontas, "
            f"agregado graúdo de {d.max_aggregate_size:g} mm (D18)."
        ),
    ]


def _results(result: AnalysisResult, first: int | None) -> list[str]:
    """Reações, verificações, armaduras e alertas; `first` numera as seções do memorial."""

    def title(offset: int, text: str) -> str:
        return f"<h2>{first + offset}. {text}</h2>" if first else f"<h3>{text}</h3>"

    failed = sum(c.status is CheckStatus.FAIL for c in result.checks)
    parts = [
        title(0, "Reações nas estacas"),
        _table(
            ("Estaca", "Caso", "Rd [kN]"),
            [(r.pile_id, r.case_id, _n(r.force / KN, 2)) for r in result.reactions],
        ),
        title(1, "Verificações"),
        _paragraph(
            f"{failed} verificação não atendida."
            if failed == 1
            else f"{failed} verificações não atendidas."
            if failed
            else "Todas as verificações atendidas."
        ),
        _checks(result.checks),
    ]
    if result.reinforcement:
        parts += [
            title(2, "Armaduras"),
            _table(
                (
                    "Armadura",
                    "Tipo",
                    "Fd [kN]",
                    "As,nec [cm²]",
                    "Barras",
                    "As,ef [cm²]",
                    "Referência",
                ),
                [
                    (
                        r.id,
                        r.kind.value,
                        _n(r.force_d / KN, 1),
                        _n(r.area_required / 100, 2),
                        bar_label(r),
                        "" if r.area_provided is None else _n(r.area_provided / 100, 2),
                        f"{r.reference.source}, {r.reference.item}",
                    )
                    for r in result.reinforcement
                ],
            ),
        ]
    parts += [title(3, "Alertas"), _list(result.warnings or ("Nenhum.",))]
    return parts


def _model_drawings(
    project: Project, result: AnalysisResult, layouts: Mapping[str, StrutTieLayout]
) -> list[str]:
    """Bielas e tirantes de cada caso em planta e em corte (ADR-008)."""
    g = project.geometry
    parts = []
    for case in project.loads.cases:
        layout = layouts.get(case.id)
        if layout is None:
            continue
        reactions = [r for r in result.reactions if r.case_id == case.id]
        parts += [
            # Cada caso numa página nova: o título não fica separado dos desenhos.
            f"<h3 style='page-break-before:always'>Modelo de bielas e tirantes: caso "
            f"{escape(case.id)}</h3>",
            _figure(model_plan(g, layout, reactions), _PLAN_WIDTH, "Planta do modelo"),
            _pair(
                (model_section(g, layout, "x"), "Projeção no plano xz"),
                (model_section(g, layout, "y"), "Projeção no plano yz"),
            ),
            _paragraph(
                "Bielas em vermelho tracejado e tirantes em azul, com as forças de cálculo; "
                "reações das estacas na planta, em kN. Nos cortes, a cota é o braço z entre o "
                "eixo dos tirantes e os nós superiores das bielas, em cm."
            ),
        ]
    return parts


def _reinforcement_drawings(project: Project, result: AnalysisResult) -> list[str]:
    """Armação em planta e em corte, tabela e resumo de aço (D19, ADR-010)."""
    positions = result.bar_positions
    if not positions:
        return []
    g = project.geometry
    return [
        "<h3 style='page-break-before:always'>Desenho de armação</h3>",
        _figure(reinforcement_plan(g, positions), _PLAN_WIDTH, "Armação inferior em planta"),
        _pair(
            (reinforcement_section(g, positions, "x"), "Corte na direção x"),
            (reinforcement_section(g, positions, "y"), "Corte na direção y"),
        ),
        _paragraph(
            "Camadas de baixo para cima: barras em x, barras em y e diagonais. Comprimentos pela "
            'linha de centro, com os ganchos, em cm; "var." indica comprimento variável, com o '
            "comprimento médio na tabela."
        ),
        "<h3>Tabela de aço</h3>",
        _table(STEEL_SCHEDULE_HEAD, steel_schedule(positions)),
        "<h3>Resumo de aço</h3>",
        _table(STEEL_SUMMARY_HEAD, steel_summary(positions)),
        _paragraph(
            f"Massa específica do aço de {_STEEL_DENSITY:g} kg/m³ (NBR 6118:2023, 8.3.3), sem "
            "perdas nem emendas."
        ),
    ]


def tie_axis_height(project: Project) -> float:
    """Altura do eixo do tirante sobre o topo da estaca (D8), com o φ adotado pela D18."""
    tie_height = project.geometry.cap.cover + project.detailing.bar_diameter / 2.0
    if project.result is not None:  # φ adotado pela D18, que pode ser maior que o digitado
        tie_height = float(project.result.audit.parameters.get("tie_height_mm", tie_height))
    return tie_height


def steel_schedule(positions: Sequence[BarPosition]) -> list[tuple[str, str, str, str, str]]:
    """Linhas da tabela de aço (D19), na ordem de `STEEL_SCHEDULE_HEAD`."""
    return [
        (
            p.id,
            _phi(p.bar_diameter),
            str(p.count),
            ("var. (média " if p.variable_length else "")
            + _n(p.length / 10, 0)
            + (")" if p.variable_length else ""),
            _n(p.count * p.length / 1e3, 2),
        )
        for p in positions
    ]


def steel_summary(positions: Sequence[BarPosition]) -> list[tuple[str, str, str]]:
    """Comprimento e massa por φ; a última linha é o total."""
    lengths: dict[float, float] = {}
    for p in positions:
        lengths[p.bar_diameter] = lengths.get(p.bar_diameter, 0.0) + p.count * p.length / 1e3
    rows, total = [], 0.0
    for phi in sorted(lengths):
        mass = lengths[phi] * math.pi * phi**2 / 4.0 * 1e-6 * _STEEL_DENSITY
        total += mass
        rows.append((_phi(phi), _n(lengths[phi], 2), _n(mass, 1)))
    rows.append(("Total", "", _n(total, 1)))
    return rows


def _phi(diameter: float) -> str:
    return f"{diameter:g}".replace(".", ",")


def _image(svg: str, width: int) -> str:
    """SVG embutido no HTML; a altura segue a proporção do desenho."""
    size = re.match(r'<svg [^>]*width="(\d+)" height="(\d+)"', svg)
    height = round(width * int(size[2]) / int(size[1])) if size else width
    data = base64.b64encode(svg.encode()).decode("ascii")
    return f"<img src='data:image/svg+xml;base64,{data}' width='{width}' height='{height}'>"


def _figure(svg: str, width: int, caption: str) -> str:
    return f"<p align='center'>{_image(svg, width)}<br>{escape(caption)}</p>"


def _pair(*figures: tuple[str, str]) -> str:
    cells = "".join(
        f"<td align='center'>{_image(svg, _SECTION_WIDTH)}<br>{escape(caption)}</td>"
        for svg, caption in figures
    )
    return f"<table class='desenho' align='center'><tr>{cells}</tr></table>"


def _checks(checks: Sequence[Check]) -> str:
    head = ("Verificação", "Solicitante", "Resistente", "Unidade", "Situação", "Referência")
    rows = []
    for c in checks:
        scale, unit = (KN, "kN") if c.unit == "N" else (1.0, c.unit)
        cells = (c.description, f"{c.demand / scale:.4g}", f"{c.capacity / scale:.4g}", unit,
                 c.status.value, f"{c.reference.source}, {c.reference.item}")  # fmt: skip
        mark = ' class="falha"' if c.status is CheckStatus.FAIL else ""
        rows.append(f"<tr{mark}>{''.join(f'<td>{escape(x)}</td>' for x in cells)}</tr>")
    return _table_html(head, rows)


def _audit(label: str, result: AnalysisResult) -> str:
    audit = result.audit
    rows = [("Versão", audit.app_version), ("Método", audit.method),
            ("Hash das entradas (SHA-256)", audit.input_hash)]  # fmt: skip
    rows += [(k, str(v)) for k, v in audit.parameters.items()]
    return f"<h3>{escape(label)}</h3>" + _table(("Item", "Valor"), rows)


def _table(head: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    body = ["<tr>" + "".join(f"<td>{escape(x)}</td>" for x in row) + "</tr>" for row in rows]
    return _table_html(head, body)


def _table_html(head: Sequence[str], rows: Sequence[str]) -> str:
    header = "<tr>" + "".join(f"<th>{escape(h)}</th>" for h in head) + "</tr>"
    return f"<table>{header}{''.join(rows)}</table>"


def _paragraph(text: str) -> str:
    return f"<p>{escape(text)}</p>"


def _list(items: Iterable[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"


def bar_label(item: Reinforcement) -> str:
    """Barras escolhidas (D18): "11 φ32" no tirante, "φ12,5 c/15" na malha, só "φ16" sem barras."""
    phi = f"φ{item.bar_diameter:g}".replace(".", ",")
    if item.bar_count is not None:
        return f"{item.bar_count} {phi}"
    if item.spacing is not None:
        return f"{phi} c/{item.spacing / 10:g}".replace(".", ",")
    return phi


def _n(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}"
