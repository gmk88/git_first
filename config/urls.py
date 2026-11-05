"""根路由"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # core 路由必须先于 admin：其中包含 /admin/core/.../process/ 自定义处理页，
    # 否则会被 AdminSite 的 catch-all 视图抢占。
    path("", include("core.urls")),
    path("admin/", admin.site.urls),
]
