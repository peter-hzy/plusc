"""可用来源清单。"""

from .api import ApiAdapter
from .codex_bridge import CodexBridgeAdapter
from .directory_csv import DirectoryCsvAdapter
from .manual import ManualAdapter
from .public_web import PublicWebAdapter


def built_in_adapters() -> dict[str, object]:
    return {
        "manual": ManualAdapter(),
        "directory_csv": DirectoryCsvAdapter(),
        "public_web": PublicWebAdapter(),
        "codex_bridge": CodexBridgeAdapter(),
        "brave": ApiAdapter("brave"),
        "apollo": ApiAdapter("apollo"),
        "hunter": ApiAdapter("hunter"),
    }
