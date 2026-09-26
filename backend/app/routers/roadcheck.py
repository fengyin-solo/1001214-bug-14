"""途中核查接口：维护途中核查，覆盖执行核查、登记温度异常、登记封签异常、归档核查等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.roadcheck import RoadcheckService

router = APIRouter(prefix="/api/roadcheck", tags=["途中核查"])

service = RoadcheckService()

LIST_FIELDS = ["核查编号", "关联调度", "核查时间", "位置定位", "温度记录", "封签状态", "核查人员", "核查状态"]
STATUSES = ["待核查", "已核查", "温度异常", "封签异常", "已归档"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按核查编号检索"),
    status: str | None = Query(default=None, description="待核查、已核查、温度异常、封签异常、已归档"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按核查编号与状态过滤途中核查列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出途中核查清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "roadcheck", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条途中核查明细；已归档的记录同样可以查，只是不能再改。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"途中核查 {entry_id} 不存在")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条途中核查；同一关联调度的历史核查自动归档保留，不被覆盖。"""
    entry, error = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=error)
    return ActionResult(ok=True, message="途中核查已登记", entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """保存核查弹窗里的温度记录、封签状态等字段；已归档记录只读，修改会被拦下。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条途中核查执行动作，弹窗里的核查字段随动作一起落库；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
