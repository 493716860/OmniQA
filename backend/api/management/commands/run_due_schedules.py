"""
backend/api/management/commands/run_due_schedules.py

文件用途
-------
管理命令：手动扫描并触发已到期的定时任务（Schedule）。

为什么需要它？
-------------
生产环境通常由 celery beat / 定时器统一调度；
但在开发环境或演示环境中，你可能不想引入完整的 beat 进程。
此命令提供一个“按需触发”的入口：
- 找出 enabled=True 且 next_run_at <= now 的 Schedule
- create_task_from_schedule(...) 创建 TestTask（并更新 next_run_at）
- run_test_task.delay(...) 投递给 Celery Worker 执行
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import Schedule
from api.tasks import run_test_task
from api.services.scheduler import create_task_from_schedule


class Command(BaseCommand):
    help = "扫描并触发已到期的定时任务。适合开发环境用系统 crontab 或手动执行。"

    def handle(self, *args, **options):
        due = Schedule.objects.filter(enabled=True, next_run_at__lte=timezone.now()).select_related("plan")
        count = 0
        for schedule in due:
            task = create_task_from_schedule(schedule)
            run_test_task.delay(task.id)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"已触发 {count} 个定时任务"))
