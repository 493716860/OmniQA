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
