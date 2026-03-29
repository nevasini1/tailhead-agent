from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

from trailhead_agent.errors import ConfigurationError


def sanitize_environment() -> None:
    """
    Some Windows security tools set SSLKEYLOGFILE to a device path under \\\\.\\
    that Python's ssl module cannot open, breaking all HTTPS (including Gemini).
    Drop only clearly invalid values.
    """
    k = (os.environ.get("SSLKEYLOGFILE") or "").strip()
    if not k:
        return
    if "nllMonFltProxy" in k or "nllmonfltproxy" in k.lower():
        os.environ.pop("SSLKEYLOGFILE", None)


@dataclass(frozen=True)
class BrowserSettings:
    headless: bool
    viewport_width: int
    viewport_height: int
    navigation_timeout_ms: int


@dataclass(frozen=True)
class AgentConfig:
    browser: BrowserSettings
    selectors: dict[str, str]


def _default_config_path() -> Path:
    env = os.environ.get("TRAILHEAD_AGENT_CONFIG")
    if env:
        return Path(env)
    cwd = Path.cwd() / "config" / "default.yaml"
    if cwd.is_file():
        return cwd
    return Path(__file__).resolve().parents[2] / "config" / "default.yaml"


def load_config(path: Path | None = None) -> AgentConfig:
    load_dotenv()
    sanitize_environment()
    cfg_path = path or _default_config_path()
    if not cfg_path.is_file():
        raise ConfigurationError(f"Config file not found: {cfg_path}")
    text = cfg_path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {cfg_path}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Config root must be a mapping: {cfg_path}")
    b = raw.get("browser", {})
    browser = BrowserSettings(
        headless=bool(b.get("headless", False)),
        viewport_width=int(b.get("viewport_width", 1280)),
        viewport_height=int(b.get("viewport_height", 800)),
        navigation_timeout_ms=int(b.get("navigation_timeout_ms", 60000)),
    )
    return AgentConfig(
        browser=browser,
        selectors=dict(raw.get("selectors", {})),
    )


def action_delay_ms() -> int:
    v = os.environ.get("AGENT_ACTION_DELAY_MS", "0")
    try:
        return max(0, int(v))
    except ValueError:
        return 0


def headless_mode(cfg: AgentConfig) -> bool:
    """Env TRAILHEAD_AGENT_HEADLESS overrides YAML (true/false/1/0)."""
    v = os.environ.get("TRAILHEAD_AGENT_HEADLESS", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return cfg.browser.headless


def persistent_profile_dir() -> Path | None:
    """If set, Chromium uses this user-data dir (cookies, Google SSO session)."""
    v = os.environ.get("TRAILHEAD_BROWSER_USER_DATA_DIR", "").strip()
    if not v:
        return None
    return Path(v).expanduser().resolve()


def record_video_dir() -> Path | None:
    """If set, Playwright saves a .webm for the session under this directory."""
    v = os.environ.get("TRAILHEAD_RECORD_VIDEO_DIR", "").strip()
    if not v:
        return None
    p = Path(v).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def record_video_scroll_demo() -> bool:
    """
    When recording (TRAILHEAD_RECORD_VIDEO_DIR), scroll the page briefly so .webm demos show motion.
    The agent mostly reads the DOM (no clicking); without this, the video looks like one frozen frame.
    Set TRAILHEAD_VIDEO_SCROLL_DEMO=0 to disable.
    """
    if record_video_dir() is None:
        return False
    v = os.environ.get("TRAILHEAD_VIDEO_SCROLL_DEMO", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def start_url_from_env() -> str | None:
    u = os.environ.get("TRAILHEAD_START_URL", "").strip()
    return u or None


def intent_from_env() -> str | None:
    t = os.environ.get("TRAILHEAD_INTENT", "").strip()
    return t or None


def trailhead_host() -> str:
    return os.environ.get("TRAILHEAD_ALLOWED_HOST", "trailhead.salesforce.com").strip().lower()


def trailhead_origin() -> str:
    return f"https://{trailhead_host()}/"
