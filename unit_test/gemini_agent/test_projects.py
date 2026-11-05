"""Tests for projects: reading users' demand files, the registry, the engine and the server."""

import json
import tempfile
import unittest
from pathlib import Path

from gemini_agent import engine, projects
from gemini_agent.agent import Session

try:
    from fastapi.testclient import TestClient
except ImportError:  # the server is optional for the model and simulator tests
    TestClient = None

HEAT = (projects.CHALLENGE_DIR / projects.CHALLENGE_FILES[0]).read_bytes()
COOL = (projects.CHALLENGE_DIR / projects.CHALLENGE_FILES[1]).read_bytes()
RESERVOIR = {"depth_m": "2000", "temperature_c": "72"}


def daily(heat_csv: bytes):
    """Return the organisers' dates and MW from one of their files."""
    rows = [r.split(",") for r in heat_csv.decode().splitlines()[1:]]
    return [r[0] for r in rows], [float(r[1]) for r in rows]


class TestReadProfile(unittest.TestCase):
    """A year of demand is read from the formats people export."""

    def test_the_organisers_file(self):
        """Their file is read as it is: 365 days in MW, named by its header."""
        p = projects.read_profile("heat.csv", HEAT, "heat")
        self.assertEqual(len(p.mw), 365)
        self.assertAlmostEqual(p.annual_gwh, 111.67, places=2)
        self.assertEqual(p.column, "heating_demand_MWth")
        self.assertEqual(p.notes, [])
        self.assertEqual(p.dates[0], "2027-01-01")

    def test_semicolons_decimal_commas_and_kw(self):
        """A Dutch export (semicolons, decimal commas, kW) gives the same MW."""
        dates, mw = daily(HEAT)
        text = "datum;warmtevraag (kW)\n" + "\n".join(
            f"{d};{x * 1000:.1f}".replace(".", ",") for d, x in zip(dates, mw)
        )
        p = projects.read_profile("warmte.csv", text.encode(), "heat")
        self.assertAlmostEqual(p.annual_gwh, 111.67, places=2)
        self.assertIn("kW read from the header, turned to MW", p.notes)

    def test_hourly_kwh_is_averaged_to_days(self):
        """8,760 hourly kWh become 365 daily means in MW."""
        dates, mw = daily(HEAT)
        rows = [f"{d} {h:02d}:00,{x * 1000:.3f}" for d, x in zip(dates, mw) for h in range(24)]
        p = projects.read_profile(
            "hourly.csv", ("time,heat_kWh\n" + "\n".join(rows)).encode(), "heat"
        )
        self.assertEqual(len(p.mw), 365)
        self.assertAlmostEqual(p.mw[27], mw[27], places=3)
        self.assertEqual(p.dates[0], "2027-01-01")
        self.assertIn("8,760 hourly values averaged to 365 days", p.notes)

    def test_daily_mwh_is_a_mean_power(self):
        """A day's MWh over 24 h is the day's mean MW."""
        dates, mw = daily(HEAT)
        text = "date,heat_MWh\n" + "\n".join(f"{d},{x * 24}" for d, x in zip(dates, mw))
        p = projects.read_profile("e.csv", text.encode(), "heat")
        self.assertAlmostEqual(p.mw[0], mw[0], places=3)

    def test_one_file_with_both_columns(self):
        """A file with heat and cool columns gives each its own."""
        dates, heat = daily(HEAT)
        _, cool = daily(COOL)
        text = "date,heat_mw,cool_mw\n" + "\n".join(
            f"{d},{h},{c}" for d, h, c in zip(dates, heat, cool)
        )
        self.assertAlmostEqual(
            projects.read_profile("b.csv", text.encode(), "heat").annual_gwh, 111.67, 2
        )
        self.assertAlmostEqual(
            projects.read_profile("b.csv", text.encode(), "cool").annual_gwh, 23.74, 2
        )

    def test_what_is_refused_says_why(self):
        """Wrong lengths, leap years, negatives, text and the wrong profile are refused."""
        dates, mw = daily(HEAT)
        body = [f"{d},{x}" for d, x in zip(dates, mw)]
        cases = {
            "360 values": "date,heat_mw\n" + "\n".join(body[:360]),
            "leap year": "date,heat_mw\n" + "\n".join(body + ["2027-12-32,1"]),
            "row 3: demand can't be negative": "date,heat_mw\n2027-01-01,1\n2027-01-02,-2\n"
            + "\n".join(body[2:]),
            "row 2: n/a is not a number": "date,heat_mw\n2027-01-01,n/a\n" + "\n".join(body[1:]),
        }
        for words, text in cases.items():
            with self.subTest(words):
                with self.assertRaises(projects.ProjectError) as err:
                    projects.read_profile("x.csv", text.encode(), "heat")
                self.assertIn(words, str(err.exception))
        with self.assertRaises(projects.ProjectError) as err:
            projects.read_profile("heat.csv", HEAT, "cool")
        self.assertIn("looks like heating demand", str(err.exception))
        with self.assertRaises(projects.ProjectError):
            projects.read_profile("heat.xlsx", HEAT, "heat")

    def test_no_unit_and_values_too_large_for_mw_asks(self):
        """A kW column that names no unit is asked about, never read as a 30 GW district."""
        dates, mw = daily(HEAT)
        text = "date,heating_demand\n" + "\n".join(f"{d},{x * 1000:.0f}" for d, x in zip(dates, mw))
        with self.assertRaises(projects.UnitQuestion) as asked:
            projects.read_profile("kw.csv", text.encode(), "heat")
        q = asked.exception
        self.assertEqual((q.key, q.options), ("heat_unit", ["kW", "MW"]))
        self.assertIn("30,000", str(q))
        self.assertIn("30.0 MW", str(q))
        kw = projects.read_profile("kw.csv", text.encode(), "heat", "kW")
        self.assertAlmostEqual(kw.annual_gwh, 111.67, places=1)
        self.assertEqual(kw.notes, ["no unit in the header: kW as you said"])
        as_mw = projects.read_profile("kw.csv", text.encode(), "heat", "MW")
        self.assertAlmostEqual(as_mw.peak_mw, 30000.0)  # the user's answer stands
        # A unit in the header needs no question, and plausible MW none either.
        named = text.replace("heating_demand", "heating_demand_kW", 1)
        self.assertAlmostEqual(projects.read_profile("kw.csv", named.encode(), "heat").peak_mw, 30)
        self.assertEqual(projects.read_profile("h.csv", HEAT, "heat").notes, [])
        with self.assertRaises(projects.ProjectError):
            projects.read_profile("kw.csv", text.encode(), "heat", "litres")
        preview = projects.preview("kw.csv", text.encode(), "heat")
        self.assertEqual(preview["unit_question"]["key"], "heat_unit")
        self.assertAlmostEqual(preview["peak_mw"], 30.0)  # shown in the likelier unit
        self.assertIsNone(projects.preview("h.csv", HEAT, "heat")["unit_question"])


