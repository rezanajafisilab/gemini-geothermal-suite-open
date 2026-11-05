"""The conversation's running state (``chat_state``): designs in order, questions, decisions.

4 Nov, conversation C3: after a list of two designs, "the second one" and "the first one's" were
read as the recommended design. The state marks each design the which-design reading may pick
with its place in the last list shown, the turn it came up and its figures; these tests play
whole chats with scripted models that read those marks.
"""

import os
import re
import unittest
from unittest import mock

from gemini_agent import Agent, chat_state, reporter
from gemini_agent.chat_state import ChatState
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import fake_intake, run
from unit_test.gemini_agent.test_naming import designed

ORDINAL = {"first": "1st", "second": "2nd", "third": "3rd"}
EMPTY_READING = {
    "changes": [],
    "doublets": [],
    "unsupported": [],
    "failures": [],
    "designs": [],
    "asks_for": [],
    "premises": [],
    "origin_of": [],
    "on_topic": True,
    "objective": None,
    "steps": [{"do": "answer", "quote": "", "changes": []}],
    "open": [],
}


def two_picks(session):
    """Return two picks of the search with different ids, the recommended one last."""
    picks = []
    for e in session.candidates:
        if e.alternative.picks and all(e.alternative.uid != p.alternative.uid for p in picks):
            picks.append(e)
    picks.sort(key=lambda e: e is session.chosen)
    return picks[:2]


def chat_model(listed, seen):
    """Return a scripted reasoning model that reads ordinals from the options' marks.

    ``listed``: the reply the answerer writes to "which designs did the search pick?"; ``seen``
    collects each call's prompt by purpose.
    """

    def reply(purpose, messages):
        prompt = "\n".join(m["content"] for m in messages)
        seen.setdefault(purpose, []).append(prompt)
        said = messages[-1]["content"].split("Message: ")[-1]
        if purpose == "intake":
            return dict(fake_intake(purpose, messages), intent="question")
        if purpose == "parameters":
            return EMPTY_READING
        if purpose == "needs":
            if "pick" in said:
                return {"needs": "no_particular_design"}
            return {"needs": "about_one_existing_design"}
        if purpose == "which_design":
            # The model's part: "the second one" is the option marked 2nd in the last list.
            word = next((w for w in ORDINAL if w in said.lower()), "")
            options = re.findall(r"^- (\S+) · (.*)$", prompt, re.M)
            for name, rest in options:
                if word and f"{ORDINAL[word]} in the last list shown" in rest:
                    return {"design": name}
            return {"design": "unclear"}
        if purpose == "answer" and "did the search pick" in said:
            return {
                "understood": "x",
                "kind": "answer",
                "scope": "project",
                "answer": listed,
                "used": ["search"],
                "follow_ups": [],
                "run": "none",
            }
        return fake_intake(purpose, messages)

    return ScriptedLLM(reply, model="qwen3.5:9b")


