import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import urlparse

import yaml
from openpyxl import load_workbook

from api.models import ApiCase, ApiDefinition, Environment, Module, Project

REQUIRED_HEADERS = {"id", "title", "subtitle", "level", "url", "method", "header", "payload", "expect", "rely"}


@dataclass
class ImportStats:
    created: int = 0
    updated: int = 0
    failed: int = 0
    errors: list = field(default_factory=list)

    def as_dict(self):
        return {
            "created": self.created,
            "updated": self.updated,
            "failed": self.failed,
            "errors": self.errors,
        }


def safe_parse_cell(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    raw = str(value).strip()
    if raw in ("", "None", "null"):
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        parsed = yaml.safe_load(raw)
        return default if parsed is None else parsed


def normalize_path(url):
    if not url:
        return "/"
    parsed = urlparse(str(url))
    if parsed.scheme and parsed.netloc:
        path = parsed.path or "/"
        return str(PurePosixPath(path))
    return str(url)


def get_cell_map(sheet):
    headers = {}
    for cell in sheet[1]:
        if cell.value is not None:
            key = str(cell.value).strip().lower()
            if key == "subtitle":
                key = "subtitle"
            headers[key] = cell.column
    missing = REQUIRED_HEADERS - set(headers)
    if missing:
        raise ValueError(f"缺少表头: {', '.join(sorted(missing))}")
    return headers


def row_value(sheet, headers, row_idx, key):
    value = sheet.cell(row=row_idx, column=headers[key]).value
    return "" if value is None else value


class ExcelImportService:
    def import_file(self, *, file_obj, project_name, module_name="", environment_name="测试环境(dev)", base_url=""):
        wb = load_workbook(file_obj, read_only=True, data_only=True)
        try:
            if "data" not in wb.sheetnames:
                raise ValueError("Excel 必须包含 data 页签")

            project, _ = Project.objects.get_or_create(name=project_name)
            env, _ = Environment.objects.get_or_create(
                project=project,
                name=environment_name,
                defaults={"base_url": base_url},
            )
            if base_url and env.base_url != base_url:
                env.base_url = base_url
                env.save(update_fields=["base_url", "updated_at"])

            stats = ImportStats()
            for sheet_name, is_setup in (("setup", True), ("data", False)):
                if sheet_name not in wb.sheetnames:
                    continue
                self._import_sheet(wb[sheet_name], project, module_name or project_name, stats, is_setup)
            return {"project": project.id, "environment": env.id, **stats.as_dict()}
        finally:
            wb.close()

    def _import_sheet(self, sheet, project, module_name, stats, is_setup):
        headers = get_cell_map(sheet)
        module, _ = Module.objects.get_or_create(project=project, name=module_name)
        pending_dependencies = []
        for row_idx in range(2, sheet.max_row + 1):
            case_code = row_value(sheet, headers, row_idx, "id")
            if not case_code:
                break
            try:
                title = str(row_value(sheet, headers, row_idx, "title") or "")
                method = str(row_value(sheet, headers, row_idx, "method") or "POST").upper()
                raw_url = row_value(sheet, headers, row_idx, "url")
                path = normalize_path(raw_url)
                header = safe_parse_cell(row_value(sheet, headers, row_idx, "header"), {})
                payload = safe_parse_cell(row_value(sheet, headers, row_idx, "payload"), {})
                expect = safe_parse_cell(row_value(sheet, headers, row_idx, "expect"), {})
                if header and not isinstance(header, dict):
                    raise ValueError("Header 必须是 JSON/YAML 对象")

                api, _ = ApiDefinition.objects.update_or_create(
                    module=module,
                    path=path,
                    method=method,
                    defaults={"name": title or path},
                )
                case, created = ApiCase.objects.update_or_create(
                    api=api,
                    case_code=str(case_code),
                    is_setup=is_setup,
                    defaults={
                        "title": title,
                        "subtitle": str(row_value(sheet, headers, row_idx, "subtitle") or ""),
                        "header": header or {},
                        "payload": payload,
                        "expect": expect,
                        "extractors": default_extractors(case_code, title, is_setup),
                        "level": int(row_value(sheet, headers, row_idx, "level") or 1),
                        "rely": str(row_value(sheet, headers, row_idx, "rely") or ""),
                        "sort_order": row_idx,
                        "enabled": True,
                    },
                )
                rely = str(row_value(sheet, headers, row_idx, "rely") or "").strip()
                if rely:
                    pending_dependencies.append((case, parse_rely_codes(rely)))
                stats.created += 1 if created else 0
                stats.updated += 0 if created else 1
            except Exception as exc:
                stats.failed += 1
                stats.errors.append({"sheet": sheet.title, "row": row_idx, "error": str(exc)})

        for case, codes in pending_dependencies:
            dependencies = ApiCase.objects.filter(
                api__module__project=project,
                case_code__in=codes,
            )
            case.dependencies.set(dependencies)


def parse_rely_codes(raw):
    return [item.strip() for item in raw.replace("，", ",").split(",") if item.strip()]


def default_extractors(case_code, title, is_setup):
    if not is_setup and "登录" not in str(title):
        return []
    prefix = str(case_code)
    return [
        {"name": "token", "path": "$.data.token", "required": False},
        {"name": "uid", "path": "$.data.uid", "required": False},
        {"name": "uid_str", "path": "$.data.uid_str", "required": False},
        {"name": "cellphone", "path": "$.data.cellphone", "required": False},
        {"name": f"{prefix}_data", "path": "$.data", "required": False},
    ]
