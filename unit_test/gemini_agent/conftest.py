"""The agent's behaviour is tested on the toy model, whose numbers are fixed (the canvas).

GEMINI's physics is tested on its own in ``test_gemini_tools.py``, which calls
``gemini_agent.tools.gemini`` directly, so a GEMINI release cannot break the agent tests.
"""

import os

os.environ.setdefault("DIOSCURI_PHYSICS", "toy")
# The design-space sweep (5,000 designs a search) is off, so the searches stay as the tests pin
# them; ``test_sweep`` turns it on.
os.environ.setdefault("DIOSCURI_SWEEP", "0")