class TestOrdinals(unittest.TestCase):
    """After a list, "the second one" and "the first one's" are its second and first items."""

    def test_second_then_first(self):
        """A three-turn chat: the list, its second item, its first item."""
        _, s = designed()
        picks = two_picks(s)
        if len(picks) < 2:
            self.skipTest("the toy search picked one design")
        first, second = picks  # the reply lists the non-recommended one first
        listed = (
            f"The search picked {first.alternative.uid} ({first.alternative.code}) and "
            f"{second.alternative.uid} ({second.alternative.code})."
        )
        seen = {}
        agent = Agent(chat_model(listed, seen))
        run(agent, s, "Which designs did the search pick?")
        self.assertEqual(
            [x.split(" (")[0] for x in s.thread.shown[:2]],
            [reporter.design_id(first), reporter.design_id(second)],
        )

        run(agent, s, "What is the CO2 saving of the second one?")
        prompt = seen["which_design"][-1]
        self.assertIn("2nd in the last list shown", prompt)
        self.assertIn("CO2 saving", prompt)  # each option's figures, from the ledger
        self.assertEqual(s.thread.focus_id, reporter.design_id(second))
        self.assertNotEqual(s.last.get("behaviour"), "clarify")

        run(agent, s, "And the first one's capital cost?")
        self.assertEqual(s.thread.focus_id, reporter.design_id(first))
        # The readings of a follow-up that names no design get the state too.
        self.assertIn("Conversation state (kept by code)", seen["needs"][-1])
        self.assertIn("Designs in the order they came up", seen["parameters"][-1])

        # The state: the designs in the order they came up, the questions, a decision.
        state = s.state
        ids = [d["id"] for d in state.designs]
        self.assertLess(ids.index(first.alternative.uid), ids.index(second.alternative.uid))
        self.assertEqual(
            [q for _, q, _ in state.asked][-2:],
            ["What is the CO2 saving of the second one?", "And the first one's capital cost?"],
        )
        self.assertTrue(any("recommended" in d for d in state.decisions))

    def test_original_of_a_what_if(self):
        """The design a what-if ran on is marked the original one, and may be picked."""
        _, s = designed()
        what_if = s.chosen.model_copy(deep=True)
        what_if.alternative.role, what_if.alternative.uid = "what_if", "W1"
        what_if.change_label = "gas price 45 €/MWh"
        s.ledger.append(what_if)
        s.thread.focus, s.thread.focus_id = "W1", reporter.design_id(what_if)
        self.assertIs(chat_state.original_of(what_if, s), s.chosen)
        options = [
            (f"W1 · what-if ({what_if.alternative.code})", reporter.design_id(what_if)),
            (f"{s.chosen.alternative.uid} · best overall", reporter.design_id(s.chosen)),
        ]
        marked = chat_state.annotate(options, s)
        self.assertIn("the design under discussion", marked[0])
        self.assertIn("the original design", marked[1])
        self.assertIn("what-if of " + s.chosen.alternative.uid, chat_state.what_of(what_if, s))


class TestState(unittest.TestCase):
    """The state itself: kept in order, compacted, saved, and off with its flag."""

    def test_questions_are_compacted_not_dropped(self):
        """Past ``KEPT`` the oldest fold into one line that says which turns it covers."""
        state = ChatState()
        for n in range(1, chat_state.KEPT + 6):
            state.ask(n, f"question number {n} about the cost of heat")
        self.assertEqual(len(state.asked), chat_state.KEPT)
        self.assertTrue(state.earlier.startswith("T1-T5: "))
        self.assertIn("question number 1", state.earlier)
        text = chat_state._questions(state)
        self.assertIn("T1-T5", text)  # said, not dropped
        # The first two and the last ``RECENT`` stay word for word, the rest are cut short.
        self.assertIn(f"«question number {chat_state.KEPT + 5} about the cost of heat»", text)

    def test_figures_and_round_trip(self):
        """A repeated figure moves to the end; the state survives a save."""
        state = ChatState()
        state.mention("A1 · X", "A1", "X", "best overall", 1)
        state.mention("A1 · X", "A1", "X", "best overall", 3)  # its first turn stays
        for k in range(chat_state.NUMBERS + 2):
            state.figure(k, "A1", f"what {k}", f"{k} M€")
        state.figure(9, "A1", "what 3", "3 M€")
        self.assertEqual(len(state.numbers), chat_state.NUMBERS)
        self.assertEqual(state.numbers[-1]["what"], "what 3")
        again = ChatState.from_dict(state.to_dict())
        self.assertEqual(again, state)
        self.assertEqual(again.designs[0]["turn"], 1)
        self.assertEqual(ChatState.from_dict(None), ChatState())

    def test_limit_says_what_it_leaves_out(self):
        """A short limit drops figures and middle designs, and says how many are not shown."""
        _, s = designed()
        state = ChatState()
        for k, e in enumerate(s.candidates[:6]):
            state.mention(reporter.design_id(e), e.alternative.uid, e.alternative.code, "", k + 1)
        full = chat_state.text(state, s, "reading")
        short = chat_state.text(state, s, "reading", limit=200)
        self.assertLess(len(short), len(full))
        self.assertLessEqual(len(short), 200)
        if len(state.designs) > 4:
            self.assertIn("more not shown", short)

    def test_off(self):
        """``DIOSCURI_CHAT_STATE=0``: nothing is noted or shown; the which prompt is v1."""
        from gemini_agent import parameters

        with mock.patch.dict(os.environ, {"DIOSCURI_CHAT_STATE": "0"}):
            self.assertFalse(chat_state.on())
            state = ChatState(asked=[[1, "hello", ""]])
            self.assertEqual(chat_state.text(state, None), "")
            seen = []

            def reply(purpose, messages):
                seen.append(messages[0]["content"])
                return {"design": "unclear"}

            parameters.design_meant("the second one", ["A1 · x", "A2 · y"], ScriptedLLM(reply))
            self.assertTrue(seen[0].startswith("Dioscuri, which designs"))
            self.assertNotIn("marked with what the chat knows", seen[0])