BUILT_IN = ["challenge", "trias-westland", "hal-leyweg"]


class TestRegistry(unittest.TestCase):
    """Projects are made, listed, read by the engine and removed."""

    def setUp(self):
        """Keep user projects in a folder of their own."""
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = projects.Projects(self.tmp.name)

    def tearDown(self):
        """Remove the folder."""
        self.tmp.cleanup()

    def test_the_challenge_comes_first(self):
        """The organisers' district is built in, with their totals and reservoir."""
        first = self.reg.list()[0]
        self.assertEqual(first.id, "challenge")
        self.assertTrue(first.builtin)
        self.assertEqual(first.totals["annual_heat_gwh"], 111.67)
        self.assertEqual(first.reservoir["temperature_c"], 87.0)
        self.assertEqual(self.reg.rules("challenge"), engine.dp.Rules())

    def test_make_read_and_remove(self):
        """A project keeps its uploads, gives its rules and data, and can be removed."""
        r = self.reg.create("Riccarton campus", ("heat.csv", HEAT), ("cool.csv", COOL), RESERVOIR)
        self.assertRegex(r.id, r"^riccarton-campus-[0-9a-f]{6}$")
        self.assertEqual([x.id for x in self.reg.list()], [*BUILT_IN, r.id])
        folder = Path(self.tmp.name) / r.id
        self.assertTrue((folder / "files" / "heat.csv").is_file())
        self.assertEqual(
            json.loads((folder / "project.json").read_text())["name"], "Riccarton campus"
        )
        rules = self.reg.rules(r.id)
        self.assertEqual(rules.reservoir_depth_m, 2000)
        self.assertAlmostEqual(rules.reservoir_temperature_c(), 72.0)
        self.assertAlmostEqual(rules.reservoir_pressure_bar, 202.1)  # the brine column
        data = self.reg.data(r.id)
        self.assertEqual(
            (data.id, data.reservoir_temp_c, data.heating.label()), (r.id, 72.0, "100/60 °C")
        )
        self.assertEqual(self.reg.file_path(r.id, "COOL.csv"), folder / "files" / "cool.csv")
        view = self.reg.view(r.id)
        self.assertEqual(len(view["weekly_mw"]["heat"]), 52)
        self.reg.delete(r.id)
        self.assertFalse(folder.exists())
        self.assertEqual([x.id for x in self.reg.list()], BUILT_IN)

    def test_cooling_from_the_heat_file_or_none(self):
        """Without a cooling upload, the heating file's cooling column, else no cooling."""
        dates, heat = daily(HEAT)
        _, cool = daily(COOL)
        both = "date,heat_mw,cool_mw\n" + "\n".join(
            f"{d},{h},{c}" for d, h, c in zip(dates, heat, cool)
        )
        r = self.reg.create("Both", ("both.csv", both.encode()), None, RESERVOIR)
        self.assertEqual(r.totals["annual_cool_gwh"], 23.74)
        self.assertTrue(r.has_cool_profile)
        r = self.reg.create("Heat only", ("heat.csv", HEAT), None, RESERVOIR)
        self.assertEqual(r.totals["annual_cool_gwh"], 0.0)
        self.assertFalse(self.reg.data(r.id).has_cool_profile)

    def test_bad_values_are_refused(self):
        """Missing or impossible values are refused with what to change; nothing is kept."""
        for values, words in (
            ({"temperature_c": "72"}, "reservoir depth (m) is needed"),
            ({"depth_m": "9000", "temperature_c": "72"}, "between 500 and 6000"),
            ({"depth_m": "2000", "temperature_c": "hot"}, "must be a number"),
            ({**RESERVOIR, "heat_return_c": "98"}, "at least 5 °C below"),
            (
                {**RESERVOIR, "cool_supply_c": "20", "cool_return_c": "15"},
                "cooling return must be warmer than its supply",
            ),
        ):
            with self.subTest(words):
                with self.assertRaises(projects.ProjectError) as err:
                    self.reg.create("X", ("heat.csv", HEAT), None, values)
                self.assertIn(words, str(err.exception))
        with self.assertRaises(projects.ProjectError):
            self.reg.create("  ", ("heat.csv", HEAT), None, RESERVOIR)
        self.assertEqual(list(Path(self.tmp.name).glob("*")), [])

    def test_a_unit_answer_makes_the_project(self):
        """A file whose unit was asked about is made once the unit is given, not before."""
        dates, mw = daily(HEAT)
        text = "date,heating_demand\n" + "\n".join(f"{d},{x * 1000:.0f}" for d, x in zip(dates, mw))
        with self.assertRaises(projects.UnitQuestion):
            self.reg.create("kW", ("kw.csv", text.encode()), ("cool.csv", COOL), RESERVOIR)
        self.assertEqual(list(Path(self.tmp.name).glob("*")), [])
        r = self.reg.create(
            "kW", ("kw.csv", text.encode()), ("cool.csv", COOL), RESERVOIR, {"heat": "kW"}
        )
        self.assertEqual((r.totals["annual_heat_gwh"], r.totals["peak_heat_mw"]), (111.67, 30.0))

    def test_ids_are_checked(self):
        """Built-in projects can't be removed; unknown or unsafe ids are not found."""
        for builtin in BUILT_IN:
            with self.assertRaises(projects.ProjectError):
                self.reg.delete(builtin)
        for bad in ("nope-123456", "../etc", ""):
            with self.assertRaises(KeyError):
                self.reg.get(bad)


