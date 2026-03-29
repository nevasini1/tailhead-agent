"""
Human-facing copy for ``e2e-org-prepare-latest.json`` (optional ``demo_guide`` object).

Written when ``org prepare`` updates that JSON; consumers can read it from the file (not shown in ``e2e-report.html``).
"""

from __future__ import annotations

from typing import Any


def build_org_prepare_demo_guide(*, start_url: str) -> dict[str, Any]:
    su = (start_url or "").strip()
    return {
        "schema_version": 1,
        "purpose": (
            "This file describes one optional step in a Trailhead demo: opening the module in a browser "
            "after you already have (or will show) a ranked plan. It is not the LLM ranking step."
        ),
        "elevator_pitch": (
            "org prepare --open-playground only opens Trailhead in Chromium and records a short clip. "
            "Five on-screen slides explain plan vs org, what you will see, your Playground steps, "
            "sf CLI / org doctor, and checklist commands; then you see the real module page. "
            "You still sign in and click Launch Playground yourself."
        ),
        "what_to_play": {
            "file": "org-prepare.webm",
            "hint": "Play this after or beside plan-primary.webm. Open e2e-report.html to preview both.",
        },
        "timeline_in_the_video": [
            "Slides 1-5: full-screen text — plan vs org, recording outline, Trailhead steps, sf/doctor, checklists.",
            "Then: this start URL loads in the browser, we wait and smooth-scroll so the UI is visible.",
            "Recording ends; the human continues in Trailhead and Salesforce outside the tool.",
        ],
        "contrast_with_plan": {
            "plan_command": "trailhead-agent plan --artifacts-dir <DIR> --start-url ... --intent ...",
            "plan_delivers": (
                "Ranked unit list in e2e-plan-latest.json + plan-primary.webm "
                "(inputs slide, discovery, dedicated LLM ordered-output slide, next-steps slide, optional ranked walk)."
            ),
            "org_prepare_delivers": "org-prepare.webm + this JSON — browser + narrative for hands-on / Playground, not ranking.",
        },
        "say_to_the_room": [
            "First we ran plan: the agent scraped Trailhead and the LLM ordered units — that is plan-primary.webm and e2e-plan-latest.json.",
            "Now this shorter clip is org prepare: same repo, different job — we only open the module so I can Launch Playground and do labs myself.",
            "Nothing here clicks Launch Playground or submits quizzes; it is intentionally human-in-the-loop.",
            "For step-by-step org work tied to the ranked list, we use org checklist with the plan JSON.",
        ],
        "try_next_commands": {
            "checklist_from_plan": (
                "trailhead-agent org checklist --plan-json .\\<your-artifacts-dir>\\e2e-plan-latest.json"
            ),
            "doctor_if_sf": "trailhead-agent org doctor --json",
            "full_folder_view": "Open e2e-report.html in the same folder as this file.",
        },
        "this_run_start_url": su,
        "faq": [
            {
                "q": "Why is playground_ready false?",
                "a": "Default executor is Noop — it does not call Salesforce. Set TRAILHEAD_ORG_EXECUTOR=cli and install sf for real checks.",
            },
            {
                "q": "Do I need org prepare if I only care about the study order?",
                "a": "No. plan + e2e-plan-latest.json is enough. org prepare is for demos that include opening Trailhead / talking about Playground.",
            },
            {
                "q": "Where is the ranked list?",
                "a": "In e2e-plan-latest.json (units[].title, href, reason) from a plan run in the same artifacts directory.",
            },
        ],
    }
