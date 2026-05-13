"""
backend/api/admin.py

文件用途
-------
Django Admin 后台注册。

主要作用：
- 方便开发/演示时直接在 /admin/ 查看与维护核心数据（项目、环境、接口、用例、计划、任务等）
- 对 ApiCase 增加 dependencies 的可视化编辑（filter_horizontal）

说明：生产环境通常会把管理能力迁移到前端平台页面，本文件更多用于开发期与快速排障。
"""

from django.contrib import admin

from .models import (
    ApiCase,
    ApiDefinition,
    Environment,
    EnvironmentVariable,
    Module,
    Project,
    ProjectVariable,
    ScenarioCase,
    ScenarioStep,
    ScenarioStepResult,
    Schedule,
    TestPlan,
    TestResult,
    TestTask,
)

admin.site.register(Project)
admin.site.register(Environment)
admin.site.register(ProjectVariable)
admin.site.register(EnvironmentVariable)
admin.site.register(Module)
admin.site.register(ApiDefinition)
@admin.register(ApiCase)
class ApiCaseAdmin(admin.ModelAdmin):
    list_display = ("case_code", "title", "subtitle", "level", "is_setup", "enabled")
    filter_horizontal = ("dependencies",)


admin.site.register(TestPlan)
admin.site.register(TestTask)
admin.site.register(TestResult)
admin.site.register(ScenarioCase)
admin.site.register(ScenarioStep)
admin.site.register(ScenarioStepResult)
admin.site.register(Schedule)
