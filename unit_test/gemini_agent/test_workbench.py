"""The tabs' endpoints: designs, assumptions, user designs, GEMINI projects, sensitivity."""

import tempfile
import unittest

from fastapi.testclient import TestClient

from gemini_agent import Agent
from gemini_agent.llm import ScriptedLLM
from gemini_agent.server import create_app
from unit_test.gemini_agent.test_agent import FULL_BRIEF, fake_intake


class TestWorkbench(unittest.TestCase):
    """One conversation with a design, read and changed through the tabs' endpoints."""

    @classmethod
    def setUpClass(cls):
        """Run one design in a conversation."""
        cls.tmp = tempfile.TemporaryDirectory()
        agent = Agent(ScriptedLLM(fake_intake), trace_dir=cls.tmp.name)
        cls.client = TestClient(create_app(agent))
        cls.client.post("/api/run", json={"threadId": "wb", "message": FULL_BRIEF})
        cls.client.post(
            "/api/run",
            json={"threadId": "wb", "answers": {"confirm": "Run the design with these inputs"}},
        )
        cls.wb = cls.client.get("/api/workbench", params={"threadId": "wb"}).json()

    @classmethod
    def tearDownClass(cls):
        """Remove the traces."""
        cls.tmp.cleanup()

    def test_designs_have_every_view(self):
        """The chosen design comes first, with plant, year, economics, graph and provenance."""
        designs = self.wb["designs"]
        self.assertTrue(designs[0]["chosen"])
        d = designs[0]
        self.assertEqual(len(d["year"]["daily_mw"]["heat"]["demand"]), 365)
        self.assertTrue(d["graph"]["nodes"])
        self.assertEqual(
            d["provenance"],
            {"plant": "gemini", "year": "dioscuri", "economics": "dioscuri", "cooling": "dioscuri"},
        )
        self.assertEqual(d["graph"]["nodes"][0]["type"], "reservoir")
        self.assertTrue(self.wb["candidates"])
        self.assertEqual(self.wb["reference"]["code"], "REF")

    def test_cost_lines_add_up_to_the_cost_of_heat(self):
        """The Economics tab's lines add up to the cost of heat, and of cold."""
        econ = self.wb["designs"][0]["economics"]
        total = sum(line["eur_per_mwh"] for line in econ["lines"]["heat"])
        self.assertAlmostEqual(total, econ["lcoh"], delta=0.1)
        cold = sum(line["eur_per_mwh"] for line in econ["lines"]["cold"])
        self.assertAlmostEqual(cold, econ["lcoc"], delta=0.1)
        self.assertIsNotNone(econ["versus_reference"])

    def test_assumptions_change_the_economics_and_reset(self):
        """A higher electricity price raises the cost of heat; null goes back to the default."""
        base = self.wb["designs"][0]["economics"]["lcoh"]
        put = {"threadId": "wb", "assumptions": {"electricity_eur_per_mwh": 200}}
        high = self.client.put("/api/assumptions", json=put).json()
        self.assertGreater(high["designs"][0]["economics"]["lcoh"], base)
        reset = {"threadId": "wb", "assumptions": {"electricity_eur_per_mwh": None}}
        back = self.client.put("/api/assumptions", json=reset).json()
        self.assertEqual(back["designs"][0]["economics"]["lcoh"], base)
        bad = self.client.put("/api/assumptions", json={"threadId": "wb", "assumptions": {"x": 1}})
        self.assertEqual(bad.status_code, 422)

    def test_user_design_is_run_kept_and_deleted(self):
        """A design edited on the tabs is simulated, verified, listed and can be removed."""
        base = self.wb["designs"][0]["id"]
        body = {"threadId": "wb", "base": base, "changes": {"heat_pump_mw": 0, "n_doublets": 1}}
        made = self.client.post("/api/designs", json=body).json()["design"]
        self.assertEqual((made["origin"], made["parent"]), ("user", base))
        self.assertEqual(made["plant"]["sizes_mw"]["heat_pump"], 0)
        self.assertEqual(made["plant"]["n_doublets"], 1)
        bad = {"threadId": "wb", "base": base, "changes": {"n_doublets": 5}}
        self.assertEqual(self.client.post("/api/designs", json=bad).status_code, 422)
        ids = [
            d["id"]
            for d in self.client.get("/api/workbench", params={"threadId": "wb"}).json()["designs"]
        ]
        self.assertIn(made["id"], ids)
        gone = self.client.delete("/api/designs", params={"threadId": "wb", "id": made["id"]})
        self.assertEqual(gone.status_code, 200)
        agent_design = self.client.delete("/api/designs", params={"threadId": "wb", "id": base})
        self.assertEqual(agent_design.status_code, 422)

    def test_library_scenarios_parents_and_prices(self):
        """Every design is listed under its scenario, and at the chat's prices.

        Yours goes under its parent's scenario when only the plant changed; after a price change
        every row is at the new prices and says so.
        """
        t = "lib"
        self.client.post("/api/run", json={"threadId": t, "message": FULL_BRIEF})
        self.client.post(
            "/api/run",
            json={"threadId": t, "answers": {"confirm": "Run the design with these inputs"}},
        )
        wb = self.client.get("/api/workbench", params={"threadId": t}).json()
        lib, base = wb["library"], wb["designs"][0]["id"]
        self.assertEqual({r["scenario"]["id"] for r in lib}, {"S1"})
        self.assertEqual(sum(r["recommended"] for r in lib), 1)
        plant = {"threadId": t, "base": base, "changes": {"boiler_mw": 20}}
        colder = {"threadId": t, "base": base, "changes": {"reservoir_delta_c": -10}}
        u1 = self.client.post("/api/designs", json=plant).json()["design"]["id"]
        u2 = self.client.post("/api/designs", json=colder).json()["design"]["id"]
        lib = self.client.get("/api/workbench", params={"threadId": t}).json()["library"]
        rows = {r["id"]: r for r in lib}
        self.assertEqual((rows[u1]["scenario"]["id"], rows[u1]["parent"]), ("S1", base))
        self.assertEqual(rows[u2]["scenario"]["id"], "user")
        put = {"threadId": t, "assumptions": {"electricity_eur_per_mwh": 200}}
        self.client.put("/api/assumptions", json=put)
        high = {
            r["id"]: r
            for r in self.client.get("/api/workbench", params={"threadId": t}).json()["library"]
        }
        self.assertTrue(all(r["scenario"]["repriced"] for r in high.values()))
        self.assertGreater(high[base]["lcoe"], rows[base]["lcoe"])

    def test_sensitivity_tornado_and_monte_carlo(self):
        """Chosen parameters give a sorted tornado, a spider and percentiles."""
        body = {
            "threadId": "wb",
            "design": self.wb["designs"][0]["id"],
            "parameters": [
                {"key": "electricity_price", "low": 120, "high": 220},
                {"key": "capex", "low": 0.8, "high": 1.3},
            ],
            "outputs": ["lcoh"],
            "samples": 20,
        }
        s = self.client.post("/api/sensitivity", json=body).json()
        swings = [abs(t["high"]["lcoh"] - t["low"]["lcoh"]) for t in s["tornado"]]
        self.assertEqual(swings, sorted(swings, reverse=True))
        self.assertEqual(len(s["spider"][0]["points"]), 5)
        mc = s["monte_carlo"]["outputs"]["lcoh"]
        self.assertLessEqual(mc["p10"], mc["p50"])
        self.assertLessEqual(mc["p50"], mc["p90"])

    def test_gemini_catalogue_and_run(self):
        """The catalogue lists GEMINI's types; a project runs on the fixed and the release."""
        types = {t["type"] for t in self.client.get("/api/gemini/catalogue").json()["types"]}
        self.assertTrue({"producer_well", "heat_exchanger", "heatpump"} <= types)
        from gemini_agent.tools import gemini

        project = gemini.challenge_project(2500, 2)
        run = self.client.post(
            "/api/gemini/run", json={"project": project, "compare_released": True}
        ).json()
        self.assertTrue(run["ok"])
        self.assertIn("producer_well_1", run["outputs"])
        self.assertAlmostEqual(run["outputs"]["producer_well_1"]["flow_rate"], 300.0, delta=0.5)
        self.assertAlmostEqual(run["outputs"]["brine_mixer"]["flow"] * 3600, 600.0, delta=1.0)
        # GEMINI as released has no root in the physical range for this well (water, 10 mm
        # roughness): the comparison says so instead of failing.
        released = run["released"]
        self.assertTrue(released["ok"] or "different signs" in (released["error"] or ""))

    def test_trace_and_evidence(self):
        """The trace lists the run with its message; evidence has the benchmark tables."""
        runs = self.client.get("/api/trace", params={"threadId": "wb"}).json()["runs"]
        self.assertEqual(runs[0]["message"], FULL_BRIEF)
        self.assertTrue(runs[0]["steps"])
        evidence = self.client.get("/api/evidence").json()
        self.assertTrue(evidence["benchmarks"])


