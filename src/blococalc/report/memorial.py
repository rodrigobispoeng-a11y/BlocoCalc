"""Memorial de cálculo em HTML simples (ADR-005).

Só títulos, parágrafos e tabelas, para o `QTextDocument` da tela imprimir em PDF. Unidades
da tela: kN, kN·m, mm, MPa e cm². Recebe o projeto já conferido por
`analysis.refresh_project`; não recalcula nada.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from html import escape

from blococalc.schemas import AnalysisResult, Check, CheckStatus, Project

KN = 1e3  # N
KNM = 1e6  # N·mm
_SHAPES = {"circular": "circular", "square": "quadrada"}
_COMBINATIONS = {"normal": "normal", "special": "especial", "exceptional": "excepcional"}
_STYLE = (
    "body{font-family:sans-serif;font-size:9pt}h1{font-size:15pt}h2{font-size:12pt}"
    "table{border-collapse:collapse}th,td{border:1px solid #888;padding:2px 4px}"
    "th{background:#ddd}.falha{background:#f6c6c6}"
)


def calculation_report(project: Project, issued: date) -> str:
    """Memorial com entradas, método, resultados e trilha de auditoria (ADR-005, item 2)."""
    result = project.result
    if result is None:
        raise ValueError("Calcule o bloco antes de gerar o memorial.")
    parts = [
        f"<html><head><meta charset='utf-8'><style>{_STYLE}</style></head><body>",
        f"<h1>Memorial de cálculo: {escape(project.name)}</h1>",
        _paragraph(f"Emitido em {issued:%d/%m/%Y} pelo BlocoCalc {result.audit.app_version}."),
        _paragraph(project.notes) if project.notes else "",
        f"<p><b>{escape(result.disclaimer)}</b></p>",
        *_inputs(project),
        "<h2>3. Método</h2>",
        _paragraph(
            f"Bloco {'rígido' if result.rigid else 'flexível'} pela NBR 6118:2023, 22.7.1. "
            f"Método: {result.audit.method}."
        ),
        _list(result.audit.assumptions),
        *_results(result, 4),
    ]
    if project.fem_result is not None:
        parts += ["<h2>8. Conferência por MEF (D14)</h2>", *_results(project.fem_result, None)]
    parts += ["<h2>9. Trilha de auditoria</h2>", _audit("Análise", result)]
    if project.fem_result is not None:
        parts.append(_audit("MEF", project.fem_result))
    parts.append("</body></html>")
    return "\n".join(p for p in parts if p)


def _inputs(project: Project) -> list[str]:
    g, m, loads, d = project.geometry, project.materials, project.loads, project.detailing
    cap = g.cap
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
            ("Estaca", "x [mm]", "y [mm]", "φ ou lado [mm]", "Forma"),
            [(p.id, _n(p.x), _n(p.y), _n(p.size), _SHAPES[p.shape.value]) for p in g.piles],
        ),
        _table(
            ("Pilar", "x [mm]", "y [mm]", "bx [mm]", "by [mm]", "ρ [%]"),
            [
                (c.id, _n(c.x), _n(c.y), _n(c.bx), _n(c.by), _n(100 * c.reinforcement_ratio, 2))
                for c in g.columns
            ],
        ),
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
                )
                for case in loads.cases
                for c in case.column_loads
            ],
        ),
        _paragraph(
            f"Tirantes φ {_n(d.bar_diameter)} mm, classe de agressividade "
            f"{d.aggressiveness_class.value}, {'com' if d.hooked else 'sem'} ganchos nas pontas."
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
                ("Armadura", "Tipo", "Fd [kN]", "As,nec [cm²]", "φ [mm]", "Referência"),
                [
                    (
                        r.id,
                        r.kind.value,
                        _n(r.force_d / KN, 1),
                        _n(r.area_required / 100, 2),
                        _n(r.bar_diameter),
                        f"{r.reference.source}, {r.reference.item}",
                    )
                    for r in result.reinforcement
                ],
            ),
        ]
    parts += [title(3, "Alertas"), _list(result.warnings or ("Nenhum.",))]
    return parts


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


def _n(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}"
