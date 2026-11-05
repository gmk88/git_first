"""Core 应用路由"""
from django.urls import path
from core import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("request/", views.request_form, name="request_form"),
    path("request/done/<str:request_no>/", views.request_done, name="request_done"),
    path(
        "admin/core/consultationrequest/<int:pk>/process/",
        views.request_process,
        name="request_process",
    ),
    path("report/lookup/", views.report_lookup, name="report_lookup"),
    path("report/detail/<uuid:uuid>/", views.report_detail, name="report_detail"),
    path("report/download/<uuid:uuid>/", views.report_download, name="report_download"),
]
