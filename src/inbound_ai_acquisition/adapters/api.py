"""可选窄接口；只有显式执行才联网，未配置不产生费用或伪造结果。"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..storage.database import canonical_hash, utc_now
from .base import SourceResult


class ApiAdapter:
    def __init__(self, provider: str):
        self.adapter_id = provider
        self.key_name = {"brave": "BRAVE_SEARCH_API_KEY", "apollo": "APOLLO_API_KEY", "hunter": "HUNTER_API_KEY"}[
            provider
        ]
        self.capabilities = {"discover"} if provider == "brave" else {"inspect_contact"}

    def status(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "configured": bool(os.environ.get(self.key_name)),
            "capabilities": sorted(self.capabilities),
            "live_verified": False,
        }

    def execute(self, operation: str, request: dict[str, Any]) -> SourceResult:
        fingerprint = canonical_hash({"provider": self.adapter_id, "operation": operation, "request": request})
        result = SourceResult(self.adapter_id, "unavailable", fingerprint, cost_amount=None)
        key = os.environ.get(self.key_name)
        if not key:
            result.error_code = "api_key_not_configured"
            return result
        if operation not in self.capabilities:
            result.error_code = "unsupported_operation"
            return result
        headers = {"Accept": "application/json"}
        data = None
        if self.adapter_id == "brave":
            query = str(request.get("query", "")).strip()
            if not query:
                result.error_code = "query_required"
                return result
            url = "https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": query, "count": 10})
            headers["X-Subscription-Token"] = key
        elif self.adapter_id == "apollo":
            domain = str(request.get("domain", "")).strip()
            titles = request.get("titles", [])
            if not domain or not isinstance(titles, list) or not titles:
                result.error_code = "company_domain_and_role_titles_required"
                return result
            url = "https://api.apollo.io/api/v1/mixed_people/api_search"
            headers.update({"X-Api-Key": key, "Content-Type": "application/json"})
            data = json.dumps(
                {"q_organization_domains_list": [domain], "person_titles": titles, "page": 1, "per_page": 10}
            ).encode()
        else:
            email = str(request.get("email", "")).strip()
            if "@" not in email:
                result.error_code = "email_required"
                return result
            url = "https://api.hunter.io/v2/email-verifier?" + urlencode({"email": email, "api_key": key})
        try:
            with urlopen(Request(url, data=data, headers=headers), timeout=20) as response:
                payload = json.loads(response.read(2_000_000).decode("utf-8"))
            if self.adapter_id == "brave":
                records = payload.get("web", {}).get("results", [])
                result.observations = [
                    {
                        "source_url": r["url"],
                        "observed_text": r.get("description", ""),
                        "title": r.get("title", ""),
                        "source_level": "search_lead",
                        "observed_at": utc_now(),
                        "requires_original_page": True,
                    }
                    for r in records
                    if r.get("url")
                ]
            elif self.adapter_id == "apollo":
                result.observations = [
                    {
                        "provider_record_id": r.get("id"),
                        "name": r.get("first_name", ""),
                        "title": r.get("title", ""),
                        "identity_status": "unverified",
                        "observed_at": utc_now(),
                        "source_url": "https://docs.apollo.io/reference/people-api-search",
                        "source_kind": "provider_api",
                        "requires_identity_verification": True,
                    }
                    for r in payload.get("people", [])
                ]
            else:
                value = payload.get("data", {})
                result.observations = [
                    {
                        "email": request["email"],
                        "verification_status": value.get("status", "unknown"),
                        "result": value.get("result", "unknown"),
                        "observed_at": utc_now(),
                        "source_kind": "provider_api",
                        "identity_verified": False,
                        "marketing_consent": "unknown",
                    }
                ]
            result.outcome = "succeeded" if result.observations else "no_results"
        except HTTPError as exc:
            result.outcome = (
                "rate_limited"
                if exc.code == 429
                else "restricted"
                if exc.code in {401, 403}
                else "failed_retryable"
                if exc.code >= 500
                else "failed_terminal"
            )
            result.error_code = f"http_{exc.code}"
            result.retryable = exc.code == 429 or exc.code >= 500
            exc.close()
        except (URLError, TimeoutError, OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
            result.outcome = "failed_retryable" if isinstance(exc, (URLError, TimeoutError)) else "failed_terminal"
            # 不回传带有API Key的请求URL或异常正文。
            result.error_code = type(exc).__name__
            result.retryable = result.outcome == "failed_retryable"
        return result

    def discover(self, request: dict[str, Any]) -> SourceResult:
        return self.execute("discover", request)

    def inspect_contact(self, request: dict[str, Any]) -> SourceResult:
        return self.execute("inspect_contact", request)

    def inspect_company(self, request: dict[str, Any]) -> SourceResult:
        return self.execute("inspect_company", request)
