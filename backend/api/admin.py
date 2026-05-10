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
