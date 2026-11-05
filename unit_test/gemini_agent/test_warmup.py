"""Loading the models at start, ``GET /api/models`` and the run's "Load the model" row.

Every test talks to a fake Ollama over HTTP (``fake_ollama``), never to the real one. The models
come from the router, so the tests hold when it hands out other models or windows.
"""

import socket
import time
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # the server is optional for the model and simulator tests
    TestClient = None

from gemini_agent import Agent, Session
from gemini_agent.llm import OllamaLLM, ScriptedLLM
from gemini_agent.router import REASONING_CTX, REASONING_GPU_MODEL, Hardware, Router
from gemini_agent.warmup import ModelLoad, Warmup, failure
from unit_test.gemini_agent.fake_ollama import PULLED, FakeOllama
from unit_test.gemini_agent.test_agent import fake_intake, run

GPU = Hardware("RTX 4090", 20000, 0, 24000)  # room for the 9B on the GPU


def models_of(router):
    """Return the (model, window) of the clients a message uses, in order, without repeats."""
    out = []
    for client in (router.reader(), router.answerer(), router.reasoning()):
        key = (client.model, client.options["num_ctx"])
        if key not in out:
            out.append(key)
    return out


def closed_port() -> int:
    """Return a port nothing listens on."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(check, seconds=10.0):
    """Wait until ``check()`` is true; return its last value."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(0.02)
    return check()


def steps(events, name="load_model"):
    """Return the labels of the run's steps called ``name``."""
    return [
        e["metadata"]["label"]
        for e in events
        if e["type"] == "STEP_STARTED" and e["stepName"] == name
    ]


class TestModelLoad(unittest.TestCase):
    """What counts as loaded, the row's words and the failure messages."""

    def test_loaded_means_same_window_and_device(self):
        """A model loaded with another window, or on the GPU for a CPU-only call, is not loaded."""
        load = ModelLoad("qwen3.5:9b", 16384, "gpu", False, None)
        ps = {"qwen3.5:9b": {"context_length": 16384, "size_vram": 6_000_000_000}}
        self.assertTrue(load.in_memory(ps))
        self.assertFalse(load.in_memory({"qwen3.5:9b": {"context_length": 8192}}))
        self.assertFalse(load.in_memory({}))
        cpu = ModelLoad("qwen3.5:4b", 8192, "cpu", True, None)
        self.assertFalse(cpu.in_memory({"qwen3.5:4b": {"context_length": 8192, "size_vram": 9}}))
        self.assertTrue(cpu.in_memory({"qwen3.5:4b": {"context_length": 8192, "size_vram": 0}}))

    def test_row_names_model_place_and_size(self):
        """The row says what is loaded, where, how big, and that it happens once."""
        load = ModelLoad("qwen3.5:9b", 16384, "gpu", False, None, size_bytes=6_550_825_550)
        self.assertEqual(load.label(), "Load qwen3.5:9b into GPU memory (6.6 GB, first time only)")
        cpu = ModelLoad("qwen3:1.7b", 4096, "cpu", True, None)
        self.assertEqual(cpu.label(), "Load qwen3:1.7b into RAM (first time only)")

    def test_failures_say_what_to_do(self):
        """Ollama down, a model not pulled and a timeout each get a short message and a hint."""
        down = failure("qwen3.5:9b", "ConnectionError: Failed to connect to Ollama.")
        self.assertEqual(down[:2], ("not_running", "Ollama is not running"))
        self.assertIn("ollama serve", down[2])
        missing = failure("qwen3.5:9b", "ResponseError: model 'qwen3.5:9b' not found")
        self.assertEqual(missing, ("not_pulled", "qwen3.5:9b is not downloaded", missing[2]))
        self.assertEqual(missing[2], "Run: ollama pull qwen3.5:9b")
        self.assertEqual(failure("x", "ReadTimeout: timed out")[0], "timeout")


