from pathlib import Path

from django.conf import settings
from django.utils import timezone

from OmniQA.celery import app

from .models import Schedule, TestTask
from .services.db_runner import DbTaskRunner
from .services.scheduler import create_task_from_schedule


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
        report_root = Path(settings.NEXUS_REPORT_ROOT) / str(task.id)
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