if __name__ == "__main__":
    unittest.main()


class TestTurnLog(unittest.TestCase):
    """The user's messages, a numbered list of their own.

    5 Nov: "what were we discussing before the weather?" named the turn before that, and "which
    question did I ask right after the heat split?" the heat split itself: the questions came
    on one line with the state.
    """

    def test_one_line_a_turn_in_order(self):
        """One line a turn, in order, with what was done when not answered."""
        state = ChatState()
        for n, q in enumerate(["the heat split?", "what does GEMINI do?", "the weather?"], 1):
            state.ask(n, q, "declined as off-topic" if "weather" in q else "")
        text = chat_state.turns_text(state)
        lines = text.split("\n")
        self.assertIn("T4", lines[0])  # the message being answered
        self.assertEqual(lines[1], "T1: «the heat split?»")
        self.assertEqual(lines[2], "T2: «what does GEMINI do?»")
        self.assertEqual(lines[3], "T3: «the weather?» (declined as off-topic)")
        # The state no longer repeats them, unless asked to.
        self.assertNotIn("questions so far", chat_state.text(state, None, "answer"))

    def test_a_limit_keeps_the_first_two_and_the_latest(self):
        """A limit keeps the first two and the latest turns, and says how many it left out."""
        state = ChatState()
        for n in range(1, 21):
            state.ask(n, f"question number {n} about the cost of heat and the doublets")
        text = chat_state.turns_text(state, limit=600)
        self.assertLessEqual(len(text), 700)
        self.assertIn("T1:", text)
        self.assertIn("T2:", text)
        self.assertIn("T20:", text)
        self.assertIn("turns not shown", text)

    def test_the_turn_a_message_points_to_comes_with_its_neighbours(self):
        """Code finds the turn by a word only it has; the model reads before and after."""
        state = ChatState()
        for n, q in enumerate(
            ["What does it cost?", "Could we cool with outside air?", "Weather in Delft?"], 1
        ):
            state.ask(n, q)
        text = chat_state.turns_text(state, message="What came before the weather question?")
        self.assertIn("point to T3: «Weather in Delft?»; just before it: T2: «Could we", text)
        # Last, so the context budget's cut of the oldest lines keeps it.
        from gemini_agent.answer import Block, _cut_lines

        cut = _cut_lines(Block("turns", "history", text), 300).text
        self.assertIn("point to T3", cut.split("\n")[-1])
        state.ask(4, "And the cost with a store?")
        self.assertEqual(chat_state.pointed(state, "What does it cost now?"), [])  # two turns

    def test_off_and_empty(self):
        """Nothing without turns or with the state off."""
        self.assertEqual(chat_state.turns_text(None), "")
        self.assertEqual(chat_state.turns_text(ChatState()), "")
        with mock.patch.dict(os.environ, {"DIOSCURI_CHAT_STATE": "0"}):
            self.assertEqual(chat_state.turns_text(ChatState(asked=[[1, "hi", ""]])), "")

    def test_a_cut_keeps_the_head_and_the_latest_turns(self):
        """The context budget cuts the oldest turns, never the head."""
        from gemini_agent.answer import Block, _cut_lines

        text = "head\n" + "\n".join(f"turn {n}: «q{n}»" for n in range(1, 40))
        cut = _cut_lines(Block("turns", "history", text), 120).text
        self.assertTrue(cut.startswith("head\n…"))
        self.assertTrue(cut.endswith("turn 39: «q39»"))
        self.assertLessEqual(len(cut), 120)


class TestRunOfAPick(unittest.TestCase):
    """A pick of a later search says its run ("best overall of run B": "the new design")."""

    def test_a_pick_of_the_second_search_says_run_b(self):
        """With one search no run is said; with two, the second's picks say run B."""
        _, s = designed()
        pick = next(e for e in s.candidates if e.alternative.picks)
        self.assertNotIn(" of run ", chat_state.what_of(pick, s))
        s.searches = list(s.searches) + [{"candidates": [pick], "brief": {}}]
        s.searches[0] = dict(s.searches[0], candidates=[])
        self.assertIn(" of run B", chat_state.what_of(pick, s))


