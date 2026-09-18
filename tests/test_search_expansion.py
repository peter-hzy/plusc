"""Isolated qualification and safety counterexamples, not real leads."""

import copy
import unittest

import test_cli_workflow as fixtures
from test_integrated_workflow import fixture_bundle

from inbound_ai_acquisition.application.research import (
    approve_run_claims,
    ingest_source_bundle,
    research_status,
    verify_company_list,
)
from inbound_ai_acquisition.application.services import create_run
from inbound_ai_acquisition.domain.policies import normalize_reply
from inbound_ai_acquisition.errors import ValidationError
from inbound_ai_acquisition.exporters.workbook import export_workbook
from inbound_ai_acquisition.storage.database import utc_now


class ExpansionTests(unittest.TestCase):
    setUp = fixtures.CliWorkflowTests.setUp
    tearDown = fixtures.CliWorkflowTests.tearDown

    def one_run(self, bundle=None):
        run = create_run(
            self.db, markets=["AU"], segments=["travel_agency"], target=1, request_id="one", idempotency_key="one"
        )["run_id"]
        ingest_source_bundle(self.db, run, bundle or fixture_bundle(), "source")
        return run

    def verify(self, run):
        path = self.root / "result.xlsx"
        export_workbook(self.db, path, run)
        return verify_company_list(self.db, run, path)

    def test_reply_alias_and_strict_boolean(self):
        self.assertEqual(normalize_reply({"reply_category": "request_information"})["reply_category"], "request_info")
        self.assertFalse(normalize_reply({"reply_category": "automatic_reply"})["do_not_contact"])
        self.assertTrue(normalize_reply({"reply_category": "declined", "do_not_contact": False})["do_not_contact"])
        for value in ("false", "true", 0, None):
            with self.assertRaises(ValidationError):
                normalize_reply({"reply_category": "other", "do_not_contact": value})
        with self.assertRaises(ValidationError):
            normalize_reply({"reply_category": "invented"})

    def test_expansion_without_china_signal_is_persisted(self):
        bundle = fixture_bundle()
        bundle["companies"][0].update(
            qualification_path="expansion",
            china_product_signal="none",
            audience_fit="Fixture cultural groups",
            cooperation_hypothesis="Unconfirmed regional extension",
            counter_evidence="Supplier openness unknown",
            next_action="Review fit",
        )
        run = self.one_run(bundle)
        result = self.verify(run)
        self.assertTrue(result["passed"], result)
        self.assertEqual(
            research_status(self.db, run)["review"][0]["company_preview"]["qualification_path"], "expansion"
        )

    def test_direct_without_china_rejected_and_missing_expansion_rationale_rejected(self):
        for path in ("direct", "expansion", "channel"):
            bundle = fixture_bundle()
            bundle["companies"][0].update(qualification_path=path, china_product_signal="none")
            with self.assertRaises(ValidationError):
                ingest_source_bundle(self.db, self.run, bundle, path)

    def test_channel_not_disguised_as_outbound_buyer(self):
        bundle = fixture_bundle()
        bundle["companies"][0].update(
            qualification_path="channel",
            source_market_role="channel_partner",
            china_product_signal="none",
            audience_fit="Fixture audience",
            cooperation_hypothesis="Referral hypothesis",
            counter_evidence="Not an operator",
            next_action="Confirm partnership",
        )
        run = self.one_run(bundle)
        self.assertTrue(self.verify(run)["passed"])
        bundle["companies"][0]["fit_status"] = "priority_chat"
        with self.assertRaises(ValidationError):
            ingest_source_bundle(self.db, run, bundle, "priority")

    def test_unsuitable_contact_page_not_accepted(self):
        bundle = fixture_bundle()
        bundle["companies"][0]["contact"].update(route_purpose="unsuitable")
        run = self.one_run(bundle)
        self.assertFalse(self.verify(run)["passed"])
        approve_run_claims(self.db, run, "ISOLATED_TEST", "fixture only", "approve")
        self.assertFalse(self.verify(run)["passed"])

    def test_observation_a_b_a_returns_to_latest_a(self):
        bundle = fixture_bundle()
        run = self.one_run(bundle)
        bundle["companies"][0]["fit_reason"] = "B fixture"
        ingest_source_bundle(self.db, run, bundle, "B")
        ingest_source_bundle(self.db, run, fixture_bundle(), "A")
        self.assertEqual(
            research_status(self.db, run)["review"][0]["company_preview"]["fit_reason"], "Fixture China tours"
        )

    def test_pending_stopped_contact_matches_new_batch(self):
        bundle = fixture_bundle()
        bundle["companies"][0]["contact"]["public_email"] = "team@fixture.example.org"
        old_run = self.one_run(bundle)
        contact = research_status(self.db, old_run)["review"][0]["contacts"][0]
        with self.db.transaction() as c:
            c.execute(
                "INSERT INTO stop_rules VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "stop_pending",
                    "contact",
                    contact["contact_id"],
                    "fixture",
                    "active",
                    "TEST",
                    utc_now(),
                    None,
                    None,
                    "",
                ),
            )
        ingest_source_bundle(self.db, self.run, bundle, "new")
        self.assertTrue(any("停止联系" in f for f in self.verify(self.run)["failures"]))

    def test_general_route_does_not_count_as_confirmed_business(self):
        result = self.verify(self.one_run())
        self.assertEqual(result["public_route_count"], 1)
        self.assertEqual(result["business_route_count"], 0)
        self.assertEqual(result["handoff_route_count"], 1)

    def test_department_route_and_invalid_person_grade(self):
        bundle = fixture_bundle()
        bundle["companies"][0]["contact"].update(route_grade="R2", route_purpose="business")
        self.assertEqual(self.verify(self.one_run(bundle))["business_route_count"], 1)
        bundle["companies"][0]["contact"]["route_grade"] = "R1"
        with self.assertRaises(ValidationError):
            ingest_source_bundle(self.db, self.run, bundle, "person")

    def test_pending_domain_stop_blocks_delivery(self):
        run = self.one_run()
        with self.db.transaction() as c:
            c.execute(
                "INSERT INTO stop_rules VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "stop_fixture",
                    "domain",
                    "fixture.example.org",
                    "fixture",
                    "active",
                    "TEST",
                    utc_now(),
                    None,
                    None,
                    "",
                ),
            )
        result = self.verify(run)
        self.assertFalse(result["passed"])
        self.assertTrue(any("停止联系" in f for f in result["failures"]))

    def test_blocking_company_gap_fails_delivery(self):
        run = self.one_run()
        company = research_status(self.db, run)["review"][0]["company"]
        with self.db.transaction() as c:
            c.execute(
                "INSERT INTO research_gaps VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "gap_fixture",
                    "company",
                    company["company_id"],
                    "identity",
                    "Identity conflict",
                    1,
                    "open",
                    utc_now(),
                    None,
                ),
            )
        self.assertFalse(self.verify(run)["passed"])

    def test_field_source_unknown_url_rolls_back(self):
        bundle = fixture_bundle()
        bundle["companies"][0]["field_sources"] = {"website": ["https://unread.example.org"]}
        with self.assertRaises(ValidationError):
            ingest_source_bundle(self.db, self.run, bundle, "bad")
        self.assertFalse(self.db.query("SELECT * FROM companies"))

    def test_two_brands_need_independence_evidence(self):
        bundle = fixture_bundle()
        bundle["companies"][0]["group_key"] = "fixture-group"
        second = copy.deepcopy(bundle["companies"][0])
        second.update(name="Fixture Brand Two", website="https://second.example.org")
        bundle["companies"].append(second)
        bundle["discovered_candidates"].append(
            {**bundle["discovered_candidates"][0], "name": second["name"], "website": second["website"]}
        )
        bundle["discovered_count"] = 2
        run = create_run(
            self.db, markets=["AU"], segments=["travel_agency"], target=2, request_id="two", idempotency_key="two"
        )["run_id"]
        ingest_source_bundle(self.db, run, bundle, "source")
        self.assertTrue(any("集团" in f for f in self.verify(run)["failures"]))


if __name__ == "__main__":
    unittest.main()
