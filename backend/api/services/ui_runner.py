"""
backend/api/services/ui_runner.py

文件用途
-------
UI 自动化执行引擎（Playwright Runner，MVP 版本）。

它对应接口自动化的 db_runner.py，但面向的是 UI 场景：
- UiScenarioStep（场景步骤）组织执行流程，当前主要支持“调用页面方法”
- UiPageMethod/UiMethodStep（PO + 可复用步骤）定义要在页面上做的动作
- UiDatasetRow 提供 DDT 数据，步骤参数支持 ${field} 替换
- UiStepResult/UiTaskEvent/UiArtifact 负责产出结果、事件流与工件（trace.zip/截图）

关键设计点（面试讲解抓手）
-------------------------
1) async_api + 线程隔离：
   - Playwright 使用 asyncio；Django ORM 大多是同步
   - 本实现将 ORM 读写集中在同步阶段 _prepare_sync()
   - 真正执行放到 asyncio.run(...)，并通过 sync_to_async 写库，避免 “async context” 错误
2) 可观测性：
   - 每步写 UiTaskEvent（时间线）
   - 失败自动截图并登记 UiArtifact
   - 全程 tracing，最终产出 trace.zip 便于回放
3) 调试体验：
   - HEADED 模式支持 slow_mo 与执行完成后保持窗口打开一段时间
"""

import re
import time
import queue
import _thread
import asyncio
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from api.models import (
    UiArtifact,
    UiDatasetRow,
    UiMethodStep,
    UiScenarioStep,
    UiStepResult,
    UiTask,
    UiTaskEvent,
)


