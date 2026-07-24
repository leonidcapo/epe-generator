from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Uniform return contract for every agent in this repo.

    ok       : the deterministic core always succeeds; ok=False is reserved
               for unrecoverable input errors (e.g. no Sheets access and no cache).
    data     : primary in-memory result.
    warnings : non-fatal notes (e.g. LLM degraded, PubMed unavailable).
    """

    ok: bool
    data: Any = None
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def success(cls, data: Any, warnings: list[str] | None = None) -> "AgentResult":
        return cls(ok=True, data=data, warnings=list(warnings or []))

    @classmethod
    def degraded(cls, data: Any, warnings: list[str]) -> "AgentResult":
        return cls(ok=True, data=data, warnings=list(warnings))

    @classmethod
    def failure(cls, warnings: list[str], data: Any = None) -> "AgentResult":
        return cls(ok=False, data=data, warnings=list(warnings))
