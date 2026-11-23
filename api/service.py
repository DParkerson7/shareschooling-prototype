"""Community rules that must run on the server.

Portal status does not change rating averages, which reviews are public,
moderation, search, or map order. Do not set featured or listingTier from
the portal, and do not put portal status on a public listing summary.
"""

import copy
import hmac
import os
import re
import secrets
from datetime import timedelta

from api.logic import (
    HELD_MESSAGE,
    averages,
    check_password,
    contact_field_reasons,
    default_settings,
    display_name_error,
    domain_of,
    email_on_domain,
    fee_split,
    filter_fields,
    filter_text,
    hash_code,
    hash_password,
    iso,
    issue_token,
    new_id,
    parse_iso,
    published_count,
    ratings_error,
    read_token,
    summary_for,
    utcnow,
    with_new_account,
)

SCORE_LABELS = ["Poor", "Fair", "Good", "Very good", "Excellent"]
RULES = (
    "Keep it about the group's program. Don't include children's names. "
    "Don't include home addresses, personal phone numbers, or personal emails. "
    "Fair criticism is welcome. A low rating is posted like any other review. "
    "Personal attacks aren't allowed."
)


class ServiceError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _by_id(rows, item_id):
    return next((row for row in rows if row.get("id") == item_id), None)


def _rows(state, name):
    return state["collections"][name]


