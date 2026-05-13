"""
backend/OmniQA/urls.py

文件用途
-------
Django URL 路由总入口（项目级 urls.py）。

路由策略：
1) /admin/：Django Admin
2) /api/：后端 REST API（见 backend/api/urls.py）
3) 前端静态资源与 SPA 兜底：
   - DEBUG 下显式把 /assets/* 指向 frontend/dist/assets，避免被 catch-all 错误返回 index 导致白页
   - 所有其它路径最终走 FrontendCatchAllView：
     - 若 frontend/dist/index.html 存在，返回构建后的前端
     - 开发时若 dist 不存在，尝试代理到 Vite dev server（127.0.0.1:5173）

面试讲解抓手
-----------
- 这是典型的“单域名部署”形态：Django 同时托管 API 与前端 SPA（生产可用 Nginx/网关替代）
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

from api.views import FrontendCatchAllView

FRONTEND_DIST_DIR = settings.REPO_ROOT / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.OMNIQA_REPORT_URL, document_root=settings.REPO_ROOT / "reports")

    # 关键：让 Django 在 DEBUG 下也能正确返回前端构建产物的静态资源。
    # 否则刷新 /api-definitions 这类前端路由时，index.html 会引用 /assets/*.js，
    # 这些请求会被 catch-all 返回 index.html，从而出现“白页”。
    urlpatterns += [
        re_path(
            r"^assets/(?P<path>.*)$",
            static_serve,
            {"document_root": str(FRONTEND_ASSETS_DIR)},
        ),
        re_path(
            r"^favicon\.ico$",
            static_serve,
            {"path": "favicon.ico", "document_root": str(FRONTEND_DIST_DIR)},
        ),
    ]

urlpatterns += [
    re_path(r"^.*$", FrontendCatchAllView.as_view()),
]
