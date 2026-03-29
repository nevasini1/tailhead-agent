from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from trailhead_agent.context import get_trace_id


class RunContextFilter(logging.Filter):
    """Attach trace_id and llm_provider for formatters (no secrets)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "-"
        record.llm_provider = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
        return True


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line (stdout/stderr friendly for aggregators)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "llm_provider": getattr(record, "llm_provider", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, level: int, json_format: bool) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(RunContextFilter())
    if json_format:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(levelname)s %(name)s [%(trace_id)s] %(message)s")
        )
    root.addHandler(handler)
    root.setLevel(level)
