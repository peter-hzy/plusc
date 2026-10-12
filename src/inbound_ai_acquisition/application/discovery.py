"""候选发现的覆盖诊断。"""

from __future__ import annotations

import math
from typing import Any

from ..errors import ValidationError
from ..storage.database import Database


def discovery_coverage(db: Database, run_id: str) -> dict[str, Any]:
    """评估发现范围；细分类型只提示补搜，不用固定比例凑数。"""
    runs = db.query(
        "SELECT target_count,segments,candidate_pool_multiplier,min_source_categories,production_min_target "
        "FROM runs WHERE run_id=?",
        (run_id,),
    )
    if not runs:
        raise ValidationError("找不到 run")
    run = runs[0]
    target = int(run["target_count"])
    multiplier = float(run["candidate_pool_multiplier"])
    min_categories = int(run["min_source_categories"])
    production_min_target = int(run["production_min_target"])
    candidates = db.query(
        "SELECT candidate_id,segment_hint,discovery_status,selected_company_id FROM candidates WHERE run_id=?",
        (run_id,),
    )
    plans = db.query(
        "SELECT source_category,source_role,target_signal,query_or_entry_url,coverage,access_status,contribution "
        "FROM source_plan_entries WHERE run_id=? ORDER BY source_category,query_or_entry_url",
        (run_id,),
    )
    performance = db.query(
        "WITH category_counts AS ("
        "SELECT candidate_id,COUNT(DISTINCT source_category) AS category_count FROM candidate_sources "
        "WHERE run_id=? GROUP BY candidate_id) "
        "SELECT cs.source_category,COUNT(DISTINCT cs.source_run_id) AS source_runs,"
        "COUNT(DISTINCT cs.candidate_id) AS candidates,"
        "COUNT(DISTINCT CASE WHEN cc.category_count=1 THEN cs.candidate_id END) AS unique_candidates,"
        "COUNT(DISTINCT CASE WHEN cc.category_count>1 THEN cs.candidate_id END) AS overlap_candidates,"
        "COUNT(DISTINCT CASE WHEN c.selected_company_id IS NOT NULL THEN cs.candidate_id END) AS selected "
        "FROM candidate_sources cs JOIN candidates c ON c.candidate_id=cs.candidate_id "
        "JOIN category_counts cc ON cc.candidate_id=cs.candidate_id "
        "WHERE c.run_id=? GROUP BY cs.source_category ORDER BY candidates DESC,cs.source_category",
        (run_id, run_id),
    )
    selected = sum(row["selected_company_id"] is not None for row in candidates)
    categories = {row["source_category"] for row in performance}
    found_segments = {str(row["segment_hint"]).strip() for row in candidates if str(row["segment_hint"]).strip()}
    requested_segments = {item.strip() for item in str(run["segments"]).split(",") if item.strip()}
    requested_segments.discard("*")
    recommended_pool = max(target, math.ceil(target * multiplier))
    warnings: list[str] = []
    if selected < target:
        warnings.append(f"入选数量尚未达标：{selected}/{target}，还缺{target - selected}家；保持原目标继续研究")
    if target < production_min_target:
        warnings.append(f"target_count={target} 低于本批次正式基线 {production_min_target}，当前按小样本测试处理")
    if len(candidates) < recommended_pool:
        warnings.append(f"候选池偏小：{len(candidates)}/{recommended_pool}（本批次基线为目标的 {multiplier:g} 倍）")
    if len(categories) < min_categories:
        warnings.append(f"发现来源偏少：当前{len(categories)}类，本批次基线为{min_categories}类")
    missing_segments = sorted(requested_segments - found_segments)
    if missing_segments:
        warnings.append("尚未发现这些目标类型：" + ", ".join(missing_segments) + "；这是补搜提示，不是硬配额")
    if not plans:
        warnings.append("没有保存来源计划，无法判断哪些渠道尚未执行")
    coverage_ready = (
        target >= production_min_target
        and selected >= target
        and len(candidates) >= recommended_pool
        and len(categories) >= min_categories
    )
    execution_outcomes = {
        row["outcome"]: row["n"]
        for row in db.query("SELECT outcome,COUNT(*) AS n FROM source_runs WHERE run_id=? GROUP BY outcome", (run_id,))
    }
    return {
        "target_count": target,
        "candidate_count": len(candidates),
        "selected_count": selected,
        "selected_shortfall": max(0, target - selected),
        "selection_target_met": selected >= target,
        "recommended_pool": recommended_pool,
        "source_category_count": len(categories),
        "found_segments": sorted(found_segments),
        "missing_segments": missing_segments,
        "production_ready": coverage_ready,
        "coverage_complete": coverage_ready,
        "readiness_note": "仅数量/来源覆盖诊断，不证明产品匹配、采购意向或允许发送",
        "policy": {
            "candidate_pool_multiplier": multiplier,
            "min_source_categories": min_categories,
            "production_min_target": production_min_target,
        },
        "warnings": warnings,
        "source_plan": plans,
        "source_performance": performance,
        "execution_outcomes": execution_outcomes,
    }
