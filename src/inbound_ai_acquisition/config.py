"""工作区配置与路径。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = """# 非敏感配置；API 密钥请放环境变量或系统密钥管理器。
markets = ["AU", "NZ", "US", "CA"]
segments = ["travel_agency", "dmc", "tour_operator"]
default_batch_size = 20
network_retry_limit = 2
"""


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def database(self) -> Path:
        return self.root / "acquisition.db"

    @property
    def config(self) -> Path:
        return self.root / "config.toml"

    def ensure_layout(self) -> list[str]:
        self.root.mkdir(parents=True, exist_ok=True)
        created: list[str] = []
        for name in ("imports", "exports", "logs", "backups"):
            path = self.root / name
            if not path.exists():
                path.mkdir()
                created.append(name + "/")
        if not self.config.exists():
            self.config.write_text(DEFAULT_CONFIG, encoding="utf-8")
            created.append("config.toml")
        return created
