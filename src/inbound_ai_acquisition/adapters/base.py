"""来源适配器统一合同。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class SourceResult:
    adapter_id: str
    outcome: str
    query_fingerprint: str
    observations: list[dict[str, Any]] = field(default_factory=list)
    error_code: str = ""
    retryable: bool = False
    cost_amount: float | None = None


class SourceAdapter(Protocol):
    adapter_id: str
    capabilities: set[str]

    def discover(self, request: dict[str, Any]) -> SourceResult: ...
    def inspect_company(self, request: dict[str, Any]) -> SourceResult: ...
    def inspect_contact(self, request: dict[str, Any]) -> SourceResult: ...
