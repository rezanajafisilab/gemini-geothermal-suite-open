"""GEMINI absorption wrapper; three circuits and explicit source boundaries."""

from gemini_model.cooling_common.config import CoolingSettings
from gemini_model.cooling_common.wrapper import calculate_scalar
from gemini_model.model_abstract import StaticModel


class AbsorptionChiller(StaticModel):
    """Single-effect screening absorber plus the same electric backup kernel."""

    def __init__(self):
        """Initialize uninstalled absorption and backup capacities."""
        super().__init__()
        self.parameters = {"settings": CoolingSettings(option="absorption")}

    def calculate_output(self, u, x=None):
        """Replace output; source includes allocated heat, finite HX and returns."""
        settings = self.parameters["settings"]
        if settings.option != "absorption":
            raise ValueError("AbsorptionChiller requires absorption option")
        self.output = calculate_scalar(u, settings)