class TestGasFreeGraph(unittest.TestCase):
    """The Design tab's drawing of the designs that buy no gas: an electric boiler, the gas."""

    @classmethod
    def setUpClass(cls):
        """Search the challenge once: it has gas-free designs (EB), some selling the gas (GS)."""
        from gemini_agent import engine
        from gemini_agent.contract import DesignBrief

        cls.entries = engine.search(DesignBrief()).candidates

    def find(self, gas: str, used: bool = True):
        """Return a design with this gas mode (one whose electric boiler runs, when ``used``)."""
        for e in self.entries:
            a = e.alternative
            runs = (e.year.heat_split_gwh or {}).get("electric_boiler", 0.0) > 0
            if a.gas == gas and a.n_doublets and (runs or not used or gas == "buy"):
                return e
        self.skipTest(f"no {gas} design in the search")

    @staticmethod
    def graph(entry):
        """Return the drawing's nodes by id and its edges by (source, target)."""
        from gemini_agent import workbench

        g = workbench.graph_view(entry)
        return {n["id"]: n for n in g["nodes"]}, {(e["source"], e["target"]): e for e in g["edges"]}

    def test_electric_boiler_from_the_grid_to_the_heat(self):
        """The electric boiler draws from the grid and heats the network, at its size and GWh."""
        e = self.find("produced")
        nodes, edges = self.graph(e)
        eb = nodes["electric_boiler"]
        self.assertEqual(eb["type"], "electric_boiler")
        self.assertAlmostEqual(
            eb["values"]["power_mw"], e.alternative.sizes_mw["electric_boiler"], places=3
        )
        self.assertAlmostEqual(
            eb["values"]["heat_gwh"], e.year.heat_split_gwh["electric_boiler"], places=3
        )
        self.assertEqual(edges[("grid", "electric_boiler")]["kind"], "electricity")
        self.assertEqual(edges[("electric_boiler", "demand_heat")]["kind"], "network")
        self.assertAlmostEqual(
            nodes["grid"]["values"]["electric_boiler_gwh"],
            e.year.electricity_gwh["electric_boiler"],
            places=3,
        )
        # The brine's own gas in a small boiler, none bought.
        gas = nodes["gas"]
        self.assertEqual((gas["gas"], gas["label"]), ("produced", "Gas from the brine"))
        self.assertEqual(gas["values"]["bought_gwh"], 0.0)
        self.assertIn(("gas", "boiler"), edges)
        self.assertEqual(nodes["boiler"]["label"], "Gas boiler")

    def test_sold_gas_goes_to_the_grid_and_its_co2_is_the_buyers(self):
        """Sold gas: no gas boiler, the methane sold and the buyer's CO2 apart from the plant's."""
        e = self.find("sell")
        nodes, edges = self.graph(e)
        gas = nodes["gas"]
        self.assertEqual((gas["gas"], gas["label"]), ("sell", "Gas sold to the grid"))
        self.assertNotIn("boiler", nodes)
        self.assertFalse([k for k in edges if k[0] == "gas"])
        self.assertTrue([k for k in edges if k[1] == "gas" and k[0].startswith("train")])
        self.assertAlmostEqual(gas["values"]["sold_gwh"], e.year.produced_gas_sold_gwh, places=3)
        self.assertAlmostEqual(
            gas["values"]["buyer_co2_t"], e.year.co2_t["sold_gas_elsewhere"], places=1
        )
        self.assertIn("not counted", gas["units"]["buyer_co2_t"])
        self.assertGreater(gas["values"]["buyer_co2_t"], 0)

    def test_a_plant_that_buys_gas_is_drawn_as_before(self):
        """A design that buys gas has no electric boiler and its gas feeds the boiler."""
        e = next(x for x in self.entries if x.alternative.gas == "buy" and x.year.boiler_mw)
        nodes, edges = self.graph(e)
        self.assertNotIn("electric_boiler", nodes)
        self.assertEqual((nodes["gas"]["gas"], nodes["gas"]["label"]), ("buy", "Gas"))
        self.assertIn(("gas", "boiler"), edges)


if __name__ == "__main__":
    unittest.main()
