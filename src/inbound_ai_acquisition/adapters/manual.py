"""本地手工资料适配器，不访问网络。"""

from __future__ import annotations

from typing import Any

from ..storage.database import canonical_hash
from .base import SourceResult


class ManualAdapter:
    capabilities = {"discover", "inspect_company", "inspect_contact"}

    def __init__(self, adapter_id: str = "manual") -> None:
        self.adapter_id = adapter_id

    def _result(self, request: dict[str, Any]) -> SourceResult:
        observations = list(request.get("observations", []))
        return SourceResult(
            adapter_id=self.adapter_id,
            outcome="succeeded" if observations else "no_results",
            query_fingerprint=canonical_hash(request),
            observations=observations,
        )

    discover = _result
    inspect_company = _result
    inspect_contact = _result
