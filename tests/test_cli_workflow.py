import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from inbound_ai_acquisition.application.legacy_import import import_legacy_bundle
from inbound_ai_acquisition.application.services import (
    approve_draft,
    create_draft,
    create_run,
    import_companies,
    import_contacts,
    import_evidence,
    ingest_reply,
    record_source_result,
    set_draft_status,
)
from inbound_ai_acquisition.audit.public_repo import audit_public_repo
from inbound_ai_acquisition.cli import _context_validate, _init_workspace, _skill_install, _skill_status
from inbound_ai_acquisition.config import Workspace
from inbound_ai_acquisition.errors import StateError, ValidationError
from inbound_ai_acquisition.exporters.workbook import SHEETS, export_workbook
from inbound_ai_acquisition.storage.database import Database, utc_now


class CliWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = Workspace(self.root / "workspace")
        self.workspace.ensure_layout()
        self.db = Database(self.workspace.database)
        self.db.migrate()
        self.run = create_run(
            self.db,
            markets=["AU", "NZ"],
            segments=["travel_agency", "dmc"],
            target=20,
            request_id="req-run",
            idempotency_key="idem-run",
        )["run_id"]

    def tearDown(self):
        self.temp.cleanup()

    def write_json(self, name, payload):
        path = self.root / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def seed_company_contact_claim(self):
        company_file = self.write_json(
            "companies.json",
            [
                {
                    "company_id": "co_demo",
                    "name": "Example Travel",
                    "country": "AU",
                    "segment": "travel_agency",
                    "website": "https://example.test",
                    "fit_reason": "Offers tailored Asia trips",
                }
            ],
        )
        import_companies(self.db, self.run, company_file, "req-company")
        contact_file = self.write_json(
            "contacts.json",
            [
                {
                    "contact_id": "ct_demo",
                    "company_id": "co_demo",
                    "full_name": "Alex Example",
                    "title": "Product Manager",
                    "linkedin_url": "https://linkedin.com/in/alex-example",
                    "identity_status": "supported",
                    "identity_evidence_url": "https://example.test/team",
                    "identity_evidence_text": "The team page lists Alex as Product Manager.",
                    "observed_at": "2026-09-04T00:00:00+00:00",
                }
            ],
        )
        import_contacts(self.db, contact_file, "req-contact")
        evidence_file = self.write_json(
            "evidence.json",
            [
                {
                    "evidence_id": "ev_demo",
                    "entity_type": "company",
                    "entity_id": "co_demo",
                    "source_url": "https://example.test/china",
                    "observed_text": "The company publicly lists tailored trips to China.",
                    "source_level": "primary",
                }
            ],
        )
        import_evidence(self.db, evidence_file, "req-evidence")
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "cl_demo",
                    "company",
                    "co_demo",
                    "fit_reason",
                    "Offers tailored China trips",
                    "accepted",
                    "strong",
                    "",
                    "human",
                    utc_now(),
                    "官网证据",
                    None,
                    utc_now(),
                ),
            )
            connection.execute("INSERT INTO claim_evidence VALUES (?,?)", ("cl_demo", "ev_demo"))

    def test_run_create_is_idempotent(self):
        second = create_run(
            self.db,
            markets=["AU", "NZ"],
            segments=["travel_agency", "dmc"],
            target=20,
            request_id="req-run-retry",
            idempotency_key="idem-run",
        )
        self.assertEqual(second["status"], "already_applied")
        self.assertEqual(second["run_id"], self.run)

    def test_unknown_import_field_rolls_back_entire_file(self):
        source = self.write_json(
            "bad.json",
            [
                {"name": "Good Before Bad", "website": "https://good.test"},
                {"name": "Bad", "website": "https://bad.test", "invented": "must fail"},
            ],
        )
        with self.assertRaises(ValidationError):
            import_companies(self.db, self.run, source, "req-bad")
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM companies")[0]["n"], 0)

    def test_verified_contact_without_identity_evidence_is_rejected(self):
        source = self.write_json(
            "company.json", [{"company_id": "co_one", "name": "One", "website": "https://one.test"}]
        )
        import_companies(self.db, self.run, source, "req-company")
        contacts = self.write_json(
            "bad-contact.json",
            [
                {
                    "company_id": "co_one",
                    "full_name": "Unproven Person",
                    "identity_status": "verified",
                }
            ],
        )
        with self.assertRaises(ValidationError):
            import_contacts(self.db, contacts, "req-bad-contact")
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM contacts")[0]["n"], 0)

    def test_approved_draft_can_be_marked_sent_but_never_sends(self):
        self.seed_company_contact_claim()
        result = create_draft(
            self.db,
            {
                "run_id": self.run,
                "contact_id": "ct_demo",
                "channel": "email",
                "subject": "China ground support",
                "body": "Hi Alex, I noticed your tailored China trips. Would a sample ground-service outline be useful?",
                "evidence_ids": ["ev_demo"],
            },
            "req-draft",
        )
        draft_id = result["draft_id"]
        approve_draft(self.db, draft_id, "human", "内容已核验", "req-approve")
        sent = set_draft_status(self.db, draft_id, "sent", "req-sent")
        self.assertEqual(sent["status"], "succeeded")
        row = self.db.query("SELECT status,sent_at FROM drafts WHERE draft_id=?", (draft_id,))[0]
        self.assertEqual(row["status"], "sent")
        self.assertIsNotNone(row["sent_at"])

    def test_unsubscribe_is_atomic_and_idempotent(self):
        self.seed_company_contact_claim()
        draft_id = create_draft(
            self.db,
            {
                "run_id": self.run,
                "contact_id": "ct_demo",
                "channel": "linkedin",
                "body": "Hi Alex, I saw your China itineraries. Open to a quick ground-service outline?",
                "evidence_ids": ["ev_demo"],
            },
            "req-draft",
        )["draft_id"]
        payload = {
            "message_id": "msg-1",
            "contact_id": "ct_demo",
            "channel": "email",
            "received_at": "2026-09-04T00:00:00+00:00",
            "reply_category": "unsubscribe",
        }
        first = ingest_reply(self.db, payload, "reply-key", "req-reply")
        second = ingest_reply(self.db, payload, "reply-key", "req-reply-retry")
        self.assertGreaterEqual(first["changed_records"], 3)
        self.assertEqual(second["status"], "already_applied")
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM replies")[0]["n"], 1)
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM stop_rules WHERE status='active'")[0]["n"], 1)
        self.assertEqual(
            self.db.query("SELECT status FROM drafts WHERE draft_id=?", (draft_id,))[0]["status"], "stopped"
        )

    def test_workbook_round_trip_has_all_review_sheets(self):
        output = self.root / "batch.xlsx"
        result = export_workbook(self.db, output, self.run)
        self.assertEqual(result["sheets"], len(SHEETS))
        self.assertTrue(output.exists())

    def test_legacy_bundle_is_preserved_and_mapped(self):
        other_root = self.root / "legacy-workspace"
        Workspace(other_root).ensure_layout()
        other_db = Database(other_root / "acquisition.db")
        other_db.migrate()
        fixture = Path(__file__).resolve().parents[1] / "examples" / "fictional-workbook.json"
        first = import_legacy_bundle(other_db, fixture, "req-legacy")
        second = import_legacy_bundle(other_db, fixture, "req-legacy-retry")
        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(second["status"], "already_applied")
        self.assertEqual(other_db.query("SELECT COUNT(*) AS n FROM raw_imports")[0]["n"], 1)
        self.assertEqual(other_db.query("SELECT COUNT(*) AS n FROM companies")[0]["n"], 5)
        self.assertEqual(other_db.query("SELECT COUNT(*) AS n FROM contacts")[0]["n"], 5)
        self.assertEqual(other_db.query("SELECT COUNT(*) AS n FROM evidence")[0]["n"], 10)

    def test_database_integrity_and_event_sequences(self):
        self.assertEqual(self.db.query("PRAGMA integrity_check")[0]["integrity_check"], "ok")
        events = self.db.query("SELECT sequence FROM events WHERE run_id=? ORDER BY sequence", (self.run,))
        self.assertEqual([row["sequence"] for row in events], list(range(1, len(events) + 1)))

    def test_source_restricted_is_not_no_results(self):
        payload = {
            "run_id": self.run,
            "adapter_id": "public_web",
            "query_summary": "site restricted during public research",
            "outcome": "restricted",
            "error_code": "http_403",
            "retryable": False,
            "observations": [],
        }
        result = record_source_result(self.db, payload, "source-key", "req-source")
        self.assertEqual(result["status"], "succeeded")
        row = self.db.query("SELECT outcome,error_code,result_count FROM source_runs")[0]
        self.assertEqual(row, {"outcome": "restricted", "error_code": "http_403", "result_count": 0})

    def test_conflicting_claim_cannot_be_accepted(self):
        self.seed_company_contact_claim()
        with self.db.transaction() as connection:
            connection.execute("UPDATE evidence SET conflicts=1 WHERE evidence_id='ev_demo'")
            connection.execute(
                "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "cl_conflict",
                    "company",
                    "co_demo",
                    "fit_reason",
                    "Conflicted",
                    "proposed",
                    "strong",
                    "source conflict",
                    None,
                    None,
                    "",
                    None,
                    utc_now(),
                ),
            )
            connection.execute("INSERT INTO claim_evidence VALUES (?,?)", ("cl_conflict", "ev_demo"))
        from inbound_ai_acquisition.application.services import decide_claim

        with self.assertRaises(StateError):
            decide_claim(self.db, "cl_conflict", "accepted", "human", "try", "req-conflict")

    def test_public_repo_audit_ignores_fixture_domains_but_finds_database(self):
        project = self.root / "repo"
        project.mkdir()
        (project / "README.md").write_text("contact demo@example.test", encoding="utf-8")
        (project / ".env.example").write_text("SEARCH_API_KEY=\nOTHER_SECRET=\n", encoding="utf-8")
        self.assertEqual(audit_public_repo(project)["status"], "succeeded")
        (project / "acquisition.db").write_bytes(b"private")
        self.assertEqual(audit_public_repo(project)["status"], "failed")

    def test_release_lock_excludes_build_caches(self):
        from inbound_ai_acquisition.audit.release import _portable_hash, build_lock

        project = self.root / "release-repo"
        (project / "src").mkdir(parents=True)
        (project / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
        for relative in ("build/copied.py", ".ruff_cache/cache", "src/demo.egg-info/PKG-INFO"):
            path = project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("generated", encoding="utf-8")
        lock_path = project / "skills.lock.json"
        payload = build_lock(project, lock_path)
        self.assertEqual([row["path"] for row in payload["files"]], ["src/main.py"])
        lf = project / "lf.txt"
        crlf = project / "crlf.txt"
        lf.write_bytes(b"one\ntwo\n")
        crlf.write_bytes(b"one\r\ntwo\r\n")
        self.assertEqual(_portable_hash(lf), _portable_hash(crlf))

    def test_skill_install_and_status_use_manifest_diff(self):
        base = self.root / "skills"
        self.assertEqual(_skill_status(str(base))["status"], "not_installed")
        installed = _skill_install(str(base), replace=True)
        self.assertTrue(installed["in_sync"])
        target_skill = base / "inbound-ai-acquisition" / "SKILL.md"
        target_skill.write_text(target_skill.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
        self.assertFalse(_skill_status(str(base))["in_sync"])

    def test_context_validation_rejects_unfilled_profiles(self):
        root = self.root / "context-workspace"
        _init_workspace(root)
        workspace = Workspace(root)
        db = Database(workspace.database)
        unfilled = _context_validate(workspace, db)
        self.assertEqual(unfilled["status"], "needs_review")
        self.assertIn("product-profile.md", unfilled["profile_gaps"])
        self.assertIn("voice-profile.md", unfilled["profile_gaps"])

        (root / "product-profile.md").write_text(
            "# 产品资料卡\n\n版本：1.0\n- 可接待目的地：北京、上海、西安\n"
            "- 可提供服务：线路设计、交通、导游\n- 语言：中文、英文\n",
            encoding="utf-8",
        )
        (root / "voice-profile.md").write_text(
            "# 话术资料卡\n\n版本：1.0\n- 希望像谁在说话：熟悉中国地接的合作伙伴\n",
            encoding="utf-8",
        )
        self.assertEqual(_context_validate(workspace, db)["status"], "succeeded")

    def test_cli_emits_utf8_when_environment_requests_ascii(self):
        root = self.root / "unicode-workspace"
        _init_workspace(root)
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "ascii"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "inbound_ai_acquisition.cli",
                "run",
                "create",
                "--workspace",
                str(root),
                "--market",
                "AU",
                "--segments",
                "travel_agency",
                "--idempotency-key",
                "unicode-output",
            ],
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        self.assertIn("导入或研究候选公司", result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
