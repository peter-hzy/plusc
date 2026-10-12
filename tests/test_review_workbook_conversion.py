"""Tests for conservative takeover of the seven-column review workbook."""

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from inbound_ai_acquisition.application.review_workbook import HEADERS, _route_grade, convert_review_workbook
from inbound_ai_acquisition.errors import ValidationError


class ReviewWorkbookConversionTests(unittest.TestCase):
    def temp_directory(self):
        return tempfile.TemporaryDirectory(dir=Path(__file__).parent)

    def make_workbook(self, root: Path, *, bad_header: bool = False) -> Path:
        path = root / "review.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.title = "客户结果"
        headers = list(HEADERS)
        if bad_header:
            headers[-1] = "错误列"
        sheet.append(headers)
        sheet.append(
            [
                "Example Travel",
                "澳洲 / 旅游运营商",
                "官网有中国线路。\n限制：产品、团量和供应商未知。",
                "Example Person / Product Director",
                "person@example.test\n邮箱归属待确认\n具名职责入口（以审核状态为准）",
                "内部提案\n待人工复核",
                "未联系／未发送",
            ]
        )
        sheet["A2"].hyperlink = "https://example.test"
        sheet["E2"].hyperlink = "mailto:person@example.test"
        sheet.append([None] * 7)
        sheet.append(["Example Travel｜内部文案提案（未发送)"] + [None] * 6)
        # Use the exact full-width title expected by the real workbook.
        sheet["A4"] = "Example Travel｜内部文案提案（未发送）"
        sheet.append(["Subject: China itinerary enquiry\n\nHello team,\n\nDraft only."] + [None] * 6)
        sheet.append(["限制与复核：事实/语气/产品/触达依据均待人工复核。"] + [None] * 6)
        sheet.append(
            ["核查日：2026-10-12\n公司依据：https://example.test/china\n公开入口：https://example.test/contact"]
            + [None] * 6
        )
        book.save(path)
        book.close()
        return path

    def test_conversion_recovers_only_pending_records(self):
        with self.temp_directory() as directory:
            payload = convert_review_workbook(self.make_workbook(Path(directory)), run_id="run_takeover")
        sheets = payload["sheets"]
        self.assertEqual(payload["conversion"]["company_count"], 1)
        self.assertEqual(payload["conversion"]["detected_segments"], ["旅游运营商"])
        self.assertEqual(sheets["RunConfig"][0]["run_id"], "run_takeover")
        self.assertEqual(sheets["RunConfig"][0]["market"], "AU")
        self.assertEqual(sheets["RunConfig"][0]["client_types"], "*")
        self.assertEqual(sheets["Companies"][0]["candidate_status"], "research_needed")
        self.assertEqual(sheets["Contacts"][0]["identity_status"], "unverified")
        self.assertIn("入口等级：R1", sheets["Contacts"][0]["department_or_scope"])
        self.assertEqual(sheets["Evidence"], [])
        self.assertEqual(sheets["Drafts"][0]["draft_status"], "draft")
        self.assertEqual(sheets["Drafts"][0]["human_review_status"], "pending")
        self.assertEqual(len(sheets["ResearchGaps"]), 3)
        self.assertTrue(all(row["blocks_outreach"] for row in sheets["ResearchGaps"]))

    def test_bad_headers_are_rejected(self):
        with self.temp_directory() as directory:
            path = self.make_workbook(Path(directory), bad_header=True)
            with self.assertRaisesRegex(ValidationError, "七列表头"):
                convert_review_workbook(path)

    def test_explicit_route_grade_is_preserved(self):
        self.assertEqual(_route_grade("官网悉尼通用邮箱；R3，采购职责待确认"), "R3")


if __name__ == "__main__":
    unittest.main()
