"""Isolated fixtures, not customer research or business approvals."""

import copy
import unittest

import test_cli_workflow as fixtures

from inbound_ai_acquisition.application.research import (
    approve_run_claims,
    ingest_source_bundle,
    research_status,
    verify_research_uat,
)
from inbound_ai_acquisition.application.services import create_run
from inbound_ai_acquisition.cli import _init_workspace, build_parser, dispatch
from inbound_ai_acquisition.exporters.workbook import export_workbook
from inbound_ai_acquisition.storage.database import utc_now
from inbound_ai_acquisition.storage.repositories import active_stop_exists, blocking_gap_count


def fixture_bundle():
    source = {
        "source_url": "https://fixture.example.org/china",
        "observed_text": "Isolated fixture: outbound China products and external partners.",
        "source_level": "primary",
        "purpose": "company_fit",
    }
    return {
        "executor": "codex_bridge",
        "discovered_count": 1,
        "discovered_candidates": [
            {
                "name": "Fixture Travel",
                "website": "https://fixture.example.org",
                "source_url": source["source_url"],
                "observed_text": source["observed_text"],
            }
        ],
        "companies": [
            {
                "name": "Fixture Travel",
                "website": "https://fixture.example.org",
                "country": "AU",
                "segment": "travel_agency",
                "fit_reason": "Fixture China tours",
                "fit_status": "chat_candidate",
                "source_market_role": "outbound_seller",
                "china_product_signal": "direct",
                "ground_partner_route": "unclear",
                "competitive_position": "unknown",
                "sources": [source],
                "contact": {
                    "contact_role": "handoff",
                    "why_contact": "Public company contact page",
                    "identity_status": "supported",
                    "sources": [
                        {
                            **source,
                            "source_url": "https://fixture.example.org/contact",
                            "observed_text": "Isolated fixture: general company contact form.",
                            "purpose": "contact_route",
                        }
                    ],
                },
            }
        ],
    }


