"""Evidence gates shared by report, outreach and delivery.

Free-form capability descriptions are display text, never proof of fit. A human
review is bound to both the post revision and the seller snapshot; changing
either invalidates it. Historical posts can be reviewed but never become live
opportunities. The browser implements this same small contract, tested in CI.
"""
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit


def text(value):
    return "；".join(str(x).strip() for x in value) if isinstance(value, list) else str(value or "").strip()


def seller_snapshot(profile):
    profile = profile or {}
    return [text(profile.get(k)) for k in (
        "brand_name", "actor_role", "approved_capabilities", "known_limitations", "cta_link"
    )] + [sorted(str(x).strip().lower() for x in profile.get("target_competitors", []) if str(x).strip())]


def safe_contact(url):
    try:
        if not isinstance(url, str) or re.search(r'[\s<>"\\]', url):
            return False
        p = urlsplit(url)
        p.port  # Validate malformed/non-numeric ports as well as the hostname.
        return p.scheme in ("https", "http") and bool(p.hostname) and not p.username and not p.password
    except (ValueError, TypeError):
        return False


def evaluate_facts(facts, profile=None, now=None):
    """Pure policy contract. All clocks are explicit for reproducible tests."""
    now = now or datetime.now(timezone.utc)
    def utc_time(value):
        if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
            raise ValueError("Policy timestamps must use UTC")
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    profile = profile or {}
    targets = [str(x).strip().lower() for x in profile.get("target_competitors", [])]
    complete = bool(text(profile.get("brand_name")) and text(profile.get("actor_role"))
                    and text(profile.get("approved_capabilities")) and targets and "*" not in targets)
    # Exact normalized entity membership; substrings must not match unrelated brands.
    entities = [x.strip().lower() for x in facts.get("competitor", "").split("/")]
    compatible = complete and bool(set(entities) & set(targets))
    review = (profile.get("reviews") or {}).get(facts.get("source_id"), {})
    current_review = False
    try:
        reviewed = utc_time(review.get("reviewed_at", ""))
        age = (now - reviewed).total_seconds()
        current_review = bool(
            0 <= age <= 30 * 86400
            and review.get("source") == facts.get("source")
            and review.get("content_hash") == facts.get("content_hash")
            and review.get("seller_snapshot") == seller_snapshot(profile)
            and text(review.get("reviewer")) and text(review.get("evidence"))
        )
    except (ValueError, TypeError, AttributeError):
        pass
    s1 = facts.get("pain_verified") is True
    s2 = s1 and facts.get("evaluation_verified") is True
    fit = review.get("fit") if current_review else "pending"
    s3 = s2 and compatible and fit == "supported"
    fresh = False
    try:
        published = utc_time(facts.get("published_at", ""))
        fresh = 0 <= (now - published).total_seconds() <= 30 * 86400
    except (ValueError, TypeError, AttributeError):
        pass
    live = (facts.get("dataset_kind") == "live_production" and facts.get("delivery_eligible") is True and fresh
            and facts.get("content_complete") is True)
    actionable = (review.get("authority_confirmed") is True
                  and safe_contact(review.get("contact_url")) and bool(text(review.get("contact_evidence"))))
    s4 = bool(s3 and live and actionable)
    passed = [bool(s1), bool(s2), bool(s3), s4]
    count = next((i for i, ok in enumerate(passed) if not ok), 4)
    mismatch = bool(text(profile.get("brand_name")) and complete and not compatible)
    blocked = not s2 or mismatch or (current_review and fit == "unsupported")
    return {
        "passed": passed, "contiguous": count, "compatible": bool(compatible),
        "review_current": current_review, "live": bool(live),
        "policy_status": "blocked" if blocked else "approved_recommendation" if s3 and actionable else "neutral_inquiry_only",
        "can_outreach": not blocked, "can_recommend_product": bool(s3 and actionable and not blocked),
        "allow_webhook_push": bool(s4 and not blocked),
    }
