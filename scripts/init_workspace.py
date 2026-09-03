#!/usr/bin/env python3
"""在本地创建工作区，不覆盖已有文件，不连接外部服务。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for name in ("product-profile.md", "voice-profile.md", "state.json", "leads.csv", "review.md"):
        destination = root / name
        if destination.exists():
            continue
        source_name = f"{name}.template" if name.endswith(".md") and name != "review.md" else None
        if name == "product-profile.md":
            source = Path(__file__).parent.parent / "templates/product-profile.template.md"
        elif name == "voice-profile.md":
            source = Path(__file__).parent.parent / "templates/voice-profile.template.md"
        elif name == "state.json":
            source = Path(__file__).parent.parent / "templates/state.template.json"
        elif name == "leads.csv":
            source = Path(__file__).parent.parent / "templates/leads.template.csv"
        else:
            source = Path(__file__).parent.parent / "templates/review.template.md"
        shutil.copyfile(source, destination)
        created.append(name)
    print(json.dumps({"workspace": str(root), "created": created}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