class CommunityService:
    def __init__(self, store, catalog, secret, clock=None):
        self.store = store
        self.catalog = catalog
        self.secret = secret
        self.clock = clock or utcnow

    def _now(self):
        return self.clock()

    def tx(self, fn):
        return self.store.transaction(fn)

    def ensure_ready(self, modules=None):
        def op(state):
            if state["settings"] is None:
                state["settings"] = default_settings(modules)
            return True

        return self.tx(op)

    def ensure_admin(self, email, password, display_name="David"):
        email = (email or "").strip().lower()
        if not email or not password:
            return None
        if len(password) < 8:
            raise ServiceError("ADMIN_PASSWORD must be at least 8 characters.", 500)

        def op(state):
            existing = _account_by_email(_rows(state, "accounts"), email)
            if existing:
                return {"created": False, "id": existing["id"]}
            account = _new_account(email, password, display_name or "David", self._now())
            account["emailVerified"] = True
            account["roles"] = ["admin", "family"]
            _rows(state, "accounts").append(account)
            return {"created": True, "id": account["id"]}

        return self.tx(op)

    def reset_admin_password(self, email, password):
        """Used only by the one-off reset command when ADMIN_RESET=yes."""
        email = (email or "").strip().lower()
        if len(password or "") < 8:
            raise ServiceError("ADMIN_PASSWORD must be at least 8 characters.", 500)

        def op(state):
            account = _account_by_email(_rows(state, "accounts"), email)
            if not account:
                raise ServiceError("No account uses that email.", 404)
            account["passwordHash"] = hash_password(password)
            if "admin" not in account["roles"]:
                account["roles"] = sorted(set(account["roles"]) | {"admin", "family"})
            account["emailVerified"] = True
            account["removed"] = False
            return {"reset": True, "id": account["id"]}

        return self.tx(op)

    def signup(self, email, password, display_name, invite_code, company, ip):
        if str(company or "").strip():
            return {"ok": True}
        email = (email or "").strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""):
            raise ServiceError("Enter a valid email address.")
        if len(password or "") < 8:
            raise ServiceError("Use a password of at least 8 characters.")
        name_error = display_name_error(display_name)
        if name_error:
            raise ServiceError(name_error)

        def op(state):
            settings = state["settings"]
            now = self._now()
            _bump_rate(state, f"signup-ip:{ip or 'unknown'}", 8, 3600, now)
            _bump_rate(state, f"signup-email:{email}", 5, 3600, now)
            if settings.get("inviteRequired") and (invite_code or "").strip() != settings.get("inviteCode"):
                raise ServiceError("That invite code isn't right.")
            if _account_by_email(_rows(state, "accounts"), email):
                raise ServiceError("An account already uses that email.")
            account = _new_account(email, password, display_name.strip(), now)
            _rows(state, "accounts").append(account)
            token = issue_token(account["id"], self.secret, now=now.timestamp())
            return {"ok": True, "token": token, "account": _account_out(account, settings, email=True)}

        return self.tx(op)

    def login(self, email, password, ip):
        email = (email or "").strip().lower()

        def op(state):
            now = self._now()
            _bump_rate(state, f"login-ip:{ip or 'unknown'}", 40, 3600, now)
            account = _account_by_email(_rows(state, "accounts"), email)
            if not account or account.get("removed") or not check_password(password or "", account.get("passwordHash", "")):
                raise ServiceError("That email or password isn't right.", 401)
            token = issue_token(account["id"], self.secret, now=now.timestamp())
            return {"ok": True, "token": token, "account": _account_out(account, state["settings"], email=True)}

        return self.tx(op)

    def account_from_token(self, token):
        account_id = read_token(token or "", self.secret, now=self._now().timestamp())
        if not account_id:
            return None

        def op(state):
            account = _by_id(_rows(state, "accounts"), account_id)
            if not account or account.get("removed"):
                return None
            return copy.deepcopy(account)

        return self.tx(op)

    def public_settings(self):
        def op(state):
            settings = state["settings"]
            return {
                "demo": False,
                "modules": dict(settings["modules"]),
                "ratingCategories": copy.deepcopy(settings["ratingCategories"]),
                "inviteRequired": bool(settings.get("inviteRequired")),
                "trustedBadgeAfter": settings.get("trustedBadgeAfter"),
                "portalMonthlyFeeCents": settings.get("portalMonthlyFeeCents"),
                "portalDuesCutPercent": settings.get("portalDuesCutPercent"),
                "paymentsMode": "test-only",
                "stripeTestConfigured": _stripe_test_configured(),
                "scoreLabels": SCORE_LABELS,
                "rules": RULES,
            }

        return self.tx(op)

    def admin_settings(self, actor_id):
        def op(state):
            _require_admin(_live(state, actor_id))
            settings = copy.deepcopy(state["settings"])
            settings.pop("paymentsMode", None)
            settings["paymentsMode"] = "test-only"
            settings["stripeTestConfigured"] = _stripe_test_configured()
            return settings

        return self.tx(op)

    def update_settings(self, actor_id, patch):
        if not isinstance(patch, dict):
            raise ServiceError("Expected a JSON object.")

        def op(state):
            _require_admin(_live(state, actor_id))
            settings = state["settings"]
            _apply_settings_patch(state, settings, patch)
            settings["paymentsMode"] = "test-only"
            return copy.deepcopy(settings)

        return self.tx(op)

    def summaries(self, listing_ids):
        ids = [item for item in listing_ids if isinstance(item, str)][:200]

        def op(state):
            settings = state["settings"]
            if not settings["modules"].get("reviews"):
                return []
            reviews = _rows(state, "reviews")
            out = []
            for listing_id in ids:
                summary = summary_for(listing_id, reviews, settings)
                if summary:
                    out.append(summary)
            return out

        return self.tx(op)

    def public_overlays(self, listing_ids):
        ids = [item for item in listing_ids if isinstance(item, str)][:200]

        def op(state):
            settings = state["settings"]
            if not settings["modules"].get("claims"):
                return []
            out = []
            for listing_id in ids:
                overlay = _public_overlay(state, listing_id, settings)
                if overlay:
                    out.append(overlay)
            return out

        return self.tx(op)

    def listing_community(self, listing_id, viewer_id=None, offset=0, limit=10):
        self._listing(listing_id)
        offset = max(0, int(offset or 0))
        limit = min(50, max(1, int(limit or 10)))

        def op(state):
            settings = state["settings"]
            reviews = [row for row in _rows(state, "reviews") if row["listingId"] == listing_id]
            published = [row for row in reviews if row["status"] == "published"]
            published.sort(key=lambda row: row.get("publishedAt") or row.get("createdAt") or "", reverse=True)
            summary = summary_for(listing_id, reviews, settings) if settings["modules"].get("reviews") else None
            chosen = published[offset:offset + limit] if settings["modules"].get("reviews") else []
            if viewer_id and settings["modules"].get("reviews"):
                mine = next((row for row in reviews if row["authorId"] == viewer_id and row["status"] != "published"), None)
                if mine and all(row["id"] != mine["id"] for row in chosen):
                    chosen = [mine] + chosen
            payload = {
                "summary": summary,
                "reviews": [
                    _review_out(state, row, viewer_id, settings) for row in chosen
                ] if settings["modules"].get("reviews") else [],
                "total": published_count(reviews) if settings["modules"].get("reviews") else 0,
                "offset": offset,
                "overlay": _public_overlay(state, listing_id, settings),
                "claimLabel": _claim_label(state, listing_id, settings),
                "viewer": _viewer_out(state, listing_id, viewer_id, settings) if viewer_id else None,
            }
            return payload

        return self.tx(op)

    def save_review(self, actor_id, listing_id, ratings, body, ip):
        listing = self._listing(listing_id)
        ratings = _coerce_ratings(ratings)

        def op(state):
            account = _live(state, actor_id)
            settings = state["settings"]
            _need(settings, "reviews")
            _require_verified(account)
            _bump_rate(state, f"post:{account['id']}", 30, 3600, self._now())
            if _verified_claim(state, account["id"], listing_id):
                raise ServiceError("An organization doesn't review its own listing.")
            existing = next(
                (row for row in _rows(state, "reviews") if row["listingId"] == listing_id and row["authorId"] == account["id"]),
                None,
            )
            if existing and existing.get("status") == "removed":
                _clear_flags(state, "review", existing["id"])
                existing["flagCount"] = 0
            review = _apply_review(state, account, listing, ratings, body or "", existing, self._now())
            return _review_out(state, review, account["id"], state["settings"])

        return self.tx(op)

    def delete_review(self, actor_id, review_id):
        def op(state):
            account = _live(state, actor_id)
            review = _by_id(_rows(state, "reviews"), review_id)
            if not review or review["authorId"] != account["id"]:
                raise ServiceError("That review isn't yours.", 404)
            review["status"] = "removed"
            review["pending"] = None
            review["updatedAt"] = iso(self._now())
            return {"ok": True, "status": "removed"}

        return self.tx(op)

    def flag(self, actor_id, target_type, target_id, reason):
        if target_type not in ("review", "looking", "event"):
            raise ServiceError("That can't be flagged.")

        def op(state):
            account = _live(state, actor_id)
            _require_verified(account)
            target, collection = _flag_target(state, target_type, target_id)
            if target["authorId"] == account["id"]:
                raise ServiceError("You can't flag your own post.")
            flags = _rows(state, "flags")
            if any(row["targetType"] == target_type and row["targetId"] == target_id and row["authorId"] == account["id"] for row in flags):
                return {"ok": True, "counted": False, "flagCount": target.get("flagCount", 0), "status": target["status"]}
            if target_type == "review" and not (
                "family" in account.get("roles", []) or _verified_claim(state, account["id"], target.get("listingId"))
            ):
                raise ServiceError("Sign in with a family account to flag a review.", 403)
            if target.get("status") != "published":
                raise ServiceError("Only a live post can be flagged.")
            flags.append({
                "id": new_id("flag_"),
                "targetType": target_type,
                "targetId": target_id,
                "authorId": account["id"],
                "reason": (reason or "")[:500],
                "createdAt": iso(self._now()),
            })
            target["flagCount"] = sum(1 for row in flags if row["targetType"] == target_type and row["targetId"] == target_id)
            hidden = False
            if target["flagCount"] >= int(state["settings"].get("flagsToHide", 3)):
                target["status"] = "hidden"
                hidden = True
            return {"ok": True, "counted": True, "flagCount": target["flagCount"], "status": target["status"], "hidden": hidden}

        return self.tx(op)

    def save_reply(self, actor_id, review_id, body):
        def op(state):
            account = _live(state, actor_id)
            _need(state["settings"], "reviews")
            _require_verified(account)
            review = _by_id(_rows(state, "reviews"), review_id)
            if not review or review.get("status") != "published":
                raise ServiceError("You can reply once a review is public.", 404)
            if not _verified_claim(state, account["id"], review["listingId"]):
                raise ServiceError("Only the verified organization can reply.", 403)
            listing = self._listing(review["listingId"])
            text = (body or "").strip()
            if not text:
                raise ServiceError("Write a reply first.")
            if len(text) > 4000:
                raise ServiceError("That reply is too long.")
            reasons = filter_text(text, state["settings"], listing["name"])
            now = iso(self._now())
            reply = next((row for row in _rows(state, "replies") if row["reviewId"] == review_id), None)
            if reply is None:
                reply = {
                    "id": new_id("reply_"),
                    "reviewId": review_id,
                    "listingId": review["listingId"],
                    "authorId": account["id"],
                    "createdAt": now,
                    "previousBody": "",
                }
                _rows(state, "replies").append(reply)
                reply["body"] = text
                reply["pending"] = None
                reply["status"] = "held" if reasons else "published"
                reply["holdReasons"] = reasons
            elif reasons:
                if reply.get("status") == "published":
                    reply["pending"] = {"body": text, "holdReasons": reasons}
                else:
                    reply["body"] = text
                    reply["pending"] = None
                    reply["status"] = "held"
                    reply["holdReasons"] = reasons
            else:
                reply["body"] = text
                reply["pending"] = None
                reply["status"] = "published"
                reply["holdReasons"] = []
            reply["updatedAt"] = now
            return _review_out(state, review, account["id"], state["settings"])

        return self.tx(op)

    def start_claim(self, actor_id, listing_id, represents, method, contact_email, company):
        if str(company or "").strip():
            return {"ok": True}
        if not represents:
            raise ServiceError("Confirm that you represent this organization.")
        listing = self._listing(listing_id)
        method = (method or "manual").strip().lower()

        def op(state):
            account = _live(state, actor_id)
            _need(state["settings"], "reviews")
            _require_verified(account)
            existing = next(
                (row for row in _rows(state, "claims") if row["listingId"] == listing_id and row["status"] in ("Claimed", "Verified")),
                None,
            )
            if existing and existing["accountId"] != account["id"]:
                raise ServiceError("Someone has already asked to represent this listing.")
            if existing and existing["status"] == "Verified":
                return {"ok": True, "status": "Verified", "id": existing["id"], "message": "This listing is already verified for your account."}
            now = self._now()
            code = None
            target = ""
            stored_method = "manual"
            if method == "email":
                if not listing.get("email"):
                    raise ServiceError("This listing has no public email. Ask an admin to verify the claim.")
                code = f"{secrets.randbelow(1_000_000):06d}"
                target = listing["email"]
                stored_method = "email-code"
            elif method == "domain":
                contact = (contact_email or "").strip().lower()
                if not listing.get("website") or not email_on_domain(contact, listing.get("website")):
                    host = domain_of(listing.get("website")) or "the organization's website"
                    raise ServiceError(
                        f"Use an email address at {host}, or ask an admin to verify the claim."
                    )
                code = f"{secrets.randbelow(1_000_000):06d}"
                target = contact
                stored_method = "domain-code"
            elif method != "manual":
                raise ServiceError("Choose email, the website's domain, or admin verification.")
            if existing is None:
                existing = {
                    "id": new_id("claim_"),
                    "listingId": listing_id,
                    "accountId": account["id"],
                    "createdAt": iso(now),
                }
                _rows(state, "claims").append(existing)
            existing["status"] = "Claimed"
            existing["method"] = stored_method
            existing["targetEmail"] = target
            existing["codePlain"] = code or ""
            existing["codeHash"] = hash_code(code, self.secret) if code else ""
            existing["codeExpiresAt"] = iso(now + timedelta(hours=24)) if code else ""
            message = "An admin can mark this claim verified. This test server doesn't send mail."
            if code:
                message = (
                    "This test server can't send mail. The code is in the admin queue for David to pass along, "
                    "or he can mark the claim verified."
                )
            return {
                "ok": True,
                "id": existing["id"],
                "status": "Claimed",
                "method": stored_method,
                "message": message,
                "mailed": False,
            }

        return self.tx(op)

    def submit_claim_code(self, actor_id, claim_id, code):
        def op(state):
            account = _live(state, actor_id)
            claim = _by_id(_rows(state, "claims"), claim_id)
            if not claim or claim["accountId"] != account["id"]:
                raise ServiceError("That claim isn't yours.", 404)
            if claim["status"] == "Verified":
                return {"ok": True, "status": "Verified"}
            if not claim.get("codeHash"):
                raise ServiceError("This claim is waiting for an admin, not a code.")
            if claim.get("codeExpiresAt") and parse_iso(claim["codeExpiresAt"]) < self._now():
                raise ServiceError("That code expired. Start the claim again.")
            if not hmac.compare_digest(claim["codeHash"], hash_code(str(code or "").strip(), self.secret)):
                raise ServiceError("That code isn't right.")
            _mark_claim_verified(state, claim, self._now())
            return {"ok": True, "status": "Verified"}

        return self.tx(op)

    def save_overlay(self, actor_id, listing_id, fields):
        self._listing(listing_id)
        if not isinstance(fields, dict):
            raise ServiceError("Expected a JSON object.")

        def op(state):
            account = _live(state, actor_id)
            settings = state["settings"]
            _need(settings, "claims")
            _require_verified(account)
            if not _verified_claim(state, account["id"], listing_id):
                raise ServiceError("Only the verified organization can edit this listing.", 403)
            overlay = _overlay_row(state, listing_id)
            now = self._now()
            pending = dict(overlay.get("pending") or {})
            allowed_now = ("openSpots", "meetingDays", "costNotes")
            checked = ("description", "website", "email", "phone")
            for key in allowed_now:
                if key in fields:
                    overlay[key] = str(fields.get(key) or "")[:500]
            for key in checked:
                if key not in fields:
                    continue
                value = str(fields.get(key) or "")[:4000]
                reasons = contact_field_reasons(key, value, settings)
                if reasons:
                    pending[key] = {"value": value, "reasons": reasons}
                else:
                    overlay[key] = value
                    pending.pop(key, None)
            overlay["pending"] = pending or None
            overlay["lastUpdated"] = now.date().isoformat()
            overlay["updatedBy"] = account["id"]
            return _public_overlay(state, listing_id, settings)

        return self.tx(op)

    def queue(self, actor_id):
        def op(state):
            account = _live(state, actor_id)
            _require_staff(account)
            return _queue_items(state, self.catalog, self._now())

        return self.tx(op)

    def moderate(self, actor_id, kind, item_id, action, body="", ratings=None, note=""):
        action = (action or "").strip().lower()
        if action not in ("approve", "edit", "remove"):
            raise ServiceError("Choose approve, edit, or remove.")

        def op(state):
            account = _live(state, actor_id)
            _require_staff(account)
            now = iso(self._now())
            _moderate_item(state, kind, item_id, action, body or "", _coerce_ratings(ratings) if ratings else None, (note or "")[:500], now, self.catalog)
            return {"ok": True}

        return self.tx(op)

    def accounts(self, actor_id):
        def op(state):
            _require_admin(_live(state, actor_id))
            settings = state["settings"]
            return [_account_out(row, settings, email=True) for row in _rows(state, "accounts") if not row.get("removed")]

        return self.tx(op)

    def verify_email(self, actor_id, account_id):
        def op(state):
            _require_admin(_live(state, actor_id))
            account = _by_id(_rows(state, "accounts"), account_id)
            if not account or account.get("removed"):
                raise ServiceError("That account isn't here.", 404)
            account["emailVerified"] = True
            return _account_out(account, state["settings"], email=True)

        return self.tx(op)

    def set_moderator(self, actor_id, account_id, grant):
        def op(state):
            _require_admin(_live(state, actor_id))
            account = _by_id(_rows(state, "accounts"), account_id)
            if not account or account.get("removed"):
                raise ServiceError("That account isn't here.", 404)
            roles = set(account.get("roles") or [])
            if grant:
                roles.add("moderator")
            else:
                roles.discard("moderator")
            account["roles"] = sorted(roles)
            trusted = account.get("approvedReviewCount", 0) >= int(state["settings"].get("trustedBadgeAfter", 3))
            out = _account_out(account, state["settings"], email=True)
            out["note"] = "Trusted families are the people this is for." if not trusted else ""
            return out

        return self.tx(op)

    def remove_account(self, actor_id, account_id):
        def op(state):
            admin = _live(state, actor_id)
            _require_admin(admin)
            account = _by_id(_rows(state, "accounts"), account_id)
            if not account:
                raise ServiceError("That account isn't here.", 404)
            if account["id"] == admin["id"]:
                raise ServiceError("You can't remove your own admin account.")
            account["removed"] = True
            account["displayName"] = "Removed account"
            account["roles"] = []
            return {"ok": True}

        return self.tx(op)

    def verify_claim(self, actor_id, claim_id):
        def op(state):
            _require_staff(_live(state, actor_id))
            claim = _by_id(_rows(state, "claims"), claim_id)
            if not claim:
                raise ServiceError("That claim isn't here.", 404)
            _mark_claim_verified(state, claim, self._now())
            return {"ok": True, "status": "Verified"}

        return self.tx(op)

    def revoke_claim(self, actor_id, claim_id):
        def op(state):
            _require_admin(_live(state, actor_id))
            claim = _by_id(_rows(state, "claims"), claim_id)
            if not claim:
                raise ServiceError("That claim isn't here.", 404)
            claim["status"] = "Revoked"
            claim["codePlain"] = ""
            claim["codeHash"] = ""
            _sync_org_role(state, claim["accountId"])
            portal = _by_id(_rows(state, "portals"), claim["listingId"])
            if portal:
                portal["active"] = False
            return {"ok": True, "status": "Revoked"}

        return self.tx(op)

    def grant_portal(self, actor_id, listing_id, active):
        # Granting the portal does not change reviews, averages, moderation, or map order.
        self._listing(listing_id)

        def op(state):
            admin = _live(state, actor_id)
            _require_admin(admin)
            _need(state["settings"], "groupPortal")
            claim = _listing_verified(state, listing_id)
            if not claim:
                raise ServiceError("Verify a claim before granting the group portal.")
            portal = _portal_row(state, listing_id)
            portal["active"] = bool(active)
            portal["source"] = "admin-grant"
            portal["grantedBy"] = admin["id"]
            portal["publicBadge"] = False
            now = iso(self._now())
            if active:
                portal["startedAt"] = portal.get("startedAt") or now
                portal["endedAt"] = ""
                _ensure_organizer(state, listing_id, claim["accountId"])
            else:
                portal["endedAt"] = now
            return _portal_admin_out(portal)

        return self.tx(op)

    def mark_portal_paid(self, actor_id, listing_id):
        """Simulated payment. Nothing is charged."""
        self._listing(listing_id)

        def op(state):
            account = _live(state, actor_id)
            _need(state["settings"], "groupPortal")
            _require_verified(account)
            if not _verified_claim(state, account["id"], listing_id):
                raise ServiceError("Only the verified organization can turn the portal on.", 403)
            portal = _portal_row(state, listing_id)
            portal["active"] = True
            portal["source"] = "mark-as-paid"
            portal["grantedBy"] = account["id"]
            portal["publicBadge"] = False
            portal["startedAt"] = portal.get("startedAt") or iso(self._now())
            portal["endedAt"] = ""
            _ensure_organizer(state, listing_id, account["id"])
            price = state["settings"].get("portalMonthlyFeeCents")
            return {
                "ok": True,
                "charged": False,
                "portal": _portal_admin_out(portal),
                "message": "Pricing isn't set yet. This test won't charge you." if price in (None, "") else "Marked as paid (test). Nothing was charged.",
            }

        return self.tx(op)

    def portal_home(self, actor_id, listing_id):
        self._listing(listing_id)

        def op(state):
            account = _live(state, actor_id)
            _need(state["settings"], "groupPortal")
            portal, member = _require_member(state, account, listing_id)
            return _portal_home(state, listing_id, account, member, portal, self.catalog)

        return self.tx(op)

    def invite_member(self, actor_id, listing_id, email):
        listing = self._listing(listing_id)
        email = (email or "").strip().lower()
        if "@" not in email:
            raise ServiceError("Enter the member's email address.")

        def op(state):
            account = _live(state, actor_id)
            _require_organizer(state, account, listing_id)
            invites = _rows(state, "invites")
            existing = next((row for row in invites if row["listingId"] == listing_id and row["email"] == email), None)
            if existing is None:
                existing = {"id": new_id("inv_"), "listingId": listing_id, "email": email, "createdAt": iso(self._now())}
                invites.append(existing)
            message = (
                f"You're invited to the {listing['name']} group portal on ShareSchooling (a test). "
                f"Sign in with {email} and open the group. Nothing is charged in this test."
            )
            return {"ok": True, "emailed": False, "email": email, "message": message}

        return self.tx(op)

    def join_portal(self, actor_id, listing_id):
        def op(state):
            account = _live(state, actor_id)
            _need(state["settings"], "groupPortal")
            _require_verified(account)
            if not _portal_active(state, listing_id):
                raise ServiceError("This group portal is off.", 404)
            invite = next(
                (row for row in _rows(state, "invites") if row["listingId"] == listing_id and row["email"] == account["email"]),
                None,
            )
            if invite is None and not _member(state, listing_id, account["id"]):
                raise ServiceError("There's no invite for this email.")
            _ensure_member(state, listing_id, account["id"], "member")
            if invite:
                _rows(state, "invites").remove(invite)
            return {"ok": True, "role": _member(state, listing_id, account["id"])["role"]}

        return self.tx(op)

    def add_child(self, actor_id, listing_id, first_name, grade):
        first = (first_name or "").strip()
        grade = (grade or "").strip()
        if not first or len(first) > 40 or "@" in first:
            raise ServiceError("Use the child's first name only.")
        if not grade or len(grade) > 20:
            raise ServiceError("Add a grade, such as 4 or K.")

        def op(state):
            account = _live(state, actor_id)
            _require_member(state, account, listing_id)
            child = {
                "id": new_id("child_"),
                "accountId": account["id"],
                "listingId": listing_id,
                "firstName": first,
                "grade": grade,
                "private": True,
            }
            _rows(state, "children").append(child)
            return {"id": child["id"], "firstName": first, "grade": grade}

        return self.tx(op)

    def add_offering(self, actor_id, listing_id, kind, title, capacity, fee_cents, starts_on, ends_on):
        if kind not in ("class", "field-trip", "semester"):
            raise ServiceError("An offering is a class, a field trip, or a semester.")
        title = (title or "").strip()
        if not title:
            raise ServiceError("Name the offering.")
        capacity = int(capacity or 0)
        fee_cents = int(fee_cents or 0)
        if capacity < 1:
            raise ServiceError("Capacity is at least 1.")
        if fee_cents < 0:
            raise ServiceError("A fee can't be negative. Use 0 if it's free.")

        def op(state):
            account = _live(state, actor_id)
            _require_organizer(state, account, listing_id)
            offering = {
                "id": new_id("off_"),
                "listingId": listing_id,
                "kind": kind,
                "title": title[:140],
                "capacity": capacity,
                "feeCents": fee_cents,
                "startsOn": starts_on or "",
                "endsOn": ends_on or "",
            }
            _rows(state, "offerings").append(offering)
            return offering

        return self.tx(op)

    def signup_offering(self, actor_id, offering_id, child_id=None):
        def op(state):
            account = _live(state, actor_id)
            offering = _by_id(_rows(state, "offerings"), offering_id)
            if not offering:
                raise ServiceError("That offering isn't here.", 404)
            _require_member(state, account, offering["listingId"])
            if child_id:
                child = _by_id(_rows(state, "children"), child_id)
                if not child or child["accountId"] != account["id"]:
                    raise ServiceError("That child record isn't on your account.", 404)
            enrollments = _rows(state, "enrollments")
            current = [
                row for row in enrollments
                if row["offeringId"] == offering_id and row["accountId"] == account["id"] and row["state"] != "dropped"
            ]
            if current:
                raise ServiceError("You're already signed up for that.")
            enrolled = [row for row in enrollments if row["offeringId"] == offering_id and row["state"] == "enrolled"]
            now = iso(self._now())
            row = {
                "id": new_id("enr_"),
                "offeringId": offering_id,
                "listingId": offering["listingId"],
                "accountId": account["id"],
                "childId": child_id or "",
                "createdAt": now,
            }
            if len(enrolled) < int(offering["capacity"]):
                row["state"] = "enrolled"
                row["waitlistPosition"] = None
                row["paymentState"] = "due" if int(offering.get("feeCents") or 0) else "not-required"
                enrollments.append(row)
                if row["paymentState"] == "due":
                    _ensure_fee_payment(state, offering, row, self._now())
            else:
                waiting = [item for item in enrollments if item["offeringId"] == offering_id and item["state"] == "waitlist"]
                row["state"] = "waitlist"
                row["waitlistPosition"] = len(waiting) + 1
                row["paymentState"] = "not-required"
                enrollments.append(row)
            return copy.deepcopy(row)

        return self.tx(op)

    def drop_enrollment(self, actor_id, enrollment_id):
        def op(state):
            account = _live(state, actor_id)
            enrollment = _by_id(_rows(state, "enrollments"), enrollment_id)
            if not enrollment:
                raise ServiceError("That sign-up isn't here.", 404)
            member = _member(state, enrollment["listingId"], account["id"])
            organizer = member and member.get("role") == "organizer"
            if enrollment["accountId"] != account["id"] and not organizer:
                raise ServiceError("You can only drop your own sign-up.", 403)
            if enrollment["state"] == "dropped":
                return {"ok": True}
            enrollment["state"] = "dropped"
            enrollment["waitlistPosition"] = None
            offering = _by_id(_rows(state, "offerings"), enrollment["offeringId"])
            promoted = _promote_waitlist(state, offering, self._now()) if offering else None
            return {"ok": True, "promoted": promoted}

        return self.tx(op)

    def create_due(self, actor_id, listing_id, member_id, label, amount_cents):
        amount = int(amount_cents or 0)
        if amount < 0:
            raise ServiceError("Dues can't be negative.")
        label = (label or "").strip() or "Dues (test)"

        def op(state):
            account = _live(state, actor_id)
            _require_organizer(state, account, listing_id)
            if not _member(state, listing_id, member_id):
                raise ServiceError("That person isn't on the roster.")
            payment = _new_payment(state, listing_id, member_id, "dues", label, amount, self._now())
            return copy.deepcopy(payment)

        return self.tx(op)

    def mark_paid(self, actor_id, payment_id):
        """Record a test payment. Nothing is collected or paid out."""

        def op(state):
            account = _live(state, actor_id)
            payment = _by_id(_rows(state, "payments"), payment_id)
            if not payment:
                raise ServiceError("That payment isn't here.", 404)
            member = _member(state, payment["listingId"], account["id"])
            if payment["accountId"] != account["id"] and not (member and member.get("role") == "organizer"):
                raise ServiceError("You can't mark that payment.", 403)
            if payment.get("paymentState") != "paid-test":
                split = fee_split(int(payment["amountCents"]), state["settings"].get("portalDuesCutPercent"))
                payment["paymentState"] = "paid-test"
                payment["method"] = "mark-as-paid"
                payment["platformShareCents"] = split["platformShareCents"]
                payment["summary"] = split["summary"]
                payment["collected"] = False
            return copy.deepcopy(payment)

        return self.tx(op)

    def announce(self, actor_id, listing_id, title, body, audience):
        title = (title or "").strip()
        body = body or ""
        if not title or not body.strip():
            raise ServiceError("An announcement needs a title and a body.")

        def op(state):
            account = _live(state, actor_id)
            _require_organizer(state, account, listing_id)
            listing = self._listing(listing_id)
            reasons = filter_fields([title, body], state["settings"], listing["name"])
            announcement = {
                "id": new_id("ann_"),
                "listingId": listing_id,
                "title": title[:140],
                "body": body[:4000],
                "audience": audience or "all",
                "status": "held" if reasons else "outbox",
                "holdReasons": reasons,
                "createdAt": iso(self._now()),
                "authorId": account["id"],
            }
            _rows(state, "announcements").append(announcement)
            if not reasons:
                _deliver(state, announcement)
            return {
                "id": announcement["id"],
                "status": announcement["status"],
                "emailed": False,
                "holdReasons": reasons,
                "message": "Held for a person to check." if reasons else "Saved in the test outbox. No email was sent.",
            }

        return self.tx(op)

    def add_rotation(self, actor_id, listing_id, on_date, role, member_id):
        role = (role or "").strip()
        if not on_date or not role:
            raise ServiceError("A rotation row needs a date and a role.")
        if str(member_id).startswith("child_"):
            raise ServiceError("Assign a parent, not a child.")

        def op(state):
            account = _live(state, actor_id)
            _require_organizer(state, account, listing_id)
            if _by_id(_rows(state, "children"), member_id):
                raise ServiceError("Assign a parent, not a child.")
            if not _member(state, listing_id, member_id):
                raise ServiceError("That person isn't on the roster.")
            row = {
                "id": new_id("rot_"),
                "listingId": listing_id,
                "date": on_date,
                "role": role[:40],
                "accountId": member_id,
            }
            _rows(state, "rotation").append(row)
            return row

        return self.tx(op)

    def public_looking(self, state_code, county):
        def op(state):
            settings = state["settings"]
            if not settings["modules"].get("lookingFor"):
                return []
            now = self._now()
            out = []
            for row in _rows(state, "looking_posts"):
                if row.get("status") != "published":
                    continue
                if row.get("expiresAt") and parse_iso(row["expiresAt"]) < now:
                    continue
                if state_code and row.get("state") != state_code:
                    continue
                if county and row.get("county") != county:
                    continue
                out.append(_looking_out(state, row, None, settings))
            out.sort(key=lambda item: item["createdAt"], reverse=True)
            return out

        return self.tx(op)

    def save_looking(self, actor_id, fields):
        def op(state):
            account = _live(state, actor_id)
            settings = state["settings"]
            _need(settings, "lookingFor")
            _require_verified(account)
            title = str(fields.get("title") or "").strip()
            body = str(fields.get("body") or "").strip()
            if not title or not body:
                raise ServiceError("A post needs a title and a description.")
            if fields.get("street") or fields.get("address"):
                raise ServiceError("Don't include a street address.")
            category = fields.get("category") or ""
            if category and category not in self.catalog.get("categories", []):
                raise ServiceError("That category isn't on the map.")
            state_code = str(fields.get("state") or "").strip().upper()
            county = str(fields.get("county") or "").strip()
            if not state_code or not county:
                raise ServiceError("Choose a state and a county.")
            reasons = with_new_account(
                filter_fields([title, body], settings, ""),
                account,
                settings,
            )
            now = self._now()
            row = {
                "id": new_id("need_"),
                "authorId": account["id"],
                "title": title[:140],
                "body": body[:4000],
                "category": category,
                "state": state_code,
                "county": county,
                "city": str(fields.get("city") or "")[:80],
                "status": "held" if reasons else "published",
                "holdReasons": reasons,
                "flagCount": 0,
                "createdAt": iso(now),
                "expiresAt": iso(now + timedelta(days=int(settings.get("lookingForExpireDays") or 90))),
                "counted": False,
            }
            _rows(state, "looking_posts").append(row)
            return _looking_out(state, row, account["id"], settings)

        return self.tx(op)

    def reply_looking(self, actor_id, post_id, body):
        text = (body or "").strip()
        if not text:
            raise ServiceError("Write a reply first.")

        def op(state):
            account = _live(state, actor_id)
            _need(state["settings"], "lookingFor")
            _require_verified(account)
            post = _by_id(_rows(state, "looking_posts"), post_id)
            if not post or post.get("status") != "published":
                raise ServiceError("That post isn't public.", 404)
            org = "organization" in account.get("roles", [])
            family = "family" in account.get("roles", [])
            if not org and not family:
                raise ServiceError("Sign in to reply.", 403)
            reasons = filter_text(text, state["settings"], "")
            reply = {
                "id": new_id("lrep_"),
                "postId": post_id,
                "authorId": account["id"],
                "body": text[:4000],
                "status": "held" if reasons else "published",
                "holdReasons": reasons,
                "createdAt": iso(self._now()),
            }
            _rows(state, "looking_replies").append(reply)
            return {"id": reply["id"], "status": reply["status"], "holdReasons": reasons if reply["authorId"] == account["id"] else []}

        return self.tx(op)

    def renew_looking(self, actor_id, post_id):
        def op(state):
            account = _live(state, actor_id)
            settings = state["settings"]
            post = _by_id(_rows(state, "looking_posts"), post_id)
            if not post or post["authorId"] != account["id"]:
                raise ServiceError("That post isn't yours.", 404)
            reasons = with_new_account(filter_fields([post["title"], post["body"]], settings, ""), account, settings)
            now = self._now()
            post["expiresAt"] = iso(now + timedelta(days=int(settings.get("lookingForExpireDays") or 90)))
            post["holdReasons"] = reasons
            post["status"] = "held" if reasons else "published"
            return _looking_out(state, post, account["id"], settings)

        return self.tx(op)

    def public_events(self, state_code, county):
        def op(state):
            if not state["settings"]["modules"].get("events"):
                return []
            now = self._now()
            out = []
            for row in _rows(state, "events"):
                if row.get("status") != "published":
                    continue
                if row.get("endsAt") and parse_iso(row["endsAt"]) < now:
                    continue
                if state_code and row.get("state") != state_code:
                    continue
                if county and row.get("county") != county:
                    continue
                out.append(_event_out(row, self.catalog))
            out.sort(key=lambda item: item["startsAt"])
            return out

        return self.tx(op)

    def save_event(self, actor_id, fields):
        def op(state):
            account = _live(state, actor_id)
            settings = state["settings"]
            _need(settings, "events")
            _require_verified(account)
            if fields.get("address") or fields.get("street"):
                raise ServiceError("Don't include a street address. Name a public venue.")
            title = str(fields.get("title") or "").strip()
            summary = str(fields.get("summary") or "").strip()
            venue = str(fields.get("venue") or "").strip()
            if not title or not summary or not venue:
                raise ServiceError("An event needs a title, a summary, and a public venue.")
            try:
                start = parse_iso(fields.get("startsAt"))
                end = parse_iso(fields.get("endsAt"))
            except (TypeError, ValueError):
                raise ServiceError("Use a start and end time.")
            if end < start:
                raise ServiceError("The end time is before the start.")
            listing_id = fields.get("listingId") or ""
            if listing_id and listing_id not in self.catalog["listings"]:
                raise ServiceError("That listing isn't on the map.", 404)
            reasons = with_new_account(filter_fields([title, summary, venue], settings, ""), account, settings)
            row = {
                "id": new_id("evt_"),
                "authorId": account["id"],
                "listingId": listing_id,
                "title": title[:140],
                "summary": summary[:2000],
                "startsAt": iso(start),
                "endsAt": iso(end),
                "state": str(fields.get("state") or "").strip().upper(),
                "county": str(fields.get("county") or "").strip(),
                "city": str(fields.get("city") or "")[:80],
                "venue": venue[:140],
                "status": "held" if reasons else "published",
                "holdReasons": reasons,
                "flagCount": 0,
                "createdAt": iso(self._now()),
                "counted": False,
            }
            if not row["state"] or not row["county"]:
                raise ServiceError("Choose a state and a county.")
            _rows(state, "events").append(row)
            public = _event_out(row, self.catalog)
            public["status"] = row["status"]
            public["holdReasons"] = reasons
            public["waitingMessage"] = HELD_MESSAGE if reasons else ""
            return public

        return self.tx(op)

    def save_favorite(self, actor_id, listing_id, alert_on_open_spots=False):
        self._listing(listing_id)

        def op(state):
            account = _live(state, actor_id)
            _need(state["settings"], "favorites")
            _require_verified(account)
            favorite_id = f"{account['id']}:{listing_id}"
            row = _by_id(_rows(state, "favorites"), favorite_id)
            if row is None:
                row = {
                    "id": favorite_id,
                    "accountId": account["id"],
                    "listingId": listing_id,
                    "savedAt": iso(self._now()),
                    "seenOpenSpots": None,
                }
                _rows(state, "favorites").append(row)
            row["alertOnOpenSpots"] = bool(alert_on_open_spots)
            return {"ok": True, "listingId": listing_id, "saved": True}

        return self.tx(op)

    def remove_favorite(self, actor_id, listing_id):
        def op(state):
            account = _live(state, actor_id)
            favorite_id = f"{account['id']}:{listing_id}"
            rows = _rows(state, "favorites")
            row = _by_id(rows, favorite_id)
            if row:
                rows.remove(row)
            return {"ok": True, "saved": False}

        return self.tx(op)

    def list_favorites(self, actor_id):
        def op(state):
            account = _live(state, actor_id)
            settings = state["settings"]
            if not settings["modules"].get("favorites"):
                return {"saved": [], "changes": []}
            saved = []
            changes = []
            claims_on = bool(settings["modules"].get("claims"))
            for row in _rows(state, "favorites"):
                if row["accountId"] != account["id"]:
                    continue
                listing = self.catalog["listings"].get(row["listingId"], {})
                overlay = _by_id(_rows(state, "overrides"), row["listingId"])
                current = (overlay or {}).get("openSpots") if claims_on else None
                if row.get("seenOpenSpots") is None:
                    row["seenOpenSpots"] = current
                elif row.get("alertOnOpenSpots") and claims_on and current != row.get("seenOpenSpots"):
                    changes.append({
                        "listingId": row["listingId"],
                        "name": listing.get("name") or row["listingId"],
                        "kind": "open-spots",
                        "before": row.get("seenOpenSpots") or "",
                        "after": current or "",
                    })
                    row["seenOpenSpots"] = current
                saved.append({
                    "listingId": row["listingId"],
                    "name": listing.get("name") or row["listingId"],
                    "savedAt": row.get("savedAt"),
                    "alertOnOpenSpots": bool(row.get("alertOnOpenSpots")),
                })
            watch_changes = _watch_changes(state, account["id"], self.catalog)
            return {"saved": saved, "changes": changes + watch_changes, "emailed": False}

        return self.tx(op)

    def set_watch(self, actor_id, state_code, county, enabled):
        state_code = (state_code or "").strip().upper()
        county = (county or "").strip()
        if not state_code or not county:
            raise ServiceError("Choose a state and a county.")

        def op(state):
            account = _live(state, actor_id)
            _need(state["settings"], "favorites")
            watch_id = f"{account['id']}:{state_code}:{county}"
            rows = _rows(state, "watches")
            row = _by_id(rows, watch_id)
            if not enabled:
                if row:
                    rows.remove(row)
                return {"ok": True, "watching": False}
            if row is None:
                row = {"id": watch_id, "accountId": account["id"], "state": state_code, "county": county, "seenIds": None}
                rows.append(row)
            return {"ok": True, "watching": True}

        return self.tx(op)

    def _listing(self, listing_id):
        listing = self.catalog["listings"].get(listing_id)
        if not listing:
            raise ServiceError("That listing isn't on the map.", 404)
        return listing


