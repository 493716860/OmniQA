"""
backend/OmniQA/settings.py

文件用途
-------
Django 项目配置入口（Settings）。

这个项目的设置文件刻意保持“可本地一键启动、可通过环境变量覆盖”的风格：
- 启动时会尝试从仓库根目录的 .env 读取配置（load_project_env），但系统环境变量优先级更高
- DB_ENGINE=sqlite 时使用 SQLite（适合面试演示/本地调试）；默认走 MySQL
- Celery/Redis、报告目录、UI 执行参数等均提供默认值，便于开箱即用

关键设计点
-------------------------
1) BASE_DIR / REPO_ROOT：
   - BASE_DIR 指向 backend/
   - REPO_ROOT 指向仓库根目录（用于读取 .env、定位 reports/、关联前端 dist）
2) 环境变量分层：
   - “安全敏感或部署相关”都放在 .env / 系统环境变量中（SECRET_KEY、DB、Redis）
3) 任务系统配置：
   - CELERY_BROKER_URL / CELERY_RESULT_BACKEND 默认从 build_redis_url() 推导
   - OMNIQA_CELERY_EAGER=1 可让 Celery 同步执行（便于本地调试/单进程演示）
4) 报告与产物目录：
   - OMNIQA_REPORT_ROOT：接口任务 HTML 报告输出根目录（默认为 <repo>/reports/tasks）
   - OMNIQA_UI_REPORT_ROOT：UI 任务产物输出根目录（默认为 <repo>/reports/ui-tasks）
"""

import os
from pathlib import Path
from urllib.parse import quote

from .env import load_project_env

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
load_project_env(REPO_ROOT / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "OmniQA.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "OmniQA.wsgi.application"

if os.getenv("DB_ENGINE", "mysql") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("MYSQL_DATABASE", "omniqa_api"),
            "USER": os.getenv("MYSQL_USER", "root"),
            "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
            "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.getenv("MYSQL_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.CsrfExemptSessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

def build_redis_url():
    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    username = os.getenv("REDIS_USERNAME", "")
    password = os.getenv("REDIS_PASSWORD", "")
    if username and password:
        auth = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    elif password:
        auth = f":{quote(password, safe='')}@"
    else:
        auth = ""
    return f"redis://{auth}{host}:{port}/{db}"


CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL") or build_redis_url()
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_BROKER_CONNECTION_TIMEOUT = float(os.getenv("CELERY_BROKER_CONNECTION_TIMEOUT", "1"))
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "socket_connect_timeout": CELERY_BROKER_CONNECTION_TIMEOUT,
    "socket_timeout": CELERY_BROKER_CONNECTION_TIMEOUT,
    "retry_on_timeout": False,
}
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = CELERY_BROKER_TRANSPORT_OPTIONS
CELERY_TASK_ALWAYS_EAGER = os.getenv("OMNIQA_CELERY_EAGER", "0") == "1"
CELERY_TASK_PUBLISH_RETRY = False
OMNIQA_REPORT_ROOT = os.getenv("OMNIQA_REPORT_ROOT", str(REPO_ROOT / "reports" / "tasks"))
OMNIQA_REPORT_URL = os.getenv("OMNIQA_REPORT_URL", "/reports/")
OMNIQA_UI_REPORT_ROOT = os.getenv("OMNIQA_UI_REPORT_ROOT", str(REPO_ROOT / "reports" / "ui-tasks"))
OMNIQA_UI_HEADED_KEEP_OPEN_SECONDS = int(os.getenv("OMNIQA_UI_HEADED_KEEP_OPEN_SECONDS", "120"))
OMNIQA_UI_SLOW_MO_MS = int(os.getenv("OMNIQA_UI_SLOW_MO_MS", "200"))
OMNIQA_REQUEST_TIMEOUT = int(os.getenv("OMNIQA_REQUEST_TIMEOUT", "10"))
