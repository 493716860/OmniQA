# OmniQA 自动化测试平台

OmniQA 是一个面向测试平台场景的自动化测试系统，目标不是只“跑接口”，而是把接口资产管理、场景编排、异步执行、结果追踪、质量看板、定时触发、UI 自动化能力放进同一套平台里。

这个仓库已经补充了大量“文件级说明”注释，你现在可以直接打开关键文件理解它的职责；本 `README.md` 则负责从更高层把项目的整体架构、模块关系、设计思想和关键文件用途串起来，方便你在面试时完整讲清楚。

## 项目定位

- 面向对象：测试开发、QA、接口自动化维护者、内部平台使用者
- 核心问题：用例维护分散、执行链路不透明、依赖链路难追踪、结果不可观测、演示/落地成本高
- 解决方式：前后端分离 + 异步任务执行 + 平台化资产管理 + 结构化结果沉淀

## 技术架构

- 前端：`Vue 3` + `Element Plus` + `Pinia` + `Vue Router` + `Axios`
- 后端：`Django` + `Django REST Framework`
- 异步任务：`Celery` + `Redis`
- 数据库：`MySQL`，本地调试默认可使用 `SQLite`
- Excel 解析：`openpyxl`
- 接口执行：`requests` + `jsonpath` + `pactverify`
- UI 自动化：`Playwright`

## 整体架构

