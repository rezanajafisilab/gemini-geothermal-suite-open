"""Export reviewable metadata/contracts for Reza; no sensitivity execution."""

import ast
import json
import re
from pathlib import Path

from dioscuri_plant.cooling.parameters import parameter_metadata


def export(root):
    """Export actual additive bindings and unchanged START_HERE legacy inventory."""
    folder = root / "hackathon/docs/cooling"
    records = parameter_metadata()
    for binding, unit, base, values, source in [
        ("Rules.brine_cp_j_kg_k", "J/kg/K", 3990, [3990], "D009/A001"),
        ("Rules.operating_days", "days/year/doublet", 330, [330], "D004"),
        ("Rules.cool_supply_c", "C", 20, [20], "challenge"),
        ("Rules.cool_return_c", "C", 25, [23, 25, 28], "A002"),
        ("Rules.heat_return_c", "C", 60, [50, 60, 70], "A002"),
        ("Prices.discount_rate", "real fraction/year", 0.052, [0.03, 0.052, 0.08], "D015"),
    ]:
        records.append(
            dict(
                parameter_id=binding,
                binding_path=binding,
                binding_status=(
                    "legacy START_HERE or proposed Prices mapping; " "joint M5 owner must confirm"
                ),
                unit=unit,
                base=base,
                sensitivity=values,
                source_id=source,
                status="team_assumption" if source != "challenge" else "challenge",
                validity="fixed challenge constraints remain fixed",
                restrictions=(
                    "single Rules owner; at_most active days; " "all 365 demand days retained"
                ),
                outputs=["plant and cooling inventories"],
            )
        )
    app_parameters = []
    for record in records:
        values = record["sensitivity"]
        if isinstance(values, dict):
            values = values.get("water")
        if (
            not isinstance(values, list)
            or len(values) < 2
            or not all(type(v) in (int, float) for v in values)
        ):
            continue
        app_parameters.append(
            dict(
                key=record["binding_path"],
                label=record["binding_path"],
                unit=record["unit"],
                group="prices" if record["binding_path"].startswith("Prices.") else "equipment",
                low=min(values),
                high=max(values),
                kind="absolute",
                description=record["restrictions"],
            )
        )
    payload = {
        "schema": "cooling_parameter_handoff_v1",
        "existing_app_ref": "rn/challenge@4c77016f1dd584a1ba01ac9d24b75247c7890a7a",
        "existing_app_files": [
            "frontend/src/tabs/sensitivity/params.ts",
            "frontend/src/workbench/types.ts",
        ],
        "integration_status": (
            "metadata only; no app writes or runner; " "binding adapter remains joint M5"
        ),
        "parameters": records,
        "proposed_app_parameters": app_parameters,
        "app_schema_note": (
            "Matches inspected SensParam shape; new keys require Reza server binding. "
            "Categories/missing-price bases are metadata only. Default water COP "
            "bounds apply to water configurations; use air bounds for air cases."
        ),
    }
    (folder / "PARAMETER_HANDOFF.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    text = (root / "hackathon/docs/cooling/START_HERE.md").read_text(encoding="utf-8")
    fields = {}
    for block in re.findall(r"```python\n(.*?)```", text, flags=re.S):
        for node in ast.parse(block).body:
            if isinstance(node, ast.ClassDef):
                fields[node.name] = [n.target.id for n in node.body if isinstance(n, ast.AnnAssign)]
    fields["YearResult"] = [
        "heat_demand_gwh",
        "cool_demand_gwh",
        "heat_delivered_gwh",
        "cool_delivered_gwh",
        "heat_coverage",
        "cool_coverage",
        "heat_split_gwh",
        "cool_split_gwh",
        "peak_heat_mw",
        "peak_cool_mw",
        "daily_mw",
        "monthly_gwh",
        "doublets",
        "electricity_gwh",
        "purchased_gas_gwh",
        "produced_gas_burned_gwh",
        "produced_gas_flared_gwh",
        "co2_t",
        "violations",
        "source",
    ]
    fields["Economics"] = [
        "lcoh_eur_per_mwh",
        "lcoc_eur_per_mwh",
        "capex_meur",
        "lines",
        "capex_items",
        "co2_saving_vs_gas",
        "assumptions",
    ]
    contract = {
        "schema": "cooling_contract_handoff_v1",
        "legacy_fields": fields,
        "legacy_functions": [
            "simulate_year(plant, demand, doublet, rules=Rules())",
            "economics(plant, year, prices=Prices())",
            "stub_doublet(flow_m3h, depth_m)",
        ],
        "doublet_required_keys": ["wellhead_c", "esp_mw", "injector_pump_mw", "gas_nm3h"],
        "doublet_added_diagnostic": "well_loss_k already included in wellhead_c",
        "legacy_electricity_keys": ["hp", "recovery_hp", "chillers", "pumps"],
        "additive_electricity_key": "towers",
        "legacy_cold_keys": ["abs", "chill", "recovery_hp"],
        "additive_cold_key": "free",
        "status": (
            "field inventory frozen; actual annual caller/field compatibility tests "
            "deferred to joint M5"
        ),
    }
    (folder / "CONTRACT_HANDOFF.json").write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    print("Exported", len(records), "parameter records and legacy field inventory")


if __name__ == "__main__":
    export(Path(__file__).resolve().parents[2])
