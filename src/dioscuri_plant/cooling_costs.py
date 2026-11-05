"""Cooling-direct EUR-2025 costs for handoff; never replaces plant economics.

Inventories and source records are explicit inputs. No heat price or geothermal
allocation is applied here. Unknown values remain missing; partial subtotal is useful.
See specifications 05/11/12. Native tower bases remain MW/MWh rejected.
"""

from dataclasses import dataclass, field
from math import expm1, isfinite, log1p


def _positive(name, value, zero=True):
    if not isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValueError(f'{name} must be finite and {"nonnegative" if zero else "positive"}')


def capital_recovery_factor(lifetime_years, real_discount_rate=0.052):
    """Return real annuity factor; accepted team rate D015, life explicitly supplied."""
    _positive("lifetime", lifetime_years, zero=False)
    _positive("real discount rate", real_discount_rate)
    if real_discount_rate == 0:
        return 1 / lifetime_years
    return real_discount_rate / (-expm1(-lifetime_years * log1p(real_discount_rate)))


@dataclass(frozen=True)
class ConversionStep:
    """Reproducible source-to-EUR2025 multiplier with mandatory source/basis."""

    factor: float
    source_id: str
    description: str


@dataclass(frozen=True)
class CoolingCostRecord:
    """Linear per-module cost record; use modules to preserve fixed intercepts.

    All monetary fields are EUR-2025. None is missing, explicit zero is allowed.
    Scope must identify installation and tower inclusion; otherwise costs stay partial.
    Sourced nonlinear cost curves should be evaluated upstream into installed module
    records rather than extrapolated into this linear schema.
    """

    item_id: str
    technology: str
    source_id: str
    basis: str = "cold"
    status: str = "missing"
    capex_meur_per_mw: float | None = None
    capex_intercept_meur: float | None = None
    fixed_om_eur_per_mw_year: float | None = None
    variable_om_eur_per_mwh: float | None = None
    lifetime_years: float | None = None
    capacity_min_mw: float | None = None
    capacity_max_mw: float | None = None
    includes_tower: bool | None = None
    installed_scope: bool | None = None
    includes_water_service: bool = False
    includes_electricity: bool = False
    currency: str = "EUR"
    price_year: int = 2025
    original_value: float | None = None
    original_unit: str | None = None
    original_currency: str | None = None
    original_price_year: int | None = None
    conversion_chain: tuple[ConversionStep, ...] = ()
    scope_flags: tuple[tuple[str, str], ...] = ()
    reference_conditions: str = "not supplied"


@dataclass(frozen=True)
class InstalledCoolingItem:
    """One actual installed module and its annual native-basis operating energy."""

    record: CoolingCostRecord
    installed_mw: float
    delivered_mwh: float
    tower_group: str | None = None


@dataclass(frozen=True)
class CoolingWaterPrices:
    """Proposed additive Prices fields, same names as specification 11.

    This is a handoff view, not a second Prices class. Sources may be user_input.
    Combined supply/treatment must have treatment=None and one composite scope.
    """

    water_supply_eur_per_m3: float | None = None
    water_treatment_eur_per_m3: float | None = None
    blowdown_disposal_eur_per_m3: float | None = None
    water_fixed_eur_per_year: float | None = None
    combined_supply_treatment: bool = False
    source_id: str = "missing_user_water_prices"
    price_year: int = 2025


@dataclass
class CoolingDirectCost:
    """Known subtotal and missing data; never a full-plant LCOC or CO2 total."""

    known_subtotal_eur_per_year: float
    lines_eur_per_year: dict[str, float]
    capex_meur: float
    missing: list[str] = field(default_factory=list)
    direct_eur_per_mwh: float | None = None
    coverage: float | None = None
    scope: str = "partial_cooling_direct_excludes_shared_geothermal"


def convert_to_eur2025(original_value, steps):
    """Apply explicit factors only; never guess FX direction or index years."""
    _positive("original value", original_value)
    result = original_value
    for step in steps:
        _positive("conversion factor", step.factor, zero=False)
        if not step.source_id or not step.description:
            raise ValueError("Every conversion needs a source and direction/year description")
        result *= step.factor
    return result


