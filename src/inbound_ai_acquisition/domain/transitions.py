"""状态迁移白名单。"""

from __future__ import annotations

from ..errors import StateError

ALLOWED_DRAFT_TRANSITIONS = {
    "draft": {"review_ready", "stopped"},
    "review_ready": {"approved", "draft", "stopped"},
    "approved": {"sent", "draft", "stopped"},
    "sent": set(),
    "stopped": set(),
}


def require_draft_transition(current: str, target: str) -> None:
    if target not in ALLOWED_DRAFT_TRANSITIONS.get(current, set()):
        raise StateError(f"不允许草稿从 {current} 变为 {target}")
