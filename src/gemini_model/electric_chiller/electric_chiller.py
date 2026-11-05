"""GEMINI electric chiller wrapper; pure shared kernel, SI inputs/outputs."""

from gemini_model.cooling_common.config import CoolingSettings
from gemini_model.cooling_common.wrapper import calculate_scalar
from gemini_model.model_abstract import StaticModel


class ElectricChiller(StaticModel):
    """Constant compressor-only COP with declared condenser and auxiliaries."""

    def __init__(self):
        """Initialize an uninstalled screening component."""
        super().__init__()
        self.parameters = {"settings": CoolingSettings()}

    def calculate_output(self, u, x=None):
        """Replace output using SI inputs documented in cooling_common.kernel."""
        settings = self.parameters["settings"]
        if settings.option not in ("water", "air"):
            raise ValueError("ElectricChiller requires water or air option")
        self.output = calculate_scalar(u, settings)
