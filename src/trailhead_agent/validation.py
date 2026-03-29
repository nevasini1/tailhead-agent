from __future__ import annotations

from urllib.parse import urlparse

from trailhead_agent.config import trailhead_host
from trailhead_agent.errors import UrlValidationError


def validate_start_url(url: str) -> str:
    """
    Require https and an allowed Trailhead host (default trailhead.salesforce.com).
    Returns normalized URL string.
    """
    u = (url or "").strip()
    if not u:
        raise UrlValidationError("Start URL is empty.")
    parsed = urlparse(u)
    if parsed.scheme.lower() != "https":
        raise UrlValidationError("Start URL must use https.")
    hn = (parsed.hostname or "").lower()
    if not hn:
        raise UrlValidationError("Start URL is missing a host.")
    host = trailhead_host()
    if hn != host and not hn.endswith("." + host):
        raise UrlValidationError(
            f"Start URL host {hn!r} is not allowed. "
            f"Expected {host!r} (override with TRAILHEAD_ALLOWED_HOST if appropriate)."
        )
    path = parsed.path or "/"
    if "/content/learn/" not in path:
        raise UrlValidationError(
            "Start URL path should include /content/learn/ (a Trailhead trail or module URL)."
        )
    return u