def _new_account(email, password, display_name, now):
    return {
        "id": new_id("acc_"),
        "email": email,
        "passwordHash": hash_password(password),
        "displayName": display_name,
        "emailVerified": False,
        "roles": ["family"],
        "approvedReviewCount": 0,
        "removed": False,
        "createdAt": iso(now),
    }


def _account_by_email(rows, email):
    return next((row for row in rows if row.get("email") == email), None)


def _account_out(account, settings, email=False):
    trusted = account.get("approvedReviewCount", 0) >= int(settings.get("trustedBadgeAfter") or 3)
    payload = {
        "id": account["id"],
        "displayName": account.get("displayName") or "",
        "emailVerified": bool(account.get("emailVerified")),
        "roles": list(account.get("roles") or []),
        "approvedReviewCount": account.get("approvedReviewCount", 0),
        "trusted": trusted,
        "createdAt": account.get("createdAt"),
    }
    if email:
        payload["email"] = account.get("email")
    return payload


def _live(state, account_id):
    account = _by_id(_rows(state, "accounts"), account_id)
    if not account or account.get("removed"):
        raise ServiceError("Sign in first.", 401)
    return account


def _require_verified(account):
    if not account.get("emailVerified"):
        raise ServiceError("Confirm your email first. On this test, an admin marks it verified.", 403)


