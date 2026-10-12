"""Release regression checks using isolated fictional records only."""

import unittest

import test_tourism_revision as fixtures

from inbound_ai_acquisition.application.services import (
    add_stop,
    approve_draft,
    create_draft,
    create_run,
    ingest_reply,
    release_stop,
    set_draft_status,
)
from inbound_ai_acquisition.errors import StateError, ValidationError
from inbound_ai_acquisition.storage.repositories import active_stop_exists


class ReleaseBehaviorTests(unittest.TestCase):
    setUp = fixtures.TourismRevisionTests.setUp
    tearDown = fixtures.TourismRevisionTests.tearDown
    write_json = fixtures.TourismRevisionTests.write_json
    seed_company_contact_claim = fixtures.TourismRevisionTests.seed_company_contact_claim
    draft_payload = fixtures.TourismRevisionTests.draft_payload

    def test_no_product_and_mismatched_product_cannot_create_draft(self):
        self.seed_company_contact_claim()
        payload = self.draft_payload()
        payload["product_version"] = "invented-version"
        with self.assertRaises(StateError):
            create_draft(self.db, payload, "mismatch")
        with self.db.transaction() as c:
            c.execute("UPDATE runs SET product_version='' WHERE run_id=?", (self.run,))
        with self.assertRaises(StateError):
            create_draft(self.db, self.draft_payload(), "no-product")
        self.assertEqual(len(self.db.query("SELECT * FROM drafts")), 0)

    def test_changed_run_product_blocks_approval_and_sent_record(self):
        self.seed_company_contact_claim()
        draft = create_draft(self.db, self.draft_payload(), "new")["draft_id"]
        with self.db.transaction() as c:
            c.execute("UPDATE runs SET product_version='changed' WHERE run_id=?", (self.run,))
        with self.assertRaises(StateError):
            approve_draft(self.db, draft, "test-human", "test only", "approve")
        with self.db.transaction() as c:
            c.execute("UPDATE runs SET product_version='test-v1' WHERE run_id=?", (self.run,))
        approve_draft(self.db, draft, "test-human", "test only", "approve2")
        with self.db.transaction() as c:
            c.execute("UPDATE runs SET product_version='' WHERE run_id=?", (self.run,))
        with self.assertRaises(StateError):
            set_draft_status(self.db, draft, "sent", "sent")

    def two_batches(self):
        self.seed_company_contact_claim()
        first = create_draft(self.db, self.draft_payload(), "first")["draft_id"]
        second_run = create_run(
            self.db,
            markets=["AU"],
            segments=["travel_agency"],
            target=20,
            request_id="second",
            idempotency_key="second",
            product_version="test-v1",
        )["run_id"]
        with self.db.transaction() as c:
            company = dict(c.execute("SELECT * FROM companies WHERE company_id='co_demo'").fetchone())
            company.update(company_id="co_second", run_id=second_run)
            c.execute(
                f"INSERT INTO companies ({','.join(company)}) VALUES ({','.join('?' for _ in company)})",
                tuple(company.values()),
            )
            contact = dict(c.execute("SELECT * FROM contacts WHERE contact_id='ct_demo'").fetchone())
            contact.update(contact_id="ct_second", company_id="co_second")
            c.execute(
                f"INSERT INTO contacts ({','.join(contact)}) VALUES ({','.join('?' for _ in contact)})",
                tuple(contact.values()),
            )
            draft = dict(c.execute("SELECT * FROM drafts WHERE draft_id=?", (first,)).fetchone())
            draft.update(draft_id="dr_second", run_id=second_run, company_id="co_second", contact_id="ct_second")
            c.execute(
                f"INSERT INTO drafts ({','.join(draft)}) VALUES ({','.join('?' for _ in draft)})", tuple(draft.values())
            )
        return first

    def test_manual_stop_stops_cross_batch_drafts_and_release_never_restores(self):
        first = self.two_batches()
        approve_draft(self.db, first, "test-human", "test only", "approve")
        add_stop(self.db, "email", "alex@example.test", "test only", "test-human", "stop")
        self.assertEqual({r["status"] for r in self.db.query("SELECT status FROM drafts")}, {"stopped"})
        rule = self.db.query("SELECT stop_rule_id FROM stop_rules")[0]["stop_rule_id"]
        with self.assertRaises(ValidationError):
            release_stop(self.db, rule, " ", "test reason", "bad-release")
        release_stop(self.db, rule, "test-human", "test reason", "release")
        self.assertEqual({r["status"] for r in self.db.query("SELECT status FROM drafts")}, {"stopped"})

    def test_reply_stop_stops_cross_batch_equivalent_contact(self):
        self.two_batches()
        ingest_reply(
            self.db,
            {
                "message_id": "isolated-reply",
                "contact_id": "ct_demo",
                "channel": "email",
                "received_at": "2026-09-18T00:00:00Z",
                "reply_category": "unsubscribe",
                "source_reference": "isolated test message",
            },
            "reply",
            "reply",
        )
        self.assertEqual({r["status"] for r in self.db.query("SELECT status FROM drafts")}, {"stopped"})

    def test_domain_stop_inherits_only_real_subdomains(self):
        self.seed_company_contact_claim()
        add_stop(self.db, "domain", "example.test", "test only", "test-human", "stop")
        with self.db.transaction() as c:
            self.assertTrue(active_stop_exists(c, "", "", preview_domain="au.example.test"))
            self.assertFalse(active_stop_exists(c, "", "", preview_domain="evil-example.test"))
            self.assertFalse(active_stop_exists(c, "", "", preview_domain="example.test.evil.test"))

    def test_expansion_and_channel_research_are_not_outreach_permission(self):
        self.seed_company_contact_claim()
        for role, signal in (("outbound_seller", "none"), ("channel_partner", "direct")):
            with self.db.transaction() as c:
                c.execute("UPDATE claims SET proposed_value=? WHERE field_name='source_market_role'", (role,))
                c.execute("UPDATE claims SET proposed_value=? WHERE field_name='china_product_signal'", (signal,))
            draft = create_draft(self.db, self.draft_payload(), "new")["draft_id"]
            with self.assertRaises(StateError):
                approve_draft(self.db, draft, "test-human", "test only", "approve")