def cooling_direct_cost(
    items,
    electricity_cost_eur,
    makeup_m3,
    blowdown_m3,
    water_prices,
    delivered_cold_mwh,
    requested_cold_mwh,
    wet_tower_installed,
    real_discount_rate=0.052,
):
    """Reconcile installed module costs and native-basis annual O&M once.

    electricity_cost_eur is already centrally priced inventory (None if missing).
    It is not recalculated from CHP or grid factors. Missing required inputs suppress
    the direct cost intensity, but all known lines and physical coverage remain.
    """
    for name, value in [
        ("makeup", makeup_m3),
        ("blowdown", blowdown_m3),
        ("delivered", delivered_cold_mwh),
        ("requested", requested_cold_mwh),
    ]:
        _positive(name, value)
    _positive("real discount rate", real_discount_rate)
    if delivered_cold_mwh > requested_cold_mwh + 1e-6 or blowdown_m3 > makeup_m3 + 1e-6:
        raise ValueError("Inconsistent service/water inventories")
    if not wet_tower_installed and (makeup_m3 > 0 or blowdown_m3 > 0):
        raise ValueError("Tower water cannot be charged without installed wet equipment")
    lines, missing, groups, ids = {}, [], {}, set()
    capex = 0.0
    if not items and delivered_cold_mwh > 0:
        missing.append("installed_cooling_equipment")
    for item in items:
        r = item.record
        _positive("installed capacity", item.installed_mw)
        _positive("operating energy", item.delivered_mwh)
        if item.installed_mw == 0 and item.delivered_mwh > 0:
            raise ValueError("Uninstalled item cannot deliver energy")
        if r.item_id in ids:
            raise ValueError("Module item IDs must be unique")
        ids.add(r.item_id)
        if r.currency != "EUR" or r.price_year != 2025:
            raise ValueError("Normalise monetary data to EUR-2025 before runtime costing")
        if r.status not in ("sourced", "user_input", "analyst_scenario", "missing"):
            raise ValueError("Unknown cost provenance status")
        if r.basis not in ("cold", "rejection"):
            raise ValueError("Cost basis must be cold or rejection")
        if r.technology == "tower" and r.basis != "rejection":
            raise ValueError("Standalone towers retain rejection capacity/energy basis")
        if item.installed_mw == 0:
            continue
        if not r.source_id:
            missing.append(r.item_id + ":source")
        if r.status == "missing":
            missing.append(r.item_id + ":provenance")
        for field_name in ("capacity_min_mw", "capacity_max_mw"):
            value = getattr(r, field_name)
            if value is not None:
                _positive(field_name, value)
        if (
            r.capacity_min_mw is not None
            and item.installed_mw < r.capacity_min_mw
            or r.capacity_max_mw is not None
            and item.installed_mw > r.capacity_max_mw
        ):
            missing.append(r.item_id + ":capacity_out_of_domain")
        if r.installed_scope is not True:
            missing.append(r.item_id + ":installed_scope")
        if r.capacity_min_mw is None or r.capacity_max_mw is None:
            missing.append(r.item_id + ":capacity_domain")
        if (r.original_currency is not None and r.original_currency != "EUR") or (
            r.original_price_year is not None and r.original_price_year != 2025
        ):
            if not r.conversion_chain:
                missing.append(r.item_id + ":conversion_chain")
            for step in r.conversion_chain:
                convert_to_eur2025(1.0, (step,))
        if any(value == "unpriced" for _, value in r.scope_flags):
            missing.append(r.item_id + ":unpriced_scope")
        if r.includes_tower is None:
            missing.append(r.item_id + ":tower_scope")
        if r.includes_electricity or r.includes_water_service:
            raise ValueError(
                "Reconcile bundled electricity/water O&M before applying central charges"
            )
        if r.includes_tower or r.technology == "tower":
            if item.tower_group is None:
                missing.append(r.item_id + ":tower_group")
            else:
                groups[item.tower_group] = groups.get(item.tower_group, 0) + 1
        for field_name in (
            "capex_meur_per_mw",
            "capex_intercept_meur",
            "fixed_om_eur_per_mw_year",
            "variable_om_eur_per_mwh",
            "lifetime_years",
        ):
            value = getattr(r, field_name)
            if value is None:
                missing.append(r.item_id + ":" + field_name)
            else:
                _positive(field_name, value, zero=field_name != "lifetime_years")
        if r.capex_meur_per_mw is not None and r.capex_intercept_meur is not None:
            investment = r.capex_meur_per_mw * item.installed_mw + r.capex_intercept_meur
            capex += investment
            if r.lifetime_years is not None:
                lines[r.item_id + ":capital"] = (
                    investment * 1e6 * capital_recovery_factor(r.lifetime_years, real_discount_rate)
                )
        if r.fixed_om_eur_per_mw_year is not None:
            lines[r.item_id + ":fixed_om"] = r.fixed_om_eur_per_mw_year * item.installed_mw
        if r.variable_om_eur_per_mwh is not None:
            lines[r.item_id + ":variable_om"] = r.variable_om_eur_per_mwh * item.delivered_mwh
    if any(count > 1 for count in groups.values()):
        raise ValueError("Tower purchased twice in a shared tower group")
    if wet_tower_installed and not groups:
        missing.append("installed_tower_cost")
    if electricity_cost_eur is None:
        missing.append("electricity_cost_eur")
    else:
        _positive("centrally priced cooling electricity", electricity_cost_eur)
        lines["electricity"] = electricity_cost_eur
    if wet_tower_installed:
        p = water_prices
        if not p.source_id or p.source_id == "missing_user_water_prices":
            missing.append("water_price_source")
        if p.price_year != 2025:
            raise ValueError("Water prices must be EUR-2025")
        if p.combined_supply_treatment and p.water_treatment_eur_per_m3 is not None:
            raise ValueError("Combined rate cannot also have a separate treatment charge")
        for name, volume in [
            ("water_supply_eur_per_m3", makeup_m3),
            ("water_treatment_eur_per_m3", makeup_m3),
            ("blowdown_disposal_eur_per_m3", blowdown_m3),
            ("water_fixed_eur_per_year", 1.0),
        ]:
            if name == "water_treatment_eur_per_m3" and p.combined_supply_treatment:
                continue
            value = getattr(p, name)
            if value is None:
                missing.append(name)
            else:
                _positive(name, value)
                lines[name] = value * volume
    subtotal = sum(lines.values())
    return CoolingDirectCost(
        subtotal,
        lines,
        capex,
        missing,
        subtotal / delivered_cold_mwh if delivered_cold_mwh > 0 and not missing else None,
        delivered_cold_mwh / requested_cold_mwh if requested_cold_mwh > 0 else None,
    )


def refrigerant_leakage_co2e_t(installed_mw, charge_kg_per_mw, annual_leak_fraction, gwp100):
    """Separate optional annual CO2e; does not change direct component CO2."""
    for name, value in [
        ("capacity", installed_mw),
        ("charge", charge_kg_per_mw),
        ("annual leakage", annual_leak_fraction),
        ("GWP100", gwp100),
    ]:
        _positive(name, value)
    if annual_leak_fraction > 1:
        raise ValueError("Annual leakage fraction must not exceed one")
    return installed_mw * charge_kg_per_mw * annual_leak_fraction * gwp100 / 1000
