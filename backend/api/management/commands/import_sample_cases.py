"""
backend/api/management/commands/import_sample_cases.py

文件用途
-------
管理命令：导入样例 Excel 用例（默认 data/控制台首页.xlsx）。

使用场景：
- 本地首次启动后，数据库为空；通过该命令快速灌入一套可跑的演示数据
- 面试/演示时“一键准备数据”，减少手工操作

核心逻辑复用 services/importer.py 的 ExcelImportService，避免两套导入实现。
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.services.importer import ExcelImportService


class Command(BaseCommand):
    help = "导入 data 目录下的样例 Excel 用例，方便本地验证平台功能。"

    def add_arguments(self, parser):
        parser.add_argument("--file", default="data/控制台首页.xlsx", help="Excel 文件路径")
        parser.add_argument("--project", default="演示项目", help="项目名称")
        parser.add_argument("--module", default="控制台首页", help="模块名称")
        parser.add_argument("--environment", default="测试环境(dev)", help="环境名称")
        parser.add_argument("--base-url", default="https://b.geekbang.org", help="环境 Base URL")

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"找不到 Excel 文件: {file_path}")

        with file_path.open("rb") as excel_file:
            result = ExcelImportService().import_file(
                file_obj=excel_file,
                project_name=options["project"],
                module_name=options["module"],
                environment_name=options["environment"],
                base_url=options["base_url"],
            )

        self.stdout.write(self.style.SUCCESS("样例用例导入完成"))
        self.stdout.write(
            f"project={result['project']} environment={result['environment']} "
            f"created={result['created']} updated={result['updated']} failed={result['failed']}"
        )
        if result["errors"]:
            for error in result["errors"]:
                self.stdout.write(self.style.WARNING(str(error)))
