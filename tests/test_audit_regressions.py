"""Isolated fixtures for the October audit; no live contacts or sends."""

import copy
import json
import unittest

import test_unified_company_pool as unified

from inbound_ai_acquisition.application.research import (
    approve_run_claims,
    ingest_draft_bundle,
    ingest_source_bundle,
    run_research,
    verify_research_uat,
)
from inbound_ai_acquisition.application.services import (
    approve_draft,
    create_draft,
    create_run,
    ingest_reply,
    set_draft_status,
)
from inbound_ai_acquisition.errors import StateError, ValidationError
from inbound_ai_acquisition.exporters.json_export import export_json
from inbound_ai_acquisition.exporters.workbook import export_workbook

service_bundle = unified.service_bundle


class AuditRegressions(unittest.TestCase):
    setUp = unified.UnifiedPoolTests.setUp
    tearDown = unified.UnifiedPoolTests.tearDown
    write_json = unified.UnifiedPoolTests.write_json
    seed_company_contact_claim = unified.UnifiedPoolTests.seed_company_contact_claim
    seed_service_claims = unified.UnifiedPoolTests.seed_service_claims
    draft_payload = unified.UnifiedPoolTests.draft_payload

    def reply(self, **changes):
        return {
            "message_id": "synthetic-message",
            "contact_id": "ct_demo",
            "channel": "email",
            "received_at": "2026-10-12T00:00:00+00:00",
            "reply_category": "request_quote",
            **changes,
        }

    def test_executor_requests_uniform_pool(self):
        request = run_research(self.db, self.run, "request")["executor_request"]
        rules = " ".join(request["rules"])
        self.assertIn("service_fit_v1", rules)
        self.assertNotIn("按direct/expansion/channel", rules)
        self.assertIn("counter_evidence", rules)

    def test_pending_and_failed_qa_cannot_be_approved(self):
        self.seed_service_claims()
        for status in ("needs_review", "failed"):
            for field in ("fact_check_status", "voice_check_status"):
                payload = self.draft_payload()
                payload[field] = status
                payload["outreach_contract"].pop(field)
                draft = create_draft(self.db, payload, "draft")["draft_id"]
                with self.assertRaises(StateError):
                    approve_draft(self.db, draft, "test", "fixture", "approve")
                set_draft_status(self.db, draft, "review_ready", "forced")
                with self.assertRaises(StateError):
                    approve_draft(self.db, draft, "test", "fixture", "approve")

    def test_pending_bundle_can_record_explicit_review(self):
        self.seed_service_claims()
        payload = self.draft_payload()
        payload["outreach_contract"]["voice_check_status"] = "pending"
        ingest_draft_bundle(self.db, self.run, {"drafts": [payload]}, "initial")
        payload["outreach_contract"]["voice_check_status"] = "passed"
        ingest_draft_bundle(self.db, self.run, {"drafts": [payload]}, "review")
        draft = self.db.query("SELECT * FROM drafts")[0]
        self.assertEqual(draft["status"], "review_ready")
        approve_draft(self.db, draft["draft_id"], "test", "fixture", "approve")
        payload["outreach_contract"]["voice_check_status"] = "failed"
        with self.assertRaises(StateError):
            ingest_draft_bundle(self.db, self.run, {"drafts": [payload]}, "mutate")

    def test_qa_conflict_is_not_silently_ignored(self):
        self.seed_service_claims()
        payload = self.draft_payload()
        payload["fact_check_status"] = "failed"
        with self.assertRaises(ValidationError):
            create_draft(self.db, payload, "conflict")

    def test_stale_evidence_and_identity_block_approval(self):
        self.seed_service_claims()
        draft = create_draft(self.db, self.draft_payload(), "draft")["draft_id"]
        for table, column in (("evidence", "observed_at"), ("contacts", "last_verified_at")):
            with self.db.transaction() as c:
                old = c.execute(f"SELECT {column} FROM {table}").fetchone()[0]
                c.execute(f"UPDATE {table} SET {column}='2000-01-01T00:00:00+00:00'")
            with self.assertRaises(StateError):
                approve_draft(self.db, draft, "test", "fixture", "approve")
            with self.db.transaction() as c:
                c.execute(f"UPDATE {table} SET {column}=?", (old,))

    def test_reply_requires_original_or_reference(self):
        self.seed_service_claims()
        with self.assertRaises(ValidationError):
            ingest_reply(self.db, self.reply(), "missing", "missing")
        self.assertEqual(self.db.query("SELECT count(*) AS n FROM replies")[0]["n"], 0)

    def test_raw_reply_replay_and_scoped_export_are_retrievable(self):
        self.seed_service_claims()
        payload = self.reply(raw_text="Synthetic original: please quote for four guests.")
        result = ingest_reply(self.db, payload, "original", "original")
        replay = ingest_reply(self.db, payload, "original", "repeat")
        self.assertEqual(result["reply_id"], replay["reply_id"])
        path = self.root / "snapshot.json"
        export_json(self.db, path, self.run)
        tables = json.loads(path.read_text(encoding="utf-8"))["tables"]
        raw = tables["raw_imports"][0]
        self.assertEqual(json.loads(raw["payload_json"])["raw_text"], payload["raw_text"])
        self.assertEqual(tables["replies"][0]["source_reference"], "raw_import:" + raw["raw_import_id"])

    def test_quote_reply_updates_excel_action(self):
        from openpyxl import load_workbook

        self.seed_service_claims()
        ingest_reply(
            self.db,
            self.reply(
                source_reference="synthetic-reference",
                confirmed_needs="four guests",
                unknown_needs="dates",
                next_action="Human quote after confirming dates",
            ),
            "quote",
            "quote",
        )
        path = self.root / "result.xlsx"
        export_workbook(self.db, path, self.run)
        book = load_workbook(path)
        text = book.active["G2"].value
        book.close()
        for expected in ("request_quote", "four guests", "dates", "Human quote", "人工接管"):
            self.assertIn(expected, text)

    def test_wrong_role_stops_contact_only(self):
        self.seed_service_claims()
        for category in ("wrong_person", "not_fit"):
            ingest_reply(
                self.db,
                self.reply(message_id=category, reply_category=category, source_reference="synthetic-reference"),
                category,
                category,
            )
        rules = self.db.query("SELECT * FROM stop_rules")
        self.assertTrue(rules)
        self.assertEqual({r["scope_type"] for r in rules}, {"contact"})
        with self.assertRaises(StateError):
            create_draft(self.db, self.draft_payload(), "blocked")
        self.assertNotEqual(self.db.query("SELECT fit_status FROM companies")[0]["fit_status"], "do_not_contact")

    def test_new_fit_uat_does_not_require_legacy_fields(self):
        bundle = copy.deepcopy(service_bundle())
        bundle["companies"][0]["contact"]["public_email"] = "team@fixture.example.org"
        run = create_run(
            self.db,
            markets=["AU"],
            segments=["*"],
            target=1,
            product_version="test-v1",
            request_id="new",
            idempotency_key="new",
        )["run_id"]
        ingest_source_bundle(self.db, run, bundle, "sources")
        approve_run_claims(self.db, run, "test", "fixture", "accept")
        self.assertIsNotNone(self.db.query("SELECT last_verified_at FROM contacts")[0]["last_verified_at"])
        result = verify_research_uat(self.db, run)
        self.assertFalse(any("公司正式字段" in f for f in result["failures"]), result)
