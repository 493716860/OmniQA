"""
backend/api/management/commands/seed_ui_demo.py

文件用途
-------
管理命令：写入一套 UI 自动化演示数据（PO + DDT + 场景编排）。

生成内容：
- UiPage：页面对象（含 URL）
- UiElement：元素库（示例使用 xpath 定位）
- UiPageMethod / UiMethodStep：页面方法与步骤（goto/fill/click 等）
- UiDataset / UiDatasetRow：数据集与演示数据行（phone/password），步骤参数支持 ${field} 替换
- UiScenario / UiScenarioStep：场景编排（当前 MVP 以“调用页面方法”为主）

配合 backend/api/services/ui_runner.py，可以直接在前端创建 UiRun/UiTask 并执行。
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import (
    Module,
    Project,
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
    help = "写入一套 UI(P0+DDT) 演示数据：页面对象/元素/页面方法/数据集/场景编排。"

    def add_arguments(self, parser):
        parser.add_argument("--project", default="UI演示项目", help="项目名称（不存在会自动创建）")
        parser.add_argument("--module", default="登录模块", help="模块名称（不存在会自动创建）")
        parser.add_argument("--page", default="GeekBangLoginPage", help="页面对象名称")
        parser.add_argument(
            "--url",
            default="https://account.geekbang.org/biz/signin?type=0",
            help="页面完整 URL",
        )
        parser.add_argument("--dataset", default="geekbang_login", help="数据集名称")
        parser.add_argument("--scenario", default="极客时间-登录", help="场景名称")
        parser.add_argument("--phone", default="18700001111", help="演示手机号")
        parser.add_argument("--password", default="123456", help="演示密码")

    @transaction.atomic
    def handle(self, *args, **options):
        project, _ = Project.objects.get_or_create(name=options["project"])
        module, _ = Module.objects.get_or_create(project=project, name=options["module"])

        # Page
        page, _ = UiPage.objects.get_or_create(
            project=project,
            name=options["page"],
            defaults={"module": module, "url": options["url"], "enabled": True},
        )
        if page.url != options["url"]:
            page.url = options["url"]
            page.module = module
            page.save(update_fields=["url", "module", "updated_at"])

        # Elements (xpath)
        def upsert_element(name, xpath):
            element, created = UiElement.objects.get_or_create(
                page=page,
                name=name,
                defaults={"locator": {"strategy": "xpath", "value": xpath}, "enabled": True},
            )
            if not created:
                element.locator = {"strategy": "xpath", "value": xpath}
                element.save(update_fields=["locator", "updated_at"])
            return element

        phone_input = upsert_element(
            "phone_input",
            '//*[@id="app"]/div/div/div[2]/div[1]/div/div[2]/div[2]/div[1]/input',
        )
        password_input = upsert_element(
            "password_input",
            '//*[@id="app"]/div/div/div[2]/div[1]/div/div[2]/div[2]/div[2]/input',
        )
        login_button = upsert_element(
            "login_button",
            '//*[@id="app"]/div/div/div[2]/div[1]/div/div[2]/div[2]/div[4]',
        )

        # Page method
        method, _ = UiPageMethod.objects.get_or_create(page=page, name="login", defaults={"enabled": True})

        # Method steps (清理后重建，避免重复)
        UiMethodStep.objects.filter(method=method).delete()
        UiMethodStep.objects.create(
            method=method,
            sort_order=1,
            name="打开登录页",
            type=UiMethodStep.Type.GOTO,
            element=None,
            params={},  # 不填则 runner 会用 page.url
            assertions={},
            enabled=True,
        )
        UiMethodStep.objects.create(
            method=method,
            sort_order=2,
            name="输入手机号",
            type=UiMethodStep.Type.FILL,
            element=phone_input,
            params={"value": "${phone}", "timeout_ms": 10000},
            assertions={},
            enabled=True,
        )
        UiMethodStep.objects.create(
            method=method,
            sort_order=3,
            name="输入密码",
            type=UiMethodStep.Type.FILL,
            element=password_input,
            params={"value": "${password}", "timeout_ms": 10000},
            assertions={},
            enabled=True,
        )
        UiMethodStep.objects.create(
            method=method,
            sort_order=4,
            name="点击登录",
            type=UiMethodStep.Type.CLICK,
            element=login_button,
            params={"timeout_ms": 10000},
            assertions={},
            enabled=True,
        )

        # Dataset + row
        dataset, _ = UiDataset.objects.get_or_create(
            project=project,
            name=options["dataset"],
            defaults={"schema": {"sensitive_fields": ["password"]}, "enabled": True},
        )
        # 合并 sensitive_fields
        schema = dataset.schema or {}
        sf = set(schema.get("sensitive_fields") or [])
        sf.add("password")
        schema["sensitive_fields"] = sorted(sf)
        dataset.schema = schema
        dataset.save(update_fields=["schema", "updated_at"])

        UiDatasetRow.objects.get_or_create(
            dataset=dataset,
            row_key=options["phone"],
            defaults={"data": {"phone": options["phone"], "password": options["password"]}, "enabled": True},
        )

        # Scenario + scenario steps (只编排方法)
        scenario, _ = UiScenario.objects.get_or_create(
            project=project,
            module=module,
            name=options["scenario"],
            defaults={"enabled": True},
        )
        UiScenarioStep.objects.filter(scenario=scenario).delete()
        UiScenarioStep.objects.create(
            scenario=scenario,
            sort_order=1,
            type=UiScenarioStep.Type.CALL_METHOD,
            method=method,
            name="调用登录方法",
            enabled=True,
        )

        self.stdout.write(self.style.SUCCESS("UI 演示数据已写入"))
        self.stdout.write(f"project={project.name} module={module.name}")
        self.stdout.write(f"page={page.name} method={method.name}")
        self.stdout.write(f"dataset={dataset.name} (rows={dataset.rows.count()})")
        self.stdout.write(f"scenario={scenario.name} (steps={scenario.scenario_steps.count()})")
