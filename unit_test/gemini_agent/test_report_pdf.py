"""The operator's report: a design of a conversation as an A4 PDF (scripted model, no GPU)."""

import io
import unittest
from datetime import date

try:
    from pypdf import PdfReader
except ImportError:  # the reader is only needed to look inside the PDF
    PdfReader = None
try:
    from fastapi.testclient import TestClient
except ImportError:  # the server is optional for the model and simulator tests
    TestClient = None

from gemini_agent import Agent, engine, parameters, reliability, report_pdf, reporter
from gemini_agent.agent import Session
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import FULL_BRIEF, fake_intake, run
from unit_test.gemini_agent.test_server import through_confirm

FAILURE = "What if the ESP of doublet 1 fails from 10 to 24 January?"


def pages_text(pdf: bytes) -> list:
    """Return each page's text."""
    return [p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages]


@unittest.skipIf(PdfReader is None, "pypdf is not installed")
class TestReportPdf(unittest.TestCase):
    """The report of the chosen design: its pages, its footers, N-1 and the what-ifs."""

    @classmethod
    def setUpClass(cls):
        """Design the district, run a failure what-if on the design, build the report once."""
        cls.s = Session()
        run(Agent(ScriptedLLM(fake_intake)), cls.s, FULL_BRIEF)
        cls.entry = cls.s.chosen
        fail = parameters.Failure(unit="doublet 1", first=9, last=23)
        result = reliability.run_failure(cls.entry, [fail], cls.s.assumptions)
        result["message"] = FAILURE  # as the agent keeps it (agent._failure)
        cls.s.failures.append(result)
        cls.pdf = report_pdf.build(cls.s, today=date(2026, 10, 31))
        cls.text = pages_text(cls.pdf)

    def test_a_valid_pdf_of_a_few_pages(self):
        """A PDF of 4 to 8 pages."""
        self.assertTrue(self.pdf.startswith(b"%PDF"))
        self.assertGreaterEqual(len(self.text), 4)
        self.assertLessEqual(len(self.text), 8)

    def test_the_design_and_the_date_on_every_page(self):
        """Every page's footer names the design and the date."""
        name = reporter.design_id(self.entry)
        for i, page in enumerate(self.text, 1):
            self.assertIn(name, page, f"page {i}")
            self.assertIn("31 October 2026", page, f"page {i}")
            self.assertIn(f"Page {i} of {len(self.text)}", page)

    def test_it_says_whether_the_plan_is_n1(self):
        """The firm capacity says N-1 in words, and lists every one-unit-out case."""
        whole = "\n".join(self.text)
        self.assertIn("N-1", whole)
        firm = reporter.firm_view(self.entry)
        verdict = "This plan is N-1" if not firm["short"] else "This plan is NOT N-1"
        self.assertIn(verdict, whole)
        for case in firm["cases"]:
            self.assertIn(case["unit"][1:], whole)

    def test_the_sections_and_the_what_if(self):
        """Each section is there, with the failure the chat ran and every check."""
        whole = " ".join(" ".join(self.text).split())
        for title in (
            "How it runs over the year",
            "Month by month",
            "Firm capacity",
            "Failures and maintenance",
            "Limits to watch",
            "Assumptions and sources",
        ):
            self.assertIn(title, whole)
        self.assertIn(FAILURE, whole)
        for check in self.entry.verification.checks:
            self.assertIn(" ".join(check.name.split()[:3]), whole)

    def test_the_co2_by_unit(self):
        """Section 2 splits the year's CO2 by unit; the parts add up to the cover's total."""
        whole = " ".join(" ".join(self.text).split())
        self.assertIn("CO₂ by unit over the year", whole)
        y = self.entry.year
        parts = report_pdf.co2_parts(y)
        self.assertTrue(parts)
        self.assertAlmostEqual(sum(p[4] for p in parts), y.co2_t["total"], places=6)
        for _, name, _, _, t in parts:
            self.assertIn(f"{name} ", whole)
        self.assertIn(f"All units {report_pdf.num(y.co2_t['total'], 0)} 100%", whole)

    def test_the_yearly_service_windows(self):
        """A design run with the yearly service on lists each unit's window in section 4."""
        s = Session()
        run(Agent(ScriptedLLM(fake_intake)), s, FULL_BRIEF)
        s.chosen.brief.rules = dict(s.chosen.brief.rules or {}, planned_service=1.0)
        entry = engine.reprice(s.chosen, s.assumptions)
        self.assertTrue(entry.year.service)
        entry.alternative = s.chosen.alternative
        s.chosen = entry
        s.ledger.append(entry)
        whole = " ".join(
            " ".join(pages_text(report_pdf.build(s, today=date(2026, 10, 31)))).split()
        )
        self.assertIn("Yearly service built into the year", whole)
        self.assertIn("Heat pump", whole)

    def test_another_design_by_id_and_unknown_ones(self):
        """A design is picked by its id; an unknown id, or none chosen yet, is a KeyError."""
        name = reporter.design_id(self.entry)
        self.assertTrue(report_pdf.build(self.s, name).startswith(b"%PDF"))
        with self.assertRaises(KeyError):
            report_pdf.build(self.s, "Z9 · no such design")
        with self.assertRaises(KeyError):
            report_pdf.build(Session())
        # The code as a file name: "1D-BO-EC@3500-N1" saves as "dioscuri-1D-BO-EC-3500-N1.pdf".
        code = self.entry.alternative.code.replace("@", "-")
        self.assertEqual(report_pdf.filename(self.entry), f"dioscuri-{code}.pdf")


