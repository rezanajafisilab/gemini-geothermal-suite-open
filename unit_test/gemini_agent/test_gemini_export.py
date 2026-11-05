"""A design's brine loop written as a GEMINI project file, read back by GEMINI's own loader."""

import importlib
import json
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # the server is optional for the model and simulator tests
    TestClient = None

from gemini_agent import Agent, gemini_export, gemini_runtime
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import FULL_BRIEF, fake_intake
from unit_test.gemini_agent.test_naming import designed
from unit_test.gemini_agent.test_server import through_confirm


class TestExport(unittest.TestCase):
    """The file GEMINI loads as it is: components, connections, and our notes it ignores."""

    def test_gemini_loads_and_runs_it(self):
        """``project_loader.load_project`` builds and runs it; what GEMINI lacks is listed."""
        _, s = designed()
        proj = gemini_export.project(s.chosen)
        self.assertIn("producer_well", proj["components"])
        self.assertIn("heat_exchanger", proj["components"])
        notes = proj["dioscuri"]
        self.assertEqual(notes["design"], s.chosen.alternative.code)
        self.assertEqual(len(notes["daily_flows"][0]["flow_m3h"]), 365)
        gemini_runtime.load("fixed")  # puts GEMINI's packages on the path
        loader = importlib.import_module("gemini_simulator.project_loader")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / gemini_export.filename(s.chosen)
            path.write_text(json.dumps(proj))
            solver = loader.load_project(path)
            solver.run()
            self.assertGreater(float(solver.get_output("heat_exchanger", "heat_duty")), 1e6)
        self.assertRegex(gemini_export.filename(s.chosen), r"^dioscuri-[\w.-]+\.gemini\.json$")


@unittest.skipIf(TestClient is None, "fastapi is not installed")
class TestExportRoute(unittest.TestCase):
    """GET /api/gemini.json downloads the file; an unknown design is a 404."""

    def test_download_and_unknown(self):
        """The chosen design by default, as an attachment; unknown ids are 404."""
        from gemini_agent.server import create_app

        client = TestClient(create_app(Agent(ScriptedLLM(fake_intake))))
        through_confirm(client, {"threadId": "gemini1", "message": FULL_BRIEF})
        r = client.get("/api/gemini.json", params={"threadId": "gemini1"})
        self.assertEqual(r.status_code, 200, r.text[:200])
        self.assertRegex(
            r.headers["content-disposition"],
            r'^attachment; filename="dioscuri-[\w.-]+\.gemini\.json"$',
        )
        self.assertIn("connections", r.json())
        missing = client.get("/api/gemini.json", params={"threadId": "gemini1", "id": "Z9 · no"})
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
