"""Convert a PlusC seven-column review workbook to conservative legacy JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inbound_ai_acquisition.application.review_workbook import convert_review_workbook


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    payload = convert_review_workbook(args.workbook, run_id=args.run_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["conversion"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
