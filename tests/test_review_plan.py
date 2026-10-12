"""Tests for the read-only incremental review task package."""

import json
import tempfile
import unittest
from pathlib import Path

from inbound_ai_acquisition.application.review_plan import build_review_plan, write_review_plan
from inbound_ai_acquisition.application.services import create_run, import_companies, import_contacts, run_status
from inbound_ai_acquisition.config import Workspace
from inbound_ai_acquisition.errors import ValidationError
from inbound_ai_acquisition.storage.database import Database, utc_now


class ReviewPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = Workspace(self.root / "workspace")
        self.workspace.ensure_layout()
        self.db = Database(self.workspace.database)
        self.db.migrate()
        self.run_id = create_run(
            self.db,
            markets=["AU"],
            segments=["*"],
            target=20,
            request_id="req-run",
            idempotency_key="idem-run",
        )["run_id"]
        company_file = self.root / "companies.json"
        company_file.write_text(
            json.dumps(
                [
                    {
                        "company_id": "co_review",
                        "name": "Review Travel",
                        "country": "AU",
                        "website": "https://review.example",
                        "fit_status": "research_needed",
                    }
                ]
            ),
            encoding="utf-8",
        )
        import_companies(self.db, self.run_id, company_file, "req-company")
        contact_file = self.root / "contacts.json"
        contact_file.write_text(
            json.dumps(
                [
                    {
                        "contact_id": "ct_review",
                        "company_id": "co_review",
                        "role_scope": "Partnerships team\n入口等级：R2",
                        "contact_role": "handoff",
                        "identity_status": "unverified",
                    }
                ]
            ),
            encoding="utf-8",
        )
        import_contacts(self.db, contact_file, "req-contact")
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO research_gaps VALUES (?,?,?,?,?,?,?,?,?)",
                ("gap_review", "company", "co_review", "original_evidence", "必须重新核验", 1, "open", utc_now(), None),
            )
            connection.execute(
                "INSERT INTO research_gaps VALUES (?,?,?,?,?,?,?,?,?)",
                ("gap_contact", "contact", "ct_review", "responsible_contact", "职责待核验", 1, "open", utc_now(), None),
            )
            connection.execute(
                "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "cl_route",
                    "contact",
                    "ct_review",
                    "route_grade",
                    "R2",
                    "proposed",
                    "unknown",
                    "",
                    None,
                    None,
                    "",
                    None,
                    utc_now(),
                ),
            )
            connection.execute(
                "INSERT INTO drafts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "dr_review",
                    self.run_id,
                    "co_review",
                    "ct_review",
                    "email",
                    "Draft subject",
                    "Draft body?",
                    "[]",
                    "",
                    "hash",
                    "draft",
                    utc_now(),
                    utc_now(),
                    None,
                ),
            )
            connection.execute(
                "INSERT INTO source_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "src_review",
                    self.run_id,
                    "public_web",
                    "Review Travel homepage",
                    "fingerprint",
                    utc_now(),
                    utc_now(),
                    1,
                    "failed_retryable",
                    0,
                    0,
                    10,
                    "timeout",
                    1,
                ),
            )

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_is_conservative_and_read_only(self):
        before = self.db.query("SELECT COUNT(*) AS n FROM events")[0]["n"]
        plan = build_review_plan(self.db, self.run_id)
        after = self.db.query("SELECT COUNT(*) AS n FROM events")[0]["n"]
        self.assertEqual(before, after)
        self.assertEqual(plan["status"], "needs_review")
        self.assertEqual(plan["summary"]["companies_without_evidence"], 1)
        self.assertEqual(plan["summary"]["route_grades"], {"R0": 0, "R1": 0, "R2": 1, "R3": 0})
        self.assertEqual(plan["contacts"][0]["route_origin"], "claim:proposed")
        self.assertEqual(plan["drafts"][0]["review_gate"], "blocked")
        self.assertEqual(plan["summary"]["failed_or_restricted_sources"], 1)

    def test_run_status_counts_company_and_contact_claims_and_gaps(self):
        status = run_status(self.db, self.run_id)
        self.assertEqual(status["counts"]["claims"], 1)
        self.assertEqual(status["counts"]["research_gaps"], 2)

    def test_markdown_contains_all_review_surfaces(self):
        output = self.root / "review-plan.md"
        result = write_review_plan(self.db, self.run_id, output)
        text = output.read_text(encoding="utf-8")
        self.assertEqual(result["output"], str(output.resolve()))
        self.assertIn("公司增量复核表", text)
        self.assertIn("Evidence / Claim 恢复缺口", text)
        self.assertIn("联系入口复核", text)
        self.assertIn("重复公司与集团关系", text)
        self.assertIn("英文开发信事实审校队列", text)
        self.assertIn("人工审核闸门", text)
        self.assertIn("claim:proposed", text)

    def test_missing_run_and_non_markdown_output_are_rejected(self):
        with self.assertRaisesRegex(ValidationError, "找不到 run"):
            build_review_plan(self.db, "run_missing")
        with self.assertRaisesRegex(ValidationError, "Markdown"):
            write_review_plan(self.db, self.run_id, self.root / "review.json")


if __name__ == "__main__":
    unittest.main()