class TestWarmup(unittest.TestCase):
    """The warm-up loads each model once, in order, and reports its state."""

    def setUp(self):
        """Start a fake Ollama with nothing loaded."""
        self.fake = FakeOllama().start()
        self.addCleanup(self.fake.stop)
        self.router = Router(hardware=GPU, host=self.fake.url)
        self.warmup = Warmup(self.router, host=self.fake.url)

    def test_one_load_per_model_and_window(self):
        """Roles that share a model and a window are one load, with every role named."""
        model, ctx = REASONING_GPU_MODEL, REASONING_CTX
        fast = OllamaLLM(model, host=self.fake.url, num_ctx=ctx)
        router = Router(fast, hardware=GPU, host=self.fake.url)
        loads = Warmup(router, host=self.fake.url).needed()
        self.assertEqual([(m.model, m.num_ctx) for m in loads], [(model, ctx)])
        self.assertEqual(loads[0].roles, ["reader", "answerer", "reasoning"])
        self.assertEqual(
            [(m.model, m.num_ctx) for m in self.warmup.needed()], models_of(self.router)
        )

    def test_start_never_blocks_and_loads_in_order(self):
        """Start returns at once; the reader loads first, each with keep-alive and its window."""
        self.fake.hold()
        began = time.perf_counter()
        self.warmup.start()
        self.assertLess(time.perf_counter() - began, 0.5)
        first = wait_for(lambda: self.warmup.status()["models"][0]["state"] == "loading")
        self.assertTrue(first)
        self.fake.release()
        self.assertTrue(wait_for(lambda: self.warmup.status()["ready"]))
        sent = [(c["model"], c["options"]["num_ctx"]) for c in self.fake.chats]
        self.assertEqual(sent, models_of(self.router))
        self.assertTrue(all(c["keep_alive"] == -1 for c in self.fake.chats))

    def test_ollama_down(self):
        """With Ollama not running, the warm-up fails with a clear message and does not raise."""
        url = f"http://127.0.0.1:{closed_port()}"
        warmup = Warmup(Router(hardware=GPU, host=url), host=url)
        warmup.start()
        status = wait_for(lambda: warmup.status()["state"] == "failed" and warmup.status())
        self.assertEqual(status["message"], "Ollama is not running")
        self.assertIn("ollama serve", status["hint"])
        self.assertFalse(status["ready"])

    def test_retries_when_ollama_starts_later(self):
        """A failed warm-up is tried again by itself; starting Ollama is enough to recover."""
        port = closed_port()
        url = f"http://127.0.0.1:{port}"
        now, said = [100.0], []
        router = Router(hardware=GPU, host=url)
        warmup = Warmup(router, host=url, log=said.append, clock=lambda: now[0])
        warmup.start()
        self.assertTrue(wait_for(lambda: warmup.status()["state"] == "failed"))
        now[0] += 5  # too soon to try again
        self.assertEqual(warmup.status()["state"], "failed")
        with FakeOllama(port=port):
            now[0] += 10
            self.assertTrue(wait_for(lambda: warmup.status()["ready"]))
        failed = [line for line in said if line.startswith("Could not load")]
        self.assertEqual(len(failed), len(models_of(router)))  # each said once


@unittest.skipIf(TestClient is None, "fastapi is not installed")
class TestModelsEndpoint(unittest.TestCase):
    """``GET /api/models``: loading, ready, failed and already loaded."""

    def app(self, fake, router=None):
        """Return a test client whose agent's models live on ``fake``."""
        from gemini_agent.server import create_app

        router = router or Router(hardware=GPU, host=fake.url)
        warmup = Warmup(router, host=fake.url)
        agent = Agent(ScriptedLLM(fake_intake), warmup=warmup)
        return TestClient(create_app(agent, router)), warmup

    def test_loading_then_ready(self):
        """While a model loads the state is loading, with seconds; then every model is ready."""
        with FakeOllama() as fake:
            client, warmup = self.app(fake)
            fake.hold()
            warmup.start()
            body = wait_for(
                lambda: (b := client.get("/api/models").json())["models"][0]["state"] == "loading"
                and b
            )
            self.assertEqual((body["state"], body["ready"], body["loaded"]), ("loading", False, 0))
            self.assertEqual(body["total"], len(models_of(warmup.router)))
            first = body["models"][0]
            self.assertEqual(first["device"], "gpu")
            self.assertIn("reader", first["roles"])
            self.assertEqual(first["size_gb"], round(PULLED[first["model"]] / 1e9, 2))
            self.assertIsNotNone(first["seconds"])
            fake.release()
            done = wait_for(lambda: (b := client.get("/api/models").json())["ready"] and b)
            self.assertEqual(done["state"], "ready")
            self.assertEqual(done["loaded"], done["total"])
            self.assertTrue(all(m["message"].startswith("Loaded in") for m in done["models"]))

    def test_already_loaded(self):
        """Models Ollama holds already (``/api/ps``) are ready without a call."""
        with FakeOllama() as fake:
            client, warmup = self.app(fake)
            for model, ctx in models_of(warmup.router):
                fake.put(model, ctx)
            body = client.get("/api/models").json()
            self.assertEqual((body["state"], body["ready"]), ("ready", True))
            self.assertEqual({m["message"] for m in body["models"]}, {"Already in memory"})
            self.assertEqual(fake.chats, [])

    def test_not_pulled_fails_with_the_command(self):
        """A model that is not pulled fails; the hint is the pull command."""
        reasoning = Router(hardware=GPU).reasoning().model
        pulled = {k: v for k, v in PULLED.items() if k != reasoning}
        with FakeOllama(pulled=pulled) as fake:
            client, warmup = self.app(fake)
            warmup.start()
            body = wait_for(
                lambda: (b := client.get("/api/models").json())["state"] == "failed" and b
            )
            self.assertEqual(body["message"], f"{reasoning} is not downloaded")
            self.assertEqual(body["hint"], f"Run: ollama pull {reasoning}")
            self.assertFalse(body["ready"])

    def test_without_a_warmup(self):
        """A scripted agent has nothing to load: ready."""
        from gemini_agent.server import create_app

        client = TestClient(create_app(Agent(ScriptedLLM(fake_intake))))
        self.assertTrue(client.get("/api/models").json()["ready"])


