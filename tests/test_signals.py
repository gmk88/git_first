"""登录安全事件信号测试（T034，FR-014）"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import SecurityEvent


class LoginSignalTest(TestCase):
    """登录成功/失败写 SecurityEvent（FR-014）"""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            "signal_admin", "signal@example.com", "strongpass123"
        )
        self.login_url = reverse("admin:login")

    def test_login_success_event(self):
        """成功登录断言 SecurityEvent(login_success) 落库且 actor=用户名"""
        response = self.client.post(self.login_url, {
            "username": "signal_admin",
            "password": "strongpass123",
        })
        self.assertEqual(response.status_code, 302)
        event = SecurityEvent.objects.filter(
            event_type=SecurityEvent.EventType.LOGIN_SUCCESS
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.actor, "signal_admin")

    def test_login_failed_event(self):
        """错误密码登录断言 SecurityEvent(login_failed) 落库且 actor=提交的用户名"""
        response = self.client.post(self.login_url, {
            "username": "signal_admin",
            "password": "wrong-password",
        })
        self.assertEqual(response.status_code, 200)
        event = SecurityEvent.objects.filter(
            event_type=SecurityEvent.EventType.LOGIN_FAILED
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.actor, "signal_admin")

    def test_login_failed_unknown_user(self):
        """不存在用户名的失败登录同样记录事件"""
        self.client.post(self.login_url, {
            "username": "ghost_user",
            "password": "whatever123",
        })
        event = SecurityEvent.objects.filter(
            event_type=SecurityEvent.EventType.LOGIN_FAILED
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.actor, "ghost_user")
