"""Pure rules for reviews and the later community modules.

The browser never decides these. A low score is not a hold reason, and portal
status is not an input to ratings, moderation, or sorting.
"""

import hashlib
import hmac
import json
import re
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone

MODULE_KEYS = (
    "reviews",
    "claims",
    "groupPortal",
    "lawGuides",
    "lookingFor",
    "events",
    "badges",
    "favorites",
)

# Portal grants must not change this order. Featured stays a hand-set label.
SORT_NOTE = "featured, then needs-confirmation, then name"

COLLECTION_NAMES = (
    "accounts",
    "reviews",
    "replies",
    "flags",
    "claims",
    "overrides",
    "portals",
    "members",
    "invites",
    "children",
    "offerings",
    "enrollments",
    "payments",
    "announcements",
    "deliveries",
    "rotation",
    "looking_posts",
    "looking_replies",
    "events",
    "favorites",
    "watches",
    "history",
    "rate_limits",
)

DEFAULT_CATEGORIES = [
    {"id": "welcoming", "label": "Welcoming to new families", "active": True},
    {"id": "organized", "label": "Well organized", "active": True},
    {"id": "communication", "label": "Clear communication", "active": True},
    {"id": "worth-it", "label": "Worth the time and cost", "active": True},
]

HELD_MESSAGE = (
    "A moderator will look at this before it appears. New accounts wait for the "
    "first couple of reviews. A review also waits if it may include a name, an "
    "address, or harsh wording. A low rating is not a reason to wait."
)

NAME_STOP = {
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "by",
    "we", "our", "their", "this", "that", "these", "those", "new", "west",
    "east", "north", "south", "my", "his", "her", "its",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}

_STREET = re.compile(
    r"\b\d{1,6}\s+(?:[A-Za-z0-9.'#-]+\s+){0,5}"
    r"(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd|court|ct|"
    r"way|circle|cir|parkway|pkwy|trail|trl|highway|hwy)\b",
    re.I,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(
    r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?!\d)"
    r"|\b\d{3}[\s.-]\d{4}\b"
)
_CHILD = re.compile(r"\bmy\s+(?:son|daughter|child|kid)\s+[A-Za-z][a-z]{1,20}\b", re.I)
_TWO_WORDS = re.compile(r"\b([A-Z][a-z]{1,20})\s+([A-Z][a-z]{1,20})\b")


def utcnow():
    return datetime.now(timezone.utc)


def iso(moment):
    if isinstance(moment, str):
        return moment
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def new_id(prefix):
    return prefix + secrets.token_hex(8)


def default_settings(modules=None):
    flags = {key: False for key in MODULE_KEYS}
    flags["reviews"] = True
    if modules:
        for key in MODULE_KEYS:
            if key in modules:
                flags[key] = bool(modules[key])
    return {
        "inviteRequired": True,
        "inviteCode": "FRIENDS-TEST",
        "nameCheck": True,
        "addressCheck": True,
        "harshLanguageCheck": True,
        "harshWords": ["stupid", "idiot"],
        "newAccountHoldCount": 2,
        "flagsToHide": 3,
        "trustedBadgeAfter": 3,
        "lookingForExpireDays": 90,
        "portalMonthlyFeeCents": None,
        "portalDuesCutPercent": None,
        "paymentsMode": "test-only",
        "modules": flags,
        "ratingCategories": [dict(row) for row in DEFAULT_CATEGORIES],
    }


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 50000)
    return f"pbkdf2${salt}${digest.hex()}"


def check_password(password, stored):
    try:
        kind, salt, _digest = stored.split("$", 2)
    except (AttributeError, ValueError):
        return False
    if kind != "pbkdf2":
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