def _require_admin(account):
    if "admin" not in (account.get("roles") or []):
        raise ServiceError("You need an admin account.", 403)


def _require_staff(account):
    roles = account.get("roles") or []
    if "admin" not in roles and "moderator" not in roles:
        raise ServiceError("You need an admin account.", 403)


def _need(settings, module):
    if not settings["modules"].get(module):
        raise ServiceError("That part of the site is turned off.", 404)


def _bump_rate(state, bucket, limit, window_seconds, now):
    rows = _rows(state, "rate_limits")
    row = _by_id(rows, bucket)
    if row is None or (now - parse_iso(row["windowStart"])).total_seconds() >= window_seconds:
        if row is None:
            row = {"id": bucket, "count": 0, "windowStart": iso(now)}
            rows.append(row)
        else:
            row["count"] = 0
            row["windowStart"] = iso(now)
    if row["count"] >= limit:
        raise ServiceError("Too many attempts. Wait a bit and try again.", 429)
    row["count"] += 1


def _coerce_ratings(ratings):
    if ratings is None:
        return {}
    if not isinstance(ratings, dict):
        return ratings
    out = {}
    for key, value in ratings.items():
        if isinstance(value, str) and value.strip().isdigit():
            value = int(value.strip())
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        out[key] = value
    return out