class TestLoadRow(unittest.TestCase):
    """A run loads a model that is not in memory first, as a row; only then."""

    def test_row_only_when_a_model_was_not_loaded(self):
        """The first run loads the models (a row each); the next has none, till one is evicted."""
        with FakeOllama() as fake:
            router = Router(hardware=GPU, host=fake.url)
            agent = Agent(ScriptedLLM(fake_intake), warmup=Warmup(router, host=fake.url))
            session = Session()
            message = "What will the weather be in Paris tomorrow?"
            first = run(agent, session, message)
            wanted = models_of(router)
            labels = steps(first)
            self.assertEqual(len(labels), len(wanted))
            self.assertEqual(
                labels[0],
                f"Load {wanted[0][0]} into GPU memory "
                f"({PULLED[wanted[0][0]] / 1e9:.1f} GB, first time only)",
            )
            names = [e["stepName"] for e in first if e["type"] == "STEP_STARTED"]
            self.assertEqual(names[: len(wanted)], ["load_model"] * len(wanted))
            done = [e for e in first if e["type"] == "STEP_FINISHED"][0]["metadata"]
            self.assertEqual(done["model"], wanted[0][0])
            summary = first[-1]["result"]
            self.assertEqual([m["model"] for m in summary["model_loads"]], [m for m, _ in wanted])
            self.assertTrue(all(c.purpose != "warm-up" for c in agent._calls))

            second = run(agent, session, message)
            self.assertEqual(steps(second), [])
            self.assertNotIn("model_loads", second[-1]["result"])

            fake.evict(wanted[-1][0])  # Ollama unloaded it: loaded again, and said so
            third = run(agent, session, message)
            self.assertEqual(len(steps(third)), 1)
            self.assertTrue(
                steps(third)[0].startswith(f"Load {wanted[-1][0]} into GPU memory again")
            )

    def test_failed_load_is_a_red_row_and_the_run_goes_on(self):
        """A model that cannot be loaded ends its row failed; the run still finishes."""
        reasoning = Router(hardware=GPU).reasoning().model
        pulled = {k: v for k, v in PULLED.items() if k != reasoning}
        with FakeOllama(pulled=pulled) as fake:
            router = Router(hardware=GPU, host=fake.url)
            agent = Agent(ScriptedLLM(fake_intake), warmup=Warmup(router, host=fake.url))
            events = run(agent, Session(), "What will the weather be in Paris tomorrow?")
            failed = [
                e["metadata"]
                for e in events
                if e["type"] == "STEP_FINISHED" and e["metadata"].get("failed")
            ]
            self.assertEqual([m["model"] for m in failed], [reasoning])
            self.assertEqual(failed[0]["error"], f"{reasoning} is not downloaded")
            self.assertEqual(events[-1]["type"], "RUN_FINISHED")

    def test_ollama_down_shows_no_row(self):
        """When Ollama does not answer there is no row: the run's own call says what is wrong."""
        url = f"http://127.0.0.1:{closed_port()}"
        agent = Agent(ScriptedLLM(fake_intake), warmup=Warmup(Router(hardware=GPU, host=url), url))
        events = run(agent, Session(), "What will the weather be in Paris tomorrow?")
        self.assertEqual(steps(events), [])


if __name__ == "__main__":
    unittest.main()
