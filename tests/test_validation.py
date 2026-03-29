import pytest

from trailhead_agent.errors import UrlValidationError
from trailhead_agent.validation import validate_start_url


def test_validate_good_module_url(monkeypatch):
    monkeypatch.setenv("TRAILHEAD_ALLOWED_HOST", "trailhead.salesforce.com")
    u = validate_start_url(
        "https://trailhead.salesforce.com/content/learn/modules/apex_database"
    )
    assert "trailhead.salesforce.com" in u


def test_validate_rejects_http(monkeypatch):
    monkeypatch.setenv("TRAILHEAD_ALLOWED_HOST", "trailhead.salesforce.com")
    with pytest.raises(UrlValidationError):
        validate_start_url("http://trailhead.salesforce.com/content/learn/modules/x")


def test_validate_rejects_wrong_host(monkeypatch):
    monkeypatch.setenv("TRAILHEAD_ALLOWED_HOST", "trailhead.salesforce.com")
    with pytest.raises(UrlValidationError):
        validate_start_url("https://evil.com/content/learn/modules/x")


def test_validate_requires_learn_path(monkeypatch):
    monkeypatch.setenv("TRAILHEAD_ALLOWED_HOST", "trailhead.salesforce.com")
    with pytest.raises(UrlValidationError):
        validate_start_url("https://trailhead.salesforce.com/foo")