def _apply_review(state, account, listing, ratings, body, existing, now):
    settings = state["settings"]
    error = ratings_error(ratings, settings)
    if error:
        raise ServiceError(error)
    if len(body or "") > 4000:
        raise ServiceError("That review is too long.")
    if existing and existing.get("status") == "hidden":
        raise ServiceError("This review is hidden while a moderator looks at it.")
    reasons = with_new_account(filter_text(body or "", settings, listing.get("name") or ""), account, settings)
    stamp = iso(now)
    if existing is None:
        existing = {
            "id": new_id("rev_"),
            "listingId": listing["id"],
            "authorId": account["id"],
            "createdAt": stamp,
            "counted": False,
            "flagCount": 0,
            "internalNote": "",
        }
        _rows(state, "reviews").append(existing)
    elif existing.get("status") == "removed":
        existing["flagCount"] = 0
    if existing.get("status") == "published" and reasons:
        existing["pending"] = {"ratings": ratings, "body": body or "", "holdReasons": reasons}
        existing["updatedAt"] = stamp
        return existing
    existing["ratings"] = ratings
    existing["body"] = body or ""
    existing["pending"] = None
    existing["holdReasons"] = reasons
    existing["updatedAt"] = stamp
    if reasons:
        existing["status"] = "held"
        existing["publishedAt"] = None
        return existing
    existing["status"] = "published"
    existing["holdReasons"] = []
    if not existing.get("publishedAt"):
        existing["publishedAt"] = stamp
    if not existing.get("counted"):
        account["approvedReviewCount"] = account.get("approvedReviewCount", 0) + 1
        existing["counted"] = True
    return existing


def _review_out(state, review, viewer_id, settings):
    author = _by_id(_rows(state, "accounts"), review["authorId"])
    reply = next((row for row in _rows(state, "replies") if row["reviewId"] == review["id"]), None)
    mine = viewer_id == review["authorId"]
    show_badge = bool(settings["modules"].get("badges")) and author and author.get("approvedReviewCount", 0) >= int(settings.get("trustedBadgeAfter") or 3)
    payload = {
        "id": review["id"],
        "listingId": review["listingId"],
        "authorName": (author or {}).get("displayName") or "Removed account",
        "trusted": bool(show_badge),
        "status": review["status"] if mine else "published",
        "ratings": dict(review.get("ratings") or {}),
        "body": review.get("body") or "",
        "createdAt": review.get("createdAt"),
        "publishedAt": review.get("publishedAt"),
        "mine": mine,
    }
    if mine and review["status"] == "held":
        payload["waitingMessage"] = HELD_MESSAGE
    if mine and review["status"] == "hidden":
        payload["waitingMessage"] = "This review is hidden while a moderator looks at flags."
    if mine and review["status"] == "removed":
        payload["waitingMessage"] = "This review was removed."
        payload["body"] = ""
        payload["ratings"] = {}
    if mine and review.get("pending"):
        payload["pendingMessage"] = "Your latest edit is waiting. The previous text stays up until a moderator approves it."
    if reply:
        reply_author = _by_id(_rows(state, "accounts"), reply["authorId"])
        visible = reply.get("status") == "published"
        if visible:
            payload["reply"] = {
                "id": reply["id"],
                "body": reply.get("body") or "",
                "createdAt": reply.get("createdAt"),
                "authorName": (reply_author or {}).get("displayName") or "The organization",
                "status": "published",
            }
            if reply.get("pending") and viewer_id == reply["authorId"]:
                payload["reply"]["pendingMessage"] = "Your latest reply is waiting. The previous text stays up."
        elif viewer_id == reply["authorId"]:
            payload["reply"] = {
                "id": reply["id"],
                "body": reply.get("body") or "",
                "createdAt": reply.get("createdAt"),
                "authorName": (reply_author or {}).get("displayName") or "The organization",
                "status": "held",
                "waitingMessage": HELD_MESSAGE,
            }
    return payload


