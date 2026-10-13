"""Cobrimento nominal (NBR 6118:2023, 7.4.7 e Tabela 7.2; NBR 6122:2019, 8.6.2)."""

from __future__ import annotations

from blococalc.schemas import AggressivenessClass, Cap, Check, CheckStatus, Reference

# Elementos estruturais em contato com o solo, Δc = 10 mm (Tabela 7.2) [mm].
_SOIL_CONTACT_COVER = {
    AggressivenessClass.I: 30.0,
    AggressivenessClass.II: 30.0,
    AggressivenessClass.III: 40.0,
    AggressivenessClass.IV: 50.0,
}
_REFERENCE = Reference(source="NBR 6118:2023", item="7.4.7 / Tab. 7.2")


def nominal_cover(aggressiveness: AggressivenessClass, bar_diameter: float) -> float:
    """cnom para elemento em contato com o solo, com cnom ≥ φ da barra (7.4.7.5 a) [mm]."""
    return max(_SOIL_CONTACT_COVER[aggressiveness], bar_diameter)


def cover_check(cap: Cap, aggressiveness: AggressivenessClass, bar_diameter: float) -> Check:
    required = nominal_cover(aggressiveness, bar_diameter)
    return Check(
        id="cobrimento",
        description=f"Cobrimento nominal ≥ cnom (CAA {aggressiveness.value}, contato com o solo)",
        demand=required,
        capacity=cap.cover,
        unit="mm",
        status=CheckStatus.OK if cap.cover >= required else CheckStatus.FAIL,
        reference=_REFERENCE,
    )
