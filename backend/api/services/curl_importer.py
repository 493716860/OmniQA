"""
backend/api/services/curl_importer.py

文件用途
-------
cURL 导入服务：把“从浏览器/抓包工具复制出来的 cURL 命令”转换为平台内部接口定义与用例。

提供两类能力：
1) preview(...)：只解析 + 生成预览结构（告诉前端将创建/复用哪个 ApiDefinition/ApiCase）
2) import_curl(...)：事务内落库（upsert ApiDefinition + upsert ApiCase）

解析范围与约束
--------------
- 仅支持标准 HTTP 请求类参数：-X/-H/-d/--data*、--cookie、--url 等
- 明确拒绝高风险/高复杂特性：
  - 不支持命令替换/HereDoc（$() / `...` / <<EOF），避免注入与不确定性
  - 不支持 form-data / 文件上传（-F/--form）
- URL 必须是绝对地址（含 scheme + netloc），并拆分出 base_url/path/query

与执行引擎的衔接
----------------
为了支持“跨域/多域名接口”，导入后的 ApiCase.payload 可能包含：
  {"__base_url": "...", "__query": {...}, "__body": {...}}
db_runner.py 的 split_request_payload()/build_url() 会识别这些字段并正确拼接 URL。
"""

import json
import re
import shlex
from dataclasses import asdict, dataclass
from urllib.parse import parse_qsl, urlparse

from django.db import transaction

from api.models import ApiCase, ApiDefinition, Module


DEFAULT_CASE_PREFIX = "CURL_AUTO_"
DEFAULT_CASE_SUBTITLE = "cURL 导入默认用例"
DEFAULT_PLACEHOLDER_PATTERN = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/.+")
ANSI_C_QUOTED_PATTERN = re.compile(r"\$'((?:\\.|[^'])*)'")


class CurlImportError(ValueError):
    pass


@dataclass
class ParsedCurlRequest:
    method: str
    url: str
    base_url: str
    path: str
    query: dict
    headers: dict
    payload: object
    content_type: str

    def to_dict(self):
        return asdict(self)


