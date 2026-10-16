"""Contratos de dados entre módulos (schemas v4, ADR-002 a ADR-004; layout transitório, ADR-006).

Unidades internas fixas: N, mm, MPa. Conversões acontecem só nas bordas (UI e importação).
Estes modelos são o único formato que atravessa a fronteira entre subpacotes. Mudanças
incompatíveis exigem ADR e um novo número de versão (v1 -> v2), nunca alteração silenciosa.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION: Literal["4"] = "4"
_READABLE_VERSIONS = ("1", "2", "3", "4")


class _Contract(BaseModel):
    """Base dos contratos: imutável e sem campos desconhecidos."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class _Versioned(_Contract):
    """Contrato de topo. Lê v1 a v3: as versões novas só acrescentam campos e valores."""

    schema_version: Literal["4"] = SCHEMA_VERSION

    @field_validator("schema_version", mode="before")
    @classmethod
    def _upgrade(cls, value: object) -> object:
        return SCHEMA_VERSION if value in _READABLE_VERSIONS else value


# --------------------------------------------------------------------------------------
# Geometria
# --------------------------------------------------------------------------------------


class PileShape(StrEnum):
    CIRCULAR = "circular"
    SQUARE = "square"


class Pile(_Contract):
    """Estaca vertical (estacas inclinadas estão fora da v1)."""

    id: str = Field(min_length=1)
    x: float = Field(description="Coordenada do eixo da estaca [mm]")
    y: float = Field(description="Coordenada do eixo da estaca [mm]")
    size: float = Field(gt=0, description="Diâmetro (circular) ou lado (quadrada) [mm]")
    shape: PileShape = PileShape.CIRCULAR


class Column(_Contract):
    """Pilar retangular apoiado no bloco.

    Por decisão D4 (docs/02-metodos.md), os modelos de bielas usam `bx` na direção x e
    `by` na direção y; nunca o lado menor para as duas.
    """

    id: str = Field(min_length=1)
    x: float = Field(description="Coordenada do centro do pilar [mm]")
    y: float = Field(description="Coordenada do centro do pilar [mm]")
    bx: float = Field(gt=0, description="Dimensão do pilar na direção x [mm]")
    by: float = Field(gt=0, description="Dimensão do pilar na direção y [mm]")
    reinforcement_ratio: float = Field(
        default=0.02, ge=0, le=0.08, description="Taxa geométrica de armadura do pilar [-]"
    )


class Cap(_Contract):
    """Bloco retangular, com origem do sistema de coordenadas no seu centro em planta."""

    lx: float = Field(gt=0, description="Dimensão do bloco em x [mm]")
    ly: float = Field(gt=0, description="Dimensão do bloco em y [mm]")
    h: float = Field(gt=0, description="Altura total do bloco [mm]")
    pile_embedment: float = Field(
        default=100.0, ge=0, description="Embutimento da estaca no bloco [mm]"
    )
    cover: float = Field(default=50.0, gt=0, description="Cobrimento nominal [mm]")