class TestRealProjects(unittest.TestCase):
    """Trias Westland and HAL Leyweg are built in, with their published reservoirs and caps."""

    def setUp(self):
        """Use a registry in a folder of its own."""
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = projects.Projects(self.tmp.name)

    def tearDown(self):
        """Remove the folder."""
        self.tmp.cleanup()

    def test_their_reservoirs_caps_and_files(self):
        """Each has its own demand, reservoir, caps and brief; no cooling."""
        trias, hal = self.reg.get("trias-westland"), self.reg.get("hal-leyweg")
        self.assertTrue(trias.builtin and hal.builtin)
        self.assertEqual(trias.totals["annual_heat_gwh"], 277.78)
        self.assertEqual(hal.totals["annual_heat_gwh"], 48.0)
        self.assertFalse(trias.has_cool_profile or hal.has_cool_profile)
        self.assertAlmostEqual(trias.reservoir["temperature_c"], 87.1, places=1)
        rules = self.reg.rules("trias-westland")
        self.assertEqual(
            (rules.flow_max_m3h, rules.max_brine_cooling_k, rules.well_spacing_m),
            (525.0, 56.0, 1800.0),
        )
        rules = self.reg.rules("hal-leyweg")
        self.assertEqual((rules.flow_max_m3h, rules.max_brine_cooling_k), (165.0, 34.0))
        self.assertEqual(rules.gas_liquid_ratio, 1.0)
        # The network returns 5 K below the published injection, the exchanger's approach.
        self.assertEqual(rules.heat_return_c + 5.0, 45.0)
        brief = self.reg.file_path("hal-leyweg", "hal_leyweg_project_brief.md")
        self.assertIn("DGKE-WO / V-109", brief.read_text())
        self.assertEqual(self.reg.data("hal-leyweg").heating.label(), "70/40 °C")

    def test_a_design_for_each(self):
        """The search finds designs on both within their caps."""
        for pid, doublets in (("trias-westland", 2), ("hal-leyweg", 1)):
            with self.subTest(pid):
                saved = projects.registry()
                projects._REGISTRY = self.reg
                try:
                    out = engine.search(Session(project=self.reg.data(pid)).brief)
                finally:
                    projects._REGISTRY = saved
                y = out.chosen.year
                self.assertEqual(y.n_doublets, doublets)
                self.assertGreater(y.heat_coverage, 0.999)
                self.assertLessEqual(y.max_brine_cooling_k, self.reg.rules(pid).max_brine_cooling_k)
                self.assertEqual(y.cool_demand_gwh, 0.0)