class CurlImportService:
    def preview(self, *, module_id, curl_text, name="", case_title="", case_code=""):
        module = self._load_module(module_id)
        parsed = self.parse(curl_text)
        api = ApiDefinition.objects.filter(module=module, method=parsed.method, path=parsed.path).first()
        api_action = "reused" if api else "created"
        default_case_code = case_code or (f"{DEFAULT_CASE_PREFIX}{api.id}" if api else "")
        api_case = ApiCase.objects.filter(api=api, case_code=default_case_code).first() if api and default_case_code else None
        case_action = "updated" if api_case else "created"
        return {
            "parsed": parsed.to_dict(),
            "api_definition": {
                "id": api.id if api else None,
                "name": self._resolve_api_name(parsed, name or (api.name if api else "")),
                "method": parsed.method,
                "path": parsed.path,
                "module": module.id,
                "module_name": module.name,
                "default_headers": self._merge_headers(api.default_headers if api else {}, parsed.headers),
            },
            "api_case": {
                "id": api_case.id if api_case else None,
                "case_code": case_code or (api_case.case_code if api_case else default_case_code or f"{DEFAULT_CASE_PREFIX}<new>"),
                "title": case_title or self._resolve_case_title(parsed, name=name, case_title=case_title, api_name=api.name if api else ""),
                "subtitle": DEFAULT_CASE_SUBTITLE,
                "header": parsed.headers,
                "payload": self._build_case_payload(parsed),
            },
            "action": {
                "api_definition": api_action,
                "api_case": case_action,
            },
        }

    @transaction.atomic
    def import_curl(self, *, module_id, curl_text, name="", case_title="", case_code=""):
        module = self._load_module(module_id)
        parsed = self.parse(curl_text)
        api, api_action = self._upsert_api(module=module, parsed=parsed, name=name)
        api_case, case_action = self._upsert_case(
            api=api,
            parsed=parsed,
            case_title=case_title,
            case_code=case_code,
        )
        return {
            "parsed": parsed.to_dict(),
            "api_definition": {
                "id": api.id,
                "name": api.name,
                "method": api.method,
                "path": api.path,
                "module": module.id,
                "module_name": module.name,
                "default_headers": api.default_headers,
            },
            "api_case": {
                "id": api_case.id,
                "api": api.id,
                "case_code": api_case.case_code,
                "title": api_case.title,
                "subtitle": api_case.subtitle,
                "header": api_case.header,
                "payload": api_case.payload,
            },
            "action": {
                "api_definition": api_action,
                "api_case": case_action,
            },
        }

    def parse(self, curl_text):
        normalized = self._normalize_curl_text(curl_text)
        self._validate_supported_text(normalized)
        try:
            tokens = shlex.split(normalized, posix=True)
        except ValueError as exc:
            raise CurlImportError(f"cURL 解析失败: {exc}") from exc
        if not tokens or tokens[0] != "curl":
            raise CurlImportError("请输入以 curl 开头的命令")

        method = None
        url = None
        headers = {}
        data_parts = []
        i = 1
        while i < len(tokens):
            token = tokens[i]
            if token in ("-X", "--request"):
                i += 1
                method = self._require_value(tokens, i, token)
            elif token in ("-H", "--header"):
                i += 1
                header_line = self._require_value(tokens, i, token)
                key, value = self._parse_header_line(header_line)
                headers[key] = value
            elif token in ("-b", "--cookie"):
                i += 1
                headers["Cookie"] = self._require_value(tokens, i, token)
            elif token in ("--data", "--data-raw", "--data-binary", "--data-urlencode", "-d"):
                i += 1
                data_parts.append(self._require_value(tokens, i, token))
            elif token in ("--url",):
                i += 1
                url = self._require_value(tokens, i, token)
            elif token in ("--compressed", "--insecure", "-k", "-s", "-L", "--location", "--globoff", "--silent"):
                pass
            elif token in ("-F", "--form"):
                raise CurlImportError("暂不支持包含文件上传或 form-data 的 cURL")
            elif token.startswith("-"):
                if token.startswith("--url="):
                    url = token.split("=", 1)[1]
                elif token.startswith("--request="):
                    method = token.split("=", 1)[1]
                elif token.startswith("--header="):
                    key, value = self._parse_header_line(token.split("=", 1)[1])
                    headers[key] = value
                elif token.startswith("--cookie="):
                    headers["Cookie"] = token.split("=", 1)[1]
                elif any(token.startswith(prefix) for prefix in ("--data=", "--data-raw=", "--data-binary=", "--data-urlencode=")):
                    data_parts.append(token.split("=", 1)[1])
                else:
                    raise CurlImportError(f"暂不支持该 cURL 参数: {token}")
            elif url is None:
                url = token
            else:
                raise CurlImportError(f"无法识别的 cURL 片段: {token}")
            i += 1

        if not url:
            raise CurlImportError("cURL 中缺少请求 URL")

        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise CurlImportError("cURL 中的 URL 不是有效的绝对地址")
        path = parsed_url.path or "/"
        query = self._parse_query(parsed_url.query)
        content_type = self._detect_content_type(headers)
        raw_body = "&".join(part for part in data_parts if part != "")
        payload = self._parse_payload(raw_body, content_type)
        resolved_method = (method or ("POST" if data_parts else "GET")).upper()
        return ParsedCurlRequest(
            method=resolved_method,
            url=url,
            base_url=f"{parsed_url.scheme}://{parsed_url.netloc}",
            path=path,
            query=query,
            headers=headers,
            payload=payload,
            content_type=content_type,
        )

    def _load_module(self, module_id):
        try:
            return Module.objects.get(id=module_id)
        except Module.DoesNotExist as exc:
            raise CurlImportError("目标模块不存在") from exc

    def _normalize_curl_text(self, curl_text):
        if not curl_text or not str(curl_text).strip():
            raise CurlImportError("请粘贴 cURL 内容")
        normalized = str(curl_text).strip()
        normalized = normalized.replace("\\\r\n", " ").replace("\\\n", " ")

        # 浏览器/平台复制出来的 cURL 有时会把 URL（甚至 Origin/Referer）包一层反引号：
        #   curl '`https://example.com/path`' -H 'Origin: `https://example.com`'
        # 反引号在 shell 里有“命令替换”的语义，但我们这里并不会执行 cURL，只是解析文本。
        # 为了提升导入成功率：把形如 `https://...` 的包裹反引号剥掉。
        normalized = re.sub(r"`(https?://[^`]+)`", r"\1", normalized)

        def decode_ansi(match):
            raw = match.group(1)
            return raw.encode("utf-8").decode("unicode_escape")

        return ANSI_C_QUOTED_PATTERN.sub(decode_ansi, normalized)

    def _validate_supported_text(self, curl_text):
        if "$(" in curl_text or "`" in curl_text or "<<EOF" in curl_text or "<<'EOF'" in curl_text:
            raise CurlImportError("暂不支持包含命令替换或 here-doc 的 cURL")

    def _require_value(self, tokens, index, option):
        if index >= len(tokens):
            raise CurlImportError(f"{option} 缺少参数值")
        return tokens[index]

    def _parse_header_line(self, header_line):
        if ":" not in header_line:
            raise CurlImportError(f"Header 格式不正确: {header_line}")
        key, value = header_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise CurlImportError(f"Header Key 不能为空: {header_line}")
        return key, value

    def _parse_query(self, query_string):
        parsed = {}
        for key, value in parse_qsl(query_string, keep_blank_values=True):
            if key in parsed:
                current = parsed[key]
                if isinstance(current, list):
                    current.append(value)
                else:
                    parsed[key] = [current, value]
            else:
                parsed[key] = value
        return parsed

    def _detect_content_type(self, headers):
        content_type = headers.get("Content-Type") or headers.get("content-type") or ""
        return content_type.split(";", 1)[0].strip().lower()

    def _parse_payload(self, raw_body, content_type):
        if raw_body == "":
            return {}
        if content_type == "application/json":
            try:
                return json.loads(raw_body)
            except json.JSONDecodeError:
                return raw_body
        if content_type == "application/x-www-form-urlencoded":
            return self._parse_query(raw_body)
        return raw_body

    def _build_case_payload(self, parsed):
        has_query = bool(parsed.query)
        has_body = parsed.payload not in ({}, "", None)
        has_base_url = bool(parsed.base_url)
        if has_query and has_body:
            return {"__base_url": parsed.base_url, "__query": parsed.query, "__body": parsed.payload}
        if has_query:
            return {"__base_url": parsed.base_url, "__query": parsed.query}
        if has_body:
            if has_base_url:
                return {"__base_url": parsed.base_url, "__body": parsed.payload}
            return parsed.payload
        if has_base_url:
            return {"__base_url": parsed.base_url}
        return {}

    def _merge_headers(self, current, incoming):
        merged = dict(current or {})
        for key, value in (incoming or {}).items():
            merged.setdefault(key, value)
        return merged

    def _resolve_api_name(self, parsed, preferred_name):
        candidate = (preferred_name or "").strip()
        if candidate:
            return candidate
        path_tail = parsed.path.rstrip("/").split("/")[-1] if parsed.path.rstrip("/") else ""
        return path_tail or f"{parsed.method} {parsed.path}"

    def _resolve_case_title(self, parsed, *, name="", case_title="", api_name=""):
        if (case_title or "").strip():
            return case_title.strip()
        if (name or "").strip():
            return name.strip()
        if (api_name or "").strip():
            return api_name.strip()
        return self._resolve_api_name(parsed, "")

    def _upsert_api(self, *, module, parsed, name):
        api = ApiDefinition.objects.filter(module=module, method=parsed.method, path=parsed.path).first()
        if not api:
            api = ApiDefinition.objects.create(
                module=module,
                name=self._resolve_api_name(parsed, name),
                method=parsed.method,
                path=parsed.path,
                default_headers=parsed.headers,
            )
            return api, "created"

        updated_fields = []
        resolved_name = self._resolve_api_name(parsed, name)
        if self._should_fill_api_name(api.name) and api.name != resolved_name:
            api.name = resolved_name
            updated_fields.append("name")
        merged_headers = self._merge_headers(api.default_headers, parsed.headers)
        if merged_headers != (api.default_headers or {}):
            api.default_headers = merged_headers
            updated_fields.append("default_headers")
        if updated_fields:
            updated_fields.append("updated_at")
            api.save(update_fields=updated_fields)
            return api, "updated"
        return api, "reused"

    def _upsert_case(self, *, api, parsed, case_title, case_code):
        resolved_code = (case_code or "").strip() or f"{DEFAULT_CASE_PREFIX}{api.id}"
        title = self._resolve_case_title(parsed, case_title=case_title, api_name=api.name)
        defaults = {
            "title": title,
            "subtitle": DEFAULT_CASE_SUBTITLE,
            "header": parsed.headers,
            "payload": self._build_case_payload(parsed),
            "expect": {},
            "extractors": [],
            "tags": ["curl-import"],
            "suite": "",
            "estimated_duration_ms": 1000,
            "level": 1,
            "rely": "",
            "enabled": True,
            "is_setup": False,
            "sort_order": 0,
        }
        case, created = ApiCase.objects.get_or_create(
            api=api,
            case_code=resolved_code,
            is_setup=False,
            defaults=defaults,
        )
        if created:
            return case, "created"

        changed = []
        for field, value in defaults.items():
            if getattr(case, field) != value:
                setattr(case, field, value)
                changed.append(field)
        if changed:
            changed.append("updated_at")
            case.save(update_fields=changed)
            return case, "updated"
        return case, "updated"

    def _should_fill_api_name(self, current_name):
        if not (current_name or "").strip():
            return True
        return bool(DEFAULT_PLACEHOLDER_PATTERN.match(current_name.strip()))