def text_boxes(fig) -> list:
    """Return each text of a laid-out page as (left, top, right, bottom, text), in inches.

    Measured as the PDF draws it: the width from the font's metrics (``report_pdf._width_in``),
    the height a line of DejaVu Sans takes (its ascent 0.93 and descent 0.23 of the size).
    """
    out = []
    for t in fig.texts:
        text = t.get_text().replace(r"\$", "$")
        if not text.strip():
            continue
        size = t.get_fontsize()
        w = report_pdf._width_in(text, size, t.get_fontweight() == "bold")
        fx, fy = t.get_position()
        x, y = fx * report_pdf.PAGE_W, (1 - fy) * report_pdf.PAGE_H
        left = {"left": x, "right": x - w}.get(t.get_ha(), x - w / 2)
        em = size / 72
        top = {"top": y, "baseline": y - 0.93 * em, "center": y - 0.58 * em}[t.get_va()]
        out.append((left, top, left + w, top + 1.16 * em, text))
    return out


class TestLongTitles(unittest.TestCase):
    """A what-if's long name and a long project name stay on the page and off each other."""

    LONG = "W3 (A1 with heat store and 5 MWp solar, gas price 45 €/MWh)"

    @classmethod
    def setUpClass(cls):
        """Lay out the scripted district's design once, renamed as a long what-if."""
        cls.s = Session()
        run(Agent(ScriptedLLM(fake_intake)), cls.s, FULL_BRIEF)
        cls.s.chosen.alternative.uid = cls.LONG
        cls.s.project.name = (
            "Trias Westland district heating and cooling, phase 2 extension to the glasshouses"
        )
        cls.did = reporter.design_id(cls.s.chosen)
        cls.doc = report_pdf.layout(cls.s, today=date(2026, 11, 5))

    def test_every_line_inside_the_page_and_none_overlapping(self):
        """Each text within the margins and the page; no two texts drawn over each other."""
        for page, fig in enumerate(self.doc.figs, 1):
            boxes = text_boxes(fig)
            for left, top, right, bottom, text in boxes:
                where = f"page {page}: {text[:50]!r}"
                self.assertGreaterEqual(left, report_pdf.LEFT - 1e-6, where)
                self.assertLessEqual(right, report_pdf.PAGE_W - report_pdf.RIGHT + 1e-6, where)
                self.assertGreaterEqual(top, 0.0, where)
                self.assertLessEqual(bottom, report_pdf.PAGE_H, where)
            for i, a in enumerate(boxes):
                for b in boxes[i + 1 :]:
                    across = min(a[2], b[2]) - max(a[0], b[0])
                    down = min(a[3], b[3]) - max(a[1], b[1])
                    self.assertFalse(
                        across > 0.005 and down > 0.005,
                        f"page {page}: {a[4][:40]!r} over {b[4][:40]!r}",
                    )

    def test_the_whole_name_on_the_cover_and_every_footer(self):
        """The cover wraps the id over two lines; each footer carries all of it."""
        self.assertIn(self.LONG, self.did)
        cover = [b for b in text_boxes(self.doc.figs[0]) if 1.6 < b[1] < 2.6]
        lines = [b[4] for b in sorted(cover, key=lambda b: b[1]) if b[4] in self.did]
        self.assertEqual(len(lines), 2)
        self.assertEqual(" ".join(lines), self.did)
        for page, fig in enumerate(self.doc.figs, 1):
            foot = [b for b in text_boxes(fig) if b[1] > report_pdf.PAGE_H - 0.6]
            name = " ".join(b[4] for b in sorted(foot, key=lambda b: b[1]) if b[0] < 1.0)
            self.assertEqual(name, self.did, f"page {page}")
            self.assertTrue(any("Page " in b[4] and "5 November 2026" in b[4] for b in foot))

    def test_a_word_wider_than_its_line_is_cut(self):
        """A code with no spaces wider than the line is cut after its hyphens, never runs past."""
        code = "-".join(["1D-HP-EC@3000-N1-FC"] * 8)
        lines = report_pdf.wrap(f"Design {code} here", 2.5, 9.0, bold=True)
        self.assertGreater(len(lines), 2)
        for line in lines:
            self.assertLessEqual(report_pdf._width_in(line, 9.0, True), 2.5 + 1e-9)
        self.assertEqual("".join(lines).replace(" ", ""), f"Design{code}here")
        self.assertTrue(lines[1].endswith("-"), lines)


@unittest.skipIf(TestClient is None, "fastapi is not installed")
class TestReportRoute(unittest.TestCase):
    """GET /api/report.pdf downloads the report; an unknown design is a 404."""

    def test_download_and_unknown(self):
        """The chosen design by default, as an attachment; unknown ids and threads are 404."""
        from gemini_agent.server import create_app

        client = TestClient(create_app(Agent(ScriptedLLM(fake_intake))))
        through_confirm(client, {"threadId": "report1", "message": FULL_BRIEF})
        r = client.get("/api/report.pdf", params={"threadId": "report1"})
        self.assertEqual(r.status_code, 200, r.text[:200])
        self.assertEqual(r.headers["content-type"], "application/pdf")
        self.assertRegex(
            r.headers["content-disposition"], r'^attachment; filename="dioscuri-[\w.-]+\.pdf"$'
        )
        self.assertTrue(r.content.startswith(b"%PDF"))
        missing = client.get("/api/report.pdf", params={"threadId": "report1", "id": "Z9 · no"})
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            client.get("/api/report.pdf", params={"threadId": "nobody"}).status_code, 404
        )


if __name__ == "__main__":
    unittest.main()
