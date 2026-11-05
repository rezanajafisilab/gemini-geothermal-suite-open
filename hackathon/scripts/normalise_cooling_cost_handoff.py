"""Prepare source-linked EUR-2025 reference data; never runs inside cooling evaluation."""

import hashlib
import json
from pathlib import Path

from dioscuri_plant.cooling_costs import ConversionStep, convert_to_eur2025


def normalise(root):
    """Use the supplied team cost-source conventions, retaining unresolved scopes/lives."""
    source = root / "hackathon/docs/challenge/cost_sources.md"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    expected = "599a1a880149e5fa279074082b81a294fd65c2a6ec42d09a4850a8900031c128"
    if digest != expected:
        raise ValueError("Review the changed cost-source snapshot before renormalising")
    path = root / "hackathon/docs/cooling/COOLING_COST_DATA.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["team_cost_source"] = dict(
        path=source.relative_to(root).as_posix(),
        sha256=digest,
        ref="local supplied untracked snapshot; integration branch still unavailable",
        preservation="read-only; left unchanged and not added to the task PR",
        factor_verification=(
            "supplied team convention; EIA/DOE tables separately read; "
            "Eurostat API not independently requeried"
        ),
    )
    data["conversion_policy"] = (
        "Source-linked EIA USD-2022 -> EUR-2022 by /1.0530, then EUR-2025 "
        "by x1.102; DOE assumed USD-2017 basis -> EUR-2017 by /1.1297 then x1.265. "
        "3.517 kW per refrigeration ton. No annual re-escalation; no USD runtime ledger."
    )
    for r in data["records"]:
        if r["item_id"] not in (
            "water_compression_unit_reference",
            "air_compression_unit_reference",
            "absorption_reference",
        ):
            continue
        doe = r["item_id"] == "absorption_reference"
        fx, uplift = (1.1297, 1.265) if doe else (1.0530, 1.102)
        year = 2017 if doe else 2022
        steps = [
            ConversionStep(
                1 / fx,
                "local_cost_sources_S25",
                f"USD-{year} to EUR-{year}: USD per EUR divisor {fx}",
            ),
            ConversionStep(
                uplift, "local_cost_sources_S25", f"Euro-area HICP EUR-{year} to EUR-2025 x{uplift}"
            ),
        ]
        r["conversion_chain"] = [
            dict(factor=s.factor, source_id=s.source_id, description=s.description) for s in steps
        ]
        r["status"] = "derived_reference_eur2025_partial_scope"
        r["conversion_source_sha256"] = digest
        if doe:
            r["original_price_year"] = 2017
            r["price_year_status"] = (
                "team source assumes publication-year price basis; "
                "original factsheet does not specify monetary year"
            )
            r["derived_eur2025"] = dict(
                capex_meur_per_mw=convert_to_eur2025(r["original_installed_usd_per_ton"], steps)
                / (3.517 * 1000),
                variable_om_eur_per_mwh=convert_to_eur2025(r["original_om_usd_per_ton_hour"], steps)
                * 1000
                / 3.517,
                fixed_om_eur_per_mw_year=None,
                economic_lifetime_years=None,
            )
            r["missing"] = [
                "confirmed monetary year",
                "economic life",
                "tower capital scope",
                "water/O&M overlap reconciliation",
            ]
        else:
            r["derived_eur2025"] = {
                point: dict(
                    capex_meur_per_mw=convert_to_eur2025(value, steps) / (3.517 * 1000),
                    fixed_om_eur_per_mw_year=convert_to_eur2025(
                        r["original_fixed_maintenance_usd_per_ton_year"][point], steps
                    )
                    * 1000
                    / 3.517,
                )
                for point, value in r["original_installed_usd_per_ton"].items()
            }
            r["normalisation_note"] = (
                "Point references only; no unpriced site scope, zero variable O&M "
                "or economic life is inferred."
            )
    tower = next(r for r in data["records"] if r["item_id"] == "tower_alone")
    tower["available_native_reference"] = dict(
        source_id="local_cost_sources_S15_secondary_transcription",
        original_currency="USD",
        original_price_year=2010,
        formula="170000 + 1500 * circulation_L_s**0.9",
        domain_circulation_l_s=[100, 10000],
        scope="field assembly, tower and pumps; not a comparable site-installed quote",
        cepci_2010=550.8,
        cepci_2024=800.0,
        usd_per_eur_2024=1.0824,
        derived_2010usd_to_2024eur_factor=800 / 550.8 / 1.0824,
        final_eur2025_value=None,
        missing=(
            "2024-to-2025 basis, installed scope/O&M/economic life; "
            "do not relabel EUR-2024 as EUR-2025"
        ),
    )
    data["source_reconciliation"] = [
        (
            "Team summary S12 says 540-590 USD/RT typical; primary 2022 typical rows are "
            "560 (400 RT) and 590 (600 RT). Preserve primary points; flag mixed-column lower end."
        ),
        (
            "Team says water chiller capital excludes tower; primary performance note excludes "
            "tower energy. Investment inclusion still requires scope confirmation."
        ),
        (
            "Team high chilled-water COP estimate extrapolates 3 K past experimental domain; "
            "no performance defaults/maps were changed."
        ),
        "Towler/Sinnott conversion in source ends in EUR-2024; EUR-2025 tower price stays missing.",
    ]
    data["plant_factor_handoff"].update(
        grid_factor_year=2024,
        grid_factor_scope=(
            "CBS integral total electricity production, Table 1; "
            "published 5 December 2025; CO2 only"
        ),
        gas_factor_source=(
            "IPCC 2006 Vol 2 Ch 2 Table 2.2, 56100 kg CO2/TJ NCV; " "rounded team 0.202 t/MWh LHV"
        ),
        source="local supplied cost_sources S20/S21; plant owns application once",
    )
    data["rate_source"] = (
        "local supplied cost_sources S3, PBL SDE++ 2026 Table 6.3 p66; "
        "accepted geothermal real rate 5.2%"
    )
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Normalised reference records; installed package/tower/O&M/lifetime gaps remain explicit")
    print(
        json.dumps(
            {r["item_id"]: r["derived_eur2025"] for r in data["records"] if "derived_eur2025" in r},
            indent=2,
        )
    )


if __name__ == "__main__":
    normalise(Path(__file__).resolve().parents[2])
