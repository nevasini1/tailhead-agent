from __future__ import annotations

import logging
import os
import re
from collections import Counter
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page

from trailhead_agent.config import trailhead_host
from trailhead_agent.errors import DiscoveryError
from trailhead_agent.models import UnitRef

logger = logging.getLogger(__name__)


def _netloc_allowed(netloc: str) -> bool:
    h = trailhead_host()
    nl = netloc.lower().split(":")[0]
    return nl == h or nl.endswith("." + h)


def _max_modules_to_crawl() -> int:
    try:
        return max(1, int(os.environ.get("TRAILHEAD_MAX_MODULES", "15")))
    except ValueError:
        return 15


def _wait_after_goto_ms() -> int:
    try:
        return max(500, int(os.environ.get("TRAILHEAD_PAGE_SETTLE_MS", "3500")))
    except ValueError:
        return 3500


def _discovery_scroll_rounds() -> int:
    try:
        return max(0, min(20, int(os.environ.get("TRAILHEAD_DISCOVERY_SCROLL_ROUNDS", "4"))))
    except ValueError:
        return 4


def _discovery_hints() -> list[str]:
    return [
        "Increase TRAILHEAD_PAGE_SETTLE_MS (e.g. 8000) if the page is slow or script-heavy.",
        "Set TRAILHEAD_BROWSER_USER_DATA_DIR and run `trailhead-agent auth`, or log in manually in that profile.",
        "Use a Trail or module URL under /content/learn/ that lists units when you are logged in.",
        "Try TRAILHEAD_DISCOVERY_SCROLL_ROUNDS=8 if units load only after scrolling.",
        "If the trail shows a Load more / Show more control, discovery will click it automatically (see TRAILHEAD_DISCOVERY_PAGINATION_CLICKS).",
        "Try TRAILHEAD_DISCOVERY_NAV_WAIT_UNTIL=load if the TOC appears only after window.onload.",
    ]


def _discovery_nav_wait_until() -> str:
    v = os.environ.get("TRAILHEAD_DISCOVERY_NAV_WAIT_UNTIL", "domcontentloaded").strip().lower()
    if v in ("domcontentloaded", "load", "commit"):
        return v
    return "domcontentloaded"


def _pagination_max_clicks() -> int:
    try:
        return max(0, min(24, int(os.environ.get("TRAILHEAD_DISCOVERY_PAGINATION_CLICKS", "8"))))
    except ValueError:
        return 8


def discovery_context_snapshot(page: Page) -> dict[str, str]:
    """Structured context for logs / DiscoveryError (no secrets)."""
    ctx: dict[str, str] = {}
    try:
        ctx["page_url"] = (page.url or "").strip()
    except Exception:
        ctx["page_url"] = ""
    try:
        ctx["page_title"] = (page.title() or "").strip()
    except Exception:
        ctx["page_title"] = ""
    return ctx


def expand_paginated_trailhead_lists(page: Page, *, max_clicks: int | None = None) -> int:
    """
    Click common Trailhead / LWC 'load more' patterns so anchors exist in the DOM.
    Returns how many clicks succeeded.
    """
    limit = max_clicks if max_clicks is not None else _pagination_max_clicks()
    if limit <= 0:
        return 0
    selectors = (
        'button:has-text("Load more")',
        'button:has-text("Show more")',
        'a:has-text("Load more")',
        'a:has-text("Show more")',
        '[aria-label*="Load more" i]',
        '[aria-label*="Show more" i]',
        'button[aria-label*="more" i]',
    )
    total = 0
    for _ in range(limit):
        clicked = False
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                if loc.count() == 0:
                    continue
                if not loc.is_visible():
                    continue
                loc.click(timeout=2500)
                page.wait_for_timeout(min(1200, _wait_after_goto_ms()))
                total += 1
                clicked = True
                break
            except Exception as e:
                logger.debug("pagination click skip %s: %s", sel, e)
        if not clicked:
            break
    if total:
        logger.info("discovery pagination clicks=%d", total)
    return total