class TestEngineOnAProject(unittest.TestCase):
    """The engine runs on a project's demand and reservoir."""

    def setUp(self):
        """Use a registry in a folder of its own."""
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = projects.registry()
        self.reg = projects.use(self.tmp.name)

    def tearDown(self):
        """Put the server's registry back."""
        projects._REGISTRY = self.saved
        self.tmp.cleanup()

    def test_search_on_a_district_without_cooling(self):
        """A district without cooling gets designs without chillers, from its reservoir down."""
        r = self.reg.create("Heat only", ("heat.csv", HEAT), None, RESERVOIR)
        session = Session(project=self.reg.data(r.id))
        self.assertEqual(session.brief.project_id, r.id)
        out = engine.search(session.brief)
        self.assertEqual(engine.summary(out)["depths"], [2000.0])  # its own aquifer only
        self.assertTrue(out.chosen.alternative.code.split("@")[0].split("-")[2] == "NC")
        self.assertEqual(out.chosen.year.cool_demand_gwh, 0.0)
        deeper = session.brief.model_copy(
            update={
                "doublet_depths_m": list(projects.assumed_depths(engine.rules_for(session.brief)))
            }
        )
        out = engine.search(deeper)
        self.assertEqual(engine.summary(out)["depths"], [2000.0, 2500.0, 3000.0])
        self.assertIn("Depths other than 2,000 m", " ".join(out.notes))
        self.assertEqual(engine.demand_summary(r.id)["source"], "heat.csv")

    def test_the_reply_speaks_of_the_project(self):
        """A user's district: its own year, its own networks, no cooling when it has none."""
        from gemini_agent import answer, reporter

        r = self.reg.create(
            "Heat only", ("heat.csv", HEAT), None, {**RESERVOIR, "heat_return_c": "55"}
        )
        out = engine.search(Session(project=self.reg.data(r.id)).brief)
        text = reporter.challenge_answer(out, reporter.Facts("Design the heating."))
        self.assertIn("every day of the year", text)
        self.assertIn("no cooling demand", text)
        self.assertIn("The project's network returns are 55 °C for heating", text)
        self.assertNotIn("not given", text)
        design = [answer.Block("A1", "design", "a design")]
        self.assertIn("every day of the year", answer.rules(design, own_project=True))
        self.assertNotIn("are not given", answer.rules(design, own_project=True))
        self.assertIn("are not given", answer.rules(design))
        self.assertIn(
            "the project's own",
            answer.brief_text(Session(project=self.reg.data(r.id)).brief, self.reg.data(r.id)),
        )

    def test_a_started_conversation_keeps_its_project(self):
        """Only a conversation that has not started can move to another project."""
        r = self.reg.create("Heat only", ("heat.csv", HEAT), None, RESERVOIR)
        session = Session()
        session.use_project(self.reg.data(r.id))
        self.assertEqual(session.brief.reservoir_depth_m, 2000)
        session.turns = 1
        with self.assertRaises(ValueError):
            session.use_project(self.reg.data("challenge"))


