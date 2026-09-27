"""数据仓库：内存表 + 本地 JSON 快照。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
写操作成功后调 persist() 落盘，重启后从快照恢复，改动不会因为服务重启丢失。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "store.json"


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tables: dict[str, list[dict[str, Any]]] = self._load()

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if DATA_FILE.exists():
            try:
                raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                return {name: [dict(row) for row in rows] for name, rows in raw.items()}
            except (OSError, ValueError):
                pass  # 快照损坏时退回种子数据，保证服务起得来
        return {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}

    def persist(self) -> None:
        """把当前内存状态写入本地快照；任何写操作成功后都必须调一次。"""
        with self._lock:
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            DATA_FILE.write_text(
                json.dumps(self._tables, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
