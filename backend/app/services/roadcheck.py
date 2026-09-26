"""途中核查业务规则：状态流转、字段校验与筛选口径都收在这里。

口径约定：
- 「核查状态」以内部 status 为唯一来源，列表、详情、弹窗读到的都是同一份；
- 温度记录、封签状态等核查字段只挂在核查编号这条记录上，不允许另起副本；
- 已归档记录只能查看，任何修改与动作都会被拦下；
- 同一趟运输再次核查时只新增记录、归档旧记录，历史核查不被覆盖。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "roadcheck"
REQUIRED_FIELDS = ["核查编号", "关联调度", "核查时间"]
STATUS_ORDER = ["待核查", "已核查", "温度异常", "封签异常", "已归档"]
ACTION_RULES = {"执行核查": "已核查", "登记温度异常": "温度异常", "登记封签异常": "封签异常", "归档核查": "已归档"}
EDITABLE_FIELDS = ["核查时间", "位置定位", "温度记录", "封签状态", "核查人员"]
ABNORMAL_STATUSES = {"温度异常", "封签异常"}
ARCHIVED_STATUS = "已归档"


def _sync_status(row: dict[str, Any]) -> dict[str, Any]:
    """对外展示前把「核查状态」对齐到内部 status，保证各页面读到同一结论。"""
    row["核查状态"] = str(row.get("status") or STATUS_ORDER[0])
    return row


class RoadcheckService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("核查编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [_sync_status(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return _sync_status(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        rows = store.rows(MODULE)
        code = str(values.get("核查编号") or "").strip()
        if any(str(row.get("核查编号", "")) == code for row in rows):
            return None, f"核查编号 {code} 已存在，温度记录与封签状态必须挂在唯一核查编号下"
        # 同一趟运输的历史核查只归档保留，不被新核查覆盖
        dispatch = str(values.get("关联调度") or "").strip()
        for row in rows:
            if str(row.get("关联调度", "")) == dispatch and row.get("status") != ARCHIVED_STATUS:
                self._apply_status(row, ARCHIVED_STATUS)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in EDITABLE_FIELDS:
            if str(values.get(field) or "").strip():
                entry[field] = values.get(field)
        self._apply_status(entry, STATUS_ORDER[0])
        rows.append(entry)
        return _sync_status(entry), ""

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"途中核查 {entry_id} 不存在"
        if entry.get("status") == ARCHIVED_STATUS:
            return None, f"途中核查 {entry.get('核查编号', entry_id)} 已归档，只能查看不能修改"
        if "核查编号" in values and str(values["核查编号"]).strip() != str(entry.get("核查编号", "")):
            return None, "核查编号不允许修改，温度记录与封签状态只能跟着原核查编号走"
        changed = False
        for field in EDITABLE_FIELDS:
            if field in values:
                entry[field] = values[field]
                changed = True
        if not changed:
            return None, "没有可保存的字段：温度记录与封签状态只能跟着这条核查编号更新"
        return _sync_status(entry), "途中核查已保存"

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"途中核查 {entry_id} 不存在"
        if entry.get("status") == ARCHIVED_STATUS:
            return None, f"途中核查 {entry.get('核查编号', entry_id)} 已归档，只能查看不能修改"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于途中核查可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        # 核查弹窗里的温度记录、封签状态等字段随动作一起落库，都挂在这条核查编号下
        for field in EDITABLE_FIELDS:
            if values and field in values:
                entry[field] = values[field]
        self._apply_status(entry, target)
        return _sync_status(entry), f"途中核查已{action}"

    @staticmethod
    def _apply_status(entry: dict[str, Any], target: str) -> None:
        entry["status"] = target
        entry["核查状态"] = target
        entry["pending"] = target == STATUS_ORDER[0]
        entry["abnormal"] = target in ABNORMAL_STATUSES