class IntegratedWorkflowTests(unittest.TestCase):
    setUp = fixtures.CliWorkflowTests.setUp
    tearDown = fixtures.CliWorkflowTests.tearDown

    def test_replay_then_incremental_updates_preserve_accepted_fields(self):
        bundle = fixture_bundle()
        ingest_source_bundle(self.db, self.run, bundle, "first")
        before = research_status(self.db, self.run)
        ingest_source_bundle(self.db, self.run, bundle, "repeat")
        after = research_status(self.db, self.run)
        for key in ("companies", "contacts", "claims", "evidence"):
            self.assertEqual(before["stats"][key], after["stats"][key])
        approve_run_claims(self.db, self.run, "ISOLATED_TEST", "fixture only", "approve")
        bundle["companies"][0]["fit_reason"] = "New fixture observation"
        bundle["companies"][0]["sources"].append(
            {
                **bundle["companies"][0]["sources"][0],
                "source_url": "https://fixture.example.org/groups",
                "observed_text": "Isolated fixture: additional group product.",
            }
        )
        bundle["companies"][0]["contact"]["why_contact"] = "Updated handoff description"
        ingest_source_bundle(self.db, self.run, bundle, "update")
        current = research_status(self.db, self.run)
        self.assertEqual(current["stats"]["companies"], 1)
        self.assertEqual(current["stats"]["contacts"], 1)
        self.assertGreater(current["stats"]["evidence"], before["stats"]["evidence"])
        self.assertEqual(current["review"][0]["company"]["fit_reason"], "Fixture China tours")
        self.assertEqual(current["review"][0]["company_preview"]["fit_reason"], "New fixture observation")
        self.assertEqual(current["review"][0]["contact_previews"][0]["role_scope"], "Updated handoff description")
        self.assertEqual(current["stage"], "awaiting_claim_review")

    def test_contact_gap_is_visible_and_blocks_draft_preconditions(self):
        ingest_source_bundle(self.db, self.run, fixture_bundle(), "first")
        ct = self.db.query("SELECT * FROM contacts")[0]
        with self.db.transaction() as c:
            c.execute(
                "INSERT INTO research_gaps VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "gap_fixture",
                    "contact",
                    ct["contact_id"],
                    "role_scope",
                    "职责冲突待核实",
                    1,
                    "open",
                    utc_now(),
                    None,
                ),
            )
            self.assertEqual(blocking_gap_count(c, ct["company_id"]), 1)
        self.assertEqual(research_status(self.db, self.run)["stats"]["research_gaps"], 1)

    def test_cross_batch_email_and_stop_survive(self):
        bundle = fixture_bundle()
        bundle["companies"][0]["contact"]["public_email"] = "partners@fixture.example.org"
        ids = []
        for index in range(2):
            run = (
                self.run
                if index == 0
                else create_run(
                    self.db,
                    markets=["AU"],
                    segments=["travel_agency"],
                    target=20,
                    request_id="second",
                    idempotency_key="second",
                )["run_id"]
            )
            ingest_source_bundle(self.db, run, bundle, f"source{index}")
            approve_run_claims(self.db, run, "ISOLATED_TEST", "fixture only", f"approve{index}")
            ids.append(
                self.db.query(
                    "SELECT ct.* FROM contacts ct JOIN companies co USING(company_id) WHERE co.run_id=?", (run,)
                )[0]
            )
        with self.db.transaction() as c:
            c.execute(
                "INSERT INTO stop_rules VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "stop_fixture",
                    "contact",
                    ids[0]["contact_id"],
                    "fixture",
                    "active",
                    "ISOLATED_TEST",
                    utc_now(),
                    None,
                    None,
                    "",
                ),
            )
            self.assertTrue(active_stop_exists(c, ids[1]["contact_id"], ids[1]["company_id"]))

    def test_company_list_allows_contact_page_without_person_or_email(self):
        run = create_run(
            self.db, markets=["AU"], segments=["travel_agency"], target=1, request_id="one", idempotency_key="one"
        )["run_id"]
        ingest_source_bundle(self.db, run, fixture_bundle(), "source")
        output = self.root / "fixture.xlsx"
        export_workbook(self.db, output, run)
        result = verify_research_uat(self.db, run, output, scope="companies")
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["public_route_count"], 1)
        self.assertEqual(result["product_match_status"], "product_not_provided")
        self.assertFalse(result["outreach_ready"])
        self.assertFalse(verify_research_uat(self.db, run, output)["passed"])

    def test_twenty_target_not_reduced_for_small_fixture(self):
        ingest_source_bundle(self.db, self.run, fixture_bundle(), "source")
        output = self.root / "fixture.xlsx"
        export_workbook(self.db, output, self.run)
        result = verify_research_uat(self.db, self.run, output, scope="companies")
        self.assertEqual(result["target_count"], 20)
        self.assertFalse(result["passed"])

    def test_missing_route_preserves_company_but_fails_delivery(self):
        run = create_run(
            self.db,
            markets=["AU"],
            segments=["travel_agency"],
            target=1,
            request_id="route",
            idempotency_key="route",
        )["run_id"]
        ingest_source_bundle(self.db, run, fixture_bundle(), "source")
        with self.db.transaction() as c:
            c.execute("UPDATE evidence SET access_status='restricted' WHERE purpose='contact_route'")
        output = self.root / "route.xlsx"
        export_workbook(self.db, output, run)
        result = verify_research_uat(self.db, run, output, scope="companies")
        self.assertEqual(result["company_count"], 1)
        self.assertEqual(result["public_route_count"], 0)
        self.assertFalse(result["passed"])

    def test_v4_global_contact_indexes_upgrade_with_backup(self):
        with self.db.transaction() as c:
            c.execute("DROP INDEX uq_contact_company_email")
            c.execute("DROP INDEX uq_contact_company_linkedin")
            c.execute("CREATE UNIQUE INDEX uq_contact_email ON contacts(public_email) WHERE public_email<>''")
            c.execute("CREATE UNIQUE INDEX uq_contact_linkedin ON contacts(linkedin_url) WHERE linkedin_url<>''")
            c.execute("UPDATE workspace_meta SET schema_version=4")
        result = self.db.migrate()
        from pathlib import Path

        self.assertTrue(Path(result["backup"]).is_file())
        self.assertEqual(self.db.schema_version(), 5)
        indexes = {r["name"] for r in self.db.query("PRAGMA index_list(contacts)")}
        self.assertIn("uq_contact_company_email", indexes)
        self.assertNotIn("uq_contact_email", indexes)
        self.assertEqual(len(self.db.query("SELECT * FROM runs")), 1)

    def test_company_run_with_product_does_not_require_voice(self):
        from pathlib import Path

        from inbound_ai_acquisition.storage.database import Database

        path = self.root / "product_only"
        _init_workspace(path)
        Path(path / "product-profile.md").write_text(
            "版本：fixture-v1\n- 可接待目的地：中国\n- 可提供服务：测试服务\n- 语言：英语\n",
            encoding="utf-8",
        )
        args = build_parser().parse_args(
            [
                "run",
                "create",
                "--workspace",
                str(path),
                "--market",
                "AU",
                "--segments",
                "travel_agency",
            ]
        )
        result = dispatch(args)
        run = Database(path / "acquisition.db").query("SELECT * FROM runs WHERE run_id=?", (result["run_id"],))[0]
        self.assertEqual(run["product_version"], "fixture-v1")

    def test_changed_person_creates_distinct_contact_not_overwrite(self):
        bundle = fixture_bundle()
        ingest_source_bundle(self.db, self.run, bundle, "source")
        incoming = copy.deepcopy(bundle)
        incoming["companies"][0]["contact"].update(full_name="Fixture Person", title="Product", contact_role="primary")
        ingest_source_bundle(self.db, self.run, incoming, "person")
        self.assertEqual(len(self.db.query("SELECT * FROM contacts")), 2)

    def test_research_only_cli_without_product_does_not_fabricate_version(self):
        path = self.root / "empty"
        _init_workspace(path)
        args = build_parser().parse_args(
            [
                "run",
                "create",
                "--workspace",
                str(path),
                "--research-only",
                "--market",
                "AU,NZ",
                "--segments",
                "travel_agency",
            ]
        )
        result = dispatch(args)
        from inbound_ai_acquisition.storage.database import Database

        run = Database(path / "acquisition.db").query("SELECT * FROM runs WHERE run_id=?", (result["run_id"],))[0]
        self.assertEqual(run["target_count"], 20)
        self.assertEqual(run["product_version"], "")


if __name__ == "__main__":
    unittest.main()
