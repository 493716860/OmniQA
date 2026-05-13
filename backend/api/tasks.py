"""
backend/api/tasks.py

文件用途
-------
Celery 异步任务定义（Worker 执行入口）。

在 OmniQA 中，“Web 请求”只负责创建任务并返回；真正的用例执行、定时扫描等耗时操作全部放到 Celery：

- run_test_task(task_id)
  1) 把 TestTask 从 PENDING 置为 RUNNING（并发安全：update 条件带 status=PENDING）
  2) 为该任务准备报告目录（xml/html）
  3) 调用 DbTaskRunner(task).run() 执行接口用例/场景步骤

- run_due_schedules()
  扫描 enabled 且 next_run_at 已到期的 Schedule，创建 TestTask 并投递 run_test_task.delay()
  说明：生产环境可用 celery beat；开发环境也可通过 management command 手动触发扫描。

- run_ui_task(task_id)
  UI 自动化任务入口：UiTaskRunner(task).run()

面试讲解抓手
-----------
- 这是“任务系统的边界层”：把 ORM 状态机（PENDING/RUNNING/FINISHED）与执行引擎串起来
- update(...) 返回值用于防重入：避免重复执行同一 task_id
"""

from pathlib import Path

from django.conf import settings
from django.utils import timezone

from OmniQA.celery import app

from django.db import transaction

from .models import Schedule, TestTask
from .services.db_runner import DbTaskRunner
from .services.scheduler import create_task_from_schedule
from .models import UiExecTask, UiTask
from .services.ui_runner import UiTaskRunner


@app.task
def run_test_task(task_id):
    updated = TestTask.objects.filter(id=task_id, status=TestTask.Status.PENDING).update(
        status=TestTask.Status.RUNNING,
        started_at=timezone.now(),
        updated_at=timezone.now(),
    )
    if not updated:
        return
    task = TestTask.objects.select_related("plan", "plan__environment", "plan__project").get(id=task_id)
    try:
        report_root = Path(getattr(settings, "OMNIQA_REPORT_ROOT", "/tmp/reports")) / str(task.id)
        xml_path = report_root / "xml"
        html_path = report_root / "html"
        xml_path.mkdir(parents=True, exist_ok=True)
        html_path.mkdir(parents=True, exist_ok=True)
        task.report_xml_path = str(xml_path)
        task.report_html_path = str(html_path)
        task.save(update_fields=["report_xml_path", "report_html_path", "updated_at"])
        runner = DbTaskRunner(task)
        runner.run()
    except Exception as exc:
        task.status = TestTask.Status.FAILED
        task.failure_reason = str(exc)
        task.finished_at = timezone.now()
        task.save()


@app.task
def run_due_schedules():
    now = timezone.now()
    for schedule in Schedule.objects.filter(enabled=True, next_run_at__lte=now).select_related("plan"):
        task = create_task_from_schedule(schedule)
        run_test_task.delay(task.id)


@app.task
def run_ui_task(task_id):
    updated = UiTask.objects.filter(id=task_id, status=UiTask.Status.PENDING).update(
        status=UiTask.Status.RUNNING,
        started_at=timezone.now(),
        # 防止 enqueue_ui_task_async 写入的 “投递信息”或历史错误信息干扰页面展示
        failure_reason="",
        updated_at=timezone.now(),
    )
    if not updated:
        return
    task = UiTask.objects.select_related("scenario", "scenario__project").get(id=task_id)
    try:
        runner = UiTaskRunner(task)
        runner.run()
    except Exception as exc:
        task.status = UiTask.Status.FAILED
        task.failure_reason = str(exc)
        task.finished_at = timezone.now()
        task.save(update_fields=["status", "failure_reason", "finished_at", "updated_at"])
    finally:
        # 将场景级 UiTask 的执行结果聚合回“计划执行记录”UiExecTask，保证进度/统计实时更新
        if getattr(task, "exec_task_id", None):
            _update_ui_exec_task_aggregate(task.exec_task_id)


def _update_ui_exec_task_aggregate(exec_task_id: int):
    """
    聚合 UiExecTask 下所有 UiTask 的执行状态，更新 exec_task 的进度与统计。
    - progress = 已结束任务数 / total * 100
    - status：
        - 未全部结束：RUNNING
        - 全部结束：FAILED(有失败) / CANCELED(全部取消) / PASSED(其余)
    """
    with transaction.atomic():
        exec_task = UiExecTask.objects.select_for_update().get(id=exec_task_id)
        qs = UiTask.objects.filter(exec_task_id=exec_task_id)

        total = exec_task.total or qs.count()
        passed = qs.filter(status=UiTask.Status.PASSED).count()
        failed = qs.filter(status=UiTask.Status.FAILED).count()
        canceled = qs.filter(status=UiTask.Status.CANCELED).count()
        finished = passed + failed + canceled

        progress = int(finished / total * 100) if total else 0

        if finished < total:
            status = UiExecTask.Status.RUNNING
            finished_at = None
        else:
            if failed > 0:
                status = UiExecTask.Status.FAILED
            elif canceled == total and total > 0:
                status = UiExecTask.Status.CANCELED
            else:
                status = UiExecTask.Status.PASSED
            finished_at = timezone.now()

        started_at = exec_task.started_at
        if not started_at:
            started_at = qs.exclude(started_at=None).order_by("started_at").values_list("started_at", flat=True).first() or timezone.now()

        UiExecTask.objects.filter(id=exec_task_id).update(
            total=total,
            passed=passed,
            failed=failed,
            canceled=canceled,
            progress=progress,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            updated_at=timezone.now(),
        )
