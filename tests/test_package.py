import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class PackageTests(unittest.TestCase):
    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, "-X", "utf8", str(ROOT / "scripts" / script), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_skill_validation(self):
        result = self.run_script("validate_skill.py", str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_three_pass_check(self):
        result = self.run_script("three_pass_check.py", str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_example_lead_validation(self):
        result = self.run_script("validate_leads.py", str(ROOT / "examples" / "fictional-lead.csv"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_init_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            first = self.run_script("init_workspace.py", str(workspace))
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            marker = workspace / "state.json"
            marker.write_text('{"keep": true}', encoding="utf-8")
            second = self.run_script("init_workspace.py", str(workspace))
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(json.loads(marker.read_text(encoding="utf-8")), {"keep": True})


if __name__ == "__main__":
    unittest.main()

