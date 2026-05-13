"""
创建“获取企业信息”的双账号场景：
- 使用已存在的 login 用例（手机号尾号 0001 / 8817）
- info 接口用例若仅有默认用例，则复制出两条带 session_key 的用例：INFO_0001 / INFO_8817
- 创建两条场景用例：获取企业信息-0001 / 获取企业信息-8817
  每条场景包含两步：登录 -> 获取企业信息，并建立依赖关系

说明：
- 可重复执行；会覆盖（重建）目标场景的步骤，确保结果一致。
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import ApiCase, ApiDefinition, ScenarioCase, ScenarioStep


class Command(BaseCommand):
    help = "创建双账号“获取企业信息”场景（0001/8817）"

    def add_arguments(self, parser):
        parser.add_argument("--tail-a", default="0001", help="账号A手机号尾号（默认 0001）")
        parser.add_argument("--tail-b", default="8817", help="账号B手机号尾号（默认 8817）")

    def handle(self, *args, **options):
        tail_a = str(options["tail_a"]).strip()
        tail_b = str(options["tail_b"]).strip()
        if not tail_a or not tail_b:
            raise CommandError("tail-a / tail-b 不能为空")

        with transaction.atomic():
            login_a = self._find_login_case(tail_a)
            login_b = self._find_login_case(tail_b)

            info_api = self._find_info_api(project_id=login_a.api.module.project_id)
            info_base_case = self._find_or_create_info_base_case(info_api)

            info_a = self._ensure_info_case(info_api, info_base_case, tail_a)
            info_b = self._ensure_info_case(info_api, info_base_case, tail_b)

            self._ensure_scenario(
                project_id=login_a.api.module.project_id,
                module_id=info_api.module_id,
                name=f"获取企业信息-{tail_a}",
                login_case=login_a,
                info_case=info_a,
            )
            self._ensure_scenario(
                project_id=login_b.api.module.project_id,
                module_id=info_api.module_id,
                name=f"获取企业信息-{tail_b}",
                login_case=login_b,
                info_case=info_b,
            )

        self.stdout.write(self.style.SUCCESS("已创建/更新 2 条“获取企业信息”场景用例。"))

    def _find_login_case(self, tail: str) -> ApiCase:
        # 优先按 session_key 匹配（我们已引入 session_key 隔离）
        qs = (
            ApiCase.objects.select_related("api", "api__module")
            .filter(api__path__icontains="login")
            .filter(session_key=tail)
            .order_by("id")
        )
        if qs.exists():
            return qs.first()

        # 兜底：payload/标题里包含尾号
        qs = (
            ApiCase.objects.select_related("api", "api__module")
            .filter(api__path__icontains="login")
            .filter(title__icontains=tail)
            .order_by("id")
        )
        if qs.exists():
            case = qs.first()
            case.session_key = tail
            case.save(update_fields=["session_key"])
            return case

        raise CommandError(f"未找到 login 用例：手机号尾号 {tail}（请先在用例列表创建好）")

    def _find_info_api(self, project_id: int) -> ApiDefinition:
        qs = ApiDefinition.objects.select_related("module").filter(module__project_id=project_id, path__icontains="info")
        if qs.count() == 1:
            return qs.first()
        if qs.count() == 0:
            raise CommandError("未找到 info 接口定义（path 包含 info）")
        raise CommandError(f"找到多个 info 接口定义（{qs.count()}），请手动确认并改造命令筛选条件")

    def _find_or_create_info_base_case(self, info_api: ApiDefinition) -> ApiCase:
        qs = ApiCase.objects.filter(api=info_api, enabled=True, is_setup=False).order_by("id")
        if qs.exists():
            return qs.first()
        return ApiCase.objects.create(
            api=info_api,
            case_code="INFO_BASE",
            title=info_api.name or "获取企业信息",
            subtitle="基础用例（自动创建）",
            header={},
            payload={},
            expect={},
            extractors=[],
            tags=[],
            suite="",
            estimated_duration_ms=1000,
            level=1,
            rely="",
            is_setup=False,
            enabled=True,
            sort_order=0,
            session_key="default",
        )

    def _ensure_info_case(self, info_api: ApiDefinition, base: ApiCase, tail: str) -> ApiCase:
        case_code = f"INFO_{tail}"
        defaults = {
            "title": base.title,
            "subtitle": f"获取企业信息 {tail}",
            "header": base.header or {},
            "payload": base.payload or {},
            "expect": base.expect or {},
            "extractors": base.extractors or [],
            "tags": base.tags or [],
            "suite": base.suite or "",
            "estimated_duration_ms": base.estimated_duration_ms or 1000,
            "level": base.level or 1,
            "rely": base.rely or "",
            "is_setup": False,
            "enabled": True,
            "sort_order": base.sort_order or 0,
            "session_key": tail,
        }
        case, _ = ApiCase.objects.update_or_create(api=info_api, case_code=case_code, is_setup=False, defaults=defaults)
        return case

    def _ensure_scenario(self, project_id: int, module_id: int, name: str, login_case: ApiCase, info_case: ApiCase):
        scenario, _ = ScenarioCase.objects.update_or_create(
            project_id=project_id,
            name=name,
            defaults={
                "module_id": module_id,
                "description": f"企业账号尾号 {login_case.session_key} 登录后调用 info 获取企业信息",
                "level": 1,
                "enabled": True,
                "sort_order": 0,
            },
        )

        # 重建步骤，避免历史步骤残留导致混乱
        scenario.steps.all().delete()

        step_login = ScenarioStep.objects.create(
            scenario=scenario,
            api=login_case.api,
            case=login_case,
            name=f"登录（{login_case.session_key}）",
            session_key=login_case.session_key or "default",
            header={},
            payload={},
            expect={},
            extractors=[],
            enabled=True,
            sort_order=1,
        )
        step_info = ScenarioStep.objects.create(
            scenario=scenario,
            api=info_case.api,
            case=info_case,
            name=f"获取企业信息（{info_case.session_key}）",
            session_key=info_case.session_key or "default",
            header={},
            payload={},
            expect={},
            extractors=[],
            enabled=True,
            sort_order=2,
        )
        step_info.dependencies.add(step_login)

