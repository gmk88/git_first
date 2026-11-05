from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """注册登录安全事件信号（FR-014）"""
        import core.signals  # noqa: F401
