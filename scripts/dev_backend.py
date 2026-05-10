#!/usr/bin/env python
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
MANAGE_PY = BACKEND_DIR / "manage.py"
sys.path.insert(0, str(BACKEND_DIR))

from OmniQA.env import load_project_env


def run_manage(*args):
    command = [sys.executable, str(MANAGE_PY), *args]
    subprocess.run(command, cwd=ROOT_DIR, check=True)


def ensure_default_env():
    os.environ.setdefault("DB_ENGINE", "sqlite")
    os.environ.setdefault("DJANGO_SUPERUSER_USERNAME", "admin")
    os.environ.setdefault("DJANGO_SUPERUSER_EMAIL", "admin@nexus.local")
    os.environ.setdefault("DJANGO_SUPERUSER_PASSWORD", "admin123")


def ensure_admin_user():
    username = os.environ["DJANGO_SUPERUSER_USERNAME"]
    email = os.environ["DJANGO_SUPERUSER_EMAIL"]
    password = os.environ["DJANGO_SUPERUSER_PASSWORD"]
    script = f"""
from django.contrib.auth import get_user_model

User = get_user_model()
user, created = User.objects.get_or_create(username={username!r}, defaults={{"email": {email!r}}})
user.email = {email!r}
user.is_staff = True
user.is_superuser = True
user.set_password({password!r})
user.save()
print("管理员账号已就绪: {username}")
"""
    run_manage("shell", "-c", script)


def main():
    load_project_env(ROOT_DIR / ".env")
    ensure_default_env()
    run_manage("migrate", "--noinput")
    ensure_admin_user()
    host = os.getenv("DJANGO_RUN_HOST", "127.0.0.1")
    port = os.getenv("DJANGO_RUN_PORT", "8000")
    run_manage("runserver", f"{host}:{port}")


if __name__ == "__main__":
    main()
