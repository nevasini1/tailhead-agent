from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class UnitRef:
    title: str
    href: str
    reason: str = ""  # LLM ranking rationale when present; empty from discovery-only paths

    @property
    def path(self) -> str:
        return urlparse(self.href).path.lower()