@unittest.skipIf(TestClient is None, "fastapi is not installed")
class TestServerProjects(unittest.TestCase):
    """The app lists, makes and removes projects, and a chat runs in its project."""

    def setUp(self):
        """Create the app with a scripted agent and a registry of its own."""
        from gemini_agent import Agent
        from gemini_agent.llm import ScriptedLLM
        from gemini_agent.server import create_app
        from unit_test.gemini_agent.test_agent import fake_intake

        self.tmp = tempfile.TemporaryDirectory()
        self.saved = projects.registry()
        projects.use(self.tmp.name)
        self.client = TestClient(create_app(Agent(ScriptedLLM(fake_intake))))

    def tearDown(self):
        """Put the server's registry back."""
        projects._REGISTRY = self.saved
        self.tmp.cleanup()

    def make(self, **form):
        """Post a project with the organisers' heating file."""
        return self.client.post(
            "/api/projects",
            data={"name": "Campus", **RESERVOIR, **form},
            files={"heat": ("heat.csv", HEAT, "text/csv")},
        )

    def test_list_make_and_remove(self):
        """A new project is listed after the challenge; it can be removed, the challenge not."""
        listed = self.client.get("/api/projects").json()["projects"]
        self.assertEqual([p["id"] for p in listed], BUILT_IN)
        self.assertEqual(len(listed[0]["weekly_mw"]["cool"]), 52)
        r = self.make()
        self.assertEqual(r.status_code, 201)
        made = r.json()["project"]
        self.assertEqual(made["files"], ["heat.csv"])
        self.assertEqual(made["reservoir"]["depth_m"], 2000)
        listed = self.client.get("/api/projects").json()["projects"]
        self.assertEqual([p["id"] for p in listed], [*BUILT_IN, made["id"]])
        self.assertEqual(self.client.delete(f"/api/projects/{made['id']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/projects/{made['id']}").status_code, 404)
        self.assertEqual(self.client.delete("/api/projects/challenge").status_code, 422)

    def test_profile_preview(self):
        """The form's preview reads a file as a project would, or says why it can't."""
        r = self.client.post(
            "/api/projects/profile",
            data={"kind": "heat"},
            files={"file": ("heat.csv", HEAT, "text/csv")},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["annual_gwh"], len(r.json()["weekly_mw"])), (111.67, 52))
        self.assertFalse(r.json()["cool_column"])
        bad = self.client.post(
            "/api/projects/profile",
            data={"kind": "cool"},
            files={"file": ("heat.csv", HEAT, "text/csv")},
        )
        self.assertEqual(bad.status_code, 422)
        self.assertIn("looks like heating demand", bad.json()["detail"])

    def test_the_unit_question_and_its_answer(self):
        """The preview asks for the unit; the project is made with it, refused without it."""
        dates, mw = daily(HEAT)
        text = "date,heating_demand\n" + "\n".join(f"{d},{x * 1000:.0f}" for d, x in zip(dates, mw))
        files = {"heat": ("kw.csv", text.encode(), "text/csv")}
        r = self.client.post(
            "/api/projects/profile", data={"kind": "heat"}, files={"file": files["heat"]}
        )
        self.assertEqual(r.json()["unit_question"]["options"], ["kW", "MW"])
        r = self.client.post(
            "/api/projects/profile",
            data={"kind": "heat", "unit": "kW"},
            files={"file": files["heat"]},
        )
        self.assertIsNone(r.json()["unit_question"])
        refused = self.client.post("/api/projects", data={"name": "kW", **RESERVOIR}, files=files)
        self.assertEqual(refused.status_code, 422)
        self.assertIn("Which unit is it?", refused.json()["detail"])
        made = self.client.post(
            "/api/projects", data={"name": "kW", "heat_unit": "kW", **RESERVOIR}, files=files
        )
        self.assertEqual(made.status_code, 201)
        self.assertEqual(made.json()["project"]["totals"]["peak_heat_mw"], 30.0)

    def test_bad_project_says_why(self):
        """A refused project comes back as 422 with the reason."""
        r = self.make(depth_m="")
        self.assertEqual(r.status_code, 422)
        self.assertIn("reservoir depth (m) is needed", r.json()["detail"])

    def test_a_chat_runs_in_its_project(self):
        """The first run puts the chat in its project, even when a tab made the session first."""
        pid = self.make().json()["project"]["id"]
        self.client.get("/api/workbench", params={"threadId": "p1"})  # the tabs look first
        r = self.client.post(
            "/api/run",
            json={
                "threadId": "p1",
                "message": "Design the heating for this district.",
                "projectId": pid,
            },
        )
        self.assertEqual(r.status_code, 200)
        state = self.client.get("/api/threads/p1").json()
        self.assertEqual(state["project"]["id"], pid)
        self.assertEqual(state["brief"]["project_id"], pid)
        view = self.client.get(
            "/api/files", params={"threadId": "p2", "name": "heat.csv", "projectId": pid}
        )
        self.assertEqual(view.status_code, 200)
        missing = self.client.post(
            "/api/run", json={"threadId": "p3", "message": "hi", "projectId": "nope-000000"}
        )
        self.assertEqual(missing.status_code, 404)

    def test_removing_a_project_removes_its_chats(self):
        """Its chats' sessions and traces go, saved before a restart too; other chats stay."""
        from gemini_agent import Agent
        from gemini_agent.llm import ScriptedLLM
        from gemini_agent.server import create_app
        from unit_test.gemini_agent.test_agent import fake_intake

        kept, traces = Path(self.tmp.name, "sessions"), Path(self.tmp.name, "traces")

        def app():
            agent = Agent(ScriptedLLM(fake_intake), session_dir=str(kept), trace_dir=str(traces))
            return TestClient(create_app(agent))

        first = app()
        pid = self.make().json()["project"]["id"]
        for thread, project in (("in-1", pid), ("in-2", pid), ("other", None)):
            body = {"threadId": thread, "message": "hi", "projectId": project}
            self.assertEqual(first.post("/api/run", json=body).status_code, 200)
        again = app()  # a restart: the chats are only on disk now
        again.get("/api/threads/in-2")  # one of them back in memory
        r = again.delete(f"/api/projects/{pid}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["threads"], ["in-1", "in-2"])
        self.assertEqual(sorted(p.name for p in kept.iterdir()), ["other.json"])
        self.assertEqual(sorted(p.name for p in traces.iterdir()), ["other.jsonl"])
        self.assertEqual(again.get("/api/threads/in-2").status_code, 404)
        self.assertEqual(again.get("/api/threads/other").status_code, 200)


if __name__ == "__main__":
    unittest.main()
