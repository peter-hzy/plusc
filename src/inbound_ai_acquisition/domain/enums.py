"""统一状态值。"""

RUN_STATUSES = {"created", "researching", "reviewing", "closed", "cancelled"}
CLAIM_STATUSES = {"proposed", "accepted", "held", "rejected", "superseded"}
DRAFT_STATUSES = {"draft", "review_ready", "approved", "sent", "stopped"}
SOURCE_OUTCOMES = {
    "succeeded",
    "no_results",
    "restricted",
    "failed_retryable",
    "failed_terminal",
    "cancelled",
}
CONTACT_IDENTITY_STATUSES = {"unverified", "supported", "verified", "not_found", "contradicted"}
REPLY_CATEGORIES = {
    "interested",
    "request_info",
    "request_quote",
    "meeting_requested",
    "not_now",
    "declined",
    "wrong_person",
    "unsubscribe",
    "complaint",
    "other",
}
TAKEOVER_REPLIES = {"request_quote", "meeting_requested", "unsubscribe", "complaint"}
STOP_REPLIES = {"unsubscribe", "complaint"}
