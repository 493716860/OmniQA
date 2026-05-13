"""
backend/OmniQA/asgi.py

文件用途
-------
ASGI 入口（用于异步服务器部署，如 uvicorn/daphne）。

本项目主要是传统 HTTP API + 静态资源托管，默认 WSGI 已足够；
保留 ASGI 入口便于未来接入 WebSocket/异步能力或在云环境使用 ASGI Server。
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "OmniQA.settings")
application = get_asgi_application()
