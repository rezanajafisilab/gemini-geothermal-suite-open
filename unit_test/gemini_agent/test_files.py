"""Files the agent opens: the challenge data, the views the chat shows, the figures of the docs."""

import json
import tempfile
import unittest
from pathlib import Path

from gemini_agent import Agent, Session, files
from gemini_agent.agent import CHALLENGE_PROJECT
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import custom, fake_intake, run

ROOT = Path(__file__).resolve().parents[2]


class TestChallengeData(unittest.TestCase):
    """The challenge project's files are the organisers' and can be opened."""

    def test_every_project_file_exists(self):
        """Each file the project lists is on the server."""
        for name in CHALLENGE_PROJECT.files:
            self.assertIsNotNone(files.find(name, CHALLENGE_PROJECT, []), name)


class TestViews(unittest.TestCase):
    """What the chat shows of a file, and what the answerer reads."""

    def test_profile_table_stats_total_and_chart(self):
        """A daily MW profile gets its rows, its range and its energy over the year."""
        path, origin = files.find("GEMINI_Heating_Demand_Daily_2027.csv", CHALLENGE_PROJECT, [])
        v = files.read(path, "GEMINI_Heating_Demand_Daily_2027.csv", origin, "/x", "chart")
        self.assertEqual((v.kind, v.show, v.table["total_rows"]), ("table", "chart", 365))
        self.assertEqual(len(v.table["rows"]), files.MAX_ROWS)
        self.assertEqual([s["column"] for s in v.stats], ["heating_demand_MWth"])
        self.assertAlmostEqual(v.totals[0]["value"], 111.7, delta=0.5)  # shown to 3 digits
        self.assertEqual(v.totals[0]["unit"], "GWh")
        self.assertEqual(len(v.chart["x_values"]), 365)
        self.assertIn("synthetic", v.summary().lower())

    def test_semicolons_comma_decimals_and_long_files(self):
        """European CSVs are read, and long files are averaged down for the chart."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "loads.csv"
            rows = ["hour;Q (kW)"] + [f"{h};{h % 24},5" for h in range(1, 8761)]
            path.write_text("\n".join(rows), encoding="utf-8")
            v = files.read(path, "loads.csv", "attachment")
        self.assertEqual(v.table["columns"][1]["unit"], "kW")
        self.assertEqual(v.stats[0]["max"], 23.5)
        self.assertEqual(v.step_hours, 1.0)
        self.assertEqual(v.totals[0]["unit"], "MWh")
        self.assertLessEqual(len(v.chart["x_values"]), files.MAX_POINTS)

    def test_json_becomes_a_key_value_table(self):
        """Nested JSON is shown as keys and values, and as text."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "subsurface.json"
            path.write_text(json.dumps({"reservoir": {"depth_m": 2500, "temperature_c": 87}}))
            v = files.read(path, "subsurface.json", "attachment")
        self.assertEqual(v.kind, "json")
        self.assertIn(["reservoir.depth_m", 2500.0], v.table["rows"])
        self.assertIn('"temperature_c": 87', v.text)

    def test_image(self):
        """An image is shown with its size, and the answerer is told what it is."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plant.png"
            Image.new("RGB", (40, 20)).save(path)
            v = files.read(path, "plant.png", "attachment", "/img")
        self.assertEqual((v.kind, v.show), ("image", "image"))
        self.assertEqual(v.image, {"url": "/img", "width": 40, "height": 20})
        self.assertIn("40 by 20 pixels", v.summary())


class TestNames(unittest.TestCase):
    """Which files a message is about."""

    def test_by_name_by_words_and_by_image(self):
        """Exact names, what people call a file, and "this image" with one image attached."""
        p = CHALLENGE_PROJECT
        self.assertEqual(
            files.named_in("table of GEMINI_Heating_Demand_Daily_2027.csv", p, []),
            ["GEMINI_Heating_Demand_Daily_2027.csv"],
        )
        self.assertEqual(
            files.named_in("plot the cooling demand", p, []),
            ["GEMINI_Cooling_Demand_Daily_2027.csv"],
        )
        self.assertEqual(
            files.named_in("show the requirements", p, []),
            ["GEMINI_Hackathon_Challenge_Requirements.docx.pdf"],
        )
        self.assertEqual(files.named_in("is the heating demand high?", p, []), [])
        self.assertEqual(files.named_in("design a heating system", p, []), [])
        stated = "We have a heating demand of 40 GWh/yr. What doublet do we need?"
        self.assertEqual(files.named_in(stated, p, []), [])  # a design request (S03)
        up = [{"name": "site.jpg", "path": "/nowhere/site.jpg"}]
        self.assertEqual(files.named_in("what is in this picture?", p, up), ["site.jpg"])

    def test_views_asked_for(self):
        """Plot words ask for a chart; anything else for the table."""
        self.assertEqual(files.wanted_view("plot it", Path("a.csv")), "chart")
        self.assertEqual(files.wanted_view("give me the table", Path("a.csv")), "table")
        self.assertEqual(files.wanted_view("anything", Path("a.png")), "image")


class TestDocImages(unittest.TestCase):
    """Figures in GEMINI's documentation, for the source cards."""

    def test_section_figures(self):
        """The figures of one section, with links the server answers."""
        found = files.section_images(
            ROOT,
            "src/gemini_documentation/source/application_grafana.rst",
            "Time Series Viewer > Set up the InfluxDB data source",
        )
        self.assertTrue(found)
        self.assertTrue(found[0]["url"].startswith("/api/doc-image?path=src/gemini_doc"))

    def test_paths_outside_the_docs_are_refused(self):
        """Only images under the documentation folders are served."""
        self.assertIsNone(
            files.doc_image_path(ROOT, "src/gemini_documentation/../../pyproject.toml")
        )
        self.assertIsNone(
            files.doc_image_path(ROOT, "src/gemini_documentation/../../frontend/x.png")
        )
        self.assertIsNone(files.doc_image_path(ROOT, "/etc/passwd"))


