"""
backend/OmniQA/__init__.py

文件用途
-------
Django 项目包初始化文件。

当前唯一显式动作是：
- 调用 `pymysql.install_as_MySQLdb()`，让 Django 在使用 MySQL 时可通过 PyMySQL 兼容 `MySQLdb` 接口。

这样做的好处是无需额外安装系统级 mysqlclient，更适合本地开发和轻量部署环境。
"""

import pymysql

pymysql.install_as_MySQLdb()
