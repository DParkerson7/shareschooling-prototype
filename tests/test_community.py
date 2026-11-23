"""Rules from the community brief. The store is in memory, so Postgres is not required."""

import json
import unittest
from pathlib import Path

from api.app import create_app
from api.logic import fee_split, filter_text, default_settings
from api.store import MemoryStore, load_catalog

ROOT = Path(__file__).resolve().parent.parent
MHEC = "memphis-homeschool-enrichment-cooperative-mhec-memphis"
SPARK = "spark-joy-homeschool-co-operative-jackson"
BELLEVUE = "bellevue-tutorial-cordova"
BRIDGE = "the-bridge-tutorial-arlington"


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.settings = default_settings()

    def test_phone_name_email_address_and_harsh_words(self):
        self.assertIn("phone", filter_text("Call Jamie Cole at 555-0148", self.settings, "Bellevue Tutorial"))
        self.assertIn("possible-name", filter_text("Call Jamie Cole at 555-0148", self.settings, "Bellevue Tutorial"))
        self.assertIn("possible-name", filter_text("my son Sam loved the class", self.settings, "MHEC"))
        self.assertIn("possible-name", filter_text("my daughter sam was there", self.settings, "MHEC"))
        self.assertIn("email", filter_text("write jane@home.test please", self.settings, "MHEC"))
        self.assertIn("address", filter_text("We meet at 12 Oak Street", self.settings, "MHEC"))
        self.assertIn("harsh-language", filter_text("The class was stupid", self.settings, "MHEC"))
        self.assertEqual(filter_text("The classroom was great", self.settings, "MHEC"), [])
        self.assertNotIn(
            "possible-name",
            filter_text("Memphis Homeschool was organized", self.settings, "Memphis Homeschool Enrichment Cooperative (MHEC)"),
        )

    def test_score_is_not_an_input_and_checks_can_turn_off(self):
        self.assertEqual(filter_text("Fair criticism, nothing more.", self.settings, "MHEC"), [])
        off = default_settings()
        off["nameCheck"] = False
        self.assertNotIn("possible-name", filter_text("Jamie Cole taught it", off, "Bellevue Tutorial"))

    def test_fee_split_does_not_invent_a_price(self):
        unset = fee_split(4000, None)
        self.assertIsNone(unset["platformShareCents"])
        self.assertFalse(unset["collected"])
        self.assertIn("not set", unset["summary"])
        split = fee_split(4000, 3)
        self.assertEqual(split["platformShareCents"], 120)
        self.assertFalse(split["collected"])
        self.assertEqual(
            split["summary"],
            "Test record: $40.00 dues, $1.20 platform share (not collected), $38.80 to the group.",
        )


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.app = create_app(store=self.store, catalog=load_catalog(), secret="test-secret")
        self.app.service.ensure_admin("david@example.com", "admin-pass-1", "David")
        self.client = self.app.test_client()
        self.admin = self._login("david@example.com", "admin-pass-1")

    def _login(self, email, password):
        response = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["token"]

    def _auth(self, token, method, path, body=None):
        return self.client.open(path, method=method, json=body, headers={"Authorization": f"Bearer {token}"})

    def _family(self, email, name, verified=True):
        response = self.client.post("/api/auth/signup", json={
            "email": email, "password": "family-pass-1", "displayName": name,
            "inviteCode": "FRIENDS-TEST", "company": "",
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        account = response.get_json()["account"]
        token = response.get_json()["token"]
        if verified:
            marked = self._auth(self.admin, "POST", f"/api/admin/accounts/{account['id']}/verify-email")
            self.assertEqual(marked.status_code, 200, marked.get_json())
        return token, account

    def _enable(self, **modules):
        response = self._auth(self.admin, "PATCH", "/api/admin/settings", {"modules": modules})
        self.assertEqual(response.status_code, 200, response.get_json())

    def _establish(self, token, account_id):
        def op(state):
            for row in state["collections"]["accounts"]:
                if row["id"] == account_id:
                    row["approvedReviewCount"] = 2
        self.app.service.tx(op)

    def test_invite_honeypot_and_verification_gate(self):
        bad = self.client.post("/api/auth/signup", json={
            "email": "nope@example.com", "password": "family-pass-1", "displayName": "The Nope family",
            "inviteCode": "WRONG", "company": "",
        })
        self.assertEqual(bad.status_code, 400)
        honey = self.client.post("/api/auth/signup", json={
            "email": "bot@example.com", "password": "family-pass-1", "displayName": "Bot",
            "inviteCode": "FRIENDS-TEST", "company": "Acme",
        })
        self.assertEqual(honey.status_code, 200)
        self.assertNotIn("token", honey.get_json())
        accounts = self._auth(self.admin, "GET", "/api/admin/accounts").get_json()["accounts"]
        self.assertFalse(any(row["email"] == "bot@example.com" for row in accounts))
        self.assertFalse(any(row["email"] == "nope@example.com" for row in accounts))
        token, account = self._family("new.parent@example.com", "Alex P.", verified=False)
        denied = self._auth(token, "POST", "/api/reviews", {"listingId": SPARK, "ratings": {"welcoming": 1}, "body": "Fine."})
        self.assertEqual(denied.status_code, 403)
        self._auth(self.admin, "POST", f"/api/admin/accounts/{account['id']}/verify-email")
        held = self._auth(token, "POST", "/api/reviews", {"listingId": SPARK, "ratings": {"welcoming": 1, "organized": 1}, "body": "The meeting place changed."})
        self.assertEqual(held.status_code, 200, held.get_json())
        self.assertEqual(held.get_json()["status"], "held")
        self.assertEqual(held.get_json()["holdReasons"] if "holdReasons" in held.get_json() else ["new-account"], ["new-account"])
        self.assertIn("low rating is not a reason", held.get_json().get("waitingMessage", ""))

    def test_new_account_wait_then_clean_review_publishes(self):
        token, account = self._family("alex@example.com", "Alex P.")
        first = self._auth(token, "POST", "/api/reviews", {"listingId": SPARK, "ratings": {"welcoming": 1}, "body": "It was fine."})
        self.assertEqual(first.get_json()["status"], "held")
        queue = self._auth(self.admin, "GET", "/api/admin/queue").get_json()["items"]
        self.assertTrue(any(item["id"] == first.get_json()["id"] and "new-account" in item["reasons"] for item in queue))
        self.assertTrue(all("score" not in " ".join(item["reasons"]) for item in queue))
        approved = self._auth(self.admin, "POST", f"/api/admin/queue/review/{first.get_json()['id']}", {"action": "approve"})
        self.assertEqual(approved.status_code, 200, approved.get_json())
        second = self._auth(token, "POST", "/api/reviews", {"listingId": BELLEVUE, "ratings": {"organized": 2}, "body": "The class ran late."})
        self.assertEqual(second.get_json()["status"], "held")
        self._auth(self.admin, "POST", f"/api/admin/queue/review/{second.get_json()['id']}", {"action": "approve"})
        third = self._auth(token, "POST", "/api/reviews", {"listingId": BRIDGE, "ratings": {"communication": 1}, "body": "Worth knowing the schedule slips."})
        self.assertEqual(third.get_json()["status"], "published")
        public = self.client.get(f"/api/public/listings/{BRIDGE}").get_json()
        self.assertEqual(public["summary"]["reviewCount"], 1)
        self.assertEqual(set(public["summary"]), {"listingId", "reviewCount", "averages"})
        self.assertNotIn("portal", json.dumps(public["summary"]))

    def test_filter_hold_can_be_edited_and_flags_hide(self):
        token, account = self._family("chen@example.com", "The Chen family")
        self._establish(token, account["id"])
        held = self._auth(token, "POST", "/api/reviews", {
            "listingId": BELLEVUE,
            "ratings": {"communication": 2},
            "body": "Call Jamie Cole at 555-0148 if you want the same tutor we used.",
        }).get_json()
        self.assertEqual(held["status"], "held")
        queue = self._auth(self.admin, "GET", "/api/admin/queue").get_json()["items"]
        match = next(item for item in queue if item["id"] == held["id"])
        self.assertIn("phone", match["reasons"])
        self.assertIn("possible-name", match["reasons"])
        edited = self._auth(self.admin, "POST", f"/api/admin/queue/review/{held['id']}", {
            "action": "edit",
            "body": "Ask the office if you want the same tutor we used.",
            "ratings": {"communication": 2},
        })
        self.assertEqual(edited.status_code, 200, edited.get_json())
        public = self.client.get(f"/api/public/listings/{BELLEVUE}").get_json()
        self.assertNotIn("555-0148", json.dumps(public))
        self.assertNotIn("Jamie Cole", json.dumps(public))
        other, _ = self._family("other@example.com", "The Other family")
        self._enable(reviews=True)
        self._auth(self.admin, "PATCH", "/api/admin/settings", {"flagsToHide": 1})
        flagged = self._auth(other, "POST", "/api/flags", {"targetType": "review", "targetId": held["id"], "reason": "Different campus."})
        self.assertEqual(flagged.get_json()["status"], "hidden")
        again = self._auth(other, "POST", "/api/flags", {"targetType": "review", "targetId": held["id"], "reason": "again"})
        self.assertFalse(again.get_json()["counted"])
        hidden = self.client.get(f"/api/public/listings/{BELLEVUE}").get_json()
        self.assertTrue(all(row["id"] != held["id"] for row in hidden["reviews"]))
        own = self._auth(token, "GET", f"/api/public/listings/{BELLEVUE}").get_json()
        mine = next(row for row in own["reviews"] if row["id"] == held["id"])
        self.assertIn("hidden", mine["waitingMessage"])

    def test_reply_requires_verified_claim_and_low_score_publishes(self):
        family, account = self._family("chen2@example.com", "The Chen family")
        self._establish(family, account["id"])
        review = self._auth(family, "POST", "/api/reviews", {
            "listingId": MHEC, "ratings": {"welcoming": 1, "organized": 1}, "body": "Hard to find the room, but the class itself was fine.",
        }).get_json()
        self.assertEqual(review["status"], "published")
        stranger, _ = self._family("stranger@example.com", "Pat Q.")
        denied = self._auth(stranger, "POST", f"/api/reviews/{review['id']}/reply", {"body": "Thanks for saying so."})
        self.assertEqual(denied.status_code, 403)
        org, org_account = self._family("board@example.com", "MHEC board")
        claim = self._auth(org, "POST", "/api/claims", {"listingId": MHEC, "represents": True, "method": "manual", "company": ""})
        self.assertEqual(claim.status_code, 200, claim.get_json())
        self.assertNotIn("code", claim.get_json())
        self._auth(self.admin, "POST", f"/api/admin/claims/{claim.get_json()['id']}/verify")
        reply = self._auth(org, "POST", f"/api/reviews/{review['id']}/reply", {"body": "Thank you. New families can visit one Thursday."})
        self.assertEqual(reply.status_code, 200, reply.get_json())
        public = self.client.get(f"/api/public/listings/{MHEC}").get_json()
        self.assertEqual(public["reviews"][0]["reply"]["body"], "Thank you. New families can visit one Thursday.")
        self.assertIsNone(public["claimLabel"])
        own = self._auth(org, "POST", "/api/reviews", {"listingId": MHEC, "ratings": {"welcoming": 5}, "body": "We are wonderful."})
        self.assertEqual(own.status_code, 400)

    def test_claims_overlay_and_portal_do_not_change_public_judgment(self):
        self._enable(claims=True, groupPortal=True, favorites=True)
        org, _ = self._family("board2@example.com", "MHEC board")
        claim = self._auth(org, "POST", "/api/claims", {"listingId": MHEC, "represents": True, "method": "manual"}).get_json()
        self._auth(self.admin, "POST", f"/api/admin/claims/{claim['id']}/verify")
        saved = self._auth(org, "PATCH", f"/api/listings/{MHEC}/overlay", {"openSpots": "A few Thursday spots left", "meetingDays": "Thursdays"})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        self.assertEqual(saved.get_json()["overlay"]["openSpots"], "A few Thursday spots left")
        self.assertTrue(saved.get_json()["overlay"]["updatedLabel"].startswith("Updated "))
        dirty = self._auth(org, "PATCH", f"/api/listings/{MHEC}/overlay", {"description": "Meet at 12 Oak Street behind the house."})
        self.assertEqual(dirty.get_json()["overlay"]["description"], "")
        queue = self._auth(self.admin, "GET", "/api/admin/queue").get_json()["items"]
        self.assertTrue(any(item["type"] == "overlay" and "Oak Street" in item["text"] for item in queue))
        public = self.client.get(f"/api/public/listings/{MHEC}").get_json()
        self.assertEqual(public["claimLabel"], "Claimed by the organization.")
        self.assertNotIn("Oak Street", json.dumps(public["overlay"]))
        grant = self._auth(self.admin, "POST", f"/api/admin/portals/{MHEC}", {"active": True})
        self.assertEqual(grant.status_code, 200, grant.get_json())
        self.assertFalse(grant.get_json()["publicBadge"])
        again = self.client.get(f"/api/public/listings/{MHEC}").get_json()
        self.assertNotIn("portal", json.dumps(again))
        self.assertNotIn("premium", json.dumps(again).lower())

    def test_portal_waitlist_dues_announcement_and_rotation(self):
        self._enable(groupPortal=True)
        org, _ = self._family("board3@example.com", "MHEC board")
        claim = self._auth(org, "POST", "/api/claims", {"listingId": MHEC, "represents": True, "method": "manual"}).get_json()
        self._auth(self.admin, "POST", f"/api/admin/claims/{claim['id']}/verify")
        turned = self._auth(org, "POST", f"/api/portal/{MHEC}/mark-paid", {})
        self.assertEqual(turned.status_code, 200, turned.get_json())
        self.assertFalse(turned.get_json()["charged"])
        self.assertIn("won't charge", turned.get_json()["message"])
        member, member_account = self._family("member@example.com", "The Chen family")
        other, _ = self._family("wait@example.com", "Alex P.")
        invite = self._auth(org, "POST", f"/api/portal/{MHEC}/invites", {"email": "member@example.com"}).get_json()
        self.assertFalse(invite["emailed"])
        self.assertIn("member@example.com", invite["message"])
        self._auth(org, "POST", f"/api/portal/{MHEC}/invites", {"email": "wait@example.com"})
        self.assertEqual(self._auth(member, "POST", f"/api/portal/{MHEC}/join", {}).status_code, 200)
        self.assertEqual(self._auth(other, "POST", f"/api/portal/{MHEC}/join", {}).status_code, 200)
        offering = self._auth(org, "POST", f"/api/portal/{MHEC}/offerings", {
            "kind": "class", "title": "Thursday art", "capacity": 1, "feeCents": 2000,
        }).get_json()
        first = self._auth(member, "POST", f"/api/portal/offerings/{offering['id']}/signup", {}).get_json()
        second = self._auth(other, "POST", f"/api/portal/offerings/{offering['id']}/signup", {}).get_json()
        self.assertEqual(first["state"], "enrolled")
        self.assertEqual(first["paymentState"], "due")
        self.assertEqual(second["state"], "waitlist")
        dropped = self._auth(member, "POST", f"/api/portal/enrollments/{first['id']}/drop", {}).get_json()
        self.assertEqual(dropped["promoted"]["accountId"], other and second["accountId"])
        self.assertEqual(dropped["promoted"]["paymentState"], "due")
        due = self._auth(org, "POST", f"/api/portal/{MHEC}/dues", {
            "accountId": member_account["id"], "label": "Spring dues (test)", "amountCents": 4000,
        }).get_json()
        paid = self._auth(member, "POST", f"/api/portal/payments/{due['id']}/mark-paid", {}).get_json()
        self.assertEqual(paid["paymentState"], "paid-test")
        self.assertFalse(paid["collected"])
        self.assertIn("not set", paid["summary"])
        self._auth(self.admin, "PATCH", "/api/admin/settings", {"portalDuesCutPercent": 3})
        due2 = self._auth(org, "POST", f"/api/portal/{MHEC}/dues", {
            "accountId": member_account["id"], "label": "Again", "amountCents": 4000,
        }).get_json()
        paid2 = self._auth(member, "POST", f"/api/portal/payments/{due2['id']}/mark-paid", {}).get_json()
        self.assertIn("$1.20", paid2["summary"])
        self.assertFalse(paid2["collected"])
        held = self._auth(org, "POST", f"/api/portal/{MHEC}/announcements", {
            "title": "Where", "body": "Come to 12 Oak Street.", "audience": "all",
        }).get_json()
        self.assertEqual(held["status"], "held")
        self.assertFalse(held["emailed"])
        sent = self._auth(org, "POST", f"/api/portal/{MHEC}/announcements", {
            "title": "Thursday plan", "body": "Art meets in the same room. Bring a smock.", "audience": "all",
        }).get_json()
        self.assertEqual(sent["status"], "outbox")
        home = self._auth(member, "GET", f"/api/portal/{MHEC}").get_json()
        self.assertTrue(any(item["title"] == "Thursday plan" for item in home["messages"]))
        self.assertFalse(any("Oak Street" in item.get("body", "") for item in home["messages"]))
        self.assertEqual(home["line"], "Portal on (test)")
        self.assertFalse(home["publicBadge"])
        child = self._auth(member, "POST", f"/api/portal/{MHEC}/children", {"firstName": "Sam", "grade": "4"})
        self.assertEqual(child.status_code, 200, child.get_json())
        rotation = self._auth(org, "POST", f"/api/portal/{MHEC}/rotation", {
            "date": "2027-01-08", "role": "Teach", "accountId": member_account["id"],
        })
        self.assertEqual(rotation.status_code, 200, rotation.get_json())
        refused = self._auth(org, "POST", f"/api/portal/{MHEC}/rotation", {
            "date": "2027-01-15", "role": "Teach", "accountId": child.get_json()["id"],
        })
        self.assertEqual(refused.status_code, 400)
        public = self.client.get(f"/api/public/listings/{MHEC}").get_json()
        self.assertNotIn("Sam", json.dumps(public))
        self.assertNotIn("roster", json.dumps(public))

    def test_looking_events_badges_favorites_and_module_switch(self):
        self._enable(lookingFor=True, events=True, badges=True, favorites=True, claims=True)
        family, account = self._family("chen3@example.com", "The Chen family")
        held = self._auth(family, "POST", "/api/looking-for", {
            "title": "Tutor", "body": "My son Sam needs Spanish.", "state": "TN", "county": "Shelby", "city": "Collierville", "category": "tutors",
        }).get_json()
        self.assertEqual(held["status"], "held")
        self._establish(family, account["id"])
        clean = self._auth(family, "POST", "/api/looking-for", {
            "title": "Spanish tutor near Collierville",
            "body": "Looking for a weekly Spanish class for elementary ages, in person, near Collierville.",
            "state": "TN", "county": "Shelby", "city": "Collierville", "category": "tutors",
        }).get_json()
        self.assertEqual(clean["status"], "published")
        listed = self.client.get("/api/public/looking-for?state=TN&county=Shelby").get_json()["posts"]
        self.assertTrue(any(item["id"] == clean["id"] for item in listed))
        self.assertFalse(any(item["id"] == held["id"] for item in listed))
        org, _ = self._family("board4@example.com", "MHEC board")
        claim = self._auth(org, "POST", "/api/claims", {"listingId": MHEC, "represents": True, "method": "manual"}).get_json()
        self._auth(self.admin, "POST", f"/api/admin/claims/{claim['id']}/verify")
        reply = self._auth(org, "POST", f"/api/looking-for/{clean['id']}/replies", {"body": "We have a Thursday Spanish class."})
        self.assertEqual(reply.get_json()["status"], "published")
        blocked = self._auth(family, "POST", "/api/events", {
            "title": "Park day", "summary": "Meet at 12 Oak Street.", "venue": "a house",
            "startsAt": "2026-12-03T16:00:00Z", "endsAt": "2026-12-03T18:00:00Z",
            "state": "TN", "county": "Shelby", "city": "Memphis",
        }).get_json()
        self.assertEqual(blocked["status"], "held")
        event = self._auth(family, "POST", "/api/events", {
            "title": "Park day", "summary": "Informal meet-up by the visitor center.",
            "venue": "the visitor center", "listingId": MHEC,
            "startsAt": "2026-12-03T16:00:00Z", "endsAt": "2026-12-03T18:00:00Z",
            "state": "TN", "county": "Shelby", "city": "Memphis",
        }).get_json()
        self.assertEqual(event["status"], "published")
        self.assertTrue(event["pinned"])
        review = self._auth(family, "POST", "/api/reviews", {
            "listingId": SPARK, "ratings": {"welcoming": 5}, "body": "Easy to join.",
        }).get_json()
        self.assertTrue(review["trusted"])
        before = self.client.get(f"/api/public/summaries?ids={SPARK}").get_json()["summaries"]
        self._auth(self.admin, "PATCH", "/api/admin/settings", {"modules": {"badges": False}})
        bare = self._auth(family, "GET", f"/api/public/listings/{SPARK}").get_json()
        self.assertFalse(any(row.get("trusted") for row in bare["reviews"]))
        after = self.client.get(f"/api/public/summaries?ids={SPARK}").get_json()["summaries"]
        self.assertEqual(before, after)
        self._auth(self.admin, "POST", f"/api/admin/accounts/{account['id']}/moderator", {"grant": True})
        mod = self._login("chen3@example.com", "family-pass-1")
        self.assertEqual(self._auth(mod, "GET", "/api/admin/queue").status_code, 200)
        self.assertEqual(self._auth(mod, "GET", "/api/admin/settings").status_code, 403)
        saved = self._auth(family, "POST", "/api/favorites", {"listingId": SPARK, "alertOnOpenSpots": True})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        self.assertEqual(len(self._auth(family, "GET", "/api/favorites").get_json()["saved"]), 1)
        self._auth(family, "DELETE", f"/api/favorites/{SPARK}")
        self.assertEqual(self._auth(family, "GET", "/api/favorites").get_json()["saved"], [])
        self._auth(self.admin, "PATCH", "/api/admin/settings", {"modules": {"reviews": False}})
        self.assertEqual(self.client.get(f"/api/public/summaries?ids={SPARK}").get_json()["summaries"], [])
        self.assertEqual(self.client.get(f"/api/public/listings/{SPARK}").get_json()["reviews"], [])

    def test_pending_edit_keeps_the_public_text(self):
        family, account = self._family("edit@example.com", "The Chen family")
        self._establish(family, account["id"])
        first = self._auth(family, "POST", "/api/reviews", {
            "listingId": SPARK, "ratings": {"welcoming": 4}, "body": "The weekly plan was posted in advance.",
        }).get_json()
        self.assertEqual(first["status"], "published")
        edited = self._auth(family, "POST", "/api/reviews", {
            "listingId": SPARK, "ratings": {"welcoming": 4}, "body": "Call me at 555-0199 about it.",
        }).get_json()
        self.assertIn("previous text stays up", edited["pendingMessage"])
        public = self.client.get(f"/api/public/listings/{SPARK}").get_json()
        self.assertIn("weekly plan", public["reviews"][0]["body"])
        self.assertNotIn("555-0199", public["reviews"][0]["body"])

    def test_blueprint_does_not_create_a_database(self):
        text = (ROOT / "render.yaml").read_text()
        self.assertNotIn("\ndatabases:", "\n" + text)
        self.assertIn("shareschooling-db", text)
        self.assertIn("region: ohio", text)
        self.assertIn("plan: free", text)
        self.assertIn("connectionString", text)
        self.assertNotIn("sk_live", text)
        self.assertNotIn("postgres://", text)


if __name__ == "__main__":
    unittest.main()
