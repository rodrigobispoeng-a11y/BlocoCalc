"""Contratos de dados entre módulos (schemas v1).

Unidades internas fixas: N, mm, MPa. Conversões acontecem só nas bordas (UI e importação).
Estes modelos são o único formato que atravessa a fronteira entre subpacotes. Mudanças
incompatíveis exigem ADR e um novo número de versão (v1 -> v2), nunca alteração silenciosa.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION: Literal["1"] = "1"


class _Contract(BaseModel):
    """Base dos contratos: imutável e sem campos desconhecidos."""

    model_config = ConfigDict(frozen=True, extra="forbid")


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


class GeometryInput(_Contract):
    schema_version: Literal["1"] = SCHEMA_VERSION
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


class MaterialsInput(_Contract):
    schema_version: Literal["1"] = SCHEMA_VERSION
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


class LoadsInput(_Contract):
    schema_version: Literal["1"] = SCHEMA_VERSION
    cases: tuple[LoadCase, ...] = Field(min_length=1)
    gamma_n: float = Field(
        default=1.2,
        ge=1.0,
        description="Coeficiente adicional (NBR 6118:2023, 22.2; decisão D3). Default 1,2.",
    )
    include_cap_self_weight: bool = Field(
        default=True, description="NBR 6122:2019, 5.6: peso próprio do bloco"
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


class AnalysisResult(_Contract):
    schema_version: Literal["1"] = SCHEMA_VERSION
    rigid: bool
    reactions: tuple[PileReaction, ...]
    checks: tuple[Check, ...]
    warnings: tuple[str, ...] = ()
    audit: AuditTrail
    disclaimer: str = (
        "Resultado de apoio ao projeto. Exige revisão por engenheiro habilitado antes de uso."
    )
