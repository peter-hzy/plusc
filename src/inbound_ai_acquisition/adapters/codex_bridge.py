"""Codex 公开网页研究结果的严格桥接适配器。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from ..domain.enums import SOURCE_OUTCOMES
from ..errors import ValidationError
from ..storage.database import canonical_hash
from .base import SourceResult


class CodexBridgeAdapter:
    """接收 Codex 已实际打开网页后产生的结构化观察，不负责伪造搜索结果。"""

    adapter_id = "codex_bridge"
    capabilities = {"discover", "inspect_company", "inspect_contact"}

    @staticmethod
    def _execute(request: dict[str, Any]) -> SourceResult:
        observations = request.get("observations", [])
        if not isinstance(observations, list):
            raise ValidationError("codex_bridge observations 必须是数组")
        for row in observations:
            url = str(row.get("source_url", "")).strip()
            text = str(row.get("observed_text", "")).strip()
            host = (urlsplit(url).hostname or "").lower()
            if not url.startswith(("http://", "https://")) or not host or host.endswith(".test"):
                raise ValidationError("codex_bridge 只接受真实公开 http(s) 来源")
            if not text:
                raise ValidationError("codex_bridge 必须保存打开页面后的 observed_text")
        outcome = str(request.get("outcome") or ("succeeded" if observations else "no_results"))
        if outcome not in SOURCE_OUTCOMES:
            raise ValidationError(f"codex_bridge outcome 不合法：{outcome}")
        if outcome == "succeeded" and not observations:
            raise ValidationError("codex_bridge succeeded 必须包含至少一条 observation")
        if outcome != "succeeded" and observations:
            raise ValidationError("未成功的读取不能携带事实 observation")
        if not isinstance(request.get("retryable", False), bool):
            raise ValidationError("retryable 必须是 JSON boolean")
        return SourceResult(
            adapter_id="codex_bridge",
            outcome=outcome,
            query_fingerprint=canonical_hash(request.get("query_summary", "")),
            observations=observations,
            error_code=str(request.get("error_code", "")),
            retryable=request.get("retryable", False),
        )

    discover = _execute
    inspect_company = _execute
    inspect_contact = _execute
