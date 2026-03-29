"""
Self-contained e2e-report.html in each TRAILHEAD_RECORD_VIDEO_DIR / --artifacts-dir folder.

Open the HTML file in a browser to preview .webm clips, a short manifest timeline, and JSON links.
"""

from __future__ import annotations

import html
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VIEWER_FILENAME = "e2e-report.html"
MANIFEST_NAME = "e2e-manifest.json"


def viewer_html_report_enabled() -> bool:
    v = os.environ.get("TRAILHEAD_E2E_HTML_REPORT", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _video_roles_from_sidecars(root: Path) -> dict[str, dict[str, str]]:
    """Map basename -> {role, source, hint} from latest JSON artifacts."""
    out: dict[str, dict[str, str]] = {}
    candidates = [
        ("e2e-plan-latest.json", "plan"),
        ("e2e-open-unit-latest.json", "open-unit"),
        ("e2e-org-prepare-latest.json", "org prepare"),
    ]
    for fname, source in candidates:
        doc = _load_json(root / fname)
        if not doc:
            continue
        primary = (doc.get("primary_video") or "").strip()
        if primary:
            out.setdefault(
                primary,
                {"role": "primary", "source": source, "hint": _hint_for_source(source)},
            )
        for row in doc.get("video_files") or []:
            if not isinstance(row, dict):
                continue
            name = (row.get("name") or "").strip()
            if not name:
                continue
            role = (row.get("role") or "session").strip()
            if name not in out or role == "primary":
                out[name] = {
                    "role": role,
                    "source": source,
                    "hint": _hint_for_source(source),
                }
    return out


def _hint_for_source(source: str) -> str:
    return {
        "plan": "Discovery and LLM-ranked plan.",
        "open-unit": "Opens ranked unit URLs.",
        "org prepare": "Browser open to Trailhead (org prepare).",
    }.get(source, "Recording.")


def _badge_class(role: str, source: str) -> str:
    if "org" in source:
        return "badge-org"
    if "open-unit" in source:
        return "badge-open"
    if role == "primary":
        return "badge-primary"
    return "badge-session"


def write_e2e_viewer_html(root: Path) -> Path | None:
    """
    Write ``e2e-report.html`` under ``root``. Safe to call after every artifact write.
    """
    if not root.is_dir():
        return None
    role_map = _video_roles_from_sidecars(root)
    webm_paths = sorted(
        root.glob("*.webm"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    manifest_path = root / MANIFEST_NAME
    manifest_doc = _load_json(manifest_path)
    recordings: list[dict[str, Any]] = []
    if manifest_doc and isinstance(manifest_doc.get("recordings"), list):
        recordings = [r for r in manifest_doc["recordings"] if isinstance(r, dict)]

    json_links = sorted(p.name for p in root.glob("e2e-*.json"))

    cards_html: list[str] = []
    for p in webm_paths:
        name = p.name
        try:
            st = p.stat()
        except OSError:
            continue
        sz = _fmt_bytes(st.st_size)
        mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        info = role_map.get(name)
        if info:
            role, source, hint = info["role"], info["source"], info["hint"]
            badge = _badge_class(role, source)
            chip = f'<span class="chip {badge}">{html.escape(source)} · {html.escape(role)}</span>'
            subtitle = html.escape(hint)
        else:
            chip = '<span class="chip badge-extra">unreferenced</span>'
            subtitle = html.escape("Not linked from latest e2e-*.json in this folder.")

        safe_name = html.escape(name)
        cards_html.append(
            f"""<article class="card">
  <header class="card-hd">
    {chip}
    <code class="fname">{safe_name}</code>
    <p class="sub">{subtitle}</p>
    <p class="meta">{html.escape(sz)} · {html.escape(mtime)}</p>
  </header>
  <video class="vid" controls preload="metadata" src="{html.escape(name, quote=True)}">
    Your browser cannot play this WebM inline; open <code>{safe_name}</code> directly.
  </video>
</article>"""
        )

    timeline_html: list[str] = []
    for i, rec in enumerate(recordings, start=1):
        src = html.escape(str(rec.get("source", "?")))
        cmd = html.escape(str(rec.get("command", "")))
        pv = rec.get("primary_video")
        pv_s = html.escape(str(pv)) if pv else "—"
        su = rec.get("start_url")
        if su:
            su_str = str(su)
            disp = su_str if len(su_str) <= 96 else su_str[:93] + "..."
            url_line = f'<a class="ext" href="{html.escape(su_str, quote=True)}">{html.escape(disp)}</a>'
        else:
            url_line = "—"
        timeline_html.append(
            f"""<li class="step">
  <span class="step-num">{i}</span>
  <div class="step-body">
    <strong>{src}</strong> <span class="muted">({cmd})</span>
    <div class="step-row">Video: <code>{pv_s}</code></div>
    <div class="step-row">URL: {url_line}</div>
  </div>
</li>"""
        )

    json_section = "\n".join(
        f'<li><a href="{html.escape(n, quote=True)}">{html.escape(n)}</a></li>' for n in json_links
    )
    if not json_section:
        json_section = "<li class='muted'>No e2e-*.json yet.</li>"

    folder_display = html.escape(str(root.resolve()))
    empty_state = (
        '<p class="empty">No <code>.webm</code> files in this folder yet. Run '
        "<code>plan --artifacts-dir …</code> or <code>org prepare --open-playground</code> with recording enabled.</p>"
        if not cards_html
        else ""
    )
    cards_joined = "\n".join(cards_html) if cards_html else empty_state
    timeline_joined = (
        "<ol class='timeline'>\n" + "\n".join(timeline_html) + "\n</ol>"
        if timeline_html
        else "<p class='muted'>No e2e-manifest.json entries yet.</p>"
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>trailhead-agent · E2E artifacts</title>
  <style>
:root {{
  --bg: #0f172a;
  --bg2: #1e293b;
  --text: #e2e8f0;
  --muted: #94a3b8;
  --accent: #38bdf8;
  --card: #1e293b;
  --border: #334155;
}}
* {{ box-sizing: border-box; }}
body {{
  font-family: system-ui, "Segoe UI", sans-serif;
  background: linear-gradient(165deg, var(--bg), var(--bg2));
  color: var(--text);
  margin: 0;
  min-height: 100vh;
  padding: 1.75rem clamp(1rem, 4vw, 2.5rem);
  line-height: 1.5;
}}
h1 {{
  font-size: clamp(1.35rem, 3vw, 1.85rem);
  margin: 0 0 0.35rem;
  border-bottom: 2px solid var(--accent);
  padding-bottom: 0.65rem;
  display: inline-block;
}}
.lead {{ color: var(--muted); max-width: 52rem; margin: 0.75rem 0 1.5rem; }}
.folder {{ font-size: 0.8rem; color: var(--muted); word-break: break-all; margin-bottom: 2rem; }}
h2 {{
  font-size: 1.05rem;
  margin: 2rem 0 1rem;
  color: var(--accent);
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 22rem), 1fr));
  gap: 1.25rem;
}}
.card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0,0,0,.25);
}}
.card-hd {{ padding: 1rem 1rem 0.5rem; }}
.chip {{
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}}
.badge-primary {{ background: #0ea5e9; color: #0f172a; }}
.badge-session {{ background: #475569; color: #f1f5f9; }}
.badge-org {{ background: #a78bfa; color: #1e1b4b; }}
.badge-open {{ background: #34d399; color: #064e3b; }}
.badge-extra {{ background: #64748b; color: #f8fafc; }}
.fname {{ display: block; font-size: 0.9rem; margin: 0.35rem 0; word-break: break-all; }}
.sub {{ font-size: 0.85rem; color: var(--muted); margin: 0.25rem 0; }}
.meta {{ font-size: 0.75rem; color: var(--muted); margin: 0.5rem 0 0; }}
.vid {{
  width: 100%;
  display: block;
  background: #000;
  max-height: 240px;
}}
.timeline {{
  list-style: none;
  padding: 0;
  margin: 0;
  border-left: 3px solid var(--border);
  margin-left: 0.75rem;
}}
.step {{
  position: relative;
  padding: 0 0 1.25rem 1.5rem;
}}
.step-num {{
  position: absolute;
  left: -0.6rem;
  top: 0;
  width: 1.35rem;
  height: 1.35rem;
  background: var(--accent);
  color: var(--bg);
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  transform: translateX(-50%);
}}
.step-body strong {{ color: #f8fafc; }}
.muted {{ color: var(--muted); font-size: 0.9rem; }}
.step-row {{ font-size: 0.85rem; margin-top: 0.35rem; }}
.ext {{ color: var(--accent); }}
ul.files {{ margin: 0; padding-left: 1.2rem; }}
ul.files li {{ margin: 0.35rem 0; }}
ul.files a {{ color: var(--accent); }}
.empty {{ color: var(--muted); max-width: 40rem; }}
code {{ font-size: 0.88em; background: rgba(0,0,0,.25); padding: 0.1em 0.35em; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>trailhead-agent · E2E folder</h1>
  <p class="lead">
    Recordings and JSON sidecars in this folder. Videos use relative paths — open this file in a browser.
  </p>
  <p class="folder">{folder_display}</p>

  <h2>Recordings</h2>
  <div class="grid">
{cards_joined}
  </div>

  <h2>Run order (manifest)</h2>
{timeline_joined}

  <h2>JSON</h2>
  <ul class="files">
{json_section}
  </ul>
</body>
</html>
"""
    out = root / VIEWER_FILENAME
    out.write_text(doc, encoding="utf-8")
    logger.info("e2e_viewer_html_written path=%s", out)
    return out
