#!/usr/bin/env python
"""
backend/manage.py

文件用途
-------
Django 管理命令入口（开发与运维工具入口）。

常用命令示例：
- python backend/manage.py migrate
- python backend/manage.py createsuperuser
- python backend/manage.py runserver
- python backend/manage.py import_sample_cases（项目自定义命令，见 backend/api/management/commands/）
"""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "OmniQA.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
