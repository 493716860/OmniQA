"""
backend/api/management/commands/seed_demo_data.py

文件用途
-------
一键写入“接口测试 + UI 测试”演示数据，方便你本地调试与面试演示。

为什么需要它？
-------------
你在本地调试过程中可能会频繁重建数据库/迁移，导致平台页面里看不到任何项目、环境、用例与 UI 场景。
该命令提供一个“可重复执行、幂等(upsert) 的 demo 数据初始化入口”，运行后你将能在系统中看到：

接口自动化（API）：
- 1 个项目 + 1 个环境 + 1 个模块
- 4 个接口定义 + 4 条接口用例（含依赖、变量提取与变量引用示例）
- 1 个测试计划（覆盖上述用例）

UI 自动化（Playwright）：
- 1 个 UI 页面对象（PO）+ 3 个元素 + 1 个页面方法 + 4 个方法步骤
- 1 个数据集 + 1 条数据行（DDT）
- 1 个 UI 场景（编排调用页面方法）

注意
----
- 本命令不会清空你的现有数据；如果同名数据已存在，会尽量 update_or_create。
- 部分页面元素定位器是 demo 示例（xpath/css），用于演示“PO/DDT/编排”能力，不保证对任何站点长期稳定。
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import (
    ApiCase,
    ApiDefinition,
    Environment,
    Module,
    Project,
    ScenarioCase,
    ScenarioStep,
    TestPlan,
    UiDataset,
    UiDatasetRow,
    UiElement,
    UiMethodStep,
    UiPage,
    UiPageMethod,
    UiScenario,
    UiScenarioStep,
)


class Command(BaseCommand):
    help = "写入一套接口测试 + UI 测试演示数据（可重复执行、不会清库）。"

    def add_arguments(self, parser):
        # API demo
        parser.add_argument("--project", default="演示项目", help="项目名称（不存在会自动创建）")
        parser.add_argument("--module", default="接口依赖演示", help="模块名称（不存在会自动创建）")
        parser.add_argument("--environment", default="测试环境(dev)", help="环境名称（不存在会自动创建）")
        parser.add_argument("--base-url", default="https://b.geekbang.org", help="环境 Base URL")

        # UI demo
        parser.add_argument("--ui-page", default="DemoLoginPage", help="UI 页面对象名称")
        parser.add_argument("--ui-url", default="https://account.geekbang.org/biz/signin?type=0", help="UI 页面 URL")
        parser.add_argument("--ui-dataset", default="demo_login_dataset", help="UI 数据集名称")
        parser.add_argument("--ui-scenario", default="Demo - 登录场景", help="UI 场景名称")
        parser.add_argument("--phone", default="18700001111", help="DDT 演示手机号")
        parser.add_argument("--password", default="123456", help="DDT 演示密码")

    @transaction.atomic
    def handle(self, *args, **options):
        project, _ = Project.objects.get_or_create(name=options["project"])

        env, _ = Environment.objects.get_or_create(
            project=project,
            name=options["environment"],
            defaults={"base_url": options["base_url"]},
        )
        if options["base_url"] and env.base_url != options["base_url"]:
            env.base_url = options["base_url"]
            env.save(update_fields=["base_url", "updated_at"])

        module, _ = Module.objects.get_or_create(project=project, name=options["module"])
        if module.sort_order != 1:
            module.sort_order = 1
            module.save(update_fields=["sort_order", "updated_at"])

        # -----------------------------
        # 接口定义（ApiDefinition）
        # -----------------------------
        login_api, _ = ApiDefinition.objects.update_or_create(
            module=module,
            path="/es/ticket/login",
            method="POST",
            defaults={
                "name": "登录（演示）",
                "default_headers": {
                    "Content-Type": "application/json",
                    "Origin": "https://account.geekbang.org",
                    "Referer": "https://account.geekbang.org/biz/signin",
                },
            },
        )

        company_api, _ = ApiDefinition.objects.update_or_create(
            module=module,
            path="/es/company/info",
            method="POST",
            defaults={
                "name": "获取企业信息（演示）",
                "default_headers": {"Content-Type": "application/json"},
            },
        )

        sku_api, _ = ApiDefinition.objects.update_or_create(
            module=module,
            path="/es/user/sku-list",
            method="POST",
            defaults={
                "name": "获取 SKU 列表（演示）",
                "default_headers": {"Content-Type": "application/json"},
            },
        )

        bind_api, _ = ApiDefinition.objects.update_or_create(
            module=module,
            path="/es/user/bind-list",
            method="POST",
            defaults={
                "name": "获取 SKU 绑定用户（演示）",
                "default_headers": {"Content-Type": "application/json"},
            },
        )

        # -----------------------------
        # 接口用例（ApiCase）
        # -----------------------------
        login_extractors = [
            {"name": "token", "path": "$.data.token", "required": False},
            {"name": "uid", "path": "$.data.uid", "required": False},
            {"name": "LOGIN_001_data", "path": "$.data", "required": False},
        ]

        login_case, _ = ApiCase.objects.update_or_create(
            api=login_api,
            case_code="LOGIN_001",
            is_setup=True,
            defaults={
                "title": "登录",
                "subtitle": "正常登录并提取 token（演示）",
                "header": login_api.default_headers,
                "payload": {"platform": 3, "appid": 2, "email": "", "password": ""},
                "expect": {"__assertions": [{"type": "status_code", "value": 200}]},
                "extractors": login_extractors,
                "tags": ["demo", "login"],
                "suite": "接口依赖演示",
                "level": 1,
                "estimated_duration_ms": 1000,
                "enabled": True,
                "sort_order": 1,
            },
        )

        company_case, _ = ApiCase.objects.update_or_create(
            api=company_api,
            case_code="COMPANY_001",
            is_setup=False,
            defaults={
                "title": "获取企业信息",
                "subtitle": "依赖登录 cookie（演示）",
                "header": company_api.default_headers,
                "payload": {},
                "expect": {"__assertions": [{"type": "status_code", "value": 200}]},
                "extractors": [],
                "tags": ["demo", "company"],
                "suite": "接口依赖演示",
                "level": 1,
                "estimated_duration_ms": 1000,
                "enabled": True,
                "sort_order": 2,
            },
        )

        sku_case, _ = ApiCase.objects.update_or_create(
            api=sku_api,
            case_code="SKU_LIST_001",
            is_setup=False,
            defaults={
                "title": "获取 SKU 列表",
                "subtitle": "依赖登录并提取 sku（演示）",
                "header": sku_api.default_headers,
                "payload": {"page": 1, "size": 20, "name": ""},
                "expect": {"__assertions": [{"type": "status_code", "value": 200}]},
                "extractors": [{"name": "sku", "path": "data.list[0].sku", "required": False}],
                "tags": ["demo", "sku"],
                "suite": "接口依赖演示",
                "level": 1,
                "estimated_duration_ms": 1000,
                "enabled": True,
                "sort_order": 3,
            },
        )

        bind_case, _ = ApiCase.objects.update_or_create(
            api=bind_api,
            case_code="BIND_LIST_001",
            is_setup=False,
            defaults={
                "title": "获取 SKU 绑定用户列表",
                "subtitle": "依赖登录与 sku 变量（演示）",
                "header": bind_api.default_headers,
                "payload": {"page": 1, "page_size": 20, "good_sku": "${sku}"},
                "expect": {"__assertions": [{"type": "status_code", "value": 200}]},
                "extractors": [],
                "tags": ["demo", "bind", "sku"],
                "suite": "接口依赖演示",
                "level": 1,
                "estimated_duration_ms": 1000,
                "enabled": True,
                "sort_order": 4,
            },
        )

        # 依赖关系（幂等写入）
        company_case.dependencies.set([login_case])
        sku_case.dependencies.set([login_case])
        bind_case.dependencies.set([login_case, sku_case])

        # -----------------------------
        # 场景用例（ScenarioCase/ScenarioStep）
        # -----------------------------
        scenario, _ = ScenarioCase.objects.get_or_create(
            project=project,
            module=module,
            name="演示场景：登录后获取企业信息",
            defaults={"description": "演示场景步骤依赖 + Cookie/变量传递", "level": 1, "enabled": True, "sort_order": 1},
        )
        # 为了幂等，简单起见：按名称 upsert 两个步骤
        step_login, _ = ScenarioStep.objects.update_or_create(
            scenario=scenario,
            name="1. 登录",
            defaults={
                "api": login_api,
                "header": login_case.header,
                "payload": login_case.payload,
                "expect": login_case.expect,
                "extractors": login_extractors,
                "enabled": True,
                "sort_order": 1,
            },
        )
        step_company, _ = ScenarioStep.objects.update_or_create(
            scenario=scenario,
            name="2. 获取企业信息",
            defaults={
                "api": company_api,
                "header": company_case.header,
                "payload": company_case.payload,
                "expect": company_case.expect,
                "extractors": [],
                "enabled": True,
                "sort_order": 2,
            },
        )
        step_company.dependencies.set([step_login])

        # -----------------------------
        # 测试计划（TestPlan）
        # -----------------------------
        plan, _ = TestPlan.objects.get_or_create(
            name="演示计划 - 接口依赖链路",
            project=project,
            environment=env,
            defaults={"levels": [1], "tags": ["demo"], "suites": ["接口依赖演示"]},
        )
        plan.cases.set([company_case, sku_case, bind_case])  # setup 用例由执行引擎自动额外选取

        # -----------------------------
        # UI 自动化演示数据（PO + DDT）
        # -----------------------------
        ui_page, _ = UiPage.objects.get_or_create(
            project=project,
            name=options["ui_page"],
            defaults={"module": module, "url": options["ui_url"], "enabled": True},
        )
        if ui_page.url != options["ui_url"] or ui_page.module_id != module.id:
            ui_page.url = options["ui_url"]
            ui_page.module = module
            ui_page.save(update_fields=["url", "module", "updated_at"])

        def upsert_element(name: str, locator: dict):
            element, created = UiElement.objects.get_or_create(
                page=ui_page,
                name=name,
                defaults={"locator": locator, "enabled": True},
            )
            if not created and (element.locator or {}) != (locator or {}):
                element.locator = locator
                element.save(update_fields=["locator", "updated_at"])
            return element

        # 这里用 xpath 作为 demo（与 seed_ui_demo 逻辑一致）
        phone_input = upsert_element(
            "phone_input",
            {"strategy": "xpath", "value": '//*[@id="app"]/div/div/div[2]/div[1]/div/div[2]/div[2]/div[1]/input'},
        )
        password_input = upsert_element(
            "password_input",
            {"strategy": "xpath", "value": '//*[@id="app"]/div/div/div[2]/div[1]/div/div[2]/div[2]/div[2]/input'},
        )
        login_button = upsert_element(
            "login_button",
            {"strategy": "xpath", "value": '//*[@id="app"]/div/div/div[2]/div[1]/div/div[2]/div[2]/div[4]'},
        )

        ui_method, _ = UiPageMethod.objects.get_or_create(page=ui_page, name="login", defaults={"enabled": True})
        # 保持步骤幂等：先删再建（只影响该 method，不影响其它数据）
        UiMethodStep.objects.filter(method=ui_method).delete()
        UiMethodStep.objects.create(
            method=ui_method,
            sort_order=1,
            name="打开登录页",
            type=UiMethodStep.Type.GOTO,
            element=None,
            params={},  # 不填则 runner 会用 page.url
            assertions={},
            enabled=True,
        )
        UiMethodStep.objects.create(
            method=ui_method,
            sort_order=2,
            name="输入手机号",
            type=UiMethodStep.Type.FILL,
            element=phone_input,
            params={"value": "${phone}", "timeout_ms": 10000},
            assertions={},
            enabled=True,
        )
        UiMethodStep.objects.create(
            method=ui_method,
            sort_order=3,
            name="输入密码",
            type=UiMethodStep.Type.FILL,
            element=password_input,
            params={"value": "${password}", "timeout_ms": 10000},
            assertions={},
            enabled=True,
        )
        UiMethodStep.objects.create(
            method=ui_method,
            sort_order=4,
            name="点击登录",
            type=UiMethodStep.Type.CLICK,
            element=login_button,
            params={"timeout_ms": 10000},
            assertions={},
            enabled=True,
        )

        dataset, _ = UiDataset.objects.get_or_create(
            project=project,
            name=options["ui_dataset"],
            defaults={"schema": {"sensitive_fields": ["password"]}, "enabled": True},
        )
        schema = dataset.schema or {}
        sensitive = set(schema.get("sensitive_fields") or [])
        sensitive.add("password")
        schema["sensitive_fields"] = sorted(sensitive)
        dataset.schema = schema
        dataset.save(update_fields=["schema", "updated_at"])

        UiDatasetRow.objects.update_or_create(
            dataset=dataset,
            row_key=options["phone"],
            defaults={"data": {"phone": options["phone"], "password": options["password"]}, "enabled": True},
        )

        ui_scenario, _ = UiScenario.objects.get_or_create(
            project=project,
            module=module,
            name=options["ui_scenario"],
            defaults={"description": "演示：PO + DDT + 场景编排", "enabled": True, "level": 1},
        )
        UiScenarioStep.objects.filter(scenario=ui_scenario).delete()
        UiScenarioStep.objects.create(
            scenario=ui_scenario,
            sort_order=1,
            type=UiScenarioStep.Type.CALL_METHOD,
            method=ui_method,
            name="调用 login 页面方法",
            enabled=True,
        )

        self.stdout.write(self.style.SUCCESS("✅ Demo 数据已写入（接口 + UI）"))
        self.stdout.write(f"Project: {project.name} | Env: {env.name} ({env.base_url}) | Module: {module.name}")
        self.stdout.write("API Cases: LOGIN_001 (setup), COMPANY_001, SKU_LIST_001, BIND_LIST_001")
        self.stdout.write(f"TestPlan: {plan.name}")
        self.stdout.write(f"UI Page: {ui_page.name} | UI Dataset: {dataset.name} | UI Scenario: {ui_scenario.name}")