class GeometryInput(_Versioned):
    cap: Cap
    piles: tuple[Pile, ...] = Field(min_length=1)
    columns: tuple[Column, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_consistency(self) -> GeometryInput:
        for group, items in (("estacas", self.piles), ("pilares", self.columns)):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Identificadores de {group} repetidos: {ids}")
        half_x, half_y = self.cap.lx / 2, self.cap.ly / 2
        for pile in self.piles:
            if abs(pile.x) > half_x or abs(pile.y) > half_y:
                raise ValueError(f"Estaca {pile.id} fora da projeção do bloco")
        if self.cap.pile_embedment >= self.cap.h:
            raise ValueError("Embutimento da estaca deve ser menor que a altura do bloco")
        return self


# --------------------------------------------------------------------------------------
# Materiais e ações
# --------------------------------------------------------------------------------------


class CombinationType(StrEnum):
    """Tipos de combinação última (NBR 6118:2023, Tabela 12.1)."""

    NORMAL = "normal"
    SPECIAL = "special"
    EXCEPTIONAL = "exceptional"


class MaterialsInput(_Versioned):
    fck: float = Field(gt=0, le=90, description="Resistência característica do concreto [MPa]")
    fyk: float = Field(default=500.0, gt=0, description="Resistência de escoamento do aço [MPa]")
    gamma_c: float = Field(default=1.4, ge=1.0, description="NBR 6118:2023, Tabela 12.1")
    gamma_s: float = Field(default=1.15, ge=1.0, description="NBR 6118:2023, Tabela 12.1")


class ColumnLoad(_Contract):
    """Esforços de cálculo no topo do bloco, na base de um pilar, já majorados por gamma_f.

    Convenção: N positivo é compressão; momentos em torno dos eixos globais x e y.
    """

    column_id: str = Field(min_length=1)
    n: float = Field(description="Força normal de cálculo [N]")
    mx: float = Field(default=0.0, description="Momento de cálculo em torno de x [N·mm]")
    my: float = Field(default=0.0, description="Momento de cálculo em torno de y [N·mm]")
    hx: float = Field(default=0.0, description="Força horizontal de cálculo em x [N]")
    hy: float = Field(default=0.0, description="Força horizontal de cálculo em y [N]")


class LoadCase(_Contract):
    id: str = Field(min_length=1)
    combination: CombinationType = CombinationType.NORMAL
    column_loads: tuple[ColumnLoad, ...] = Field(min_length=1)


class LoadsInput(_Versioned):
    cases: tuple[LoadCase, ...] = Field(min_length=1)
    gamma_n: float = Field(
        default=1.2,
        ge=1.0,
        description="Coeficiente adicional (NBR 6118:2023, 22.2; decisão D3). Default 1,2.",
    )
    include_cap_self_weight: bool = Field(
        default=True, description="NBR 6122:2019, 5.6: peso próprio do bloco"
    )


class AggressivenessClass(StrEnum):
    """Classe de agressividade ambiental (NBR 6118:2023, Tabela 6.1)."""

    I = "I"  # noqa: E741 - nome da classe na norma
    II = "II"
    III = "III"
    IV = "IV"


class DetailingInput(_Versioned):
    """Opções de detalhamento (ADR-002)."""

    bar_diameter: float = Field(default=16.0, gt=0, description="Diâmetro dos tirantes [mm]")
    aggressiveness_class: AggressivenessClass = AggressivenessClass.II
    hooked: bool = Field(
        default=True, description="Ganchos nas pontas dos tirantes (NBR 6118:2023, 22.7.4.1.1)"
    )


# --------------------------------------------------------------------------------------
# Resultado e trilha de auditoria
# --------------------------------------------------------------------------------------


class CheckStatus(StrEnum):
    OK = "ok"
    FAIL = "fail"
    WARNING = "warning"


class Reference(_Contract):
    """Origem rastreável de uma fórmula ou limite."""

    source: str = Field(min_length=1, description='Ex.: "NBR 6118:2023"')
    item: str = Field(min_length=1, description='Ex.: "22.3.2"')


class Check(_Contract):
    id: str = Field(min_length=1)
    description: str
    demand: float
    capacity: float
    unit: str
    status: CheckStatus
    reference: Reference


class PileReaction(_Contract):
    pile_id: str
    case_id: str
    force: float = Field(description="Reação de cálculo, positiva em compressão [N]")


class AuditTrail(_Contract):
    app_version: str
    method: str = Field(description='Ex.: "santos-stucchi-2013"')
    assumptions: tuple[str, ...] = ()
    parameters: dict[str, float | str | bool] = Field(default_factory=dict)
    input_hash: str = Field(description="SHA-256 das entradas serializadas")


class ReinforcementKind(StrEnum):
    TIE = "tie"
    DISTRIBUTION = "distribution"
    SUSPENSION = "suspension"
    LATERAL_TOP = "lateral_top"
    FLEXURE = "flexure"  # bloco flexível: malha inferior em toda a largura (ADR-003)


class Reinforcement(_Contract):
    """Armadura calculada (ADR-002). `area_required` é a área mínima, não a efetiva."""

    id: str = Field(min_length=1)
    kind: ReinforcementKind
    direction: tuple[float, float] = Field(
        description="Vetor unitário em planta; (0, 0) quando a direção não se aplica"
    )
    force_d: float = Field(ge=0, description="Força de cálculo [N]")
    area_required: float = Field(ge=0, description="Área de aço necessária [mm²]")
    bar_diameter: float = Field(gt=0, description="[mm]")
    reference: Reference


class AnalysisResult(_Versioned):
    rigid: bool
    reactions: tuple[PileReaction, ...]
    checks: tuple[Check, ...]
    reinforcement: tuple[Reinforcement, ...] = ()
    warnings: tuple[str, ...] = ()
    audit: AuditTrail
    disclaimer: str = (
        "Resultado de apoio ao projeto. Exige revisão por engenheiro habilitado antes de uso."
    )


# --------------------------------------------------------------------------------------
# Geometria do modelo de bielas e tirantes (ADR-006): transitória, fora do arquivo .bloco
# --------------------------------------------------------------------------------------


class LayoutMemberKind(StrEnum):
    STRUT = "strut"
    TIE = "tie"


class LayoutNode(_Contract):
    """Nó do modelo. z a partir da face inferior do bloco [mm]."""

    id: str = Field(min_length=1)
    x: float
    y: float
    z: float


class LayoutMember(_Contract):
    id: str = Field(min_length=1)
    kind: LayoutMemberKind
    start: str
    end: str
    force_d: float = Field(ge=0, description="Força de cálculo na barra [N]")


class StrutTieLayout(_Contract):
    """Nós e barras do modelo M5 de um caso, para desenho; recalculada a partir das entradas."""

    case_id: str
    nodes: tuple[LayoutNode, ...]
    members: tuple[LayoutMember, ...]


# --------------------------------------------------------------------------------------
# Projeto salvo (ADR-004)
# --------------------------------------------------------------------------------------


class Project(_Versioned):
    """Arquivo de projeto `.bloco`: entradas e cópias dos últimos resultados (ADR-004).

    Os resultados não são fonte de cálculo: só valem se o `audit.input_hash` bater com as
    entradas e o `audit.app_version` com o do programa (`analysis.refresh_project`).
    """

    name: str = Field(min_length=1, description="Nome do bloco ou da obra")
    notes: str = ""
    geometry: GeometryInput
    materials: MaterialsInput
    loads: LoadsInput
    detailing: DetailingInput = Field(default_factory=DetailingInput)
    result: AnalysisResult | None = None
    fem_result: AnalysisResult | None = None