def issue_token(account_id, secret, ttl_seconds=14 * 24 * 3600, now=None):
    now = int(now or time.time())
    payload = {"sub": account_id, "exp": now + ttl_seconds}
    body = urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_token(token, secret, now=None):
    try:
        body, sig = token.split(".", 1)
    except (AttributeError, ValueError):
        return None
    expected = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    padded = body + "=" * (-len(body) % 4)
    try:
        payload = json.loads(urlsafe_b64decode(padded.encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(now or time.time()):
        return None
    return payload.get("sub")


def display_name_error(name):
    text = (name or "").strip()
    if len(text) < 2 or len(text) > 60:
        return "Use a family name, or a first name and last initial."
    if "@" in text or _EMAIL.search(text) or _PHONE.search(text):
        return "Don't use an email address or a phone number as your display name."
    return ""


def active_categories(settings):
    return [row for row in settings["ratingCategories"] if row.get("active")]


def short_label(category):
    known = {
        "welcoming": "Welcoming",
        "organized": "Organized",
        "communication": "Communication",
        "worth-it": "Worth it",
    }
    if category["id"] in known:
        return known[category["id"]]
    return " ".join(category["label"].split()[:2]) or category["id"]


def ratings_error(ratings, settings):
    if not isinstance(ratings, dict) or not ratings:
        return "Choose at least one category score."
    allowed = {row["id"]: row for row in settings["ratingCategories"]}
    active = {row["id"] for row in active_categories(settings)}
    scored = 0
    for key, value in ratings.items():
        if key not in allowed:
            return "That rating category isn't used here."
        if key not in active:
            return "That category is hidden. Pick a different one."
        if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 5:
            return "Each score is a whole number from 1 to 5."
        scored += 1
    if scored < 1:
        return "Choose at least one category score."
    return ""


def _words(text):
    return {part.lower() for part in re.findall(r"[A-Za-z0-9']+", text or "")}


def filter_text(text, settings, org_name=""):
    """Return hold reasons. An empty list means the text may publish.

    Scores are not an input. A 1 is not a reason to hold.
    """
    reasons = []
    body = text or ""
    if not body.strip():
        return reasons
    if settings.get("addressCheck", True):
        if _STREET.search(body):
            reasons.append("address")
        if _EMAIL.search(body):
            reasons.append("email")
        if _PHONE.search(body):
            reasons.append("phone")
    if settings.get("nameCheck", True):
        if _CHILD.search(body):
            reasons.append("possible-name")
        else:
            org_tokens = _words(org_name)
            org_flat = (org_name or "").lower()
            for first, second in _TWO_WORDS.findall(body):
                if first.lower() in NAME_STOP:
                    continue
                phrase = f"{first} {second}".lower()
                if phrase in org_flat:
                    continue
                if first.lower() in org_tokens and second.lower() in org_tokens:
                    continue
                reasons.append("possible-name")
                break
    if settings.get("harshLanguageCheck", True):
        for word in settings.get("harshWords") or []:
            cleaned = str(word).strip()
            if not cleaned:
                continue
            if re.search(rf"\b{re.escape(cleaned)}\b", body, re.I):
                reasons.append("harsh-language")
                break
    return reasons


def filter_fields(parts, settings, org_name=""):
    """Run the filter on each field. Joining them would invent names across the gap."""
    reasons = []
    for part in parts:
        for reason in filter_text(part or "", settings, org_name):
            if reason not in reasons:
                reasons.append(reason)
    return reasons


def with_new_account(reasons, account, settings):
    out = list(reasons)
    limit = int(settings.get("newAccountHoldCount", 2))
    if account.get("approvedReviewCount", 0) < limit and "new-account" not in out:
        out.append("new-account")
    return out


def contact_field_reasons(field, value, settings):
    """Description and contact fields. A public org phone or email, in its own field, is allowed."""
    text = value or ""
    if not text.strip():
        return []
    if field == "description":
        return filter_text(text, settings, org_name="")
    reasons = []
    if _STREET.search(text):
        reasons.append("address")
    if field == "email" and _PHONE.search(text):
        reasons.append("phone")
    if field == "phone" and _EMAIL.search(text):
        reasons.append("email")
    if field == "website" and (_EMAIL.search(text) or _PHONE.search(text)):
        reasons.append("email" if _EMAIL.search(text) else "phone")
    return reasons


def fee_split(amount_cents, percent):
    """Test arithmetic only. Nothing is collected or paid out."""
    dollars = f"${amount_cents / 100:.2f}"
    if percent is None:
        return {
            "platformShareCents": None,
            "collected": False,
            "summary": f"Test record: {dollars} dues, platform share not set, not collected.",
        }
    share = int(round(amount_cents * float(percent) / 100.0))
    group = amount_cents - share
    return {
        "platformShareCents": share,
        "collected": False,
        "summary": (
            f"Test record: {dollars} dues, ${share / 100:.2f} platform share (not collected), "
            f"${group / 100:.2f} to the group."
        ),
    }


def averages(reviews, settings):
    buckets = {row["id"]: [] for row in settings["ratingCategories"]}
    for review in reviews:
        if review.get("status") != "published":
            continue
        for key, value in (review.get("ratings") or {}).items():
            if key in buckets and isinstance(value, int):
                buckets[key].append(value)
    out = {}
    for key, values in buckets.items():
        if values:
            out[key] = round(sum(values) / len(values), 1)
    return out


def published_count(reviews):
    return sum(1 for review in reviews if review.get("status") == "published")


def summary_for(listing_id, reviews, settings):
    """Public summary. Portal status is intentionally absent."""
    mine = [review for review in reviews if review.get("listingId") == listing_id]
    count = published_count(mine)
    if count == 0:
        return None
    return {"listingId": listing_id, "reviewCount": count, "averages": averages(mine, settings)}


def preview_line(summary, settings):
    if not summary or not summary.get("reviewCount"):
        return ""
    labels = {row["id"]: short_label(row) for row in settings["ratingCategories"]}
    bits = [f"{summary['reviewCount']} review" + ("" if summary["reviewCount"] == 1 else "s")]
    for key, value in summary.get("averages", {}).items():
        bits.append(f"{labels.get(key, key)} {value:.1f}")
    return " · ".join(bits)


def card_line(summary):
    if not summary or not summary.get("reviewCount"):
        return ""
    n = summary["reviewCount"]
    return f"{n} family review" + ("" if n == 1 else "s")


def domain_of(website):
    match = re.search(r"^(?:https?://)?([^/:?#]+)", (website or "").strip(), re.I)
    if not match:
        return ""
    host = match.group(1).lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def email_on_domain(email, website):
    host = domain_of(website)
    if not host or "@" not in (email or ""):
        return False
    domain = email.rsplit("@", 1)[1].lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain == host or domain.endswith("." + host)


def hash_code(code, secret):
    return hmac.new(secret.encode("utf-8"), str(code).encode("utf-8"), hashlib.sha256).hexdigest()
