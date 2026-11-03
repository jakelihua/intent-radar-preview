"""Evidence gates shared by report, outreach and delivery.

Free-form capability descriptions are display text, never proof of fit. A human
review is bound to both the post revision and the seller snapshot; changing
either invalidates it. Historical posts can be reviewed but never become live
opportunities. The browser implements this same small contract, tested in CI.
"""
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit


COMPETITOR_ALIASES = {
    "jira": "atlassian jira",
    "confluence": "atlassian confluence",
    "salesforce": "salesforce crm",
    "newrelic": "new relic",
    "clerk.dev": "clerk",
    "hellosign": "hellosign / dropbox sign",
    "dropbox sign": "hellosign / dropbox sign",
    "twenty": "twenty crm",
}

INVALID_COMPETITOR_PLACEHOLDERS = {"", "未知", "通用行业竞品", "同赛道传统竞品", "none", "unknown"}


def canonical_competitor(name) -> str:
    cleaned = str(name or "").strip().lower()
    if not cleaned:
        return ""
    return COMPETITOR_ALIASES.get(cleaned, cleaned)


def text(value):
    return "；".join(str(x).strip() for x in value) if isinstance(value, list) else str(value or "").strip()


def seller_snapshot(profile):
    profile = profile if isinstance(profile, dict) else {}
    raw_targets = profile.get("target_competitors")
    raw_targets = raw_targets if isinstance(raw_targets, list) else []
    norm_targets = sorted({canonical_competitor(x) for x in raw_targets if canonical_competitor(x)})
    return [text(profile.get(k)) for k in (
        "brand_name", "actor_role", "approved_capabilities", "known_limitations", "cta_link"
    )] + [norm_targets]


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
    facts = facts if isinstance(facts, dict) else {}
    profile = profile if isinstance(profile, dict) else {}
    raw_targets = profile.get("target_competitors")
    raw_targets = raw_targets if isinstance(raw_targets, list) else []
    targets = [canonical_competitor(x) for x in raw_targets if canonical_competitor(x)]
    complete = bool(text(profile.get("brand_name")) and text(profile.get("actor_role"))
                    and text(profile.get("approved_capabilities")) and targets and "*" not in targets)
    # Exact normalized entity membership; substrings or empty strings must not match unrelated brands.
    raw_comp = str(facts.get("competitor") or "")
    entities = [
        canonical_competitor(x)
        for x in raw_comp.split("/")
        if canonical_competitor(x) and canonical_competitor(x) not in INVALID_COMPETITOR_PLACEHOLDERS
    ]
    compatible = bool(complete and entities and (set(entities) & set(targets)))
    raw_reviews = profile.get("reviews")
    raw_reviews = raw_reviews if isinstance(raw_reviews, dict) else {}
    raw_rev = raw_reviews.get(facts.get("source_id"))
    review = raw_rev if isinstance(raw_rev, dict) else {}
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
    actionable = ( current_review and review.get("authority_confirmed") is True
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
