"""Tests for the server's event stream, with the scripted model (no Ollama needed)."""

import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # the server is optional for the model and simulator tests
    TestClient = None

from gemini_agent import Agent
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import fake_intake

RUN = {"confirm": "Run the design with these inputs"}


def through_confirm(client, body):
    """Post a run; when it stops at the inputs card, confirm it; return the last run's events."""
    r = client.post("/api/run", json=body)
    out = events(r)
    interrupts = (out[-1].get("outcome") or {}).get("interrupts") or []
    if interrupts and interrupts[0].get("reason") == "confirm":
        thread = body.get("threadId") or out[0].get("threadId")
        out = events(
            client.post(
                "/api/run", json={**body, "message": None, "answers": RUN, "threadId": thread}
            )
        )
    return out


def events(response):
    """Return the JSON events of a server-sent event stream."""
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


SHORT = "Heat and cool the district with a single doublet and no heat pumps, boilers or chillers."


@unittest.skipIf(TestClient is None, "fastapi is not installed")
class TestServer(unittest.TestCase):
    """The stream carries the agent's events, and a thread keeps its open question."""

    def setUp(self):
        """Create the app with a scripted agent."""
        from gemini_agent.server import create_app

        self.client = TestClient(create_app(Agent(ScriptedLLM(fake_intake))))

    def test_question_then_answers_on_one_thread(self):
        """A run that asks (a decision) is continued on the same thread by sending the answer."""
        r = self.client.post(
            "/api/run",
            json={
                "threadId": "t1",
                "message": SHORT,
            },
        )
        self.assertEqual(r.headers["content-type"].split(";")[0], "text/event-stream")
        self.assertEqual(events(r)[-1]["outcome"]["interrupts"][0]["reason"], "confirm")
        first = through_confirm(self.client, {"threadId": "t1", "answers": RUN})
        self.assertEqual(first[-1]["outcome"]["type"], "interrupt")
        r = self.client.post(
            "/api/run", json={"threadId": "t1", "answers": {"decision": "Lift all these limits"}}
        )
        second = events(r)
        self.assertEqual(second[-1]["result"]["behaviour"], "design")
        state = self.client.get("/api/threads/t1").json()
        self.assertEqual(state["brief"]["excluded"], [])

    def test_empty_request_is_rejected(self):
        """A run needs a message or answers."""
        self.assertEqual(self.client.post("/api/run", json={}).status_code, 400)

    def test_device_choice_and_profiles(self):
        """A run may ask for the CPU; health lists each role's model on the GPU and the CPU."""
        from gemini_agent.router import Hardware, Router
        from gemini_agent.server import create_app

        router = Router(ScriptedLLM(fake_intake), hardware=Hardware("RTX", 16000))
        client = TestClient(create_app(Agent(router.fast, router=router)))
        health = client.get("/api/health").json()
        self.assertEqual(health["profiles"]["cpu"]["answer"]["device"], "cpu")
        self.assertEqual(health["profiles"]["auto"]["answer"]["model"], "qwen3.5:9b")
        self.assertEqual(health["gpu"], "RTX")
        bad = client.post("/api/run", json={"message": "hi", "device": "tpu"})
        self.assertEqual(bad.status_code, 422)

    def test_attachment_types_are_checked(self):
        """Only readable file types are accepted, and health says which."""
        allowed = self.client.get("/api/health").json()["attachments"]["types"]
        self.assertTrue({".pdf", ".xlsx", ".png"} <= set(allowed))
        r = self.client.post(
            "/api/attachments",
            data={"threadId": "t3"},
            files={"file": ("loads.docx", b"PK\x03\x04", "application/octet-stream")},
        )
        self.assertEqual(r.status_code, 415)

    def test_files_raw_view_and_missing(self):
        """Project files come raw or as the chat's view; unknown files and paths are refused."""
        raw = self.client.get(
            "/api/files", params={"threadId": "t9", "name": "GEMINI_Heating_Demand_Daily_2027.csv"}
        )
        self.assertEqual(raw.status_code, 200)
        self.assertTrue(raw.text.startswith("date,heating_demand_MWth"))
        view = self.client.get(
            "/api/files",
            params={"threadId": "t9", "name": "GEMINI_Heating_Demand_Daily_2027.csv", "view": 1},
        ).json()
        self.assertEqual((view["kind"], view["table"]["total_rows"]), ("table", 365))
        gone = self.client.get("/api/files", params={"threadId": "t9", "name": "nope.csv"})
        self.assertEqual(gone.status_code, 404)
        sneaky = self.client.get("/api/doc-image", params={"path": "src/../pyproject.toml"})
        self.assertEqual(sneaky.status_code, 404)

    def test_unsafe_thread_id_is_rejected(self):
        """Thread ids name files on disk, so only plain ids are accepted."""
        r = self.client.post("/api/run", json={"threadId": "../x", "message": "Design heating."})
        self.assertEqual(r.status_code, 400)

    def test_health_reports_readiness(self):
        """Health says whether each model can answer and what to run if not."""
        health = self.client.get("/api/health").json()
        self.assertEqual((health["ready"], health["reasoning"]["ready"]), (True, True))

    def test_reasoning_flag_reaches_the_agent(self):
        """``"reasoning": true`` forces reasoning: the reasoning model writes the answer."""
        from gemini_agent.server import create_app
        from unit_test.gemini_agent.test_agent import FULL_BRIEF, deep_model

        client = TestClient(create_app(Agent(ScriptedLLM(fake_intake), reasoning_llm=deep_model())))
        result = through_confirm(
            client, {"threadId": "rf", "message": FULL_BRIEF, "reasoning": True}
        )[-1]["result"]
        self.assertEqual(result["decided_by"], {"answer": "model"})
        self.assertIs(result["reasoning"], True)

    def test_conversation_survives_a_restart(self):
        """A second server on the same session folder continues the open question."""
        from gemini_agent.server import create_app

        with tempfile.TemporaryDirectory() as folder:
            first = TestClient(create_app(Agent(ScriptedLLM(fake_intake), session_dir=folder)))
            through_confirm(first, {"threadId": "t2", "message": SHORT})
            again = TestClient(create_app(Agent(ScriptedLLM(fake_intake), session_dir=folder)))
            self.assertIsNotNone(again.get("/api/threads/t2").json()["pending"])
            r = again.post(
                "/api/run",
                json={"threadId": "t2", "answers": {"decision": "Lift all these limits"}},
            )
            self.assertEqual(events(r)[-1]["result"]["behaviour"], "design")

    def test_the_lead_is_not_computed_at_start(self):
        """A new chat starts empty: the recommended design waits for GET /api/lead (5 Nov)."""
        from unittest import mock

        from gemini_agent.server import lead_at_start

        with mock.patch.dict("os.environ", {}, clear=False) as env:
            env.pop("DIOSCURI_LEAD_AT_START", None)
            self.assertFalse(lead_at_start())
            env["DIOSCURI_LEAD_AT_START"] = "1"
            self.assertTrue(lead_at_start())