```text
┌─────────────────────────────────────────────────────┐
│                     Frontend                        │
│ Vue3 页面 / 表单 / 看板 / 任务详情 / UI 自动化配置     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP(`/api/*`)
┌──────────────────────▼──────────────────────────────┐
│                 Django + DRF API                    │
│ 认证 / CRUD / 导入入口 / 计划预览 / 任务创建 / 查询    │
└──────────────────────┬──────────────────────────────┘
                       │ create task / delay
┌──────────────────────▼──────────────────────────────┐
│                  Celery Worker                      │
│ run_test_task / run_ui_task / run_due_schedules     │
└──────────────────────┬──────────────────────────────┘
                       │
     ┌─────────────────┴─────────────────┐
     │                                   │
┌────▼──────────────────┐    ┌───────────▼────────────────┐
│  DB Runner            │    │ UI Runner                  │
│ 接口/场景执行引擎       │    │ Playwright UI 执行引擎      │
│ 变量替换/依赖排序/报告   │    │ PO/DDT/截图/trace          │
└────┬──────────────────┘    └───────────┬────────────────┘
     │                                   │
┌────▼───────────────────────────────────▼────────────────┐
│                 Database + Report Files                  │
│ 项目/环境/用例/计划/任务/结果/事件/报告/工件             │
└─────────────────────────────────────────────────────────┘
```

## 面试时建议怎么讲

你可以按下面这条主线讲：

1. 这是一个平台型自动化测试项目，不是单纯的脚本集合。
2. 前端负责资产维护、计划编排、执行监控和结果展示。
3. 后端 API 只负责“接收请求、校验数据、创建任务、查询结果”，不直接承担耗时执行。
4. 真正的执行在 Celery Worker 中完成，接口自动化和 UI 自动化分别由两个 Runner 执行。
5. 所有执行过程都会沉淀为结构化结果和事件流，因此平台不仅能“跑”，还能“看懂为什么成功/失败”。

## 核心设计思想

- 设计思想 1：控制层和执行层解耦
  `views.py` 只做入口和编排，`db_runner.py`、`ui_runner.py` 才是执行引擎。

- 设计思想 2：测试资产平台化
  项目、模块、环境、接口定义、接口用例、场景用例、UI 页面对象、数据集都统一入库管理。

- 设计思想 3：执行过程可观测
  结果表、事件表、HTML 报告、UI trace 和截图都不是附属品，而是平台核心能力。

- 设计思想 4：兼顾演示成本和工程可扩展性
  本地可用 SQLite 一键启动；真正部署时可以无缝切到 MySQL、Redis、Celery。

- 设计思想 5：支持“真实链路”
  变量提取、Cookie 持久化、依赖拓扑排序、定时调度、场景步骤依赖都是为了支持更接近真实业务的测试流。

## 目录设计

```text
backend/                 Django 后端服务
frontend/                Vue 前端应用
data/                    Excel 样例数据
reports/                 执行报告与 UI 工件输出目录
scripts/                 一键开发启动脚本
.env.example             环境变量模板
requirements.txt         后端 Python 依赖
README.md                项目总览与架构说明
```

## 后端模块设计

### 1. 项目入口与配置

- `backend/OmniQA/__init__.py`
  Django 项目包初始化文件，同时通过 `PyMySQL` 兼容 MySQL 驱动。

- `backend/OmniQA/settings.py`
  项目总配置入口，集中管理数据库、Redis、Celery、报告目录、时区、认证方式等。

- `backend/OmniQA/env.py`
  轻量版 `.env` 读取器，不依赖 `python-dotenv`，保证本地环境可快速启动。

- `backend/OmniQA/urls.py`
  项目级路由入口，把 `/api/` 转给后端 API，同时托管前端构建产物与 SPA 刷新兜底。

- `backend/OmniQA/celery.py`
  Celery 应用初始化入口，用于让 Worker 正确发现任务。

- `backend/OmniQA/asgi.py`
  ASGI 入口，便于未来接入异步能力或使用 ASGI Server 部署。

- `backend/OmniQA/wsgi.py`
  WSGI 入口，适合同步 HTTP 部署。

- `backend/manage.py`
  Django 管理命令入口。

### 2. 领域模型层

- `backend/api/models.py`
  整个系统的数据骨架。这里定义了项目、环境、变量、Cookie、模块、接口定义、接口用例、测试计划、任务、结果、事件、场景、定时任务以及 UI 自动化相关实体。

模型关系可以这样理解：

- `Project` 是顶层业务归属。
- `Environment` 挂在 `Project` 下，负责 base_url、headers、超时、Cookie。
- `Module` 用于项目内分组。
- `ApiDefinition` 表示接口定义。
- `ApiCase` 表示接口用例，挂在接口定义下。
- `ScenarioCase` / `ScenarioStep` 表示场景用例和步骤。
- `TestPlan` 表示“我要跑什么”。
- `TestTask` 表示“这次真的执行了什么”。
- `TestResult` / `ScenarioStepResult` 表示结果。
- `TaskEvent` 表示结构化事件流。
- `Schedule` 表示定时策略。
- `Ui*` 系列模型表示 UI 自动化资产与执行结果。

### 3. 序列化与规则层

- `backend/api/serializers.py`
  负责 REST 输入输出格式转换，同时承载关键业务校验逻辑。

这个文件的设计重点是：

- 让前端拿到更易用的字段，比如 `module_name`、`api_path`、`dependency_codes`
- 在写入时约束数据合法性，比如“环境必须属于项目”“场景不能和接口范围混用”
- 通过 `resolve_plan_cases()` 与 `resolve_plan_scenarios()` 统一定义计划选取规则，保证预览、执行、详情统计都一致

### 4. API 入口层

- `backend/api/views.py`
  后端主控制器文件，提供认证、资源 CRUD、导入、计划预览、任务创建、结果查询、看板聚合、UI 自动化接口等。

它的设计思想是：

- 把“资源管理”做成标准 REST
- 把“动作型操作”做成明确的行为接口
- 把“执行请求”与“执行本身”分离开

例如：

- 创建接口执行任务：前端调用 `/api/test-tasks/`
- 后端只创建 `TestTask`
- 再异步投递 Celery
- 真正执行在 `backend/api/tasks.py` 和 `backend/api/services/db_runner.py`

- `backend/api/urls.py`
  API 路由注册表，统一声明所有前后端交互入口。

- `backend/api/authentication.py`
  自定义 Session 认证类，用于开发/演示环境简化 CSRF 限制。

### 5. 服务层

- `backend/api/services/importer.py`
  Excel 导入引擎，把 Excel 数据解析并写成平台内部模型。

- `backend/api/services/curl_importer.py`
  cURL 导入引擎，把抓包得到的 cURL 命令转成接口定义与默认用例，适合快速补齐平台资产。

- `backend/api/services/db_runner.py`
  接口/场景执行引擎，是整个接口自动化链路的核心。它负责：
  选择待执行对象、依赖拓扑排序、变量替换、Cookie 持久化、请求发送、断言、结果落库、结构化事件记录、HTML 报告生成。

- `backend/api/services/scheduler.py`
  定时任务时间计算模块，负责 `next_run_at` 计算与从 `Schedule` 生成 `TestTask`。

- `backend/api/services/ui_runner.py`
  UI 自动化执行引擎，基于 Playwright，支持页面方法、数据驱动、失败截图、trace 产物输出。

- `backend/api/services/__init__.py`
  服务层包标记文件。

### 6. 异步任务层

- `backend/api/tasks.py`
  Celery 任务定义入口，负责把 `TestTask` / `UiTask` 从待执行状态切换为运行中，并调用对应 Runner。

### 7. 运维与调试支持

- `backend/api/admin.py`
  Django Admin 注册，便于开发和快速排障。

- `backend/api/tests.py`
  后端自动化测试，覆盖计划校验、任务创建异步性、场景结果逻辑、cURL 导入与跨域 base_url 等关键规则。

- `backend/api/apps.py`
  Django App 配置。

### 8. 自定义管理命令

- `backend/api/management/commands/import_sample_cases.py`
  导入 Excel 样例数据，帮助你快速演示接口自动化链路。

- `backend/api/management/commands/run_due_schedules.py`
  手动扫描并触发已到期的定时任务，适合开发环境。

- `backend/api/management/commands/reset_debug_data.py`
  重置并写入一套“登录 → 企业信息 → SKU → 绑定列表”的调试链路数据，用于展示依赖、Cookie、变量提取能力。

- `backend/api/management/commands/seed_ui_demo.py`
  生成一套 UI 自动化演示数据，包括页面对象、元素、方法、数据集和场景。

### 9. 迁移文件

- `backend/api/migrations/*.py`
  记录数据库结构演进历史。

各迁移的大致演进方向如下：

- `0001_initial.py`
  初始化平台第一版表结构。

- `0002_dependencies_progress.py`
  引入依赖与任务进度相关结构。

- `0003_platform_upgrade.py`
  扩展平台业务模型。

- `0004_quality_governance.py`
  引入质量治理相关字段与能力。

- `0005_environment_cookie.py`
  增加环境级 Cookie 表。

- `0006_scenario_step_result_snapshot.py`
  给场景步骤结果增加名称快照。

- `0007_scenario_step_result_scenario_name_nullable.py`
  调整快照字段兼容性。

- `0008_task_event.py`
  引入任务事件流表。

- `0009_ui_automation.py`
  增加 UI 自动化核心表。

- `0010_alter_uistep_dependencies.py`
  调整 UI 步骤依赖能力。

- `0011_po_ddt.py`
  引入 PO + DDT 能力模型。

## 前端模块设计

### 1. 启动与路由

- `frontend/index.html`
  前端宿主页面。

- `frontend/src/main.js`
  应用启动入口，注册 Vue、Pinia、Router、Element Plus 和全局样式。

- `frontend/src/App.vue`
  最顶层根组件，只保留路由出口。

- `frontend/src/router/index.js`
  路由入口，定义页面结构、登录守卫，以及开发环境使用 Hash 路由、生产环境使用 History 路由的策略。

### 2. 基础通信与状态

- `frontend/src/api/http.js`
  Axios 基础实例，统一封装超时、`withCredentials`、错误提示和会话失效处理。

- `frontend/src/api/resources.js`
  所有前端 API 的资源封装层。页面只依赖这里，不直接写 HTTP 请求。

- `frontend/src/stores/auth.js`
  Pinia 登录态仓库，负责登录、登出、用户信息缓存与恢复。

### 3. 布局层

- `frontend/src/layouts/MainLayout.vue`
  登录后的统一后台布局，负责菜单、顶部用户栏和业务页面承载。

### 4. 全局样式

- `frontend/src/styles/global.css`
  全局主题变量和通用样式容器定义。

### 5. 通用编辑器组件

- `frontend/src/components/editors/RequestConfigEditor.vue`
  组合型请求配置编辑器，是接口用例和场景步骤编辑时的核心配置区域。

- `frontend/src/components/editors/KeyValueEditor.vue`
  键值对编辑器，适用于 Header、Query 等结构。

- `frontend/src/components/editors/JsonBodyEditor.vue`
  JSON 文本编辑器，用于请求体或原始 JSON 配置录入。

- `frontend/src/components/editors/AssertionEditor.vue`
  断言编辑器，支持可视化规则与 JSON 双模式。

- `frontend/src/components/editors/ExtractorEditor.vue`
  变量提取配置编辑器。

- `frontend/src/components/editors/VariablePicker.vue`
  变量辅助选择器，用于帮助用户在配置中插入 `${变量}`。

### 6. 业务页面层

- `frontend/src/views/DashboardView.vue`
  质量看板首页，用于展示通过率、失败分布、慢接口、治理指标等聚合信息。

- `frontend/src/views/LoginView.vue`
  登录页。

- `frontend/src/views/ProjectsView.vue`
  项目管理页面，是所有测试资产的业务归属入口。

- `frontend/src/views/VariablesView.vue`
  项目变量与环境变量管理页面。

- `frontend/src/views/CookiesView.vue`
  环境 Cookie 管理页面，用于查看和维护运行态 Cookie。

- `frontend/src/views/ImportView.vue`
  导入页面，支持 Excel 导入与 cURL 导入。

- `frontend/src/views/ApiDefinitionsView.vue`
  接口定义管理页面，维护 path、method、默认请求头等。

- `frontend/src/views/CasesView.vue`
  接口用例管理页面，维护请求配置、断言、提取器、依赖、标签、套件等。

- `frontend/src/views/ScenariosView.vue`
  场景用例页面，管理场景与场景步骤。

- `frontend/src/views/PlansView.vue`
  测试计划页面，定义“要跑哪些接口/用例/场景”。

- `frontend/src/views/SchedulesView.vue`
  定时任务页面，支持简单周期与 Cron。

- `frontend/src/views/TasksView.vue`
  接口执行任务列表页。

- `frontend/src/views/TaskDetailView.vue`
  接口执行详情页，用于查看结果、步骤结果、事件流、报告链接。

- `frontend/src/views/UiPagesView.vue`
  UI 页面对象与页面方法维护页。

- `frontend/src/views/UiDatasetsView.vue`
  UI 数据集维护页。

- `frontend/src/views/UiScenariosView.vue`
  UI 场景编排页。

- `frontend/src/views/UiRunsView.vue`
  UI 批量运行入口页。

- `frontend/src/views/UiTasksView.vue`
  UI 任务列表页。

- `frontend/src/views/UiTaskDetailView.vue`
  UI 任务详情页，用于查看步骤结果、事件流、trace、截图。

## 运行时链路

### 1. Excel 导入链路

```text
前端 ImportView
  -> 后端 ExcelImportView
  -> ExcelImportService
  -> Project / Environment / Module / ApiDefinition / ApiCase 落库
```

### 2. 接口执行链路

```text
前端 Plans/Tasks 页面
  -> POST /api/test-tasks/
  -> 创建 TestTask
  -> Celery 投递 run_test_task
  -> DbTaskRunner.run()
  -> 写入 TestResult / ScenarioStepResult / TaskEvent
  -> 生成 HTML 报告
  -> 前端 TaskDetailView 轮询或查询展示
```

### 3. UI 自动化链路

```text
前端 UiRuns/UiTasks 页面
  -> POST /api/ui-runs/ 或 /api/ui-tasks/
  -> 创建 UiRun / UiTask
  -> Celery 投递 run_ui_task
  -> UiTaskRunner.run()
  -> 写入 UiStepResult / UiTaskEvent / UiArtifact
  -> 生成 trace.zip / 截图
```

### 4. 定时任务链路

```text
前端 Schedules 页面
  -> 创建 Schedule
  -> scheduler.compute_next_run()
  -> 到期后由 run_due_schedules 扫描
  -> create_task_from_schedule()
  -> 生成 TestTask 并异步执行
```

## 变量、依赖与状态设计

### 1. 变量体系

- 项目变量：`ProjectVariable`
- 环境变量：`EnvironmentVariable`
- 运行时变量：由执行过程中 `extractors` 动态提取

变量优先级：

```text
运行时变量 > 环境变量 > 项目变量
```

支持在 Header、Payload、URL、页面参数中使用：

```text
${token}
${uid}
${CASE_001.data.id}
${phone}
```

### 2. 依赖体系

- 接口用例依赖：`ApiCase.dependencies`
- 场景步骤依赖：`ScenarioStep.dependencies`
- UI 步骤依赖：`UiStep.dependencies`

执行时采用拓扑排序。若上游失败，下游直接标记为 `SKIPPED`，避免错误级联扩大。

### 3. Cookie 设计

- `EnvironmentCookie` 让平台具备“状态型接口链路”能力
- 登录后返回的 Cookie 会被保存到环境维度
- 后续执行会自动回灌进 `requests.Session`

这使平台不仅能跑“无状态接口”，也能跑真实登录后的业务接口链路。

## 为什么这个项目适合拿去面试讲

- 它不是单点功能，而是一整套平台设计。
- 它包含清晰分层：前端展示层、后端控制层、服务层、执行引擎层、任务调度层、持久化层。
- 它同时覆盖工程化与测试领域能力：资产管理、执行编排、变量体系、定时任务、结果可观测、UI 自动化。
- 它既能展示业务理解，也能展示你对架构解耦、异步系统、模型设计、平台化思维的掌握。

## 启动方式

### 1. 安装后端依赖

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

### 2. 启动后端

```bash
.venv/bin/python scripts/dev_backend.py
```

默认会自动：

- 读取 `.env`
- 使用 SQLite
- 迁移数据库
- 创建管理员账号

默认管理员账号：

```text
用户名：admin
密码：admin123
```

### 3. 启动 Celery Worker

```bash
cd backend
../.venv/bin/celery -A OmniQA worker -l info
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

访问：

```text
http://127.0.0.1:5173
```

### 5. 导入样例数据

```bash
DB_ENGINE=sqlite .venv/bin/python backend/manage.py import_sample_cases
```

或直接在前端“Excel 导入”页面上传 `data/控制台首页.xlsx`。

## 特殊文件说明

有些文件不适合直接写大量注释，但你面试时仍然应该知道它们的用途：

- `frontend/package.json`
  前端依赖与脚本清单。

- `frontend/package-lock.json`
  NPM 锁文件，属于依赖解析结果，不建议手工改动。

- `frontend/node_modules/`
  第三方依赖目录，不属于项目源码。

- `reports/`
  运行生成的报告目录，不属于手写源码。

- `backend/db.sqlite3`
  本地调试数据库文件，不属于业务代码。

## 这次文档化改造做了什么

- 为后端核心文件补充了“文件用途、职责边界、与其它模块关系”的文件级中文说明
- 为前端入口、路由、API 封装、布局、编辑器、主要页面补充了文件级中文说明
- 为脚本、配置文件、管理命令、迁移文件补充了用途说明
- 重写 `README.md`，把架构、模块、运行链路、设计思想和关键文件用途串成一条完整叙述线

## 最后建议

如果你要拿这个项目去面试，推荐你按下面的顺序讲：

1. 先讲“这个平台解决什么问题”
2. 再讲“为什么要前后端分离 + Celery 异步执行”
3. 再讲“核心模型和执行链路”
4. 最后讲“我做了哪些可扩展设计和可观测设计”

这样面试官会觉得你讲的是“一个平台架构”，而不是“几个页面 + 几个接口”。
