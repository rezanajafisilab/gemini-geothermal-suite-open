"""Scalar GEMINI adaptation; physics remains in the shared array kernel."""

from .kernel import cooling_kernel


def scalar_output(result):
    """Convert a scalar kernel result to JSON-safe snapshots and diagnostics."""
    masks = result["masks"]
    output = {k: v.item() for k, v in result.items() if k != "masks"}
    for circuit, field in [
        ("chilled", "chilled_supply_temperature_c"),
        ("hot", "hot_return_temperature_c"),
        ("brine", "brine_outlet_temperature_c"),
        ("cw", "cw_return_temperature_c"),
    ]:
        if not output[circuit + "_outlet_defined"]:
            output[field] = None
    output["diagnostics"] = [k for k, v in masks.items() if v.item()]
    output["violations"] = [
        f'{k}: cooling shortfall {output["power_cool_unmet"]:.6g} W.'
        for k in output["diagnostics"]
        if k
        in (
            "COOLING_UNMET",
            "CHILLED_FLOW_LIMIT",
            "ELECTRIC_ENVELOPE",
            "ABS_ENVELOPE",
            "ABS_HOT_LIMIT",
            "SINK_CAPACITY",
            "WATER_LIMIT",
        )
    ]
    output["status"] = (
        "off"
        if output["power_cool"] + output["power_cool_unmet"] == 0
        else "limited" if output["violations"] else "screening"
    )
    output["validation_level"] = "screening_uncoupled"
    output["cop_boundary"] = "compressor_only"
    output["model_level"] = "constant_cop_screening"
    output["effective_treatment_assumed"] = True
    return output


def calculate_scalar(u, settings):
    """Evaluate explicit SI input dict; replace complete wrapper output each call."""
    output = scalar_output(
        cooling_kernel(
            u["request_w"],
            u["supply_c"],
            u["return_c"],
            u["chilled_flow_m3s"],
            u["dry_bulb_c"],
            u["wet_bulb_c"],
            settings,
            source=u.get("source"),
            availability=u.get("availability", 1.0),
        )
    )
    output["source_ids"] = list(settings.source_ids)
    return output