def _clear_flags(state, target_type, target_id):
    rows = _rows(state, "flags")
    state["collections"]["flags"] = [
        row for row in rows if not (row.get("targetType") == target_type and row.get("targetId") == target_id)
    ]


def _flag_target(state, target_type, target_id):
    collection = {"review": "reviews", "looking": "looking_posts", "event": "events"}[target_type]
    target = _by_id(_rows(state, collection), target_id)
    if not target:
        raise ServiceError("That post isn't here.", 404)
    return target, collection


def _verified_claim(state, account_id, listing_id):
    return next(
        (
            row for row in _rows(state, "claims")
            if row["accountId"] == account_id and row["listingId"] == listing_id and row["status"] == "Verified"
        ),
        None,
    )


def _listing_verified(state, listing_id):
    return next((row for row in _rows(state, "claims") if row["listingId"] == listing_id and row["status"] == "Verified"), None)


def _mark_claim_verified(state, claim, now):
    other = _listing_verified(state, claim["listingId"])
    if other and other["id"] != claim["id"]:
        raise ServiceError("Another account is already verified for this listing.")
    claim["status"] = "Verified"
    claim["verifiedAt"] = iso(now)
    claim["codePlain"] = ""
    claim["codeHash"] = ""
    _sync_org_role(state, claim["accountId"])


def _sync_org_role(state, account_id):
    account = _by_id(_rows(state, "accounts"), account_id)
    if not account:
        return
    has = any(row["accountId"] == account_id and row["status"] == "Verified" for row in _rows(state, "claims"))
    roles = set(account.get("roles") or [])
    if has:
        roles.add("organization")
    else:
        roles.discard("organization")
    if not roles:
        roles.add("family")
    account["roles"] = sorted(roles)


def _overlay_row(state, listing_id):
    row = _by_id(_rows(state, "overrides"), listing_id)
    if row is None:
        row = {"id": listing_id, "listingId": listing_id, "pending": None}
        _rows(state, "overrides").append(row)
    return row


def _public_overlay(state, listing_id, settings):
    if not settings["modules"].get("claims"):
        return None
    row = _by_id(_rows(state, "overrides"), listing_id)
    if not row or not row.get("lastUpdated"):
        return None
    return {
        "listingId": listing_id,
        "openSpots": row.get("openSpots") or "",
        "meetingDays": row.get("meetingDays") or "",
        "costNotes": row.get("costNotes") or "",
        "description": row.get("description") or "",
        "website": row.get("website") or "",
        "email": row.get("email") or "",
        "phone": row.get("phone") or "",
        "lastUpdated": row.get("lastUpdated"),
        "updatedLabel": _updated_label(row.get("lastUpdated")),
    }


def _updated_label(iso_date):
    if not iso_date:
        return ""
    moment = parse_iso(iso_date + "T00:00:00Z") if "T" not in iso_date else parse_iso(iso_date)
    return f"Updated {moment.strftime('%b')} {moment.day}, {moment.year}"


def _claim_label(state, listing_id, settings):
    if not settings["modules"].get("claims"):
        return None
    if _listing_verified(state, listing_id):
        return "Claimed by the organization."
    return None


def _viewer_out(state, listing_id, viewer_id, settings):
    account = _by_id(_rows(state, "accounts"), viewer_id)
    if not account:
        return None
    verified_claim = _verified_claim(state, viewer_id, listing_id)
    portal = _by_id(_rows(state, "portals"), listing_id)
    member = _member(state, listing_id, viewer_id)
    portal_on = bool(portal and portal.get("active") and settings["modules"].get("groupPortal"))
    show_portal = portal_on and (verified_claim or member)
    favorite = _by_id(_rows(state, "favorites"), f"{viewer_id}:{listing_id}")
    return {
        "canReview": bool(account.get("emailVerified") and not verified_claim and settings["modules"].get("reviews")),
        "canReply": bool(verified_claim and settings["modules"].get("reviews")),
        "canEditListing": bool(verified_claim and settings["modules"].get("claims")),
        "canOpenPortal": bool(show_portal),
        "saved": bool(favorite) if settings["modules"].get("favorites") else False,
    }


def _history(state, target_type, item, now, body, ratings=None):
    _rows(state, "history").append({
        "id": new_id("hist_"),
        "targetType": target_type,
        "targetId": item["id"],
        "body": body,
        "ratings": ratings,
        "at": now,
    })


def _publish_review(state, review, now):
    if review.get("pending"):
        review["ratings"] = review["pending"].get("ratings") or review.get("ratings") or {}
        review["body"] = review["pending"].get("body") or ""
        review["pending"] = None
    review["holdReasons"] = []
    review["status"] = "published"
    review["updatedAt"] = now
    if not review.get("publishedAt"):
        review["publishedAt"] = now
    if not review.get("counted"):
        author = _by_id(_rows(state, "accounts"), review["authorId"])
        if author:
            author["approvedReviewCount"] = author.get("approvedReviewCount", 0) + 1
        review["counted"] = True
    _clear_flags(state, "review", review["id"])
    review["flagCount"] = 0


def _count_post(account, row):
    if row.get("counted"):
        return
    account["approvedReviewCount"] = account.get("approvedReviewCount", 0) + 1
    row["counted"] = True


def _queue_items(state, catalog, now):
    items = []
    accounts = {row["id"]: row for row in _rows(state, "accounts")}

    def author_bits(author_id):
        author = accounts.get(author_id) or {}
        created = author.get("createdAt")
        age = ""
        if created:
            age = max(0, (now - parse_iso(created)).days)
        return author.get("displayName") or "Unknown", age, author.get("approvedReviewCount", 0)

    def add(kind, item_id, listing_id, author_id, text, scores, reasons, flag_count, created):
        name, age, count = author_bits(author_id)
        listing = catalog["listings"].get(listing_id or "", {})
        items.append({
            "type": kind,
            "id": item_id,
            "listingId": listing_id or "",
            "listingName": listing.get("name") or listing_id or "",
            "authorName": name,
            "accountAgeDays": age,
            "approvedReviewCount": count,
            "text": text or "",
            "scores": scores or {},
            "reasons": reasons or [],
            "flagCount": flag_count or 0,
            "createdAt": created or "",
        })

    for review in _rows(state, "reviews"):
        if review.get("status") in ("held", "hidden"):
            add("review", review["id"], review["listingId"], review["authorId"], review.get("body"), review.get("ratings"), review.get("holdReasons"), review.get("flagCount"), review.get("createdAt"))
        if review.get("pending"):
            pending = review["pending"]
            add("review-edit", review["id"], review["listingId"], review["authorId"], pending.get("body"), pending.get("ratings"), pending.get("holdReasons"), review.get("flagCount"), review.get("updatedAt"))
    for reply in _rows(state, "replies"):
        if reply.get("status") == "held":
            add("reply", reply["id"], reply["listingId"], reply["authorId"], reply.get("body"), {}, reply.get("holdReasons"), 0, reply.get("createdAt"))
        if reply.get("pending"):
            add("reply-edit", reply["id"], reply["listingId"], reply["authorId"], reply["pending"].get("body"), {}, reply["pending"].get("holdReasons"), 0, reply.get("updatedAt"))
    for claim in _rows(state, "claims"):
        if claim.get("status") == "Claimed":
            text = f"Method: {claim.get('method')}. "
            if claim.get("codePlain"):
                text += f"Code for {claim.get('targetEmail')}: {claim.get('codePlain')}. Mail was not sent."
            else:
                text += "Waiting for an admin to mark it verified."
            add("claim", claim["id"], claim["listingId"], claim["accountId"], text, {}, ["claim"], 0, claim.get("createdAt"))
    for overlay in _rows(state, "overrides"):
        pending = overlay.get("pending") or {}
        if pending:
            bits = []
            reasons = []
            for key, value in pending.items():
                bits.append(f"{key}: {value.get('value')}")
                reasons.extend(value.get("reasons") or [])
            add("overlay", overlay["id"], overlay["listingId"], overlay.get("updatedBy"), "\n".join(bits), {}, reasons, 0, overlay.get("lastUpdated"))
    for post in _rows(state, "looking_posts"):
        if post.get("status") in ("held", "hidden"):
            add("looking", post["id"], "", post["authorId"], f"{post.get('title')}\n{post.get('body')}", {}, post.get("holdReasons"), post.get("flagCount"), post.get("createdAt"))
    for reply in _rows(state, "looking_replies"):
        if reply.get("status") == "held":
            post = _by_id(_rows(state, "looking_posts"), reply["postId"])
            add("looking-reply", reply["id"], "", reply["authorId"], reply.get("body"), {}, reply.get("holdReasons"), 0, reply.get("createdAt"))
    for event in _rows(state, "events"):
        if event.get("status") in ("held", "hidden"):
            add("event", event["id"], event.get("listingId") or "", event["authorId"], f"{event.get('title')}\n{event.get('summary')}", {}, event.get("holdReasons"), event.get("flagCount"), event.get("createdAt"))
    for announcement in _rows(state, "announcements"):
        if announcement.get("status") == "held":
            add("announcement", announcement["id"], announcement["listingId"], announcement.get("authorId"), f"{announcement.get('title')}\n{announcement.get('body')}", {}, announcement.get("holdReasons"), 0, announcement.get("createdAt"))
    items.sort(key=lambda item: item.get("createdAt") or "")
    return items


