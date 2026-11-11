"""使用 DBOS 原生定时工作流清理已结束的执行历史。"""

from datetime import datetime, timedelta

from dbos import DBOS


@DBOS.step()
async def prune_workflows(cutoff: str):
    while runs := await DBOS.list_workflows_async(
        status=["SUCCESS", "ERROR", "CANCELLED", "MAX_RECOVERY_ATTEMPTS_EXCEEDED"],
        completed_before=cutoff,
        has_parent=False,
        limit=100,
        load_input=False,
        load_output=False,
    ):
        # 从已结束的根工作流清理，避免移除仍在执行的父流程所需的子流程检查点。
        await DBOS.delete_workflows_async(
            [run.workflow_id for run in runs], delete_children=True
        )


@DBOS.workflow()
async def clean_workflow_history(scheduled_time: datetime, retention_days: int):
    await prune_workflows((scheduled_time - timedelta(days=retention_days)).isoformat())
