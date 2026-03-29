"""Pytest defaults: keep stderr clean unless a test enables demo narration."""

from __future__ import annotations

import os

os.environ.setdefault("TRAILHEAD_DEMO_NARRATION", "0")
