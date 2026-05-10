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
