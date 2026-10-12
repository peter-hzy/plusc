"""Industry-neutral service-fit contract; no intent or semantic evidence inference."""

from typing import Any

from ..errors import ValidationError

SERVICE_FIELDS = (
    "fit_basis", "business_signal", "service_fit", "cooperation_hypothesis",
    "counter_evidence", "next_action",
)


def validate_service_fit(company: dict[str, Any]) -> dict[str, str]:
    values = {}
    for field in SERVICE_FIELDS:
        value = company.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"统一公司池缺少有效的 {field}")
        values[field] = value.strip()
    if values["fit_basis"] not in {"supported", "hypothesis"}:
        raise ValidationError("fit_basis 必须为 supported 或 hypothesis，不代表采购意向")
    if company.get("fit_status") == "priority_chat" and values["fit_basis"] != "supported":
        raise ValidationError("关键适配仍为假设，不能进入优先联系")
    return values


def segment_allowed(segment: str, configured: str) -> bool:
    allowed = {s.strip() for s in configured.split(",") if s.strip()}
    return "*" in allowed or segment in allowed
