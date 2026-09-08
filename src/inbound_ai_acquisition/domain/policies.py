"""外联、回复和停止联系的确定性规则。"""

from __future__ import annotations

import re
from typing import Any

from ..errors import StateError, ValidationError
from .enums import STOP_REPLIES, TAKEOVER_REPLIES


def require_one_cta(text: str) -> None:
    units = [part.strip().lower() for part in re.split(r"(?<=[?.!])|[\r\n]+", text) if part.strip()]
    markers = ("?", "would you", "could you", "are you open", "let me know")
    cta_units = sum(any(marker in unit for marker in markers) for unit in units)
    if cta_units != 1:
        raise ValidationError("草稿必须且只能包含一个轻量 CTA")


def normalize_reply(payload: dict[str, Any]) -> dict[str, Any]:
    category = str(payload.get("reply_category", "")).strip()
    if not category:
        raise ValidationError("回复缺少 reply_category")
    result = dict(payload)
    result["needs_human_takeover"] = category in TAKEOVER_REPLIES or bool(payload.get("needs_human_takeover"))
    result["do_not_contact"] = category in STOP_REPLIES or bool(payload.get("do_not_contact"))
    return result


def ensure_draft_can_advance(
    *,
    has_contact: bool,
    identity_status: str,
    accepted_claims: int,
    open_blocking_gaps: int,
    stopped: bool,
) -> None:
    failures: list[str] = []
    if not has_contact:
        failures.append("缺少联系人")
    if identity_status not in {"supported", "verified"}:
        failures.append("联系人身份未核验")
    if accepted_claims < 1:
        failures.append("缺少已接受的联系依据")
    if open_blocking_gaps:
        failures.append("仍有阻止外联的研究缺口")
    if stopped:
        failures.append("命中停止联系规则")
    if failures:
        raise StateError("；".join(failures))