def _moderate_item(state, kind, item_id, action, body, ratings, note, now, catalog):
    if kind in ("review", "review-edit"):
        review = _by_id(_rows(state, "reviews"), item_id)
        if not review:
            raise ServiceError("That review isn't in the queue.", 404)
        if action == "remove":
            review["status"] = "removed"
            review["pending"] = None
            review["internalNote"] = note
            return
        if action == "edit":
            if not (body or "").strip():
                raise ServiceError("The edited review needs text, or use remove.")
            _history(state, "review", review, now, review.get("body") or "", review.get("ratings"))
            if review.get("pending"):
                _history(state, "review-pending", review, now, review["pending"].get("body") or "", review["pending"].get("ratings"))
            review["body"] = body.strip()
            if ratings:
                error = ratings_error(ratings, state["settings"])
                if error:
                    raise ServiceError(error)
                review["ratings"] = ratings
            review["pending"] = None
        elif review.get("pending") and kind == "review-edit":
            _history(state, "review", review, now, review.get("body") or "", review.get("ratings"))
        _publish_review(state, review, now)
        return
    if kind in ("reply", "reply-edit"):
        reply = _by_id(_rows(state, "replies"), item_id)
        if not reply:
            raise ServiceError("That reply isn't in the queue.", 404)
        if action == "remove":
            reply["status"] = "removed"
            reply["pending"] = None
            reply["internalNote"] = note
            return
        if action == "edit":
            _history(state, "reply", reply, now, reply.get("body") or "")
            reply["body"] = (body or "").strip()
            reply["pending"] = None
        elif reply.get("pending"):
            _history(state, "reply", reply, now, reply.get("body") or "")
            reply["body"] = reply["pending"].get("body") or reply.get("body") or ""
            reply["pending"] = None
        reply["status"] = "published"
        reply["holdReasons"] = []
        reply["updatedAt"] = now
        return
    if kind == "claim":
        claim = _by_id(_rows(state, "claims"), item_id)
        if not claim:
            raise ServiceError("That claim isn't in the queue.", 404)
        if action == "remove":
            claim["status"] = "Rejected"
            claim["codePlain"] = ""
            return
        if action == "edit":
            raise ServiceError("Approve the claim, or remove it. Claim text isn't edited here.")
        _mark_claim_verified(state, claim, parse_iso(now))
        return
    if kind == "overlay":
        overlay = _by_id(_rows(state, "overrides"), item_id)
        if not overlay:
            raise ServiceError("That edit isn't in the queue.", 404)
        if action == "remove":
            overlay["pending"] = None
            return
        pending = overlay.get("pending") or {}
        if action == "edit" and body:
            pending = {"description": {"value": body, "reasons": []}}
        for key, value in pending.items():
            _history(state, "overlay", overlay, now, overlay.get(key) or "")
            overlay[key] = value.get("value") if isinstance(value, dict) else value
        overlay["pending"] = None
        overlay["lastUpdated"] = now[:10]
        return
    if kind == "looking":
        _moderate_post(state, "looking_posts", item_id, action, body, note, now)
        return
    if kind == "looking-reply":
        reply = _by_id(_rows(state, "looking_replies"), item_id)
        if not reply:
            raise ServiceError("That reply isn't in the queue.", 404)
        if action == "remove":
            reply["status"] = "removed"
            return
        if action == "edit":
            reply["body"] = (body or "").strip()
        reply["status"] = "published"
        reply["holdReasons"] = []
        return
    if kind == "event":
        _moderate_post(state, "events", item_id, action, body, note, now)
        return
    if kind == "announcement":
        announcement = _by_id(_rows(state, "announcements"), item_id)
        if not announcement:
            raise ServiceError("That announcement isn't in the queue.", 404)
        if action == "remove":
            announcement["status"] = "removed"
            return
        if action == "edit":
            announcement["body"] = (body or "").strip()
        announcement["status"] = "outbox"
        announcement["holdReasons"] = []
        _deliver(state, announcement)
        return
    raise ServiceError("That queue type isn't known.")


def _moderate_post(state, collection, item_id, action, body, note, now):
    row = _by_id(_rows(state, collection), item_id)
    if not row:
        raise ServiceError("That post isn't in the queue.", 404)
    if action == "remove":
        row["status"] = "removed"
        row["internalNote"] = note
        return
    if action == "edit":
        if collection == "events":
            row["summary"] = (body or "").strip()
        else:
            row["body"] = (body or "").strip()
    row["status"] = "published"
    row["holdReasons"] = []
    _clear_flags(state, "looking" if collection == "looking_posts" else "event", row["id"])
    row["flagCount"] = 0


def _apply_settings_patch(state, settings, patch):
    if "ratingCategories" in patch:
        settings["ratingCategories"] = _clean_categories(state, patch["ratingCategories"])
    if "modules" in patch and isinstance(patch["modules"], dict):
        for key, value in patch["modules"].items():
            if key in settings["modules"]:
                settings["modules"][key] = bool(value)
    bools = ("nameCheck", "addressCheck", "harshLanguageCheck", "inviteRequired")
    for key in bools:
        if key in patch:
            settings[key] = bool(patch[key])
    if "harshWords" in patch:
        words = patch["harshWords"]
        if isinstance(words, str):
            words = [part.strip() for part in re.split(r"[\n,]", words) if part.strip()]
        if not isinstance(words, list) or any(not isinstance(word, str) for word in words):
            raise ServiceError("The harsh-word list is one word or phrase per line.")
        settings["harshWords"] = [word.strip()[:40] for word in words if word.strip()][:50]
    if "inviteCode" in patch:
        code = str(patch["inviteCode"] or "").strip()
        if not code:
            raise ServiceError("The invite code can't be empty while invites are required.")
        settings["inviteCode"] = code[:80]
    ranges = {
        "newAccountHoldCount": (0, 20),
        "flagsToHide": (1, 50),
        "trustedBadgeAfter": (1, 100),
        "lookingForExpireDays": (1, 3650),
    }
    for key, (low, high) in ranges.items():
        if key in patch:
            settings[key] = _bounded_int(patch[key], key, low, high)
    if "portalMonthlyFeeCents" in patch:
        settings["portalMonthlyFeeCents"] = _optional_int(patch["portalMonthlyFeeCents"], "portal monthly fee")
    if "portalDuesCutPercent" in patch:
        settings["portalDuesCutPercent"] = _optional_number(patch["portalDuesCutPercent"], "dues percent")
    if patch.get("paymentsMode") not in (None, "test-only"):
        raise ServiceError("Payments stay in test mode. Live charges are not part of this build.")


