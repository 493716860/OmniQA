from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApiCaseViewSet,
    ApiDefinitionViewSet,
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

urlpatterns = [
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("dashboard/quality/", DashboardQualityView.as_view()),
    path("imports/excel/", ExcelImportView.as_view()),
    path("", include(router.urls)),
]
