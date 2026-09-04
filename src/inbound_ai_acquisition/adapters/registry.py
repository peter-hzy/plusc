"""可用来源清单。"""

from .manual import ManualAdapter


def built_in_adapters() -> dict[str, object]:
    return {name: ManualAdapter(name) for name in ("manual", "directory_csv", "public_web", "codex_bridge")}
