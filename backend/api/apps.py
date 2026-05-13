"""
backend/api/apps.py

文件用途
-------
Django App 配置声明（AppConfig）。

这里主要用于：
- 声明 app name = "api"
- 指定默认主键类型 BigAutoField
"""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
