"""
backend/api/urls.py

文件用途
-------
后端 REST API 路由（DRF Router + 少量自定义 path）。

组织方式：
- router.register(...)：对大多数资源提供标准 CRUD：
  projects/environments/modules/api-definitions/cases/test-plans/test-tasks/schedules ...
  以及 UI 自动化域：ui-scenarios/ui-pages/ui-elements/ui-datasets/ui-tasks/ui-runs ...

- 显式 path(...)：更像“动作型 API”
  - auth/login/logout/me：会话登录与用户信息
  - dashboard/quality：质量看板数据聚合
  - imports/excel：Excel 上传导入
  - imports/curl：cURL 解析导入

--------------
接口文档如何组织：
- 资源型接口遵循 REST（router）
- 动作型接口走明确语义的路径（imports/*, auth/*, dashboard/*）
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApiCaseViewSet,
    ApiDefinitionViewSet,
    CurlImportView,
    DashboardQualityView,
    EnvironmentCookieViewSet,
    EnvironmentVariableViewSet,
    EnvironmentViewSet,
    ExcelImportView,
    LoginView,
    LogoutView,
    MeView,
    ModuleViewSet,
    ProjectVariableViewSet,
    ProjectViewSet,
    ScenarioCaseViewSet,
    ScenarioStepViewSet,
    ScheduleViewSet,
    TestPlanViewSet,
    TestTaskViewSet,
    UiDatasetRowViewSet,
    UiDatasetViewSet,
    UiElementViewSet,
    UiMethodStepViewSet,
    UiPageMethodViewSet,
    UiPageViewSet,
    UiRunViewSet,
    UiScenarioViewSet,
    UiScenarioStepViewSet,
    UiStepViewSet,
    UiPlanViewSet,
    UiExecTaskViewSet,
    UiTaskViewSet,
)

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("environments", EnvironmentViewSet, basename="environment")
router.register("project-variables", ProjectVariableViewSet, basename="project-variable")
router.register("environment-variables", EnvironmentVariableViewSet, basename="environment-variable")
router.register("environment-cookies", EnvironmentCookieViewSet, basename="environment-cookie")
router.register("modules", ModuleViewSet, basename="module")
router.register("api-definitions", ApiDefinitionViewSet, basename="api-definition")
router.register("cases", ApiCaseViewSet, basename="case")
router.register("scenarios", ScenarioCaseViewSet, basename="scenario")
router.register("scenario-steps", ScenarioStepViewSet, basename="scenario-step")
router.register("test-plans", TestPlanViewSet, basename="test-plan")
router.register("test-tasks", TestTaskViewSet, basename="test-task")
router.register("schedules", ScheduleViewSet, basename="schedule")
router.register("ui-scenarios", UiScenarioViewSet, basename="ui-scenario")
router.register("ui-steps", UiStepViewSet, basename="ui-step")
router.register("ui-tasks", UiTaskViewSet, basename="ui-task")
router.register("ui-plans", UiPlanViewSet, basename="ui-plan")
router.register("ui-exec-tasks", UiExecTaskViewSet, basename="ui-exec-task")
router.register("ui-pages", UiPageViewSet, basename="ui-page")
router.register("ui-elements", UiElementViewSet, basename="ui-element")
router.register("ui-page-methods", UiPageMethodViewSet, basename="ui-page-method")
router.register("ui-method-steps", UiMethodStepViewSet, basename="ui-method-step")
router.register("ui-datasets", UiDatasetViewSet, basename="ui-dataset")
router.register("ui-dataset-rows", UiDatasetRowViewSet, basename="ui-dataset-row")
router.register("ui-scenario-steps", UiScenarioStepViewSet, basename="ui-scenario-step")
router.register("ui-runs", UiRunViewSet, basename="ui-run")

urlpatterns = [
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("dashboard/quality/", DashboardQualityView.as_view()),
    path("imports/excel/", ExcelImportView.as_view()),
    path("imports/curl/", CurlImportView.as_view()),
    path("", include(router.urls)),
]
