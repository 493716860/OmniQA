"""
backend/api/management/commands/reset_debug_data.py

文件用途
-------
管理命令：重置本地调试数据（接口依赖链路演示用）。

它会做三件事：
1) 清空大部分业务数据（计划/任务/场景/用例/接口等），保留并重建一套固定链路
2) 写入“登录 → 企业信息 → SKU 列表 → 绑定列表”的接口定义与用例，并设置 dependencies
3) 同时写入一个场景用例（ScenarioCase/ScenarioStep），用于展示“场景步骤依赖 + Cookie/变量传递”

面试/演示价值
------------
这套数据专门用来演示平台的关键卖点：
- 依赖拓扑排序（dependency）
- Cookie 持久化（登录后继续调用业务接口）
- 变量提取与引用（例如从 sku-list 提取 ${sku} 再用于 bind-list）
"""

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
    Schedule,
    TestPlan,
    TestTask,
)


LOGIN_PATH = "/es/ticket/login"
LOGIN_URL = "https://account.geekbang.org/es/ticket/login"
COMPANY_INFO_PATH = "/es/company/info"
SKU_LIST_PATH = "/es/user/sku-list"
BIND_LIST_PATH = "/es/user/bind-list"


class Command(BaseCommand):
    help = "重置本地调试数据，保留登录、企业信息、SKU 列表、绑定列表调试链路。"

    def add_arguments(self, parser):
        parser.add_argument("--project", default="演示项目", help="项目名称")
        parser.add_argument("--module", default="接口依赖调试", help="模块名称")
        parser.add_argument("--environment", default="测试环境(dev)", help="环境名称")
        parser.add_argument("--base-url", default="https://b.geekbang.org", help="环境 Base URL")

    @transaction.atomic
    def handle(self, *args, **options):
        project, _ = Project.objects.get_or_create(name=options["project"])
        environment, _ = Environment.objects.get_or_create(
            project=project,
            name=options["environment"],
            defaults={"base_url": options["base_url"]},
        )
        if not environment.base_url:
            environment.base_url = options["base_url"]
            environment.save(update_fields=["base_url", "updated_at"])

        login_source = ApiCase.objects.filter(api__path__in=[LOGIN_PATH, LOGIN_URL]).order_by("id").first()
        company_source = ApiCase.objects.filter(api__path=COMPANY_INFO_PATH).order_by("id").first()
        sku_source = ApiCase.objects.filter(api__path=SKU_LIST_PATH).order_by("id").first()
        bind_source = ApiCase.objects.filter(api__path=BIND_LIST_PATH).order_by("id").first()

        login_header = login_source.header if login_source else {
            "Referer": "https://account.geekbang.org/biz/signin",
            "Origin": "https://account.geekbang.org",
        }
        login_header = {
            key: value
            for key, value in login_header.items()
            if key.lower() not in {"host", "cookie"}
        }
        login_payload = login_source.payload if login_source else {
            "platform": 3,
            "appid": 2,
            "email": "",
            "password": "",
        }
        login_expect = login_source.expect if login_source else {"code": 0}
        company_header = company_source.header if company_source else {
            "Referer": "https://b.geekbang.org/dashboard/home",
            "Origin": "https://b.geekbang.org",
        }
        company_header = {
            key: value
            for key, value in company_header.items()
            if key not in {"X-Nexus-Token", "X-Nexus-Uid"} and key.lower() not in {"host", "cookie"}
        }
        company_expect = company_source.expect if company_source else {"code": 0}
        business_headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Es-Type": "es",
            "Origin": "https://b.geekbang.org",
            "Referer": "https://b.geekbang.org/dashboard/lesson/manage",
            "X-GEEK-REQ-ID": "nexus-debug@1@web",
        }
        sku_header = sku_source.header if sku_source else business_headers
        sku_header = {
            key: value
            for key, value in sku_header.items()
            if key.lower() not in {"host", "cookie"}
        }
        sku_payload = sku_source.payload if sku_source else {
            "page": 1,
            "size": 20,
            "name": "",
            "goods_type": ["4", "8", "32", "64", "44"],
        }
        sku_expect = sku_source.expect if sku_source else {"__assertions": [
            {"type": "jsonpath", "path": "code", "operator": "equals", "value": 0},
            {"type": "jsonpath", "path": "data", "operator": "exists", "value": True},
        ]}
        bind_header = bind_source.header if bind_source else {
            **business_headers,
            "Referer": "https://b.geekbang.org/dashboard/lesson/assign/record/${sku}",
        }
        bind_header = {
            key: value
            for key, value in bind_header.items()
            if key.lower() not in {"host", "cookie"}
        }
        bind_payload = bind_source.payload if bind_source else {
            "page": 1,
            "page_size": 20,
            "good_sku": "${sku}",
            "org_ids": [],
            "name": "",
            "status": 0,
            "job_title": "",
            "phone": "",
            "user_status": 1,
        }
        bind_expect = bind_source.expect if bind_source else {"__assertions": [
            {"type": "jsonpath", "path": "code", "operator": "equals", "value": 0},
            {"type": "jsonpath", "path": "data", "operator": "exists", "value": True},
        ]}

        Schedule.objects.all().delete()
        TestTask.objects.all().delete()
        TestPlan.objects.all().delete()
        ScenarioCase.objects.all().delete()
        ApiCase.objects.all().delete()
        ApiDefinition.objects.all().delete()
        Module.objects.exclude(project=project).delete()
        Module.objects.filter(project=project).exclude(name=options["module"]).delete()

        module, _ = Module.objects.get_or_create(project=project, name=options["module"])
        module.sort_order = 1
        module.save(update_fields=["sort_order", "updated_at"])

        login_api = ApiDefinition.objects.create(
            module=module,
            name="登录",
            method="POST",
            path=LOGIN_URL,
            default_headers=login_header,
        )
        company_api = ApiDefinition.objects.create(
            module=module,
            name="获取企业信息",
            method="POST",
            path=COMPANY_INFO_PATH,
            default_headers=company_header,
        )
        sku_api = ApiDefinition.objects.create(
            module=module,
            name="获取课程 SKU 列表",
            method="POST",
            path=SKU_LIST_PATH,
            default_headers=sku_header,
        )
        bind_api = ApiDefinition.objects.create(
            module=module,
            name="获取 SKU 绑定用户列表",
            method="POST",
            path=BIND_LIST_PATH,
            default_headers=bind_header,
        )

        login_extractors = [
            {"name": "token", "path": "$.data.token", "required": False},
            {"name": "uid", "path": "$.data.uid", "required": False},
            {"name": "uid_str", "path": "$.data.uid_str", "required": False},
            {"name": "cellphone", "path": "$.data.cellphone", "required": False},
            {"name": "LOGIN_001_data", "path": "$.data", "required": False},
        ]
        login_case = ApiCase.objects.create(
            api=login_api,
            case_code="LOGIN_001",
            title="登录",
            subtitle="正常登录并提取 token",
            header=login_header,
            payload=login_payload,
            expect=login_expect,
            extractors=login_extractors,
            tags=["debug", "login"],
            suite="接口依赖调试",
            level=1,
            estimated_duration_ms=1000,
            sort_order=1,
        )
        company_case = ApiCase.objects.create(
            api=company_api,
            case_code="COMPANY_001",
            title="获取企业信息",
            subtitle="依赖登录后的 cookie",
            header=company_header,
            payload={},
            expect=company_expect,
            extractors=[],
            tags=["debug", "company"],
            suite="接口依赖调试",
            level=1,
            estimated_duration_ms=1000,
            sort_order=2,
        )
        company_case.dependencies.set([login_case])
        sku_extractors = [
            {"name": "sku", "path": "data.list[0].sku", "required": True},
            {"name": "sku_id", "path": "data.list[0].id", "required": False},
            {"name": "sku_name", "path": "data.list[0].name", "required": False},
            {"name": "SKU_LIST_001_data", "path": "data", "required": False},
        ]
        sku_case = ApiCase.objects.create(
            api=sku_api,
            case_code="SKU_LIST_001",
            title="获取课程 SKU 列表",
            subtitle="依赖登录 cookie 并提取 sku",
            header=sku_header,
            payload=sku_payload,
            expect=sku_expect,
            extractors=sku_extractors,
            tags=["debug", "sku", "cookie"],
            suite="接口依赖调试",
            level=1,
            estimated_duration_ms=1000,
            sort_order=3,
        )
        sku_case.dependencies.set([login_case])
        bind_case = ApiCase.objects.create(
            api=bind_api,
            case_code="BIND_LIST_001",
            title="获取 SKU 绑定用户列表",
            subtitle="依赖登录 cookie 和 sku-list 返回的 sku",
            header=bind_header,
            payload=bind_payload,
            expect=bind_expect,
            extractors=[],
            tags=["debug", "bind", "cookie", "sku"],
            suite="接口依赖调试",
            level=1,
            estimated_duration_ms=1000,
            sort_order=4,
        )
        bind_case.dependencies.set([login_case, sku_case])

        scenario = ScenarioCase.objects.create(
            project=project,
            module=module,
            name="登录后获取企业信息",
            description="登录账号建立 cookie，再请求企业信息，用于验证登录 cookie 依赖。",
            level=1,
            sort_order=1,
        )
        login_step = ScenarioStep.objects.create(
            scenario=scenario,
            api=login_api,
            name="1. 登录账号",
            header=login_header,
            payload=login_payload,
            expect=login_expect,
            extractors=login_extractors,
            sort_order=1,
        )
        company_step = ScenarioStep.objects.create(
            scenario=scenario,
            api=company_api,
            name="2. 获取企业信息",
            header=company_header,
            payload={},
            expect=company_expect,
            extractors=[],
            sort_order=2,
        )
        company_step.dependencies.set([login_step])
        sku_step = ScenarioStep.objects.create(
            scenario=scenario,
            api=sku_api,
            name="3. 获取课程 SKU 列表",
            header=sku_header,
            payload=sku_payload,
            expect=sku_expect,
            extractors=sku_extractors,
            sort_order=3,
        )
        sku_step.dependencies.set([login_step])
        bind_step = ScenarioStep.objects.create(
            scenario=scenario,
            api=bind_api,
            name="4. 获取 SKU 绑定用户列表",
            header=bind_header,
            payload=bind_payload,
            expect=bind_expect,
            extractors=[],
            sort_order=4,
        )
        bind_step.dependencies.set([login_step, sku_step])

        login_plan = TestPlan.objects.create(
            name="单接口调试 - 登录",
            project=project,
            environment=environment,
            levels=[1],
            tags=["debug", "login"],
            suites=["接口依赖调试"],
        )
        login_plan.cases.set([login_case])

        dependency_plan = TestPlan.objects.create(
            name="接口依赖调试 - 登录 + 企业信息",
            project=project,
            environment=environment,
            levels=[1],
            tags=["debug"],
            suites=["接口依赖调试"],
        )
        dependency_plan.cases.set([login_case, company_case])
        sku_dependency_plan = TestPlan.objects.create(
            name="接口依赖调试 - 登录 + SKU + 绑定列表",
            project=project,
            environment=environment,
            levels=[1],
            tags=["debug"],
            suites=["接口依赖调试"],
        )
        sku_dependency_plan.cases.set([login_case, sku_case, bind_case])

        scenario_plan = TestPlan.objects.create(
            name="场景调试 - 登录后获取企业信息",
            project=project,
            environment=environment,
            levels=[1],
        )
        scenario_plan.scenarios.set([scenario])

        self.stdout.write(self.style.SUCCESS("调试数据已重置完成"))
        self.stdout.write(f"项目: {project.name}")
        self.stdout.write(f"环境: {environment.name} / {environment.base_url}")
        self.stdout.write(f"接口: {LOGIN_URL}, {COMPANY_INFO_PATH}, {SKU_LIST_PATH}, {BIND_LIST_PATH}")
        self.stdout.write(
            "计划: 单接口调试 - 登录 / 接口依赖调试 - 登录 + 企业信息 / "
            "接口依赖调试 - 登录 + SKU + 绑定列表 / 场景调试 - 登录后获取企业信息"
        )
