"""登录安全事件信号（FR-014）"""
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from core.models import SecurityEvent


def _client_ip(request):
    if request is None:
        return "0.0.0.0"
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


@receiver(user_logged_in)
def log_login_success(sender, request, user, **kwargs):
    SecurityEvent.objects.create(
        event_type=SecurityEvent.EventType.LOGIN_SUCCESS,
        actor=user.username[:150],
        source_ip=_client_ip(request),
    )


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    SecurityEvent.objects.create(
        event_type=SecurityEvent.EventType.LOGIN_FAILED,
        actor=str(credentials.get("username", ""))[:150],
        source_ip=_client_ip(request),
    )
