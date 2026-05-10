# Nexus API 自动化测试平台

Nexus API 是一个轻量级接口自动化测试平台，当前首版采用前后端分离架构：

- 前端：Vue 3 + Element Plus + Pinia + Vue Router + Axios
- 后端：Django + Django REST Framework
- 任务：Celery + Redis
- 数据库：MySQL，开发调试可临时使用 SQLite
- 用例来源：Excel 导入后进入数据库

## 项目结构

```text
backend/              Django/DRF 后端服务
frontend/             Vue 3 前端应用
data/                 Excel 用例样例和业务数据
requirements.txt      后端直接依赖
.env.example          环境变量示例
```

## 后端启动

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python scripts/dev_backend.py
```

项目启动时会自动读取根目录 `.env` 配置文件，数据库、Redis、默认管理员账号等本地密码都可以维护在这个文件里。`.env` 已被 `.gitignore` 排除，不会提交到代码仓库；系统环境变量优先级更高，可以覆盖 `.env` 中的同名配置。

开发脚本默认使用 SQLite，并自动执行迁移、创建/更新本地管理员账号：

```text
用户名：admin
密码：admin123
```

如果想换默认账号，可以在启动前设置：

```bash
DJANGO_SUPERUSER_USERNAME=Ron
DJANGO_SUPERUSER_PASSWORD=your-password
```

连接 MySQL 时，在 `.env` 中设置 `DB_ENGINE=mysql`、`MYSQL_HOST`、`MYSQL_DATABASE`、`MYSQL_USER`、`MYSQL_PASSWORD`。

## 异步任务启动

执行测试计划依赖 Celery Worker 和 Redis。Web 接口 `/api/test-tasks/` 只创建任务并异步投递，真正的用例执行由 Worker 完成。

先确认 `.env` 中 Redis 地址配置正确。Redis 无密码时：

```env
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
```

Redis 有密码时，URL 需要带上密码，否则任务会失败并显示 `Authentication required.`：

```env
CELERY_BROKER_URL=redis://:your-redis-password@127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://:your-redis-password@127.0.0.1:6379/0
```

启动 Worker：

```bash
cd backend
../.venv/bin/celery -A OmniQA worker -l info
```

## 前端启动

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

浏览器访问 `http://127.0.0.1:5173`。

## 本地功能验证

首次进入平台时，用例列表为空是正常的，需要先导入 Excel。可以用页面导入，也可以在项目根目录执行样例导入命令：

```bash
DB_ENGINE=sqlite .venv/bin/python backend/manage.py import_sample_cases
```

导入完成后刷新“用例列表”，应能看到 `data/控制台首页.xlsx` 中的用例。

最短验证路径：

1. 启动后端：`.venv/bin/python scripts/dev_backend.py`
2. 启动 Celery Worker：`cd backend && DB_ENGINE=sqlite ../.venv/bin/celery -A OmniQA worker -l info`
3. 启动前端：`cd frontend && npm run dev -- --host 127.0.0.1`
4. 登录平台：`admin / admin123`
5. 执行样例导入命令或在“Excel 导入”页上传 `data/控制台首页.xlsx`
6. 进入“用例列表”查看导入结果

## 核心能力

- 项目与环境管理
- Excel 用例导入
- 用例查询
- 测试计划创建
- 执行任务创建、状态查询、结果查看
- 测试计划用例明细查看
- 执行任务当前用例与实时进度展示
- 依赖失败自动跳过
- 响应变量提取与 `${变量名}` 引用
- 失败结果请求/响应/错误详情查看
- 在线维护接口定义、接口用例、场景用例
- 项目变量、环境变量、任务变量三层变量
- 简单周期和 Cron 两种定时任务

## 用例依赖与变量

Excel 中的 `Rely` 字段会作为依赖用例导入。执行时平台会优先执行依赖；如果依赖失败，后续用例会标记为 `SKIPPED`。

用例支持 `extractors` 变量提取配置，格式示例：

```json
[
  {"name": "token", "path": "$.data.token", "required": false}
]
```

后续请求的 Header、Payload 中可以使用：

```text
${token}
${b_1.data.uid}
```

变量优先级：

```text
任务运行时变量 > 环境变量 > 项目变量
```

## 场景用例与定时任务

场景用例由多个步骤组成，每个步骤绑定一个接口定义，并支持独立 Header、Payload、Expect、变量提取和依赖步骤。

定时任务在“定时任务”页面维护，支持：

- 简单周期：每天、每周、每 N 小时
- Cron 表达式：例如 `*/30 * * * *`
- 立即执行：会生成普通执行任务，结果仍在“执行任务”页面查看

开发环境如果不用 Celery Beat，可以手动扫描到期任务：

```bash
DB_ENGINE=sqlite .venv/bin/python backend/manage.py run_due_schedules
```

## 说明

旧版脚本入口已经移除，当前以 `backend/api/services/importer.py` 和 `backend/api/services/db_runner.py` 作为导入与执行核心。
