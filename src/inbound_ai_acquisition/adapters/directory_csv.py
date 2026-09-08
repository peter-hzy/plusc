"""用户明确提供的行业目录 CSV 适配器。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..storage.database import canonical_hash
from .base import SourceResult


class DirectoryCsvAdapter:
    adapter_id = "directory_csv"
    capabilities = {"discover"}

    def discover(self, request: dict[str, Any]) -> SourceResult:
        path = Path(str(request.get("path", ""))).expanduser().resolve()
        if not path.is_file():
            return SourceResult(self.adapter_id, "failed_terminal", canonical_hash(request), error_code="file_not_found")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            observations = [dict(row) for row in csv.DictReader(handle)]
        return SourceResult(
            self.adapter_id,
            "succeeded" if observations else "no_results",
            canonical_hash(path.read_bytes().hex()),
            observations=observations,
        )

    def inspect_company(self, request: dict[str, Any]) -> SourceResult:
        return SourceResult(self.adapter_id, "restricted", canonical_hash(request), error_code="unsupported_capability")

    inspect_contact = inspect_company