class TestSearchedAgain(unittest.TestCase):
    """A new search's pick kept as a what-if is not a what-if of itself."""

    def test_not_its_own_original(self):
        """5 Nov: "T2: ran B1 (what-if of B1: ..., searched again)"."""
        from unit_test.gemini_agent.test_clarify import READING, chat_model

        _, s = designed()
        reading = dict(
            READING,
            changes=[{"key": "heat_return_c", "value": 50, "quote": "50 °C heating return"}],
            steps=[{"do": "what_if", "quote": "Design it again", "changes": []}],
        )
        run(
            Agent(chat_model([("50 °C", reading)], {})), s, "Design it again, 50 °C heating return."
        )
        for e in s.ledger:
            base = chat_state.original_of(e, s)
            if base is not None:
                self.assertNotEqual(reporter.design_id(base), reporter.design_id(e))
        self.assertNotIn("what-if of B1", chat_state.text(s.state, s, "answer"))


class TestClaimsReadTheChat(unittest.TestCase):
    """A reply that cites the turn log is checked against the conversation first."""

    def test_turns_cited_means_history_first(self):
        """5 Nov: "what was the first thing I asked?" was removed as unsupported."""
        from gemini_agent import answer as answering
        from gemini_agent import claims
        from gemini_agent.llm import ScriptedLLM

        agent = Agent(ScriptedLLM(lambda p, m: {}, model="qwen3.5:9b"))
        agent._message = "What was the first thing I asked?"
        agent._calls = []
        reply = answering.Reply("You first asked about the heat demand.", used=["turns"])
        pack = [answering.Block("turns", "history", "T1: «the heat demand?»")]
        seen = {}

        def fake(llm, text, blocks, used, draft=""):
            seen["used"] = list(used)
            return claims.ClaimCheck(text=text)

        with mock.patch.object(claims, "check", fake), mock.patch.object(
            Agent, "_facts_for_claims", lambda self, text, pack: []
        ):
            list(agent._check_claims(agent.llm, reply, pack, ""))
        self.assertIn("history", seen["used"])


class TestRelation(unittest.TestCase):
    """The model says before or after; code picks the turn."""

    def test_before_picks_the_turn_before(self):
        """5 Nov: "what were we discussing before the weather?" named the heat store."""
        from gemini_agent.llm import ScriptedLLM

        state = ChatState()
        for n, q in enumerate(["What does it cost?", "Could we cool with outside air?"], 1):
            state.ask(n, q)
        state.ask(3, "Weather in Delft?", "declined as off-topic")
        seen = []

        def reply(purpose, messages):
            seen.append(purpose)
            return {"turn": "before"}

        llm = ScriptedLLM(reply, model="qwen3.5:9b")
        asked, _ = chat_state.relation(state, "What came before the weather question?", llm)
        self.assertEqual(asked, "T2: «Could we cool with outside air?»")
        self.assertEqual(seen, ["chat_turn"])
        # No turn pointed to: no call.
        self.assertEqual(chat_state.relation(state, "And the reinjection?", llm)[0], "")
        self.assertEqual(seen, ["chat_turn"])


class TestAskedTurnInHistory(unittest.TestCase):
    """The turn a question about the chat asks about ends the answerer's history."""

    def test_before_the_weather(self):
        """The model reads "before"; the history says the turn before the weather one."""
        from unit_test.gemini_agent.test_clarify import chat_model

        _, s = designed()
        seen = {}
        base = chat_model([], seen)

        def reply(purpose, messages):
            if purpose == "chat_turn":
                return {"turn": "before"}
            return base._script(purpose, messages)

        agent = Agent(ScriptedLLM(reply, model="qwen3.5:9b"))
        for m in (
            "Could we cool with outside air instead of chillers?",
            "What's the weather in Delft tomorrow?",
            "Back to the plant: what did we discuss before the weather?",
        ):
            run(agent, s, m)
        prompt = seen["answer"][-1]
        self.assertIn("asks about is T2: «Could we cool with outside air", prompt)
