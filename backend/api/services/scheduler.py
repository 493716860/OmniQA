"""
backend/api/services/scheduler.py

文件用途
-------
定时任务的“业务时间计算”与“任务生成”模块。

Schedule 模型支持两类调度方式：
1) SIMPLE：简单周期（每天/每周/每 N 小时）
2) CRON：Cron 表达式（5 段：minute hour day month weekday）

本文件提供：
- compute_next_run(schedule, base=None)
  根据 Schedule 配置与当前时间，计算下一次触发时间 next_run_at。

- create_task_from_schedule(schedule)
  把 Schedule 转换为一次性的 TestTask（并同步更新 Schedule.last_run_at/next_run_at）。

说明
----
这里刻意没有直接依赖 Celery：
- 触发执行由 api/tasks.py 中的 run_due_schedules() 或管理命令/beat 完成
- 本模块只负责“算时间”和“落库生成任务”，保证职责单一
"""

from datetime import datetime, time, timedelta

from django.utils import timezone

from api.models import Schedule, TestTask


def compute_next_run(schedule, base=None):
    base = base or timezone.now()
    if schedule.mode == Schedule.Mode.CRON:
        return next_from_cron(schedule.cron, base)
    run_time = schedule.run_time or time(0, 0)
    if schedule.simple_type == Schedule.SimpleType.HOURLY:
        return base + timedelta(hours=max(schedule.interval_hours, 1))
    if schedule.simple_type == Schedule.SimpleType.WEEKLY:
        weekdays = schedule.weekdays or [base.weekday()]
        for day_offset in range(0, 15):
            candidate_day = base.date() + timedelta(days=day_offset)
            if candidate_day.weekday() not in weekdays:
                continue
            candidate = timezone.make_aware(datetime.combine(candidate_day, run_time))
            if candidate > base:
                return candidate
    candidate = timezone.make_aware(datetime.combine(base.date(), run_time))
    return candidate if candidate > base else candidate + timedelta(days=1)


def next_from_cron(expr, base):
    parts = (expr or "").split()
    if len(parts) != 5:
        raise ValueError("Cron 表达式必须包含 5 段: minute hour day month weekday")
    minute_expr, hour_expr, day_expr, month_expr, weekday_expr = parts
    candidate = base.replace(second=0, microsecond=0) + timedelta(minutes=1)
    deadline = base + timedelta(days=366)
    while candidate <= deadline:
        if (
            matches_cron(minute_expr, candidate.minute)
            and matches_cron(hour_expr, candidate.hour)
            and matches_cron(day_expr, candidate.day)
            and matches_cron(month_expr, candidate.month)
            and matches_cron(weekday_expr, candidate.weekday())
        ):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("无法在未来一年内计算 Cron 下次执行时间")


def matches_cron(expr, value):
    expr = str(expr).strip()
    if expr == "*":
        return True
    if expr.startswith("*/"):
        return value % int(expr[2:]) == 0
    return value in {int(item) for item in expr.split(",") if item}


def create_task_from_schedule(schedule):
    task = TestTask.objects.create(plan=schedule.plan, log=f"定时任务触发: {schedule.name}")
    schedule.last_run_at = timezone.now()
    schedule.next_run_at = compute_next_run(schedule)
    schedule.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
    return task
