"""Tools the agent calls: GEMINI's well solve with the team's fixes (``tools.gemini``).

The plant around the wells, the year and its costs are Dioscuri's plant model
(``dioscuri_plant``); ``gemini_agent.engine`` puts the two together. There is no stand-in
model: what GEMINI does not have (cooling, the daily dispatch, costs) is modelled there.
"""

PHYSICS = "gemini"
# Components the plant model does not model yet; a request for one is answered as such.
NOT_MODELLED = {
    "ATES": "seasonal aquifer storage is not in the challenge's plant model",
    "CHP": "a gas engine on the produced gas is not modelled yet (the boiler burns it)",
    "recovery heat pump": (
        "a heat pump between the cooling and heating networks is not modelled yet"
    ),
}

__all__ = ["NOT_MODELLED", "PHYSICS"]
