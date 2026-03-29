#!/usr/bin/env python3
"""
Build engineering-style PDF reference under docs/ (fpdf2).

Note: Some PDF viewers draw fpdf2 Helvetica PDFs as blank. Prefer:
  docs/trailhead-agent-engineering-reference.html + browser Print to PDF, or
  powershell -File scripts/print_docs_to_pdf.ps1 (Windows Edge).

Usage (from repo root):
  pip install -e ".[docs]"
  python scripts/generate_engineering_pdf.py [--out PATH]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fpdf import FPDF  # noqa: E402

from trailhead_agent import __version__  # noqa: E402


class EngPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}  |  trailhead-agent {__version__}", align="C")
        self.set_text_color(0, 0, 0)


def _w(pdf: FPDF) -> float:
    return float(pdf.epw)


def _h1(pdf: FPDF, text: str) -> None:
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(_w(pdf), 7, text)
    pdf.set_font("Helvetica", "", 9)


def _h2(pdf: FPDF, text: str) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(_w(pdf), 6, text)
    pdf.set_font("Helvetica", "", 9)


def _p(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(_w(pdf), 4.6, text)
    pdf.ln(0.5)


def _bul(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(_w(pdf), 4.6, "- " + text)
    pdf.ln(0.3)


def _mono(pdf: FPDF, lines: list[str]) -> None:
    pdf.set_font("Courier", "", 8)
    for line in lines:
        pdf.multi_cell(_w(pdf), 3.8, line)
    pdf.set_font("Helvetica", "", 9)
    pdf.ln(1)


def build_pdf(out: Path) -> None:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    pdf = EngPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "trailhead-agent", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Engineering reference (CLI, pipeline, recording)", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Version {__version__}   |   Generated UTC {gen}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    _h1(pdf, "1. Scope")
    _bul(pdf, "IN: Playwright discovery of Trailhead /content/learn/ unit links; LLM ordering under user intent (allowlisted hrefs); optional ranked URL walk; org checklist / prepare helpers; Playwright .webm + JSON artifacts.")
    _bul(pdf, "OUT: Quiz submission, auto Launch Playground, hands-on challenge solving, arbitrary non-Trailhead crawling.")

    _h1(pdf, "2. Runtime stack")
    _mono(
        pdf,
        [
            "Python 3.11+",
            "playwright (Chromium)",
            "langgraph + langchain-core (ranking graph)",
            "pydantic (LLM JSON validation)",
            "openai SDK (+ optional anthropic / google-genai extras)",
        ],
    )

    _h1(pdf, "3. Entrypoints")
    _p(pdf, "Console: trailhead-agent (setuptools script -> trailhead_agent.cli:entrypoint)")
    _p(pdf, "Module: python -m trailhead_agent <subcommand>")
    _mono(
        pdf,
        [
            "doctor",
            "plan [--artifacts-dir|--save-e2e] [--walk-ranked N] [--json] ...",
            "open-unit [--visit-count N] ...",
            "auth",
            "org doctor | org checklist | org prepare",
        ],
    )

    _h1(pdf, "4. CLI matrix")
    _mono(
        pdf,
        [
            "doctor              env/keys, executor, sf on PATH, recording dir hint",
            "plan                discovery + LangGraph rank + optional walk; e2e JSON + .webm",
            "open-unit           same rank path; goto first N ranked units only",
            "auth                persistent Chromium profile for SSO",
            "org doctor          sf org display JSON summary",
            "org checklist       Markdown/JSON steps from plan JSON or unit href",
            "org prepare         noop/cli executor checks; optional --open-playground browser",
        ],
    )

    _h1(pdf, "5. plan / open-unit shared flags")
    _mono(
        pdf,
        [
            "--config PATH              YAML browser/selectors",
            "--artifacts-dir DIR        mkdir; sets TRAILHEAD_RECORD_VIDEO_DIR",
            "--save-e2e                 shorthand artifacts/e2e",
            "--no-recording-demo-browser -> TRAILHEAD_RECORDING_DEMO_AUTO=0",
            "--start-url / --intent     or TRAILHEAD_* env",
        ],
    )

    _h1(pdf, "6. Data flow: plan while recording")
    _mono(
        pdf,
        [
            "1. demo_plan_what_you_asked (titlecard P1)",
            "2. collect_units_for_seed(page, start_url)  # DOM scrape + scroll/pagination",
            "3. demo_after_discovery (titlecard P2)",
            "4. select_and_rank_units -> run_ranking_graph",
            "5. demo_llm_ranking_output_slide (titlecard P3 ordered list)",
            "6. demo_after_llm_rank (titlecard P4 next steps)",
            "7. walk_ranked_units_for_recording (titlecard P5 per visit) if --walk-ranked>0",
            "8. _plan_recording_epilogue  # live Trailhead dwell + end card",
        ],
    )

    _h1(pdf, "6b. Title cards when recording")
    _mono(
        pdf,
        [
            "plan: P1 inputs (start_url, intent, label) | P2 discovery | P3 LLM ordered list",
            "      P4 next steps | P5 per ranked walk step | end card on live Trailhead",
            "org prepare: 5 slides (plan vs org, recording outline, Trailhead steps,",
            "             sf/doctor, checklists) then module URL + corner tag + end card",
        ],
    )

    _h1(pdf, "7. LangGraph ranking")
    _mono(
        pdf,
        [
            "START -> prepare   (payload: intent + candidates + ranking_user_message_context)",
            "      -> planner   (optional if LLM_PLANNER_PHASE=1)",
            "      -> rank_primary",
            "      -> rank_repair OR finalize  (repair if needs_repair + LLM_RANKING_REPAIR)",
            "      -> END",
        ],
    )

    _h1(pdf, "8. Key modules")
    _mono(
        pdf,
        [
            "cli.py              argparse, trace_id, artifacts-dir bootstrap",
            "runner.py           run_dry_plan, open_first_ranked_unit, walk, epilogue",
            "discovery.py        unit link extraction, DiscoveryError",
            "llm_agent.py        provider calls, select_and_rank_units",
            "ranking_graph.py    LangGraph compile + run_ranking_graph",
            "session.py          TrailheadBrowser, Playwright context/video path",
            "e2e_artifacts.py    JSON writes, friendly .webm rename, manifest",
            "e2e_viewer.py       e2e-report.html",
            "demo_titlecards.py  data-URL slides (plan phases, org x5)",
            "demo_narration.py   stderr [trailhead-agent] trace",
            "demo_browser.py     headed/slow_mo/viewport bootstrap when recording",
            "org_commands.py     prepare / checklist / doctor handlers",
        ],
    )

    _h1(pdf, "9. Artifact files")
    _mono(
        pdf,
        [
            "plan-primary.webm / open-unit-primary.webm / org-prepare.webm",
            "e2e-plan-<trace>.json, e2e-plan-latest.json",
            "e2e-open-unit-latest.json (open-unit)",
            "e2e-org-prepare-latest.json, e2e-manifest.json, e2e-report.html",
        ],
    )

    _h1(pdf, "10. Environment variables")
    _mono(
        pdf,
        [
            "LLM_PROVIDER, OPENAI_* | GOOGLE_* / GEMINI_* | ANTHROPIC_*",
            "LLM_PLANNER_PHASE, LLM_RANKING_REPAIR",
            "TRAILHEAD_START_URL, TRAILHEAD_INTENT",
            "TRAILHEAD_RECORD_VIDEO_DIR, TRAILHEAD_RECORDING_DEMO_AUTO",
            "TRAILHEAD_DEMO_TITLECARDS, TRAILHEAD_DEMO_TITLECARD_MS, TRAILHEAD_DEMO_TITLECARD_RANK_MAX",
            "TRAILHEAD_DEMO_NARRATION, TRAILHEAD_DEMO_SLOW_MO_MS, TRAILHEAD_AGENT_HEADLESS",
            "TRAILHEAD_PLAN_RECORDING_TAIL_MIN_MS, TRAILHEAD_ORG_PREPARE_RECORDING_MIN_MS",
            "TRAILHEAD_PAGE_SETTLE_MS, TRAILHEAD_DISCOVERY_* , TRAILHEAD_SHELL_WAIT_TIMEOUT_MS",
            "TRAILHEAD_ORG_EXECUTOR, TRAILHEAD_SF_ORG_ALIAS",
        ],
    )

    _h1(pdf, "11. Errors / exit codes")
    _mono(
        pdf,
        [
            "DiscoveryError      bad/empty scrape; details + hints on stderr",
            "UrlValidationError  start_url host/path policy",
            "LLMProviderError    API/schema/ranking failures",
            "ConfigurationError  YAML / env misconfig",
            "OrgExecutorError    org prepare/deploy failures",
            "KeyboardInterrupt   130",
        ],
    )

    _h1(pdf, "12. Verification")
    _mono(pdf, ["pytest tests", "TRAILHEAD_DEMO_NARRATION=0 default in tests/conftest.py"])

    _h1(pdf, "13. Regenerate PDFs")
    _mono(
        pdf,
        [
            "Preferred: open docs/trailhead-agent-engineering-reference.html -> Ctrl+P -> Save as PDF",
            "Windows: powershell -File scripts/print_docs_to_pdf.ps1  (Edge headless from HTML)",
            "Optional fpdf2: pip install -e \".[docs]\" ; python scripts/generate_engineering_pdf.py",
        ],
    )

    _h2(pdf, "14. Demo recording contract")
    _p(
        pdf,
        "Example used for contract clips: module apex_database, intent 'Hands-on Apex only', walk 2, "
        "org prepare with same start_url and TRAILHEAD_RECORD_VIDEO_DIR pointing at artifacts dir.",
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.set_compression(False)
    pdf.output(str(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs" / "fpdf-output" / "trailhead-agent-engineering-reference.pdf",
        help="Output PDF path (default under docs/fpdf-output/ so main docs/*.pdf stay browser-printed)",
    )
    args = ap.parse_args()
    build_pdf(args.out.resolve())
    print(f"Wrote {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