def detect_discovery_blockers(page: Page) -> str | None:
    """
    Detect login walls, identity redirects, and obvious geo/access pages before trusting DOM scrape.
    """
    raw_url = page.url or ""
    url_l = raw_url.lower()
    path_l = urlparse(raw_url).path.lower()

    if "login.salesforce.com" in url_l:
        return (
            "The browser is on a Salesforce login host. Trailhead content is not loaded yet, "
            "so no module/unit links can be collected."
        )
    if "/login" in path_l or path_l.rstrip("/").endswith("/login") or "/secur/" in path_l:
        return (
            "The current URL looks like a login or security interstitial. "
            "Complete sign-in (or use a saved Chromium profile) before running plan."
        )

    try:
        title = (page.title() or "").strip().lower()
    except Exception:
        title = ""
    if title.startswith("log in") or title in ("login", "sign in") or "sign in to salesforce" in title:
        return "The page title indicates a sign-in screen, not a Trailhead learn page."
    if "sign in" in title and "trailhead" not in title:
        return "The page title looks like a generic sign-in page, not Trailhead module content."

    try:
        body = (page.locator("body").inner_text(timeout=8000) or "").lower()
    except Exception:
        body = ""
    snippets = (
        "unavailable in your region",
        "not available in your country",
        "access denied",
        "403 forbidden",
        "temporarily unavailable",
        "something went wrong",
        "enable javascript",
        "sign in to continue",
        "log in to continue",
        "you must log in",
        "session expired",
        "page not found",
        "404",
        "captcha",
        "verify you are human",
    )
    for snip in snippets:
        if snip in body[:6000]:
            return (
                f"The page content suggests a block or error ({snip!r}). "
                "Discovery cannot reliably read unit links on this response."
            )
    return None


def _scroll_for_lazy_content(page: Page, *, steps: int, pause_ms: int) -> None:
    for _ in range(max(0, steps)):
        try:
            page.evaluate(
                "() => window.scrollBy(0, Math.min(window.innerHeight * 0.85, 900))"
            )
            page.wait_for_timeout(pause_ms)
        except Exception as e:
            logger.debug("discovery scroll step skipped: %s", e)
    try:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
    except Exception as e:
        logger.debug("discovery scroll reset skipped: %s", e)


def discover_units_including_lazy(page: Page, module_or_trail_url: str) -> list[UnitRef]:
    """Merge anchors after optional scroll rounds (lazy-loaded TOC / cards)."""
    rounds = _discovery_scroll_rounds()
    merged: dict[str, UnitRef] = {}
    for r in range(rounds + 1):
        if r > 0:
            _scroll_for_lazy_content(page, steps=3, pause_ms=450)
        for u in discover_units_on_page(page, module_or_trail_url):
            if u.href not in merged or len(u.title) > len(merged[u.href].title):
                merged[u.href] = u
    return list(merged.values())


def discover_module_roots_including_lazy(page: Page, base_url: str) -> list[str]:
    max_mod = _max_modules_to_crawl()
    rounds = _discovery_scroll_rounds()
    seen: dict[str, None] = {}
    for r in range(rounds + 1):
        if r > 0:
            _scroll_for_lazy_content(page, steps=4, pause_ms=500)
        for m in discover_module_roots_on_page(page, base_url):
            seen.setdefault(m, None)
        if len(seen) >= max_mod:
            break
    return list(seen.keys())[:max_mod]


def is_trail_url(url: str) -> bool:
    return "/content/learn/trails/" in urlparse(url).path.lower()


def _is_module_unit_path(path: str) -> bool:
    p = path.rstrip("/")
    marker = "/content/learn/modules/"
    if marker not in p:
        return False
    tail = p.split(marker, 1)[1]
    segments = [s for s in tail.split("/") if s]
    return len(segments) >= 2


def _is_module_root_path(path: str) -> bool:
    p = path.rstrip("/")
    marker = "/content/learn/modules/"
    if marker not in p:
        return False
    tail = p.split(marker, 1)[1]
    segments = [s for s in tail.split("/") if s]
    return len(segments) == 1


def _normalize_trailhead_url(base: str, href: str) -> str | None:
    if not href or href.startswith("#") or href.startswith("javascript:"):
        return None
    absolute = urljoin(base, href)
    parsed = urlparse(absolute)
    if not _netloc_allowed(parsed.netloc):
        return None
    if "/content/learn/modules/" not in parsed.path:
        return None
    if not _is_module_unit_path(parsed.path):
        return None
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean.rstrip("/")


def _normalize_module_root_url(base: str, href: str) -> str | None:
    if not href or href.startswith("#") or href.startswith("javascript:"):
        return None
    absolute = urljoin(base, href)
    parsed = urlparse(absolute)
    if not _netloc_allowed(parsed.netloc):
        return None
    if not _is_module_root_path(parsed.path):
        return None
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean.rstrip("/")


