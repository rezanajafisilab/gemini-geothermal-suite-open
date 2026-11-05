"""The permit and subsidy pack: the figures the applications ask for, as a PDF."""

import io
import unittest

try:
    from pypdf import PdfReader
except ImportError:  # the reader is only needed to look inside the PDF
    PdfReader = None
try:
    from fastapi.testclient import TestClient
except ImportError:  # the server is optional for the model and simulator tests
    TestClient = None

from gemini_agent import Agent, permit_pack
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import FULL_BRIEF, fake_intake
from unit_test.gemini_agent.test_naming import designed
from unit_test.gemini_agent.test_server import through_confirm


@unittest.skipIf(PdfReader is None, "pypdf is not installed")
class TestPack(unittest.TestCase):
    """Its four parts, with the subsurface limits, the SDE++ category and what is not in it."""

    def test_parts(self):
        """The mining figures, the SDE++ category from PBL, the environment, the gaps."""
        _, s = designed()
        text = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(permit_pack.build(s))).pages)
        for words in (
            "Mining permit",
            "SodM",
            "Diepe geothermie",
            "full-load hours",
            "Environment and grid",
            "seismic risk assessment",
        ):
            self.assertIn(words, text)
        self.assertRegex(permit_pack.filename(s.chosen), r"^dioscuri-[\w.-]+-permits\.pdf$")
        # The towers' water is the year model's: all the heat they reject (4 Nov).
        water = s.chosen.year.tower_water_m3 or {}
        if water.get("makeup"):
            from gemini_agent.reporter import num

            self.assertIn(f"{num(water['makeup'], 0)} m³ of make-up water", text)


@unittest.skipIf(TestClient is None, "fastapi is not installed")
class TestRoute(unittest.TestCase):
    """GET /api/permits.pdf downloads the pack; an unknown design is a 404."""

    def test_download_and_unknown(self):
        """The chosen design by default, as an attachment; unknown ids are 404."""
        from gemini_agent.server import create_app

        client = TestClient(create_app(Agent(ScriptedLLM(fake_intake))))
        through_confirm(client, {"threadId": "permits1", "message": FULL_BRIEF})
        r = client.get("/api/permits.pdf", params={"threadId": "permits1"})
        self.assertEqual(r.status_code, 200, r.text[:200])
        self.assertTrue(r.content.startswith(b"%PDF"))
        missing = client.get("/api/permits.pdf", params={"threadId": "permits1", "id": "Z9 · no"})
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
