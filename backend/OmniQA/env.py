"""
backend/OmniQA/env.py

文件用途
-------
极简版 .env 读取器（不依赖 python-dotenv）。

load_project_env(path) 会把形如 KEY=VALUE 的配置写入 os.environ，用于：
- 本地开发/演示：在仓库根目录放置 .env，避免手动 export 一堆变量
- 部署环境：若系统环境变量已存在同名 KEY，则不会覆盖（系统变量优先）

解析规则：
- 忽略空行与注释行（# 开头）
- 仅处理包含 '=' 的行
- 支持把成对引号包裹的值去掉外层引号
"""

import os
from pathlib import Path


def load_project_env(path=None):
    env_path = Path(path) if path else Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
