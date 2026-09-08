"""无需登录的公开网页读取适配器。"""

from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..storage.database import canonical_hash
from .base import SourceResult


class PublicWebAdapter:
    adapter_id = "public_web"
    capabilities = {"inspect_company", "inspect_contact"}

    def discover(self, request: dict[str, Any]) -> SourceResult:
        return SourceResult(
            adapter_id=self.adapter_id,
            outcome="restricted",
            query_fingerprint=canonical_hash(request),
            error_code="search_provider_not_configured",
            retryable=False,
        )

    def _inspect(self, request: dict[str, Any]) -> SourceResult:
        url = str(request.get("url", "")).strip()
        fingerprint = canonical_hash({"url": url})
        if not url.startswith(("http://", "https://")):
            return SourceResult(self.adapter_id, "failed_terminal", fingerprint, error_code="invalid_url")
        try:
            req = Request(url, headers={"User-Agent": "inbound-ai-acquisition/1.0 (+public research)"})
            with urlopen(req, timeout=float(request.get("timeout", 15))) as response:  # noqa: S310
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "text/plain"}:
                    return SourceResult(self.adapter_id, "restricted", fingerprint, error_code="unsupported_content")
                raw = response.read(1_000_000).decode(response.headers.get_content_charset() or "utf-8", "replace")
            text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", raw, flags=re.I)
            text = unescape(re.sub(r"<[^>]+>", " ", text))
            text = re.sub(r"\s+", " ", text).strip()[:12000]
            return SourceResult(
                self.adapter_id,
                "succeeded" if text else "no_results",
                fingerprint,
                observations=[{"source_url": url, "observed_text": text}] if text else [],
            )
        except HTTPError as exc:
            retryable = exc.code in {429, 500, 502, 503, 504}
            return SourceResult(
                self.adapter_id,
                "restricted"
                if exc.code in {401, 403, 429}
                else "failed_retryable"
                if retryable
                else "failed_terminal",
                fingerprint,
                error_code=f"http_{exc.code}",
                retryable=retryable,
            )
        except (URLError, TimeoutError) as exc:
            return SourceResult(
                self.adapter_id,
                "failed_retryable",
                fingerprint,
                error_code=type(exc).__name__,
                retryable=True,
            )

    inspect_company = _inspect
    inspect_contact = _inspect