def discover_module_roots_on_page(page: Page, base_url: str) -> list[str]:
    seen: dict[str, None] = {}
    anchors = page.locator('a[href*="/content/learn/modules/"]')
    for i in range(anchors.count()):
        a = anchors.nth(i)
        try:
            href = a.get_attribute("href")
            norm = _normalize_module_root_url(base_url, href or "")
            if norm:
                seen.setdefault(norm, None)
        except Exception as e:
            logger.debug("skip module root %s: %s", i, e)
    return list(seen.keys())


def discover_units_on_page(page: Page, module_or_trail_url: str) -> list[UnitRef]:
    seen: dict[str, UnitRef] = {}
    anchors = page.locator('a[href*="/content/learn/modules/"]')
    count = anchors.count()
    for i in range(count):
        a = anchors.nth(i)
        try:
            href = a.get_attribute("href")
            title = (a.inner_text() or "").strip()
            if not title:
                title = (a.get_attribute("aria-label") or "").strip()
            title = re.sub(r"\s+", " ", title)
            norm = _normalize_trailhead_url(module_or_trail_url, href or "")
            if not norm or not title:
                continue
            if norm not in seen or len(title) > len(seen[norm].title):
                seen[norm] = UnitRef(title=title, href=norm)
        except Exception as e:
            logger.debug("skip anchor %s: %s", i, e)
    return list(seen.values())


def _units_look_degenerate(units: list[UnitRef]) -> str | None:
    """Return a human message if the scrape looks like layout noise, not a real TOC."""
    if not units:
        return None
    titles = [u.title.strip() for u in units]
    if all(len(t) < 2 for t in titles):
        return (
            "Every collected link has an empty or trivial title. "
            "The page is probably not rendering the real Trailhead unit list (login wall, skeleton UI, or DOM change)."
        )
    if len(titles) >= 5:
        top_n, top_count = Counter(titles).most_common(1)[0]
        if top_count / len(titles) >= 0.85 and len(top_n) <= 40:
            return (
                f"Most links share the same title ({top_n!r}), so discovery likely grabbed the wrong anchors "
                f"({top_count}/{len(titles)}). Try another start URL or increase waits / scroll rounds."
            )
    return None


def collect_units_for_seed(page: Page, seed_url: str) -> list[UnitRef]:
    wait_ms = _wait_after_goto_ms()
    max_mod = _max_modules_to_crawl()
    nav_wait = _discovery_nav_wait_until()
    page.goto(seed_url, wait_until=nav_wait)
    page.wait_for_timeout(wait_ms)
    expand_paginated_trailhead_lists(page)

    blocked = detect_discovery_blockers(page)
    if blocked:
        raise DiscoveryError(
            blocked,
            hints=_discovery_hints(),
            details=discovery_context_snapshot(page),
        )

    if is_trail_url(seed_url):
        modules = discover_module_roots_including_lazy(page, seed_url)
        if not modules:
            raise DiscoveryError(
                f"No module links found on trail page after scrolling ({max_mod} max). "
                f"The trail layout may have changed, or content is hidden until login.",
                hints=_discovery_hints(),
                details=discovery_context_snapshot(page),
            )
        by_href: dict[str, UnitRef] = {}
        for mod_url in modules:
            page.goto(mod_url, wait_until=nav_wait)
            page.wait_for_timeout(wait_ms)
            expand_paginated_trailhead_lists(page)
            sub = detect_discovery_blockers(page)
            if sub:
                logger.warning("Skipping module %s: %s", mod_url, sub)
                continue
            for u in discover_units_including_lazy(page, mod_url):
                by_href[u.href] = u
        if not by_href:
            raise DiscoveryError(
                "Visited trail modules but collected zero unit links. "
                "Every module page may be behind a login wall or returned an error.",
                hints=_discovery_hints(),
                details=discovery_context_snapshot(page),
            )
        merged = list(by_href.values())
        bad = _units_look_degenerate(merged)
        if bad:
            raise DiscoveryError(bad, hints=_discovery_hints(), details=discovery_context_snapshot(page))
        return merged

    units = discover_units_including_lazy(page, seed_url)
    if not units:
        raise DiscoveryError(
            "No Trailhead unit links matched on this page after scrolling. "
            "If this is a module overview, confirm you are not on a login or marketing page.",
            hints=_discovery_hints(),
            details=discovery_context_snapshot(page),
        )
    bad = _units_look_degenerate(units)
    if bad:
        raise DiscoveryError(bad, hints=_discovery_hints(), details=discovery_context_snapshot(page))
    return units
