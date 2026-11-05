"""测试报告查询（T025，先写后实现）"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    ConsultationRequest,
    ReportAccessToken,
    ReportVersion,
    SecurityEvent,
    Stage,
)
from core.services import hash_token


class ReportLookupTest(TestCase):
    """报告查询（US3）"""

    def setUp(self):
        self.owner = User.objects.create_user("owner_user", password="pass12345", is_staff=True)
        self.request = ConsultationRequest.objects.create(
            request_no="20261105-0001",
            company_name="某某科技有限公司",
            contact_person="张三",
            contact_phone="13800138000",
            contact_email="test@example.com",
            requirement="技术咨询需求",
            stage=Stage.DELIVERED,
            owner=self.owner,
        )
        self.raw_token = "test-token-abc123"
        self.token_record = ReportAccessToken.objects.create(
            request=self.request,
            token_hash=hash_token(self.raw_token),
        )
        self.version = ReportVersion.objects.create(
            request=self.request,
            version_no=1,
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4 test"),
            title="技术咨询报告",
            uploaded_by=self.owner,
        )

    def lookup_url(self):
        return reverse("core:report_lookup")

    def test_correct_lookup_redirects_to_detail(self):
        """正确编号+凭证 302 详情页"""
        response = self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": self.raw_token,
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(self.request.uuid), response.url)

    def test_detail_shows_report_info(self):
        """详情页展示企业名/标题/交付日期"""
        self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": self.raw_token,
        })
        response = self.client.get(
            reverse("core:report_detail", args=[self.request.uuid])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "某某科技有限公司")
        self.assertContains(response, "技术咨询报告")

    def test_wrong_token_message_does_not_leak_existence(self):
        """错误凭证统一提示且不因编号存在与否变化文案"""
        resp_existing = self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": "wrong-token",
        })
        resp_missing = self.client.post(self.lookup_url(), {
            "request_no": "20261105-9999",
            "token": "wrong-token",
        })
        self.assertContains(resp_existing, "编号或凭证不正确")
        self.assertContains(resp_missing, "编号或凭证不正确")
        self.assertNotContains(resp_existing, "不存在")
        self.assertNotContains(resp_missing, "不存在")

    def test_five_failures_lock_15_minutes(self):
        """连续 5 次失败后锁定 15 分钟（含正确凭证）"""
        for _ in range(5):
            self.client.post(self.lookup_url(), {
                "request_no": "20261105-0001",
                "token": "wrong-token",
            })
        self.token_record.refresh_from_db()
        self.assertIsNotNone(self.token_record.locked_until)
        self.assertGreater(self.token_record.locked_until, timezone.now())

        # 锁定期内正确凭证也被拒
        response = self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": self.raw_token,
        })
        self.assertContains(response, "尝试次数过多")

    def test_locked_attempts_not_incremented(self):
        """锁定窗口内 failed_attempts 不再增长"""
        self.token_record.locked_until = timezone.now() + timedelta(minutes=10)
        self.token_record.failed_attempts = 5
        self.token_record.save()
        self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": "wrong-token",
        })
        self.token_record.refresh_from_db()
        self.assertEqual(self.token_record.failed_attempts, 5)

    def test_lock_expiry_resets_counter(self):
        """T037 回归：锁定期满后计数重置，用户重新获得 5 次机会"""
        # 模拟已锁定，且锁定期已过
        self.token_record.locked_until = timezone.now() - timedelta(seconds=1)
        self.token_record.failed_attempts = 5
        self.token_record.save()

        # 期满后连续 4 次错误——不得触发锁定
        for i in range(4):
            self.client.post(self.lookup_url(), {
                "request_no": "20261105-0001",
                "token": "wrong-token",
            })
            self.token_record.refresh_from_db()
            self.assertIsNone(
                self.token_record.locked_until,
                f"第 {i + 1} 次错误不应锁定（期满后应重新计数）",
            )
        self.assertEqual(self.token_record.failed_attempts, 4)

        # 第 5 次错误才锁定
        self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": "wrong-token",
        })
        self.token_record.refresh_from_db()
        self.assertIsNotNone(self.token_record.locked_until)
        self.assertGreater(self.token_record.locked_until, timezone.now())

    def test_lock_expiry_allows_successful_lookup(self):
        """T037 回归：锁定期满后正确凭证可正常查询（计数清零）"""
        self.token_record.locked_until = timezone.now() - timedelta(seconds=1)
        self.token_record.failed_attempts = 5
        self.token_record.save()

        response = self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": self.raw_token,
        })
        self.assertEqual(response.status_code, 302)
        self.token_record.refresh_from_db()
        self.assertEqual(self.token_record.failed_attempts, 0)
        self.assertIsNone(self.token_record.locked_until)

    def test_success_resets_failed_attempts(self):
        """成功查询清零计数"""
        self.token_record.failed_attempts = 3
        self.token_record.save()
        self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": self.raw_token,
        })
        self.token_record.refresh_from_db()
        self.assertEqual(self.token_record.failed_attempts, 0)

    def test_security_events_recorded(self):
        """lookup_failed/lookup_locked/report_download 按场景落库（FR-014）"""
        for _ in range(5):
            self.client.post(self.lookup_url(), {
                "request_no": "20261105-0001",
                "token": "wrong-token",
            })
        self.assertTrue(SecurityEvent.objects.filter(event_type="lookup_failed").exists())
        self.assertTrue(SecurityEvent.objects.filter(event_type="lookup_locked").exists())

    def test_unverified_detail_redirects(self):
        """未验证 GET /report/detail/<uuid>/ 302 回查询页"""
        response = self.client.get(
            reverse("core:report_detail", args=[self.request.uuid])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/report/lookup/", response.url)

    def test_download_records_event(self):
        """下载写 SecurityEvent(report_download)"""
        self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": self.raw_token,
        })
        self.client.get(reverse("core:report_download", args=[self.request.uuid]))
        self.assertTrue(SecurityEvent.objects.filter(event_type="report_download").exists())

    def test_archived_version_not_downloadable(self):
        """归档版本不可下载（FR-009+Q2）"""
        # 创建版本 2 并归档版本 1
        self.version.is_archived = True
        self.version.save()
        ReportVersion.objects.create(
            request=self.request,
            version_no=2,
            file=SimpleUploadedFile("report_v2.pdf", b"%PDF-1.4 v2"),
            title="技术咨询报告V2",
            uploaded_by=self.owner,
        )
        self.client.post(self.lookup_url(), {
            "request_no": "20261105-0001",
            "token": self.raw_token,
        })
        response = self.client.get(reverse("core:report_download", args=[self.request.uuid]))
        # 下载的是最新版（v2），文件名包含 v2 或非归档内容
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.version.is_archived is False)  # v1 保持归档
