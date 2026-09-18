"""Publishing checks must not silently skip tracked private artifacts."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inbound_ai_acquisition.audit.public_repo import audit_public_repo
from inbound_ai_acquisition.audit.release import audit_release, build_lock
from inbound_ai_acquisition.cli import _doctor


class ReleaseSafetyTests(unittest.TestCase):
    def test_doctor_checks_actual_provider_keys_without_revealing_them(self):
        with patch.dict("os.environ", {"HUNTER_API_KEY": "isolated-fixture", "BRAVE_SEARCH_API_KEY": "test"}, clear=True):
            result = _doctor(None)
        self.assertEqual(result["optional_api_keys"]["HUNTER_API_KEY"], "configured")
        self.assertEqual(result["optional_api_keys"]["BRAVE_SEARCH_API_KEY"], "configured")
        self.assertNotIn("isolated-fixture", str(result))

    def test_tracked_private_directory_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
            (root / "outputs").mkdir()
            (root / "outputs" / "customer.json").write_text('{"fixture": true}', encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "outputs/customer.json"], check=True)
            result = audit_public_repo(root)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["findings"][0]["path"], "outputs/customer.json")

    def test_env_variants_and_sqlite_are_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (".env.production", "contacts.sqlite3"):
                (root / name).write_text("fixture", encoding="utf-8")
            (root / ".env.example").write_text("API_KEY=", encoding="utf-8")
            result = audit_public_repo(root)
            self.assertEqual({row["path"] for row in result["findings"]}, {".env.production", "contacts.sqlite3"})

    def test_parent_directory_named_data_does_not_disable_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data" / "repo"
            root.mkdir(parents=True)
            (root / "acquisition.db").write_text("fixture", encoding="utf-8")
            self.assertEqual(audit_public_repo(root)["status"], "failed")

    def test_parent_directory_does_not_create_empty_release_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "outputs" / "repo"
            root.mkdir(parents=True)
            (root / "README.md").write_text("fixture", encoding="utf-8")
            lock = root / "skills.lock.json"
            result = build_lock(root, lock)
            self.assertEqual(result["file_count"], 1)
            self.assertEqual(audit_release(root, lock)["status"], "succeeded")
            (root / "README.md").write_text("changed", encoding="utf-8")
            self.assertEqual(audit_release(root, lock)["status"], "failed")

    def test_large_file_needs_explicit_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "large.txt").write_text("x" * 2_000_001, encoding="utf-8")
            self.assertEqual(audit_public_repo(root)["status"], "failed")