def _bounded_int(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ServiceError(f"{name} needs a whole number.")
    if value < low or value > high:
        raise ServiceError(f"{name} must be between {low} and {high}.")
    return value


def _optional_int(value, name):
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ServiceError(f"The {name} is empty, or a whole number of cents. Don't guess a price.")
    return value


def _optional_number(value, name):
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ServiceError(f"The {name} is empty, or a number. Don't guess a price.")
    if value < 0 or value > 100:
        raise ServiceError(f"The {name} is between 0 and 100, or empty.")
    return value


def _clean_categories(state, raw):
    if not isinstance(raw, list) or not raw:
        raise ServiceError("Keep at least one rating category.")
    cleaned = []
    seen = set()
    for row in raw:
        if not isinstance(row, dict):
            raise ServiceError("A category needs an id and a label.")
        cid = str(row.get("id") or "").strip().lower()
        label = str(row.get("label") or "").strip()
        if not re.fullmatch(r"[a-z0-9-]{2,40}", cid):
            raise ServiceError("Category ids use short lowercase words.")
        if cid in seen:
            raise ServiceError("That category id is already there.")
        if not label or len(label) > 80:
            raise ServiceError("Each category needs a label.")
        seen.add(cid)
        cleaned.append({"id": cid, "label": label, "active": bool(row.get("active", True))})
    used = set()
    for review in _rows(state, "reviews"):
        used.update((review.get("ratings") or {}).keys())
        if review.get("pending"):
            used.update((review["pending"].get("ratings") or {}).keys())
    old_ids = {row["id"] for row in state["settings"]["ratingCategories"]}
    missing = (old_ids & used) - seen
    if missing:
        raise ServiceError("Don't delete a category id that already has scores. Hide it instead.")
    if not any(row["active"] for row in cleaned):
        raise ServiceError("Keep at least one category available.")
    return cleaned


def _portal_row(state, listing_id):
    row = _by_id(_rows(state, "portals"), listing_id)
    if row is None:
        row = {"id": listing_id, "listingId": listing_id, "active": False, "publicBadge": False}
        _rows(state, "portals").append(row)
    row["publicBadge"] = False
    return row


def _portal_admin_out(portal):
    return {
        "listingId": portal["listingId"],
        "active": bool(portal.get("active")),
        "source": portal.get("source") or "",
        "grantedBy": portal.get("grantedBy") or "",
        "startedAt": portal.get("startedAt") or "",
        "publicBadge": False,
    }


def _portal_active(state, listing_id):
    portal = _by_id(_rows(state, "portals"), listing_id)
    if portal and portal.get("active"):
        return portal
    return None


def _member(state, listing_id, account_id):
    member_id = f"{listing_id}:{account_id}"
    return _by_id(_rows(state, "members"), member_id)


def _ensure_member(state, listing_id, account_id, role):
    row = _member(state, listing_id, account_id)
    if row is None:
        row = {"id": f"{listing_id}:{account_id}", "listingId": listing_id, "accountId": account_id, "role": role, "status": "active"}
        _rows(state, "members").append(row)
    else:
        row["status"] = "active"
        if role == "organizer":
            row["role"] = "organizer"
    return row


def _ensure_organizer(state, listing_id, account_id):
    return _ensure_member(state, listing_id, account_id, "organizer")


def _require_member(state, account, listing_id):
    _need(state["settings"], "groupPortal")
    portal = _portal_active(state, listing_id)
    if not portal:
        raise ServiceError("This group portal is off.", 404)
    member = _member(state, listing_id, account["id"])
    if not member or member.get("status") != "active":
        raise ServiceError("You aren't a member of this group.", 403)
    return portal, member


def _require_organizer(state, account, listing_id):
    portal, member = _require_member(state, account, listing_id)
    if member.get("role") != "organizer":
        raise ServiceError("Only an organizer can do that.", 403)
    return portal, member


def _promote_waitlist(state, offering, now):
    enrollments = _rows(state, "enrollments")
    promoted = None
    while True:
        enrolled = [row for row in enrollments if row["offeringId"] == offering["id"] and row["state"] == "enrolled"]
        waiting = [
            row for row in enrollments if row["offeringId"] == offering["id"] and row["state"] == "waitlist"
        ]
        waiting.sort(key=lambda row: (row.get("waitlistPosition") or 0, row.get("createdAt") or ""))
        if len(enrolled) >= int(offering["capacity"]) or not waiting:
            break
        nxt = waiting.pop(0)
        nxt["state"] = "enrolled"
        nxt["waitlistPosition"] = None
        nxt["paymentState"] = "due" if int(offering.get("feeCents") or 0) else "not-required"
        if nxt["paymentState"] == "due":
            _ensure_fee_payment(state, offering, nxt, now)
        promoted = {"enrollmentId": nxt["id"], "accountId": nxt["accountId"], "paymentState": nxt["paymentState"], "message": "You're in."}
    still = [row for row in enrollments if row["offeringId"] == offering["id"] and row["state"] == "waitlist"]
    still.sort(key=lambda row: (row.get("waitlistPosition") or 0, row.get("createdAt") or ""))
    for index, row in enumerate(still, start=1):
        row["waitlistPosition"] = index
    return promoted


def _new_payment(state, listing_id, account_id, kind, label, amount, now):
    payment = {
        "id": new_id("pay_"),
        "listingId": listing_id,
        "accountId": account_id,
        "kind": kind,
        "label": label,
        "amountCents": int(amount),
        "paymentState": "due" if int(amount) else "not-required",
        "method": "",
        "platformShareCents": None,
        "summary": "",
        "collected": False,
        "createdAt": iso(now),
    }
    _rows(state, "payments").append(payment)
    return payment


def _ensure_fee_payment(state, offering, enrollment, now):
    existing = next(
        (
            row for row in _rows(state, "payments")
            if row.get("enrollmentId") == enrollment["id"] and row.get("paymentState") in ("due", "paid-test")
        ),
        None,
    )
    if existing:
        return existing
    payment = _new_payment(
        state,
        offering["listingId"],
        enrollment["accountId"],
        "class-fee",
        offering["title"],
        offering.get("feeCents") or 0,
        now,
    )
    payment["enrollmentId"] = enrollment["id"]
    payment["offeringId"] = offering["id"]
    return payment


def _deliver(state, announcement):
    members = [row for row in _rows(state, "members") if row["listingId"] == announcement["listingId"] and row.get("status") == "active"]
    audience = announcement.get("audience") or "all"
    if audience.startswith("offering:"):
        offering_id = audience.split(":", 1)[1]
        allowed = {
            row["accountId"] for row in _rows(state, "enrollments")
            if row["offeringId"] == offering_id and row["state"] == "enrolled"
        }
        members = [row for row in members if row["accountId"] in allowed]
    for member in members:
        delivery_id = f"{announcement['id']}:{member['accountId']}"
        if _by_id(_rows(state, "deliveries"), delivery_id):
            continue
        _rows(state, "deliveries").append({
            "id": delivery_id,
            "announcementId": announcement["id"],
            "accountId": member["accountId"],
            "listingId": announcement["listingId"],
            "seenAt": None,
        })


def _portal_home(state, listing_id, account, member, portal, catalog):
    accounts = {row["id"]: row for row in _rows(state, "accounts")}
    organizer = member.get("role") == "organizer"
    roster = []
    for row in _rows(state, "members"):
        if row["listingId"] != listing_id or row.get("status") != "active":
            continue
        person = accounts.get(row["accountId"]) or {}
        item = {"accountId": row["accountId"], "role": row["role"], "displayName": person.get("displayName") or ""}
        if organizer:
            item["email"] = person.get("email") or ""
        roster.append(item)
    children = []
    for child in _rows(state, "children"):
        if child.get("listingId") != listing_id:
            continue
        if organizer or child["accountId"] == account["id"]:
            children.append({"id": child["id"], "accountId": child["accountId"], "firstName": child["firstName"], "grade": child["grade"]})
    offerings = [row for row in _rows(state, "offerings") if row["listingId"] == listing_id]
    enrollments = []
    for row in _rows(state, "enrollments"):
        if row["listingId"] != listing_id or row["state"] == "dropped":
            continue
        if organizer or row["accountId"] == account["id"]:
            shown = copy.deepcopy(row)
            if shown.get("childId") and not organizer and row["accountId"] != account["id"]:
                shown["childId"] = ""
            enrollments.append(shown)
    payments = [
        row for row in _rows(state, "payments")
        if row["listingId"] == listing_id and (organizer or row["accountId"] == account["id"])
    ]
    messages = []
    announcements = {row["id"]: row for row in _rows(state, "announcements") if row["listingId"] == listing_id}
    for delivery in _rows(state, "deliveries"):
        if delivery["accountId"] != account["id"]:
            continue
        announcement = announcements.get(delivery["announcementId"])
        if announcement and announcement.get("status") == "outbox":
            messages.append({"id": announcement["id"], "title": announcement["title"], "body": announcement["body"], "createdAt": announcement["createdAt"]})
    if organizer:
        for announcement in announcements.values():
            if announcement.get("status") == "held":
                messages.append({
                    "id": announcement["id"],
                    "title": announcement["title"],
                    "body": announcement["body"],
                    "status": "held",
                    "waitingMessage": HELD_MESSAGE,
                })
    rotation = []
    for row in _rows(state, "rotation"):
        if row["listingId"] != listing_id:
            continue
        person = accounts.get(row["accountId"]) or {}
        rotation.append({"id": row["id"], "date": row["date"], "role": row["role"], "accountId": row["accountId"], "displayName": person.get("displayName") or ""})
    rotation.sort(key=lambda row: row["date"])
    price = state["settings"].get("portalMonthlyFeeCents")
    return {
        "listingId": listing_id,
        "listingName": catalog["listings"].get(listing_id, {}).get("name") or listing_id,
        "line": "Portal on (test)",
        "role": member["role"],
        "source": portal.get("source") or "",
        "publicBadge": False,
        "pricingMessage": "Pricing isn't set yet. This test won't charge you." if price in (None, "") else "",
        "roster": roster,
        "children": children,
        "offerings": offerings,
        "enrollments": enrollments,
        "payments": payments,
        "messages": messages,
        "rotation": rotation,
        "invites": [row["email"] for row in _rows(state, "invites") if row["listingId"] == listing_id] if organizer else [],
    }


def _looking_out(state, row, viewer_id, settings):
    author = _by_id(_rows(state, "accounts"), row["authorId"])
    replies = []
    for reply in _rows(state, "looking_replies"):
        if reply.get("postId") != row["id"]:
            continue
        if reply.get("status") != "published" and reply.get("authorId") != viewer_id:
            continue
        person = _by_id(_rows(state, "accounts"), reply["authorId"])
        replies.append({
            "id": reply["id"],
            "authorName": (person or {}).get("displayName") or "",
            "body": reply.get("body") if reply.get("status") == "published" or reply.get("authorId") == viewer_id else "",
            "status": reply.get("status"),
            "createdAt": reply.get("createdAt"),
        })
    payload = {
        "id": row["id"],
        "title": row.get("title"),
        "body": row.get("body"),
        "category": row.get("category") or "",
        "state": row.get("state"),
        "county": row.get("county"),
        "city": row.get("city") or "",
        "status": row.get("status"),
        "createdAt": row.get("createdAt"),
        "expiresAt": row.get("expiresAt"),
        "authorName": (author or {}).get("displayName") or "",
        "replies": replies,
    }
    if viewer_id == row["authorId"] and row.get("status") == "held":
        payload["waitingMessage"] = HELD_MESSAGE
    if row.get("status") != "published" and viewer_id != row["authorId"]:
        payload["body"] = ""
    return payload


def _event_out(row, catalog):
    listing = catalog["listings"].get(row.get("listingId") or "")
    pinned = bool(listing and listing.get("latitude") is not None and listing.get("longitude") is not None)
    return {
        "id": row["id"],
        "title": row.get("title"),
        "summary": row.get("summary"),
        "startsAt": row.get("startsAt"),
        "endsAt": row.get("endsAt"),
        "state": row.get("state"),
        "county": row.get("county"),
        "city": row.get("city") or "",
        "venue": row.get("venue") or "",
        "listingId": row.get("listingId") or "",
        "pinned": pinned,
        "status": "published",
    }


def _watch_changes(state, account_id, catalog):
    changes = []
    for watch in _rows(state, "watches"):
        if watch["accountId"] != account_id:
            continue
        current = [
            listing_id for listing_id, listing in catalog["listings"].items()
            if listing.get("state") == watch["state"] and listing.get("county") == watch["county"]
        ]
        if watch.get("seenIds") is None:
            watch["seenIds"] = current
            continue
        seen = set(watch.get("seenIds") or [])
        for listing_id in current:
            if listing_id not in seen:
                listing = catalog["listings"][listing_id]
                changes.append({
                    "listingId": listing_id,
                    "name": listing.get("name") or listing_id,
                    "kind": "new-listing",
                    "county": watch["county"],
                    "state": watch["state"],
                })
        watch["seenIds"] = current
    return changes


def _stripe_test_configured():
    secret = os.environ.get("STRIPE_SECRET_KEY", "")
    publishable = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    if secret.startswith("sk_live") or publishable.startswith("pk_live"):
        return False
    return secret.startswith("sk_test_") and publishable.startswith("pk_test_")
