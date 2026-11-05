"""Stateless tower around the same numerical budget used by cooling options."""

from gemini_model.cooling_common.config import CoolingSettings
from gemini_model.cooling_common.tower import tower_kernel
from gemini_model.model_abstract import StaticModel


class CoolingTower(StaticModel):
    """Screening tower at fixed flow/approach with constant auxiliary ratios."""

    def __init__(self):
        """Initialize uninstalled tower and explicit effective-treatment settings."""
        super().__init__()
        self.parameters = {"settings": CoolingSettings()}

    def calculate_output(self, u, x=None):
        """Replace the scalar SI snapshot, retaining unmet heat and water status."""
        s = self.parameters["settings"]
        raw = tower_kernel(
            u["core_rejection_w"], u["wet_bulb_c"], s, availability=u.get("availability", 1.0)
        )
        self.output = {k: v.item() for k, v in raw.items()}
        active = self.output["power_reject"] > 0
        if not active:
            self.output["cw_return_temperature_c"] = None
        self.output["diagnostics"] = []
        if u["core_rejection_w"] > 0 and self.output["cw_inlet_temperature_c"] <= 0:
            self.output["diagnostics"].append("SINK_FREEZE_RISK")
        if active and s.water.max_makeup_water_m3h is None:
            self.output["diagnostics"].append("WATER_SUPPLY_NOT_CHECKED")
        if active and s.water.max_blowdown_m3h is None:
            self.output["diagnostics"].append("DISCHARGE_NOT_CHECKED")
        unmet = self.output["power_reject_unmet"]
        self.output["violations"] = (
            [f"Tower rejection shortfall {unmet:.6g} W."] if unmet > 1 else []
        )
        self.output["status"] = "limited" if unmet > 1 else "screening" if active else "off"
        self.output["validation_level"] = "screening_uncoupled"