class SlowAgent(Agent):
    """An agent whose run waits mid-way, then writes its session and trace as a run does."""

    def __init__(self, *args, **kwargs):
        """Make the agent; ``started`` is set when a run waits, ``go_on`` lets it go on."""
        super().__init__(*args, **kwargs)
        self.started = threading.Event()
        self.go_on = threading.Event()

    def run(self, session, message=None, **kwargs):
        """Yield one event, wait, write the session and the trace, then yield the rest."""
        yield {"type": "RUN_STARTED", "threadId": session.thread_id, "runId": "r1"}
        self.started.set()
        self.go_on.wait(10)
        session.turns += 1
        session.save(self.session_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        with open(self.trace_dir / f"{session.thread_id}.jsonl", "a", encoding="utf-8") as fh:
            fh.write('{"type": "TEXT_MESSAGE_CONTENT"}\n')
        yield {"type": "TEXT_MESSAGE_CONTENT", "messageId": "m1", "delta": "late"}
        yield {"type": "RUN_FINISHED", "threadId": session.thread_id, "runId": "r1"}


@unittest.skipIf(TestClient is None, "fastapi is not installed")
class TestRemoveThread(unittest.TestCase):
    """DELETE /api/threads/{id}: the run stops and all the server keeps of the chat goes."""

    def setUp(self):
        """Make an app whose sessions, traces and document search live in the test's folder."""
        from gemini_agent.docs import DocIndex
        from gemini_agent.server import create_app

        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "pump.md").write_text("# Pump\n\nThe ESP lifts the brine.\n")
        self.docs = DocIndex(
            root=self.root,
            corpus=(("docs", (".md",)),),
            cache_dir=self.root / "cache",
            backend="bm25",
            background=False,
        )
        self.sessions = self.root / "sessions"
        self.traces = self.root / "traces"
        self.agent = Agent(
            ScriptedLLM(fake_intake),
            session_dir=str(self.sessions),
            trace_dir=str(self.traces),
            docs=self.docs,
        )
        self.client = TestClient(create_app(self.agent))

    def chat(self, thread):
        """Run a design on a thread and attach a note to it."""
        through_confirm(self.client, {"threadId": thread, "message": SHORT})
        r = self.client.post(
            "/api/attachments",
            data={"threadId": thread},
            files={"file": ("notes.md", b"# Notes\n\nThe client wants 70 C.\n", "text/markdown")},
        )
        self.assertEqual(r.status_code, 200)

    def test_removes_the_session_uploads_trace_and_passages(self):
        """Every file named by the thread goes, and what the agent holds; other chats stay."""
        self.chat("del-1")
        self.chat("del-10")  # a neighbour whose id starts with the same letters
        for name in ("del-1.json", "del-1/notes.md"):
            self.assertTrue((self.sessions / name).is_file(), name)
        self.assertTrue((self.traces / "del-1.jsonl").is_file())
        self.assertIn("del-1", self.docs.info()["threads"])
        self.assertTrue(self.client.get("/api/trace", params={"threadId": "del-1"}).json()["runs"])
        self.assertTrue(
            self.client.get("/api/workbench", params={"threadId": "del-1"}).json()["designs"]
        )

        r = self.client.delete("/api/threads/del-1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["stopped"], 0)
        self.assertEqual(sorted(r.json()["removed"]), ["del-1", "del-1.json", "del-1.jsonl"])
        self.assertFalse((self.sessions / "del-1.json").exists())
        self.assertFalse((self.sessions / "del-1").exists())
        self.assertFalse((self.traces / "del-1.jsonl").exists())
        self.assertNotIn("del-1", self.docs.info()["threads"])
        self.assertFalse(any(k[0] == "del-1" for k in self.agent._attached))
        self.assertEqual(self.client.get("/api/threads/del-1").status_code, 404)
        self.assertEqual(
            self.client.get("/api/trace", params={"threadId": "del-1"}).json()["runs"], []
        )
        self.assertEqual(
            self.client.get("/api/workbench", params={"threadId": "del-1"}).json()["designs"], []
        )
        # The neighbour is untouched.
        self.assertTrue((self.sessions / "del-10.json").is_file())
        self.assertTrue((self.sessions / "del-10" / "notes.md").is_file())
        self.assertTrue((self.traces / "del-10.jsonl").is_file())
        self.assertIn("del-10", self.docs.info()["threads"])
        self.assertEqual(self.client.get("/api/threads/del-10").status_code, 200)
        # Removing it again finds nothing to remove.
        again = self.client.delete("/api/threads/del-1").json()
        self.assertEqual((again["ok"], again["removed"]), (True, []))

    def test_a_restarted_server_removes_what_is_on_disk(self):
        """A chat saved before a restart (not in memory) is removed from disk all the same."""
        from gemini_agent.server import create_app

        self.chat("del-2")
        fresh = TestClient(
            create_app(
                Agent(
                    ScriptedLLM(fake_intake),
                    session_dir=str(self.sessions),
                    trace_dir=str(self.traces),
                )
            )
        )
        self.assertEqual(
            sorted(fresh.delete("/api/threads/del-2").json()["removed"]),
            ["del-2", "del-2.json", "del-2.jsonl"],
        )
        self.assertEqual(list(self.sessions.iterdir()), [])
        self.assertEqual(list(self.traces.iterdir()), [])

    def test_only_plain_ids(self):
        """A thread id names files, so anything but letters, digits, - and _ is refused."""
        outside = self.root / "outside.json"
        outside.write_text("{}")
        for bad in ("a.b", "x" * 65, "a b", "outside.json"):
            self.assertEqual(self.client.delete(f"/api/threads/{bad}").status_code, 400, bad)
        for path in ("..", "..%2Foutside", "../outside"):  # no route: never a removal
            self.assertNotEqual(self.client.delete(f"/api/threads/{path}").status_code, 200, path)
        self.assertTrue(outside.is_file())

    def test_a_run_going_on_stops_and_leaves_nothing(self):
        """The run stops at its next event; what it wrote after the removal goes too."""
        from gemini_agent.server import create_app

        agent = SlowAgent(
            ScriptedLLM(fake_intake), session_dir=str(self.sessions), trace_dir=str(self.traces)
        )
        client = TestClient(create_app(agent))
        out = {}

        def post():
            out["events"] = events(
                client.post("/api/run", json={"threadId": "del-3", "message": "hi"})
            )

        worker = threading.Thread(target=post)
        worker.start()
        self.assertTrue(agent.started.wait(10))
        r = client.delete("/api/threads/del-3").json()
        self.assertEqual(r["stopped"], 1)
        conflict = client.post("/api/run", json={"threadId": "del-3", "message": "hi"})
        self.assertEqual(conflict.status_code, 409)  # not while the removal waits for the run
        agent.go_on.set()
        worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual([e["type"] for e in out["events"]], ["RUN_STARTED"])
        self.assertFalse((self.sessions / "del-3.json").exists())
        self.assertFalse((self.traces / "del-3.jsonl").exists())
        self.assertEqual(client.get("/api/threads/del-3").status_code, 404)
        # Once stopped, the next run is a new chat with that id.
        self.assertEqual(
            client.post("/api/run", json={"threadId": "del-3", "message": "hi"}).status_code, 200
        )


if __name__ == "__main__":
    unittest.main()
