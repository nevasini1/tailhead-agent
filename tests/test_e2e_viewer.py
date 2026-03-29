from __future__ import annotations

import json
from pathlib import Path

from trailhead_agent.e2e_viewer import write_e2e_viewer_html


def test_write_e2e_viewer_html_embeds_video_and_manifest(tmp_path: Path) -> None:
    (tmp_path / "plan-primary.webm").write_bytes(b"fake")
    (tmp_path / "e2e-plan-latest.json").write_text(
        json.dumps(
            {
                "primary_video": "plan-primary.webm",
                "video_files": [
                    {"name": "plan-primary.webm", "role": "primary", "size_bytes": 4, "mtime_utc": "x"}
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "e2e-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "recordings": [
                    {
                        "source": "plan",
                        "command": "plan",
                        "primary_video": "plan-primary.webm",
                        "start_url": "https://trailhead.salesforce.com/x",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out = write_e2e_viewer_html(tmp_path)
    assert out is not None
    html_text = out.read_text(encoding="utf-8")
    assert "plan-primary.webm" in html_text
    assert 'src="plan-primary.webm"' in html_text or "plan-primary.webm" in html_text
    assert "timeline" in html_text
    assert "e2e-plan-latest.json" in html_text


def test_e2e_viewer_org_prepare_video_card(tmp_path: Path) -> None:
    (tmp_path / "org-prepare.webm").write_bytes(b"x")
    (tmp_path / "e2e-org-prepare-latest.json").write_text(
        json.dumps(
            {
                "command": "org prepare",
                "trace_id": "t-org",
                "open_playground": True,
                "start_url": "https://trailhead.salesforce.com/mod",
                "primary_video": "org-prepare.webm",
                "executor": "NoopOrgExecutor",
                "video_files": [
                    {"name": "org-prepare.webm", "role": "primary", "size_bytes": 1, "mtime_utc": "x"}
                ],
            }
        ),
        encoding="utf-8",
    )
    out = write_e2e_viewer_html(tmp_path)
    assert out is not None
    html_text = out.read_text(encoding="utf-8")
    assert "org prepare" in html_text.lower()
    assert "org-prepare.webm" in html_text
    assert "e2e-org-prepare-latest.json" in html_text
    assert "presenter" not in html_text.lower()
