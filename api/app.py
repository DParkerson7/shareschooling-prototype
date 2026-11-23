"""HTTP API for the GitHub Pages site. The browser sends a bearer token."""

import os

from flask import Flask, jsonify, request

from api.service import ServiceError
from api.store import PostgresStore, load_catalog, load_site_modules
from api.service import CommunityService


def create_app(store=None, catalog=None, secret=None, clock=None):
    own_store = store is None
    if own_store:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL is not set. On Render this is the internal URL of shareschooling-db.")
        secret = secret or os.environ.get("TOKEN_SECRET")
        if not secret:
            raise RuntimeError("TOKEN_SECRET is not set.")
        store = PostgresStore(dsn).connect()
    secret = secret or os.environ.get("TOKEN_SECRET") or "test-secret"
    catalog = catalog or load_catalog()
    service = CommunityService(store, catalog, secret, clock=clock)
    service.ensure_ready(load_site_modules())
    if own_store:
        email = os.environ.get("ADMIN_EMAIL", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if email and password:
            created = service.ensure_admin(email, password, os.environ.get("ADMIN_DISPLAY_NAME", "David"))
            if created and created.get("created"):
                print("Created the first admin account.", flush=True)
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 200_000
    app.service = service
    _routes(app)
    return app


def _routes(app):
    service = app.service
    allowed = [
        item.strip()
        for item in os.environ.get(
            "CORS_ORIGINS",
            "https://dparkerson7.github.io,http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
        if item.strip()
    ]

    @app.errorhandler(ServiceError)
    def on_service_error(err):
        return jsonify(error=err.message), err.status

    @app.after_request
    def cors(resp):
        origin = request.headers.get("Origin", "")
        local = origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:")
        if origin in allowed or local:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        return resp

    @app.route("/api/<path:rest>", methods=["OPTIONS"])
    def options(rest):
        return ("", 204)

    def payload():
        data = request.get_json(silent=True)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ServiceError("Expected a JSON object.")
        return data

    def token():
        header = request.headers.get("Authorization", "")
        return header[7:].strip() if header.startswith("Bearer ") else ""

    def actor(required=True):
        account = service.account_from_token(token())
        if required and not account:
            raise ServiceError("Sign in first.", 401)
        return account

    def ip():
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown"

    @app.get("/api/health")
    def health():
        service.public_settings()
        return jsonify(ok=True)

    @app.get("/api/public/settings")
    def public_settings():
        return jsonify(service.public_settings())

    @app.get("/api/public/summaries")
    def summaries():
        ids = [part for part in request.args.get("ids", "").split(",") if part]
        return jsonify(summaries=service.summaries(ids))

    @app.get("/api/public/overlays")
    def overlays():
        ids = [part for part in request.args.get("ids", "").split(",") if part]
        return jsonify(overlays=service.public_overlays(ids))

    @app.get("/api/public/listings/<listing_id>")
    def listing_community(listing_id):
        user = actor(required=False)
        return jsonify(service.listing_community(
            listing_id,
            user["id"] if user else None,
            request.args.get("offset", 0),
            request.args.get("limit", 10),
        ))

    @app.get("/api/public/looking-for")
    def public_looking():
        return jsonify(posts=service.public_looking(request.args.get("state", ""), request.args.get("county", "")))

    @app.get("/api/public/events")
    def public_events():
        return jsonify(events=service.public_events(request.args.get("state", ""), request.args.get("county", "")))

    @app.post("/api/auth/signup")
    def signup():
        data = payload()
        return jsonify(service.signup(
            data.get("email"), data.get("password"), data.get("displayName"),
            data.get("inviteCode"), data.get("company"), ip(),
        ))

    @app.post("/api/auth/login")
    def login():
        data = payload()
        return jsonify(service.login(data.get("email"), data.get("password"), ip()))

    @app.get("/api/auth/me")
    def me():
        account = actor()
        settings = service.public_settings()
        return jsonify(account={
            "id": account["id"],
            "email": account["email"],
            "displayName": account["displayName"],
            "emailVerified": account["emailVerified"],
            "roles": account["roles"],
            "approvedReviewCount": account["approvedReviewCount"],
            "trusted": account["approvedReviewCount"] >= int(settings["trustedBadgeAfter"]),
        })

    @app.post("/api/reviews")
    def save_review():
        data = payload()
        user = actor()
        return jsonify(service.save_review(user["id"], data.get("listingId"), data.get("ratings") or {}, data.get("body") or "", ip()))

    @app.delete("/api/reviews/<review_id>")
    def delete_review(review_id):
        return jsonify(service.delete_review(actor()["id"], review_id))

    @app.post("/api/flags")
    def flag():
        data = payload()
        return jsonify(service.flag(actor()["id"], data.get("targetType"), data.get("targetId"), data.get("reason") or ""))

    @app.post("/api/reviews/<review_id>/reply")
    def reply(review_id):
        return jsonify(service.save_reply(actor()["id"], review_id, payload().get("body") or ""))

    @app.post("/api/claims")
    def start_claim():
        data = payload()
        return jsonify(service.start_claim(
            actor()["id"], data.get("listingId"), bool(data.get("represents")),
            data.get("method") or "manual", data.get("contactEmail"), data.get("company"),
        ))

    @app.post("/api/claims/<claim_id>/code")
    def claim_code(claim_id):
        return jsonify(service.submit_claim_code(actor()["id"], claim_id, payload().get("code")))

    @app.patch("/api/listings/<listing_id>/overlay")
    def overlay(listing_id):
        return jsonify(overlay=service.save_overlay(actor()["id"], listing_id, payload()))

    @app.get("/api/admin/queue")
    def queue():
        return jsonify(items=service.queue(actor()["id"]))

    @app.post("/api/admin/queue/<kind>/<item_id>")
    def moderate(kind, item_id):
        data = payload()
        return jsonify(service.moderate(
            actor()["id"], kind, item_id, data.get("action"),
            data.get("body") or "", data.get("ratings"), data.get("note") or "",
        ))

    @app.get("/api/admin/settings")
    def admin_settings():
        return jsonify(service.admin_settings(actor()["id"]))

    @app.patch("/api/admin/settings")
    def update_settings():
        return jsonify(service.update_settings(actor()["id"], payload()))

    @app.get("/api/admin/accounts")
    def accounts():
        return jsonify(accounts=service.accounts(actor()["id"]))

    @app.post("/api/admin/accounts/<account_id>/verify-email")
    def verify_email(account_id):
        return jsonify(account=service.verify_email(actor()["id"], account_id))

    @app.post("/api/admin/accounts/<account_id>/moderator")
    def moderator(account_id):
        return jsonify(account=service.set_moderator(actor()["id"], account_id, bool(payload().get("grant", True))))

    @app.post("/api/admin/accounts/<account_id>/remove")
    def remove_account(account_id):
        return jsonify(service.remove_account(actor()["id"], account_id))

    @app.post("/api/admin/claims/<claim_id>/verify")
    def verify_claim(claim_id):
        return jsonify(service.verify_claim(actor()["id"], claim_id))

    @app.post("/api/admin/claims/<claim_id>/revoke")
    def revoke_claim(claim_id):
        return jsonify(service.revoke_claim(actor()["id"], claim_id))

    @app.post("/api/admin/portals/<listing_id>")
    def grant_portal(listing_id):
        return jsonify(service.grant_portal(actor()["id"], listing_id, bool(payload().get("active", True))))

    @app.get("/api/portal/<listing_id>")
    def portal_home(listing_id):
        return jsonify(service.portal_home(actor()["id"], listing_id))

    @app.post("/api/portal/<listing_id>/mark-paid")
    def mark_portal(listing_id):
        return jsonify(service.mark_portal_paid(actor()["id"], listing_id))

    @app.post("/api/portal/<listing_id>/invites")
    def invite(listing_id):
        return jsonify(service.invite_member(actor()["id"], listing_id, payload().get("email")))

    @app.post("/api/portal/<listing_id>/join")
    def join(listing_id):
        return jsonify(service.join_portal(actor()["id"], listing_id))

    @app.post("/api/portal/<listing_id>/children")
    def child(listing_id):
        data = payload()
        return jsonify(service.add_child(actor()["id"], listing_id, data.get("firstName"), data.get("grade")))

    @app.post("/api/portal/<listing_id>/offerings")
    def offering(listing_id):
        data = payload()
        return jsonify(service.add_offering(
            actor()["id"], listing_id, data.get("kind"), data.get("title"),
            data.get("capacity"), data.get("feeCents"), data.get("startsOn"), data.get("endsOn"),
        ))

    @app.post("/api/portal/offerings/<offering_id>/signup")
    def offering_signup(offering_id):
        return jsonify(service.signup_offering(actor()["id"], offering_id, payload().get("childId")))

    @app.post("/api/portal/enrollments/<enrollment_id>/drop")
    def drop(enrollment_id):
        return jsonify(service.drop_enrollment(actor()["id"], enrollment_id))

    @app.post("/api/portal/<listing_id>/dues")
    def dues(listing_id):
        data = payload()
        return jsonify(service.create_due(actor()["id"], listing_id, data.get("accountId"), data.get("label"), data.get("amountCents")))

    @app.post("/api/portal/payments/<payment_id>/mark-paid")
    def mark_paid(payment_id):
        return jsonify(service.mark_paid(actor()["id"], payment_id))

    @app.post("/api/portal/payments/<payment_id>/stripe-test")
    def stripe_test(payment_id):
        raise ServiceError("Stripe isn't configured. Use Mark as paid (test). No card is charged.")

    @app.post("/api/portal/<listing_id>/announcements")
    def announce(listing_id):
        data = payload()
        return jsonify(service.announce(actor()["id"], listing_id, data.get("title"), data.get("body"), data.get("audience") or "all"))

    @app.post("/api/portal/<listing_id>/rotation")
    def rotation(listing_id):
        data = payload()
        return jsonify(service.add_rotation(actor()["id"], listing_id, data.get("date"), data.get("role"), data.get("accountId")))

    @app.post("/api/looking-for")
    def save_looking():
        return jsonify(service.save_looking(actor()["id"], payload()))

    @app.post("/api/looking-for/<post_id>/replies")
    def looking_reply(post_id):
        return jsonify(service.reply_looking(actor()["id"], post_id, payload().get("body")))

    @app.post("/api/looking-for/<post_id>/renew")
    def renew(post_id):
        return jsonify(service.renew_looking(actor()["id"], post_id))

    @app.post("/api/events")
    def save_event():
        return jsonify(service.save_event(actor()["id"], payload()))

    @app.get("/api/favorites")
    def favorites():
        return jsonify(service.list_favorites(actor()["id"]))

    @app.post("/api/favorites")
    def save_favorite():
        data = payload()
        return jsonify(service.save_favorite(actor()["id"], data.get("listingId"), data.get("alertOnOpenSpots")))

    @app.delete("/api/favorites/<listing_id>")
    def remove_favorite(listing_id):
        return jsonify(service.remove_favorite(actor()["id"], listing_id))

    @app.post("/api/watches")
    def watch():
        data = payload()
        return jsonify(service.set_watch(actor()["id"], data.get("state"), data.get("county"), bool(data.get("enabled", True))))