class UiTaskRunner:
    """
    Playwright UI Runner（MVP）
    - Chromium
    - headless / headed
    - trace + 失败截图
    """

    def __init__(self, task: UiTask):
        self.task = task
        self.scenario = task.scenario

        report_root = Path(getattr(settings, "OMNIQA_UI_REPORT_ROOT", str(settings.REPO_ROOT / "reports" / "ui-tasks")))
        self.report_root = report_root / str(task.id)
        self.report_root.mkdir(parents=True, exist_ok=True)

    def event(self, *, level=UiTaskEvent.Level.INFO, category=UiTaskEvent.Category.TASK, message="", step_name="", data=None):
        # 同步路径（在 asyncio 外调用）
        UiTaskEvent.objects.create(
            task=self.task,
            level=level,
            category=category,
            message=message,
            step_name=step_name or "",
            data=data or {},
        )

    async def aevent(self, *, level=UiTaskEvent.Level.INFO, category=UiTaskEvent.Category.TASK, message="", step_name="", data=None):
        # asyncio 内写库必须走 sync_to_async，否则 Django 会报 “You cannot call this from an async context”
        await sync_to_async(UiTaskEvent.objects.create, thread_sensitive=True)(
            task_id=self.task.id,
            level=level,
            category=category,
            message=message,
            step_name=step_name or "",
            data=data or {},
        )

    async def atask_update(self, **fields):
        fields["updated_at"] = timezone.now()
        await sync_to_async(UiTask.objects.filter(id=self.task.id).update, thread_sensitive=True)(**fields)

    def replace_tokens(self, value, ctx):
        if value is None:
            return value
        if isinstance(value, str):
            # ${field} → ctx[field]
            def repl(match):
                key = match.group(1)
                return str(ctx.get(key, match.group(0)))

            return re.sub(r"\$\{([a-zA-Z0-9_]+)\}", repl, value)
        if isinstance(value, list):
            return [self.replace_tokens(item, ctx) for item in value]
        if isinstance(value, dict):
            return {k: self.replace_tokens(v, ctx) for k, v in value.items()}
        return value

    def find_missing_tokens(self, value, ctx: dict) -> list[str]:
        """
        找出 value 中引用了但 ctx 不存在的 ${field}。
        仅用于提示（不会中断执行）。
        """
        if not isinstance(value, str):
            return []
        keys = re.findall(r"\$\{([a-zA-Z0-9_]+)\}", value)
        return sorted({k for k in keys if k not in (ctx or {})})

    def selector_from_locator(self, locator: dict) -> str:
        locator = locator or {}
        strategy = (locator.get("strategy") or "css").lower()
        value = (locator.get("value") or "").strip()
        if strategy == "css":
            return value
        if strategy == "text":
            return f"text={value}"
        if strategy == "role":
            role = locator.get("role") or "button"
            name = locator.get("name") or value
            return f'role={role}[name="{name}"]'
        if strategy == "xpath":
            return f"xpath={value}"
        return value

    def run(self):
        """
        采用 Playwright async_api（不受 “You cannot call this from an async context” 限制）。
        仍然放到 OS 线程里执行，避免 Celery/运行环境对 asyncio 的干扰。
        """
        q: "queue.Queue[Exception | None]" = queue.Queue(maxsize=1)

        def _target():
            try:
                prepared = self._prepare_sync()
                asyncio.run(self._run_async(prepared))
                q.put(None)
            except Exception as e:  # noqa: BLE001
                q.put(e)

        _thread.start_new_thread(_target, ())
        err = q.get()
        if err:
            raise err

    def _prepare_sync(self):
        """
        所有 ORM 读取/写入都在同步上下文完成，避免 Django async 限制。
        返回纯 Python 结构供 async 执行器使用。
        """
        scenario_steps = list(
            self.scenario.scenario_steps.filter(enabled=True)
            .select_related("method", "method__page")
            .order_by("sort_order", "id")
        )

        compiled = []
        steps_per_row = 0
        for scenario_step in scenario_steps:
            if scenario_step.type != UiScenarioStep.Type.CALL_METHOD or not scenario_step.method_id:
                continue
            method = scenario_step.method
            method_steps = list(
                method.steps.filter(enabled=True)
                .select_related("element", "method", "method__page")
                .order_by("sort_order", "id")
            )
            steps_per_row += len(method_steps)
            compiled.append({"method_name": method.name, "page_name": method.page.name, "steps": method_steps})

        # DDT 支持：
        # - 旧模式：dataset_row_id 不为空 → 一个任务只跑一行数据
        # - 新模式：dataset_id 不为空 → 一个任务在内部按数据集行循环执行（一次运行=一个任务）
        rows: list[UiDatasetRow] = []
        if getattr(self.task, "dataset_id", None):
            rows = list(UiDatasetRow.objects.filter(dataset_id=self.task.dataset_id, enabled=True).order_by("id"))
        elif getattr(self.task, "dataset_row_id", None):
            # dataset_row 已在 UiTask select_related 时可能未预取，这里直接访问会触发一次查询（同步 ok）
            rows = [self.task.dataset_row] if self.task.dataset_row_id else []
        if not rows:
            rows = [None]

        total_rows = len([r for r in rows if r is not None]) if rows != [None] else 0
        total_steps = max(1, steps_per_row * (len(rows) if rows != [None] else 1))

        # 初始化任务字段
        self.task.total_steps = total_steps
        self.task.passed_steps = 0
        self.task.failed_steps = 0
        self.task.skipped_steps = 0
        self.task.total_rows = total_rows
        self.task.passed_rows = 0
        self.task.failed_rows = 0
        self.task.skipped_rows = 0
        self.task.progress = 0
        self.task.report_dir = str(self.report_root)
        self.task.save(
            update_fields=[
                "total_steps",
                "passed_steps",
                "failed_steps",
                "skipped_steps",
                "total_rows",
                "passed_rows",
                "failed_rows",
                "skipped_rows",
                "progress",
                "report_dir",
                "updated_at",
            ]
        )

        self.event(
            message="UI 任务开始执行",
            data={
                "scenario": self.scenario.id,
                "scenario_name": self.scenario.name,
                "mode": self.task.mode,
                "dataset": getattr(self.task, "dataset_id", None),
                "dataset_row": getattr(self.task, "dataset_row_id", None),
                "total_rows": total_rows,
            },
        )
        return {"compiled": compiled, "rows": rows, "steps_per_row": steps_per_row, "total_steps": total_steps}

    async def _run_async(self, prepared: dict):
        compiled = prepared["compiled"]
        rows = prepared["rows"]
        total_steps = prepared["total_steps"] or 1
        passed_steps = 0
        failed_steps = 0
        skipped_steps = 0
        passed_rows = 0
        failed_rows = 0
        skipped_rows = 0

        trace_path = self.report_root / "trace.zip"

        async with async_playwright() as p:
            slow_mo = int(getattr(settings, "OMNIQA_UI_SLOW_MO_MS", 0) or 0)
            browser = await p.chromium.launch(
                headless=self.task.mode != UiTask.Mode.HEADED,
                slow_mo=slow_mo if self.task.mode == UiTask.Mode.HEADED else 0,
            )
            context = await browser.new_context()
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = await context.new_page()

            try:
                for row in rows:
                    canceled = await sync_to_async(
                        UiTask.objects.filter(id=self.task.id, status=UiTask.Status.CANCELED).exists,
                        thread_sensitive=True,
                    )()
                    if canceled:
                        await self.aevent(level=UiTaskEvent.Level.WARN, message="任务已取消，提前结束")
                        return

                    ctx = (row.data or {}) if row is not None else {}
                    row_key = getattr(row, "row_key", "") if row is not None else ""
                    row_id = getattr(row, "id", None) if row is not None else None

                    if row is not None:
                        await self.aevent(
                            category=UiTaskEvent.Category.TASK,
                            message="开始执行数据行",
                            data={"dataset_row": row_id, "row_key": row_key},
                        )

                    row_failed = False
                    for method_block in compiled:
                        await self.aevent(
                            category=UiTaskEvent.Category.STEP,
                            step_name=method_block["method_name"],
                            message="开始执行页面方法",
                            data={"page": method_block["page_name"], "method": method_block["method_name"], "row_key": row_key},
                        )

                        for method_step in method_block["steps"]:
                            result = await self.run_method_step(page, method_step, ctx, row_key=row_key, row_id=row_id)
                            if result.status == UiStepResult.Status.PASSED:
                                passed_steps += 1
                            elif result.status in [UiStepResult.Status.FAILED, UiStepResult.Status.ERROR]:
                                failed_steps += 1
                                row_failed = True
                            else:
                                skipped_steps += 1

                            # 调试体验：有头模式下每步之间稍作停顿，方便肉眼观察输入/点击是否正确
                            if self.task.mode == UiTask.Mode.HEADED:
                                await page.wait_for_timeout(300)

                            done = passed_steps + failed_steps + skipped_steps
                            progress = min(99, int(done / total_steps * 100))
                            await self.atask_update(
                                progress=progress,
                                passed_steps=passed_steps,
                                failed_steps=failed_steps,
                                skipped_steps=skipped_steps,
                                passed_rows=passed_rows,
                                failed_rows=failed_rows,
                                skipped_rows=skipped_rows,
                            )

                    if row is not None:
                        if row_failed:
                            failed_rows += 1
                            await self.aevent(message="数据行执行失败", data={"row_key": row_key, "dataset_row": row_id})
                        else:
                            passed_rows += 1
                            await self.aevent(message="数据行执行通过", data={"row_key": row_key, "dataset_row": row_id})

                # 汇总
                final_status = UiTask.Status.FAILED if failed_steps else UiTask.Status.PASSED
                await self.atask_update(
                    failed_steps=failed_steps,
                    passed_steps=passed_steps,
                    skipped_steps=skipped_steps,
                    failed_rows=failed_rows,
                    passed_rows=passed_rows,
                    skipped_rows=skipped_rows,
                    progress=100,
                    status=final_status,
                    finished_at=timezone.now(),
                )
                await self.aevent(message="UI 任务执行完成", data={"status": final_status})

                # 调试模式：有头执行完成后保持浏览器打开一段时间，便于观察页面停留状态
                if self.task.mode == UiTask.Mode.HEADED:
                    keep_s = int(getattr(settings, "OMNIQA_UI_HEADED_KEEP_OPEN_SECONDS", 0) or 0)
                    if keep_s > 0:
                        await self.aevent(
                            level=UiTaskEvent.Level.WARN,
                            category=UiTaskEvent.Category.SYSTEM,
                            message="调试模式：将保持浏览器打开一段时间，便于观察",
                            data={"keep_open_seconds": keep_s, "slow_mo_ms": int(getattr(settings, 'OMNIQA_UI_SLOW_MO_MS', 0) or 0)},
                        )
                        # 加超时保护，避免外部环境异常导致等待无法结束
                        await asyncio.wait_for(page.wait_for_timeout(keep_s * 1000), timeout=keep_s + 5)
            finally:
                try:
                    # tracing.stop 在某些情况下可能卡住（例如浏览器异常/被外部强制中断）。
                    # 为避免导致“任务无法收尾、浏览器不关闭”，这里加超时保护。
                    await asyncio.wait_for(context.tracing.stop(path=str(trace_path)), timeout=10)
                    url = f"{getattr(settings, 'OMNIQA_REPORT_URL', '/reports/')}ui-tasks/{self.task.id}/trace.zip"
                    await sync_to_async(UiArtifact.objects.create, thread_sensitive=True)(
                        task_id=self.task.id,
                        type=UiArtifact.Type.TRACE,
                        name="trace.zip",
                        path=str(trace_path),
                        url=url,
                    )
                    await self.aevent(category=UiTaskEvent.Category.ARTIFACT, message="Trace 已生成", data={"url": url})
                except Exception:
                    pass
                await context.close()
                await browser.close()

    async def run_method_step(self, page, step: UiMethodStep, ctx: dict, *, row_key: str = "", row_id: int | None = None) -> UiStepResult:
        start = time.monotonic()
        status = UiStepResult.Status.PASSED
        failure_category = ""
        error_message = ""
        data = {}

        step_name = f"{step.method.name} / {step.name}"
        await self.aevent(category=UiTaskEvent.Category.STEP, step_name=step_name, message=f"开始步骤: {step.type}")

        try:
            params = self.replace_tokens(step.params or {}, ctx)
            assertions = self.replace_tokens(step.assertions or {}, ctx)

            if step.type == UiMethodStep.Type.GOTO:
                url = (params or {}).get("url") or step.method.page.url or ""
                await page.goto(url, wait_until="load")
                data = {"url": url}
            elif step.type in {UiMethodStep.Type.CLICK, UiMethodStep.Type.FILL, UiMethodStep.Type.WAIT, UiMethodStep.Type.ASSERT}:
                if not step.element_id and step.type != UiMethodStep.Type.ASSERT:
                    raise ValueError("步骤缺少 element")
                locator_json = step.element.locator if step.element_id else {}
                sel = self.selector_from_locator(locator_json)
                locator = page.locator(sel) if sel else None

                timeout_ms = int((params or {}).get("timeout_ms") or 10000)
                if step.type == UiMethodStep.Type.CLICK:
                    await locator.click(timeout=timeout_ms)
                    data = {"selector": sel}
                elif step.type == UiMethodStep.Type.FILL:
                    value = (params or {}).get("value") or ""
                    missing = self.find_missing_tokens((step.params or {}).get("value") or "", ctx)
                    if missing:
                        await self.aevent(
                            level=UiTaskEvent.Level.WARN,
                            category=UiTaskEvent.Category.SYSTEM,
                            step_name=step_name,
                            message="DDT 变量未匹配，已按原样输入（请检查是否通过 Run 绑定了数据集/数据行）",
                            data={"missing_fields": missing},
                        )
                    await locator.fill(str(value), timeout=timeout_ms)
                    data = {"selector": sel, "value": value}
                elif step.type == UiMethodStep.Type.WAIT:
                    state = (params or {}).get("state") or "visible"
                    await locator.wait_for(state=state, timeout=timeout_ms)
                    data = {"selector": sel, "state": state}
                else:
                    # ASSERT：支持 text_contains / visible / url_contains
                    kind = (assertions.get("kind") or "text_contains").lower()
                    expected = assertions.get("value") or ""
                    if kind == "url_contains":
                        assert expected in (page.url or ""), f"URL 断言失败: 期望包含 {expected}, 实际 {page.url}"
                    else:
                        if not step.element_id:
                            raise ValueError("断言步骤缺少 element")
                        if kind == "visible":
                            assert await locator.is_visible(), f"元素不可见: {sel}"
                        else:
                            text = await locator.inner_text(timeout=timeout_ms)
                            assert expected in (text or ""), f"文本断言失败: 期望包含 {expected}, 实际 {text}"
                    data = {"assert": assertions, "selector": sel}
            elif step.type == UiMethodStep.Type.PRESS:
                key = (params or {}).get("key") or "Enter"
                await page.keyboard.press(str(key))
                data = {"key": key}
            else:
                raise ValueError(f"不支持的步骤类型: {step.type}")
        except PlaywrightTimeoutError as exc:
            status = UiStepResult.Status.ERROR
            failure_category = "TIMEOUT"
            error_message = str(exc)
        except AssertionError as exc:
            status = UiStepResult.Status.FAILED
            failure_category = "ASSERTION_FAILED"
            error_message = str(exc)
        except PlaywrightError as exc:
            status = UiStepResult.Status.ERROR
            failure_category = "PLAYWRIGHT_ERROR"
            error_message = str(exc)
        except Exception as exc:
            status = UiStepResult.Status.ERROR
            failure_category = "SCRIPT_ERROR"
            error_message = str(exc)

        duration_ms = int((time.monotonic() - start) * 1000)
        result = await sync_to_async(UiStepResult.objects.create, thread_sensitive=True)(
            task_id=self.task.id,
            step=None,
            step_name=step_name,
            status=status,
            duration_ms=duration_ms,
            failure_category=failure_category,
            error_message=error_message,
            data={
                **(data or {}),
                "dataset_row": row_id,
                "row_key": row_key,
                "method": step.method.name,
                "page": step.method.page.name,
                "element": getattr(step.element, "name", "") if step.element_id else "",
                "step_type": step.type,
            },
        )

        if status in [UiStepResult.Status.FAILED, UiStepResult.Status.ERROR]:
            # 失败截图
            screenshot_path = self.report_root / f"screenshot_step_{result.id}.png"
            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
                url = f"{getattr(settings, 'OMNIQA_REPORT_URL', '/reports/')}ui-tasks/{self.task.id}/{screenshot_path.name}"
                await sync_to_async(UiArtifact.objects.create, thread_sensitive=True)(
                    task_id=self.task.id,
                    result_id=result.id,
                    type=UiArtifact.Type.SCREENSHOT,
                    name=screenshot_path.name,
                    path=str(screenshot_path),
                    url=url,
                    meta={"step": step_name},
                )
                await self.aevent(category=UiTaskEvent.Category.ARTIFACT, level=UiTaskEvent.Level.WARN, step_name=step_name, message="失败截图已生成", data={"url": url})
            except Exception:
                pass
            await self.aevent(level=UiTaskEvent.Level.ERROR, category=UiTaskEvent.Category.STEP, step_name=step_name, message="步骤失败", data={"failure_category": failure_category, "error": error_message})
        else:
            await self.aevent(category=UiTaskEvent.Category.STEP, step_name=step_name, message="步骤通过", data={"duration_ms": duration_ms})
        return result
