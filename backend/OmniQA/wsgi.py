"""
backend/OmniQA/wsgi.py

文件用途
-------
WSGI 入口（用于同步服务器部署，如 gunicorn/uwsgi）。

部署时通常通过：
  gunicorn OmniQA.wsgi:application
启动 Django 应用。
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "OmniQA.settings")
application = get_wsgi_application()
