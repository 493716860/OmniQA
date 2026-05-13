"""
backend/api/authentication.py

文件用途
-------
自定义认证类：CsrfExemptSessionAuthentication。

为什么需要它？
-------------
前端（Vue SPA）通过 Cookie + Session 方式与 Django 交互时，默认 SessionAuthentication 会强制 CSRF 校验。
对于一个前后端分离、且主要通过 AJAX 调用 API 的平台来说：
- 开发/演示环境常常不希望被 CSRF 机制打断（否则需要额外处理 csrftoken 传递）
- 生产环境更推荐用 Token/JWT 或者在网关层做 CSRF/同源策略

因此这里把 enforce_csrf() 置空，让 SessionAuthentication 在 API 层不校验 CSRF。
注意：这属于“便于演示/内网平台”的取舍，若面试官关注安全，可说明替代方案。
"""

from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return
