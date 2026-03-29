"""
Full-screen HTML title cards (data URLs) during Playwright recording so .webm demos
label phases: plan uses Phase 1 inputs, Phase 2 discovery, Phase 3 LLM ordered output,
Phase 4 next steps, Phase 5 ranked walk; org prepare uses five purple intro slides.

On by default whenever video recording is active (TRAILHEAD_RECORD_VIDEO_DIR / --artifacts-dir).
Set TRAILHEAD_DEMO_TITLECARDS=0 to disable. Optional dwell: TRAILHEAD_DEMO_TITLECARD_MS (default 2800).
Cap ranked lines on the LLM slide with TRAILHEAD_DEMO_TITLECARD_RANK_MAX (default 18).
"""

from __future__ import annotations

import base64
import html
import logging
import os
from typing import Literal

from playwright.sync_api import Page

from trailhead_agent.config import record_video_dir
from trailhead_agent.models import UnitRef

logger = logging.getLogger(__name__)

TitlecardKind = Literal["plan", "org", "neutral"]


def demo_titlecards_enabled() -> bool:
    """Explicit 1/0, or default **on** whenever Playwright is recording (see TRAILHEAD_RECORD_VIDEO_DIR)."""
    raw = os.environ.get("TRAILHEAD_DEMO_TITLECARDS", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return record_video_dir() is not None


def _dwell_ms() -> int:
    try:
        return max(800, int(os.environ.get("TRAILHEAD_DEMO_TITLECARD_MS", "2800")))
    except ValueError:
        return 2800


def _end_card_dwell_ms() -> int:
    try:
        v = int(os.environ.get("TRAILHEAD_DEMO_END_CARD_MS", "2400").strip())
        return max(0, min(v, 60_000))
    except ValueError:
        return 2400


def _theme(kind: TitlecardKind) -> dict[str, str]:
    if kind == "plan":
        return {
            "g1": "#0c4a6e",
            "g2": "#0f172a",
            "accent": "#38bdf8",
            "badge_bg": "#0ea5e9",
            "badge_fg": "#0f172a",
            "badge": "PLAN · discovery + LLM ranking",
            "wm": "PLAN",
        }
    if kind == "org":
        return {
            "g1": "#5b21b6",
            "g2": "#1e1b4b",
            "accent": "#c4b5fd",
            "badge_bg": "#a78bfa",
            "badge_fg": "#1e1b4b",
            "badge": "ORG PREPARE · Playground helper",
            "wm": "ORG",
        }
    return {
        "g1": "#0f172a",
        "g2": "#1e293b",
        "accent": "#38bdf8",
        "badge_bg": "#0ea5e9",
        "badge_fg": "#0f172a",
        "badge": "trailhead-agent demo",
        "wm": "",
    }


def _titlecard_rank_max_items() -> int:
    try:
        return max(3, min(int(os.environ.get("TRAILHEAD_DEMO_TITLECARD_RANK_MAX", "18").strip()), 80))
    except ValueError:
        return 18


def _ranked_units_body_html(units: list[UnitRef], *, intent: str) -> str:
    """Safe HTML fragment: ordered list of LLM-ranked titles (+ short reason)."""
    if not units:
        return ""

    max_n = _titlecard_rank_max_items()
    reason_cap = 120
    parts = [
        f'<p class="intent-ref">Intent the model must follow: {html.escape(intent)}</p>',
        '<ol class="rank">',
    ]
    for i, u in enumerate(units[:max_n], 1):
        title = html.escape((u.title or "(untitled)").strip())
        raw_r = (getattr(u, "reason", None) or "").strip()
        esc_r = html.escape(raw_r)
        if len(esc_r) > reason_cap:
            esc_r = esc_r[: reason_cap - 1] + "…"
        if esc_r:
            parts.append(
                f'<li><span class="n">{i}.</span> <strong>{title}</strong>'
                f'<div class="why">{esc_r}</div></li>'
            )
        else:
            parts.append(f'<li><span class="n">{i}.</span> <strong>{title}</strong></li>')
    parts.append("</ol>")
    if len(units) > max_n:
        parts.append(
            f"<p>… and {len(units) - max_n} more units (see <code>e2e-plan-latest.json</code>).</p>"
        )
    return "".join(parts)


def show_demo_titlecard(
    page: Page,
    *,
    heading: str,
    lines: list[str] | None = None,
    body_html: str | None = None,
    kind: TitlecardKind = "neutral",
) -> None:
    """Navigate to a data-URL HTML slide; recorded in .webm when video is on."""
    if not demo_titlecards_enabled():
        return
    dwell = _dwell_ms()
    t = _theme(kind)
    esc_heading = html.escape(heading)
    if body_html is not None:
        body = body_html
    else:
        body = "".join(f"<p>{html.escape(line)}</p>" for line in (lines or []))
    wm_block = ""
    if t["wm"]:
        wm_esc = html.escape(t["wm"])
        wm_block = f'<div class="wm" aria-hidden="true">{wm_esc}</div>'
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<title>{esc_heading}</title>
<style>
body{{font-family:system-ui,Segoe UI,sans-serif;margin:0;min-height:100vh;display:flex;
align-items:center;justify-content:center;text-align:center;padding:2rem;box-sizing:border-box;
background:linear-gradient(160deg,{t["g1"]},{t["g2"]});color:#e2e8f0;position:relative;overflow:hidden}}
.wm{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;
font-size:min(26vw,11rem);font-weight:800;color:rgba(255,255,255,.07);pointer-events:none;z-index:0;letter-spacing:-0.04em}}
.wrap{{max-width:46rem;position:relative;z-index:1}}
h1{{font-size:clamp(1.25rem,4vw,1.85rem);font-weight:700;margin:0 0 1rem;line-height:1.25;
border-bottom:2px solid {t["accent"]};padding-bottom:0.75rem}}
p{{font-size:clamp(0.95rem,2.2vw,1.15rem);line-height:1.5;margin:0.65rem 0;color:#cbd5e1}}
p.intent-ref{{font-size:clamp(0.88rem,2vw,1.02rem);color:#e2e8f0;margin-bottom:0.85rem;text-align:center}}
code{{font-size:0.88em;background:rgba(0,0,0,.22);padding:0.12em 0.4em;border-radius:4px;color:#e2e8f0}}
ol.rank{{text-align:left;margin:0.4rem auto 0;max-width:42rem;padding:0;list-style:none}}
ol.rank li{{margin:0.5rem 0;line-height:1.35}}
ol.rank li .n{{color:{t["accent"]};font-weight:800;margin-right:0.35rem}}
ol.rank .why{{font-size:0.86em;color:#94a3b8;margin-top:0.2rem;line-height:1.45}}
p.intro{{font-size:clamp(0.88rem,2vw,1.02rem);color:#cbd5e1;margin:0 0 0.85rem;line-height:1.45}}
.badge{{display:inline-block;background:{t["badge_bg"]};color:{t["badge_fg"]};font-size:0.72rem;font-weight:700;
padding:0.25rem 0.6rem;border-radius:4px;margin-bottom:0.75rem;letter-spacing:0.03em;text-transform:uppercase}}
</style></head><body>{wm_block}<div class="wrap"><div class="badge">{html.escape(t["badge"])}</div>
<h1>{esc_heading}</h1>{body}</div></body></html>"""
    b64 = base64.b64encode(doc.encode("utf-8")).decode("ascii")
    url = f"data:text/html;base64,{b64}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(dwell)
    except Exception as e:
        logger.debug("demo titlecard skipped: %s", e)


def inject_recording_corner_tag(page: Page, *, session: Literal["plan", "org"]) -> None:
    """
    Fixed label on the live Trailhead page so plan-primary.webm and org-prepare.webm differ during the module segment.
    Best-effort (ignored if the page blocks inline scripts).
    """
    if record_video_dir() is None:
        return
    if session == "plan":
        label = "PLAN · trailhead-agent"
        bg = "rgba(14,165,233,0.93)"
        fg = "#0f172a"
    else:
        label = "ORG PREPARE · trailhead-agent"
        bg = "rgba(124,58,237,0.92)"
        fg = "#faf5ff"
    esc = label.replace("\\", "\\\\").replace("'", "\\'")
    script = f"""
(() => {{
  const id = '__tha_recording_corner';
  const existing = document.getElementById(id);
  if (existing) existing.remove();
  const el = document.createElement('div');
  el.id = id;
  el.setAttribute('aria-hidden', 'true');
  el.textContent = '{esc}';
  el.style.cssText =
    'position:fixed;bottom:14px;left:14px;z-index:2147483647;font:700 13px system-ui,Segoe UI,sans-serif;' +
    'padding:9px 14px;border-radius:10px;background:{bg};color:{fg};' +
    'box-shadow:0 6px 24px rgba(0,0,0,.4);pointer-events:none;max-width:calc(100vw - 28px);';
  (document.body || document.documentElement).appendChild(el);
  setTimeout(() => {{ try {{ el.remove(); }} catch (e) {{}} }}, 5200);
}})();
"""
    try:
        page.evaluate(script)
    except Exception as e:
        logger.debug("recording corner tag skipped: %s", e)


def demo_recording_end_card(page: Page, *, session: Literal["plan", "org"]) -> None:
    """Short closing slide so viewers can tell which .webm they are watching."""
    if not demo_titlecards_enabled():
        return
    kind: TitlecardKind = "plan" if session == "plan" else "org"
    if session == "plan":
        heading = "End of PLAN recording"
        lines = [
            "This clip is plan-primary.webm: browser discovery, LLM ranking, then your module again.",
            "org-prepare.webm is separate: purple ORG PREPARE slides, then the same URL — no LLM step in that run.",
        ]
    else:
        heading = "End of ORG PREPARE recording"
        lines = [
            "This clip is org-prepare.webm: Playground-helper flow only (no ranking in the browser).",
            "Compare with plan-primary.webm: cyan PLAN slides and discovery + LLM phases.",
        ]
    dwell = _end_card_dwell_ms()
    t = _theme(kind)
    esc_heading = html.escape(heading)
    body = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    wm_esc = html.escape(t["wm"])
    wm_block = f'<div class="wm" aria-hidden="true">{wm_esc}</div>' if t["wm"] else ""
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<title>{esc_heading}</title>
<style>
body{{font-family:system-ui,Segoe UI,sans-serif;margin:0;min-height:100vh;display:flex;
align-items:center;justify-content:center;text-align:center;padding:2rem;box-sizing:border-box;
background:linear-gradient(160deg,{t["g1"]},{t["g2"]});color:#e2e8f0;position:relative;overflow:hidden}}
.wm{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;
font-size:min(26vw,11rem);font-weight:800;color:rgba(255,255,255,.07);pointer-events:none;z-index:0}}
.wrap{{max-width:44rem;position:relative;z-index:1}}
h1{{font-size:clamp(1.25rem,4vw,1.85rem);font-weight:700;margin:0 0 1rem;line-height:1.25;
border-bottom:2px solid {t["accent"]};padding-bottom:0.75rem}}
p{{font-size:clamp(0.95rem,2.2vw,1.15rem);line-height:1.5;margin:0.65rem 0;color:#cbd5e1}}
.badge{{display:inline-block;background:{t["badge_bg"]};color:{t["badge_fg"]};font-size:0.72rem;font-weight:700;
padding:0.25rem 0.6rem;border-radius:4px;margin-bottom:0.75rem;letter-spacing:0.03em;text-transform:uppercase}}
</style></head><body>{wm_block}<div class="wrap"><div class="badge">{html.escape(t["badge"])}</div>
<h1>{esc_heading}</h1>{body}</div></body></html>"""
    b64 = base64.b64encode(doc.encode("utf-8")).decode("ascii")
    url = f"data:text/html;base64,{b64}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(dwell)
    except Exception as e:
        logger.debug("demo end card skipped: %s", e)


def demo_plan_what_you_asked(
    page: Page, *, start_url: str, intent: str, label: str | None = None
) -> None:
    """Opening slide: exact CLI inputs before discovery (recorded when title cards are on)."""
    lines = [
        f"start_url (module or trail): {start_url}",
        f"intent: {intent}",
    ]
    if label and label.strip() and label.strip() != start_url.strip():
        lines.append(f"label (--label): {label}")
    lines.extend(
        [
            "Phase 2 will scrape unit links from Trailhead in the browser.",
            "Phase 3 will show the LLM’s ordered output (titles + short reasons) on its own slide.",
        ]
    )
    show_demo_titlecard(page, kind="plan", heading="Phase 1 - What you asked for", lines=lines)


def demo_after_discovery(page: Page, *, candidate_count: int) -> None:
    show_demo_titlecard(
        page,
        kind="plan",
        heading="Phase 2 - Discovery (browser)",
        lines=[
            f"Collected {candidate_count} candidate unit links from Trailhead (DOM scrape).",
            "The LLM call runs next over the network — nothing to watch in the browser for that step.",
            "The following slide lists the model’s ordered output (separate from this discovery phase).",
        ],
    )


def demo_llm_ranking_output_slide(page: Page, *, intent: str, units: list[UnitRef]) -> None:
    """Dedicated slide: ranked titles (+ reasons) so viewers see the LLM ordering explicitly."""
    if not units:
        show_demo_titlecard(
            page,
            kind="plan",
            heading="Phase 3 - LLM ranking (ordered output)",
            lines=[
                "The model returned no allowlisted rows in ordered output (unusual).",
                "Downstream may fall back to discovery order — check logs and e2e-plan-latest.json.",
            ],
        )
        return
    intro = (
        '<p class="intro">Ordered output for your intent (below). Discovery already produced the '
        "candidate links; the LLM only permutes allowlisted hrefs and may attach reasons.</p>"
    )
    show_demo_titlecard(
        page,
        kind="plan",
        heading="Phase 3 - LLM ranking (ordered output)",
        body_html=intro + _ranked_units_body_html(units, intent=intent),
    )


def demo_after_llm_rank(page: Page, *, ranked_count: int, walk_will_visit: int) -> None:
    if walk_will_visit > 0:
        lines = [
            f"Phase 4 — The model ranked {ranked_count} unit(s); the full order was on the previous slide.",
            f"This recording continues with the ranked walk: top {walk_will_visit} URLs in order (navigation only).",
            "After your run: trailhead-agent org checklist --plan-json …e2e-plan-latest.json",
        ]
    else:
        lines = [
            f"Phase 4 — The model ranked {ranked_count} unit(s); the full order was on the previous slide.",
            "Next: this recording returns to your Trailhead module (live page + scroll) so the clip does not end here.",
            "Use trailhead-agent org checklist --plan-json …e2e-plan-latest.json for Playground / org steps.",
        ]
    show_demo_titlecard(page, kind="plan", heading="Phase 4 - What happens next", lines=lines)


def demo_before_walk_unit(page: Page, *, index_one_based: int, total: int, title: str) -> None:
    show_demo_titlecard(
        page,
        kind="plan",
        heading=f"Phase 5 - Ranked walk {index_one_based} / {total}",
        lines=[
            title,
            "Opening this Trailhead unit in the browser (human-in-the-loop in the real org).",
            "Org checklist: trailhead-agent org checklist --unit-href <this unit URL>",
        ],
    )


def demo_org_prepare_browser(page: Page) -> None:
    """
    Multiple slides so org-prepare .webm walks viewers through plan vs org, Playground, sf CLI, and checklists.
    """
    show_demo_titlecard(
        page,
        kind="org",
        heading="Org prepare - Slide 1 of 5 - Plan vs org prepare",
        lines=[
            "trailhead-agent plan: browser discovery + LLM ranks units → e2e-plan-latest.json (+ optional ranked walk in plan-primary.webm).",
            "trailhead-agent org prepare: Playground / org helper only — no LLM ranking in this command.",
            "You are watching the purple ORG PREPARE title cards, then one live Trailhead URL.",
        ],
    )
    show_demo_titlecard(
        page,
        kind="org",
        heading="Org prepare - Slide 2 of 5 - What this recording will show",
        lines=[
            "After these slides, the browser opens your module start URL with dwell + smooth scroll.",
            "We inject a short corner tag (ORG PREPARE) so this clip is easy to tell apart from cyan PLAN clips.",
            "Open e2e-report.html in your artifacts folder to compare plan-primary.webm vs org-prepare.webm side by side.",
        ],
    )
    show_demo_titlecard(
        page,
        kind="org",
        heading="Org prepare - Slide 3 of 5 - Your steps in Trailhead",
        lines=[
            "Sign in to Trailhead if prompted.",
            "Launch Playground (or open the linked hands-on org) yourself — the CLI does not auto-click Launch.",
            "We do not submit quizzes, solve challenges, or deploy metadata unless you passed --deploy with a project dir.",
        ],
    )
    show_demo_titlecard(
        page,
        kind="org",
        heading="Org prepare - Slide 4 of 5 - Salesforce CLI and org doctor",
        lines=[
            "Install Salesforce CLI (sf) and authorize an org if you want automated org checks later.",
            "With TRAILHEAD_ORG_EXECUTOR=cli and sf on PATH: trailhead-agent org doctor summarizes org display JSON.",
            "org prepare can still open the browser even when sf is missing — you’ll see a warning in the CLI output.",
        ],
    )
    show_demo_titlecard(
        page,
        kind="org",
        heading="Org prepare - Slide 5 of 5 - Plan JSON and checklists",
        lines=[
            "From a plan run: trailhead-agent plan --artifacts-dir YOUR_DIR (writes e2e-plan-latest.json + plan-primary.webm).",
            "Hands-on checklists: trailhead-agent org checklist --plan-json YOUR_DIR/e2e-plan-latest.json",
            "Single unit: org checklist --unit-href https://trailhead.salesforce.com/content/learn/modules/.../unit_slug",
            "Next: live Trailhead module, corner tag, scroll, short end card — then the browser session closes.",
        ],
    )
