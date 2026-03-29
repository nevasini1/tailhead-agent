#!/usr/bin/env python3
"""
Structured project report PDF (fpdf2). Some viewers show fpdf2 PDFs as blank.

Prefer docs/trailhead-agent-project-report.html + Print to PDF, or
scripts/print_docs_to_pdf.ps1 (Windows).

Requires: pip install -e ".[docs]"
  python scripts/generate_project_report_pdf.py [--out PATH]
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


class ReportPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}  |  Project report  |  {__version__}", align="C")
        self.set_text_color(0, 0, 0)


def _w(pdf: FPDF) -> float:
    return float(pdf.epw)


def _h1(pdf: FPDF, text: str) -> None:
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(_w(pdf), 6.5, text)
    pdf.set_font("Helvetica", "", 9)


def _h2(pdf: FPDF, text: str) -> None:
    pdf.ln(2.5)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.multi_cell(_w(pdf), 5.5, text)
    pdf.set_font("Helvetica", "", 9)


def _p(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(_w(pdf), 4.5, text)
    pdf.ln(0.4)


def _bul(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(_w(pdf), 4.5, "- " + text)
    pdf.ln(0.25)


def _mono(pdf: FPDF, lines: list[str]) -> None:
    pdf.set_font("Courier", "", 7.8)
    for line in lines:
        pdf.multi_cell(_w(pdf), 3.6, line)
    pdf.set_font("Helvetica", "", 9)
    pdf.ln(0.8)


def build_report_pdf(out: Path) -> None:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 7, "trailhead-agent", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Project report: architecture, impact, novelties, research positioning", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 5, f"Version {__version__}  |  Generated UTC {gen}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.ln(3)
    _p(
        pdf,
        "Product/systems narrative derived from README.md and DESIGN.md. Not peer-reviewed research; "
        "novelties are engineering and workflow design unless stated otherwise.",
    )

    _h1(pdf, "1. Executive summary")
    _p(
        pdf,
        "CLI tool: (1) Playwright discovers Trailhead module/unit links under URL policy; "
        "(2) an LLM ranks and orders units from natural-language intent with Pydantic-validated JSON "
        "and href allowlisting; (3) optional human-in-the-loop org helpers (checklists, prepare, sf hooks). "
        "Explicit non-goals: quiz automation, credential abuse, inventing URLs.",
    )
    _bul(pdf, "Orchestration: mandatory LangGraph StateGraph (prepare, planner, rank, repair, finalize).")
    _bul(pdf, "Observability: trace_id, duration_ms, agent_version; optional E2E .webm + JSON + HTML gallery.")

    _h1(pdf, "2. Problem space and stakeholders")
    _mono(
        pdf,
        [
            "Learners        Prioritize units (e.g. hands-on only) without manual TOC scanning",
            "Demos / L&D     Reproducible recordings + structured artifacts for walkthroughs",
            "Operators       Safe URLs, exit codes, CI headless, log-json for pipelines",
            "Future org work Extensible OrgExecutor without coupling ranking to Salesforce today",
        ],
    )

    _h1(pdf, "3. System overview")
    _mono(
        pdf,
        [
            "CLI          Args/env, --json, --log-json, trace_id",
            "Validation   HTTPS + host allowlist + /content/learn/ path",
            "Session      Chromium; persistent profile or optional password login",
            "Discovery    DOM scrape; scroll/pagination envs; DiscoveryError + hints",
            "LLM agent    Schema + allowlist; optional planner LLM; repair pass on failure",
            "Org          NoopOrgExecutor / CliOrgExecutor; org doctor | checklist | prepare",
        ],
    )
    _h2(pdf, "Data flow")
    _mono(
        pdf,
        [
            "start_url -> collect_units_for_seed -> UnitRef[]",
            "           -> LangGraph ranking -> ordered plan (title, href, reason)",
            "           -> optional walk_ranked / open-unit navigation for E2E video",
        ],
    )

    _h1(pdf, "4. Impact")
    _h2(pdf, "4.1 Intended positive impact")
    _bul(pdf, "Reduces cognitive load: intent-ordered study queue vs flat TOC.")
    _bul(pdf, "Machine-readable plans (JSON) for tooling and integration.")
    _bul(pdf, "Demo transparency: stderr narration, phased title cards, e2e-report.html, manifest.")
    _bul(pdf, "Safety framing: documented threat model; no assessment automation.")
    _h2(pdf, "4.2 Limits")
    _bul(pdf, "DOM drift and LLM vendor uptime/cost constrain reliability and TCO.")
    _bul(pdf, "No formal human benchmark of ranking quality in-repo.")
    _bul(pdf, "Deep Salesforce automation deferred to v2 roadmap.")

    _h1(pdf, "5. Novelties and differentiators")
    _bul(
        pdf,
        "Scrape vs reason split: model sees structured candidates only; cannot emit non-allowlisted hrefs "
        "(reduces prompt-injection surface from arbitrary page text).",
    )
    _bul(pdf, "Multi-step LangGraph pipeline with conditional repair after validation failure.")
    _bul(pdf, "E2E storytelling: plan vs org clips, friendly .webm names, primary vs session roles, tail dwell.")
    _bul(pdf, "Discovery treated as product: blockers, pagination, degenerate TOC errors with operator hints.")
    _bul(pdf, "Org boundary: human-in-the-loop Playground; explicit contrast with plan in recordings/docs.")

    _h1(pdf, "6. Research positioning")
    _p(
        pdf,
        "This repository does not claim new ML architectures or published empirical benchmarks. "
        "It applies known techniques: structured LLM outputs, grounding to retrieved links, web automation under policy.",
    )
    _mono(
        pdf,
        [
            "Closest areas   Structured generation; tool grounding; safe web agents; ed-tech integrity policy",
            "Gaps vs paper   No user study; no fixed public Trailhead snapshot dataset in-repo",
            "To formalize     Gold rankings, ablations (planner/repair), latency/token metrics",
        ],
    )

    _h1(pdf, "7. Risks, ethics, and failure modes")
    _bul(pdf, "Trailhead DOM changes: fewer links; tune waits, scroll rounds, selectors.")
    _bul(pdf, "URL policy mitigates open redirect / SSRF class issues for start_url.")
    _bul(pdf, "Academic dishonesty: explicit non-support for auto-answers; scope documented.")
    _bul(pdf, "sf subprocess: argv lists, no shell=True; org errors surfaced with exit codes.")

    _h1(pdf, "8. Roadmap")
    _bul(pdf, "Richer OrgExecutor: deploy, Tooling API, guided org browser.")
    _bul(pdf, "Optional LLM checklist extraction from unit HTML (still human-in-the-loop).")
    _bul(pdf, "Disk cache keyed by (start_url, intent_hash) for CI cost control.")
    _bul(pdf, "Optional Pydantic settings migration for environment configuration.")

    _h1(pdf, "9. Conclusion")
    _p(
        pdf,
        "trailhead-agent is a production-leaning assistant CLI: strict scope, layered architecture, "
        "observable runs, and demo-grade artifacts. Impact targets learner navigation and team clarity; "
        "novelty is primarily systems integration, safety boundaries, and operability rather than new algorithms.",
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.set_compression(False)
    pdf.output(str(out))


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate structured project report PDF.")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs" / "fpdf-output" / "trailhead-agent-project-report.pdf",
        help="Output PDF path (default under docs/fpdf-output/ so main docs/*.pdf stay browser-printed)",
    )
    args = ap.parse_args()
    build_report_pdf(args.out.resolve())
    print(f"Wrote {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
