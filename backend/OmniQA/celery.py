"""
backend/OmniQA/celery.py

文件用途
-------
Celery 应用初始化入口。

- 设置 DJANGO_SETTINGS_MODULE，确保 Worker 启动时能读取 Django 配置
- 以 namespace="CELERY" 从 settings.py 加载 Celery 相关配置
- app.autodiscover_tasks() 自动发现各 Django app 下的 tasks.py

提示
----
本项目的 Celery task 定义位于：backend/api/tasks.py
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "OmniQA.settings")

app = Celery("OmniQA")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
