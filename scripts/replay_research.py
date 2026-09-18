"""离线复放已采集来源，验证入库/去重/导出；不代表重新抓取或人工批准。"""

import argparse
import json
from pathlib import Path

from inbound_ai_acquisition.application.research import ingest_source_bundle, research_status, verify_research_uat
from inbound_ai_acquisition.application.services import create_run
from inbound_ai_acquisition.exporters.json_export import export_json
from inbound_ai_acquisition.exporters.workbook import export_workbook
from inbound_ai_acquisition.storage.database import Database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--target", type=int, default=20, help="预先确认的目标，不随实际入选数量缩小")
    parser.add_argument("--markets", nargs="+", default=["AU", "NZ"])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    db = Database(args.output / "research.db")
    db.migrate()
    run = create_run(
        db,
        markets=args.markets,
        segments=["travel_agency", "tour_operator"],
        target=args.target,
        request_id="replay",
        idempotency_key="replay",
    )["run_id"]
    ingest_source_bundle(db, run, bundle, "replay-ingest")
    before = len(db.query("SELECT * FROM companies"))
    counts = research_status(db, run)["stats"]
    ingest_source_bundle(db, run, bundle, "replay-repeat")
    assert len(db.query("SELECT * FROM companies")) == before
    for key in ("companies", "contacts", "claims", "evidence"):
        assert research_status(db, run)["stats"][key] == counts[key], key
    assert not db.query("SELECT * FROM claims WHERE status='accepted'")
    assert not db.query("SELECT * FROM drafts")
    export_workbook(db, args.output / "客户结果_待核准.xlsx", run)
    export_json(db, args.output / "audit.json", run)
    status = research_status(db, run)
    verification = verify_research_uat(db, run, args.output / "客户结果_待核准.xlsx", scope="companies")
    (args.output / "verification.json").write_text(
        json.dumps(
            {
                "mode": "recorded_source_replay_not_live_fetch",
                "input": str(args.bundle.resolve()),
                "run_id": run,
                "companies": before,
                "target_count": args.target,
                "selection_target_met": before >= args.target,
                "duplicate_ingest_did_not_duplicate_companies": True,
                "claims_accepted": 0,
                "drafts": 0,
                "sent": 0,
                "status": status["status"],
                "company_list_verification": verification,
                "idempotent_tables": ["companies", "contacts", "claims", "evidence"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"companies": before, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
