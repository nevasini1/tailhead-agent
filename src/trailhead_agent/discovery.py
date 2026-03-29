from __future__ import annotations

import logging
import os
import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page

from trailhead_agent.config import trailhead_host
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
            title = re.sub(r"\s+", " ", title)
            norm = _normalize_trailhead_url(module_or_trail_url, href or "")
            if not norm or not title:
                continue
            if norm not in seen or len(title) > len(seen[norm].title):
                seen[norm] = UnitRef(title=title, href=norm)
        except Exception as e:
            logger.debug("skip anchor %s: %s", i, e)
    return list(seen.values())


def collect_units_for_seed(page: Page, seed_url: str) -> list[UnitRef]:
    wait_ms = _wait_after_goto_ms()
    max_mod = _max_modules_to_crawl()
    page.goto(seed_url, wait_until="domcontentloaded")
    page.wait_for_timeout(wait_ms)
    if is_trail_url(seed_url):
        modules = discover_module_roots_on_page(page, seed_url)[:max_mod]
        if not modules:
            logger.warning("No module roots found on trail page (try login or longer wait): %s", seed_url)
        by_href: dict[str, UnitRef] = {}
        for mod_url in modules:
            page.goto(mod_url, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            for u in discover_units_on_page(page, mod_url):
                by_href[u.href] = u
        return list(by_href.values())
    return discover_units_on_page(page, seed_url)