class TestConversation(unittest.TestCase):
    """Asking for a file in the chat."""

    def setUp(self):
        """Create an agent on the scripted model."""
        self.agent = Agent(ScriptedLLM(fake_intake))

    def test_table_request_shows_the_file_and_cites_it(self):
        """The table comes from the file; the reply describes it and cites it as [^1]."""
        s = Session(thread_id="t1")
        ev = run(self.agent, s, "give me the table of GEMINI_Heating_Demand_Daily_2027.csv")
        view = custom(ev, "file")
        self.assertEqual(
            (view["name"], view["show"]), ("GEMINI_Heating_Demand_Daily_2027.csv", "table")
        )
        self.assertEqual(
            view["url"], "/api/files?threadId=t1&name=GEMINI_Heating_Demand_Daily_2027.csv"
        )
        self.assertNotIn("path", view)
        tool = next(e for e in ev if e["type"] == "TOOL_CALL_START")
        self.assertEqual(tool["toolCallName"], "read_file")
        self.assertIn("[^1]", s.last["answer"])
        sources = custom(ev, "sources")
        self.assertEqual(
            (sources[0]["kind"], sources[0]["file"]),
            ("data", "GEMINI_Heating_Demand_Daily_2027.csv"),
        )
        self.assertEqual(s.last["ungrounded"], [])

    def test_missing_file_is_said_not_invented(self):
        """A file the project lists but the server lacks is reported as missing."""
        s = Session()
        s.project.files.append("campus_heat.xlsx")
        ev = run(self.agent, s, "show me campus_heat.xlsx")
        self.assertIsNone(custom(ev, "file"))
        step = next(e for e in ev if e.get("stepName") == "file" and e["type"] == "STEP_FINISHED")
        self.assertIn("not on the server", json.dumps(step))

    def test_image_question_goes_to_a_model_that_can_see(self):
        """A question about an uploaded image is answered by a vision model, with the image."""
        from PIL import Image

        seen = []

        def model(purpose, messages):
            if purpose == "answer":
                seen.append(messages[-1].get("images"))
            return fake_intake(purpose, messages)

        fast = ScriptedLLM(model)
        fast.model = "qwen3:1.7b"
        deep = ScriptedLLM(model)
        deep.model = "qwen3.5:9b"
        agent = Agent(fast, reasoning_llm=deep)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plant.png"
            Image.new("RGB", (8, 8)).save(path)
            s = Session()
            agent.attach(s, path)
            ev = run(agent, s, "what is in this picture?")
        self.assertEqual(custom(ev, "file")["kind"], "image")
        self.assertEqual(custom(ev, "answer")["model"], "qwen3.5:9b")
        self.assertTrue(seen and seen[-1] and isinstance(seen[-1][0], bytes))


if __name__ == "__main__":
    unittest.main()
