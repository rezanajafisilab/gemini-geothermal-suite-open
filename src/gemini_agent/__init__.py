"""Dioscuri agent: designs geothermal district heating and cooling on top of GEMINI.

A small local model reads each request; typed tools (GEMINI's well solve with the team's fixes,
Dioscuri's plant model over every day of the year) compute every number; a verifier checks the
challenge's caps; a local model writes the reply from a checked draft. See README.md
and the decision records in hackathon/docs/decisions/.
"""

from gemini_agent.agent import CHALLENGE_PROJECT, EXAMPLE_PROJECT, Agent, Session

__all__ = ["Agent", "Session", "CHALLENGE_PROJECT", "EXAMPLE_PROJECT"]
