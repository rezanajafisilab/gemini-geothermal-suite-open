"""Metadata for the existing Sensitivity tab; no runner, tab or random sampler."""

from dataclasses import fields, is_dataclass

from gemini_model.cooling_common.config import CoolingSettings

# The water prices ``dioscuri_plant.economics.Prices`` has (4 Nov); the others stay missing.
PRICED = ("water_supply_eur_per_m3", "blowdown_disposal_eur_per_m3")


def parameter_metadata(settings=None):
    """Return actual additive bindings, units, defaults, domains and source status.

    Bounds are physical/formal or explicitly exploratory, not fitted distributions.
    Missing tariffs/capacities need user/source values. Celsius envelopes themselves
    require supplier confirmation; changing them does not calibrate constant COP.
    """
    s = settings if settings is not None else CoolingSettings()
    records = []

    def walk(value, path):
        for f in fields(value):
            v = getattr(value, f.name)
            binding = path + "." + f.name
            if is_dataclass(v):
                walk(v, binding)
                continue
            if f.name == "source_ids":
                continue
            unit, validity, sensitivity = "1", "explicit scenario", None
            if f.name == "water_cp_j_kg_k":
                unit, validity = "J/kg/K", ">0; secondary water, independent of brine Rules cp"
            elif f.name.endswith("_w"):
                unit, validity = "W", ">=0; installed capacity, supplier domain required"
            elif f.name.endswith("_w_k"):
                unit, validity = "W/K", ">=0; finite HX conductance"
            elif f.name.endswith("_c"):
                unit, validity = "C", "> -273.15; enforce declared paired temperature envelope"
            elif f.name.endswith("_k"):
                unit, validity = "K", ">=0"
            elif f.name.endswith("_m3s"):
                unit, validity = "m3/s", ">=0; actual supplied circuit flow"
            elif f.name.endswith("_m3h"):
                unit, validity = "m3/h", "None unchecked; finite >=0; zero means unavailable"
            elif f.name == "density_kg_m3":
                unit, validity = "kg/m3", ">0; secondary water only"
            elif f.name == "latent_heat_j_kg":
                unit, validity = "J/kg", ">0"
            elif "ratio" in f.name:
                unit, validity = (
                    "W/W named duty",
                    ">=0; scope and heat destination must be retained",
                )
            elif f.name in ("latent_fraction", "pump_heat_to_water", "chilled_pump_heat_to_water"):
                validity = "[0,1]; heat fractions, not efficiency"
            if f.name == "cycles":
                validity, sensitivity = ">1; effective treatment assumed", [3, 5, 6]
            if f.name == "cop":
                validity, sensitivity = ">0 compressor-only within declared envelope", {
                    "water": [4, 8],
                    "air": [3, 6],
                }
            if f.name == "cop_th":
                validity, sensitivity = "(0,1]; single-effect envelope", [0.55, 0.70, 0.75]
            if f.name in ("approach_k", "hx_approach_k"):
                sensitivity = [2, 3, 5] if f.name == "approach_k" else [3, 5, 8]
            if f.name == "option":
                validity, sensitivity = "supported categories", ["water", "air", "absorption"]
            if f.name == "condenser":
                validity, sensitivity = "must match nonhybrid option", ["water", "air"]
            if f.name == "cop_boundary":
                validity, sensitivity = (
                    "package COP requires reconciliation; currently unsupported",
                    ["compressor_only"],
                )
            if f.name == "free_cooling_enabled":
                validity, sensitivity = "False only until optional M3 is implemented", [False]
            source = (
                "A013"
                if ".water." in binding
                else "A007" if ("ratio" in f.name or "heat_to_water" in f.name) else "D018"
            )
            if f.name in ("cop", "cop_th"):
                source = "A006"
            if f.name == "hx_approach_k":
                source = "A003"
            records.append(
                dict(
                    parameter_id=binding,
                    binding_path=binding,
                    unit=unit,
                    base=v,
                    source_id=source,
                    status="analyst_scenario",
                    validity=validity,
                    sensitivity=sensitivity,
                    bound_kind="exploratory",
                    applies_to="all; tower/water only when wet equipment operates",
                    restrictions=(
                        "fixed challenge supply and caps cannot be relaxed; "
                        "supplier envelopes unvalidated"
                    ),
                    outputs=[
                        "cooling",
                        "electricity",
                        "source heat",
                        "rejection",
                        "water",
                        "diagnostics",
                    ],
                )
            )

    walk(s, "CoolingSettings")
    from dioscuri_plant.economics import SOURCES, Prices

    for name in (
        "water_supply_eur_per_m3",
        "water_treatment_eur_per_m3",
        "blowdown_disposal_eur_per_m3",
        "water_fixed_eur_per_year",
    ):
        records.append(
            dict(
                parameter_id="Prices." + name,
                binding_path="Prices." + name,
                unit="EUR-2025/year" if name.endswith("_year") else "EUR-2025/m3",
                base=getattr(Prices(), name) if name in PRICED else None,
                source_id=SOURCES[name] if name in PRICED else "user_input_required",
                status=(
                    "sourced" if name == PRICED[0] else "assumed" if name in PRICED else "missing"
                ),
                validity="None missing; explicit >=0 allowed",
                sensitivity="0.5/1/2 x sourced/user base",
                bound_kind="exploratory",
                applies_to="installed wet tower",
                restrictions="combined water tariffs and tower O&M scopes cannot overlap",
                outputs=["cooling direct cost"],
            )
        )
    return records
