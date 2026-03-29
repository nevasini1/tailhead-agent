"""Discovery blocker heuristics (no live browser)."""

from __future__ import annotations

from unittest.mock import MagicMock

from trailhead_agent.discovery import detect_discovery_blockers


def test_detect_login_salesforce_host():
    page = MagicMock()
    page.url = "https://login.salesforce.com/?foo=1"
    page.title.return_value = "Login"
    page.locator.return_value.inner_text.return_value = ""
    assert detect_discovery_blockers(page) is not None


def test_detect_path_login():
    page = MagicMock()
    page.url = "https://trailhead.salesforce.com/content/learn/login"
    page.title.return_value = "Trailhead"
    page.locator.return_value.inner_text.return_value = "welcome"
    assert detect_discovery_blockers(page) is not None


def test_detect_geo_block_body():
    page = MagicMock()
    page.url = "https://trailhead.salesforce.com/content/learn/modules/foo"
    page.title.return_value = "Trailhead"
    page.locator.return_value.inner_text.return_value = "Unavailable in your region."
    assert detect_discovery_blockers(page) is not None


def test_no_blocker_on_normal_title():
    page = MagicMock()
    page.url = "https://trailhead.salesforce.com/content/learn/modules/apex_database"
    page.title.return_value = "Apex Basics | Trailhead"
    page.locator.return_value.inner_text.return_value = "Get Started with Apex"
    assert detect_discovery_blockers(page) is None
