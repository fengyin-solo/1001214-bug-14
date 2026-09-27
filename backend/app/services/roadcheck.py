"""途中核查业务规则：状态流转、字段校验与筛选口径都收在这里。

数据一致性约定：
- 核查编号全局唯一，温度记录、封签状态等核查结果只挂在这条编号对应的记录上；
- 核查编号、关联调度建档后不可改，新一轮核查必须开新编号，历史记录不被覆盖；
- 归档后的记录只能查询，更新与动作一律拒绝。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "roadcheck"
REQUIRED_FIELDS = ["核查编号", "关联调度", "核查时间"]
# 核查弹窗里允许修改的核查结果字段；核查编号、关联调度不在其列，建档后不动
EDITABLE_FIELDS = ["核查时间", "位置定位", "温度记录", "封签状态", "核查人员"]
STATUS_ORDER = ["待核查", "已核查", "温度异常", "封签异常"]
ACTION_RULES = {"执行核查": "已核查", "登记温度异常": "温度异常", "登记封签异常": "封签异常"}
NEGATIVE_ACTIONS = []
ARCHIVE_ACTION = "归档"


class RoadcheckService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        dispatch: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("核查编号", ""))]
        if dispatch:
            rows = [row for row in rows if dispatch in str(row.get("关联调度", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        code = str(values["核查编号"]).strip()
        rows = store.rows(MODULE)
        if any(str(row.get("核查编号", "")) == code for row in rows):
            return None, f"核查编号 {code} 已存在，同一趟运输的再次核查请换用新编号，历史核查记录不能被覆盖"
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + EDITABLE_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip() != "":
                entry[field] = value
        entry["status"] = STATUS_ORDER[0]
        entry["核查状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["archived"] = False
        rows.append(entry)
        store.persist()
        return entry, None

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"途中核查 {entry_id} 不存在"
        if entry.get("archived"):
            return None, f"途中核查 {entry_id}（{entry.get('核查编号', '')}）已归档，只能查询不能修改"
        touched = {field: values[field] for field in EDITABLE_FIELDS if field in values}
        if not touched:
            return None, f"没有可更新的核查字段，仅支持：{'、'.join(EDITABLE_FIELDS)}"
        entry.update(touched)
        store.persist()
        return entry, None

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"途中核查 {entry_id} 不存在"
        if entry.get("archived"):
            return None, f"途中核查 {entry_id}（{entry.get('核查编号', '')}）已归档，只能查询不能再执行动作"
        if action == ARCHIVE_ACTION:
            entry["archived"] = True
            entry["pending"] = False
            store.persist()
            return entry, "途中核查已归档，归档后仅可查询"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于途中核查可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["核查状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        store.persist()
        return entry, f"途中核查已{action}"
