"""测试后台视图（T018/T019，先写后实现）"""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    CommunicationNote,
    ConsultationRequest,
    ReportAccessToken,
    ReportVersion,
    Stage,
    StageTransitionRecord,
)
from core.services import hash_token


def make_request(request_no, owner=None, stage=Stage.PENDING):
    return ConsultationRequest.objects.create(
        request_no=request_no,
        company_name="测试企业",
        contact_person="张三",
        contact_phone="13800138000",
        contact_email="test@example.com",
        requirement="技术咨询需求描述",
        stage=stage,
        owner=owner,
    )


def make_consultant(username):
    user = User.objects.create_user(username=username, password="testpass123", is_staff=True)
    group, _ = Group.objects.get_or_create(name="consultant")
    user.groups.add(group)
    return user


class ProcessViewPermissionTest(TestCase):
    """流转与权限（T018）"""

    def setUp(self):
        self.consultant_a = make_consultant("consultant_a")
        self.consultant_b = make_consultant("consultant_b")
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "adminpass123")
        self.request_a = make_request("20261105-0001", owner=self.consultant_a)
        self.request_b = make_request("20261105-0002", owner=self.consultant_b)

    def process_url(self, req):
        return reverse("core:request_process", args=[req.pk])

    def test_unauthenticated_redirects_to_login(self):
        """未登录 302 到登录页"""
        response = self.client.get(self.process_url(self.request_a))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_owner_can_open_process_page(self):
        """顾问登录后 GET 自己的申请处理页 200"""
        self.client.login(username="consultant_a", password="testpass123")
        response = self.client.get(self.process_url(self.request_a))
        self.assertEqual(response.status_code, 200)

    def test_other_consultant_forbidden(self):
        """顾问 A 访问顾问 B 的申请 403"""
        self.client.login(username="consultant_a", password="testpass123")
        response = self.client.get(self.process_url(self.request_b))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_open_any_request(self):
        """管理员可打开任意申请"""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(self.process_url(self.request_b))
        self.assertEqual(response.status_code, 200)

    def test_advance_creates_transition_record(self):
        """推进 pending→accepted 产生 StageTransitionRecord(kind=advance)"""
        self.client.login(username="consultant_a", password="testpass123")
        response = self.client.post(self.process_url(self.request_a), {"action": "advance"})
        self.assertEqual(response.status_code, 302)
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.stage, Stage.ACCEPTED)
        record = StageTransitionRecord.objects.get(request=self.request_a, kind="advance")
        self.assertEqual(record.operator, self.consultant_a)
        self.assertEqual(record.from_stage, Stage.PENDING)
        self.assertEqual(record.to_stage, Stage.ACCEPTED)

    def test_rollback_without_reason_fails(self):
        """回退缺原因报错且 stage 不变"""
        self.request_a.stage = Stage.EVALUATING
        self.request_a.save(update_fields=["stage"])
        self.client.login(username="consultant_a", password="testpass123")
        response = self.client.post(self.process_url(self.request_a), {
            "action": "rollback",
            "to_stage": Stage.ACCEPTED,
            "reason": "",
        })
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.stage, Stage.EVALUATING)
        self.assertEqual(StageTransitionRecord.objects.filter(request=self.request_a).count(), 0)
        self.assertContains(response, "回退原因必填")

    def test_rollback_with_reason_succeeds(self):
        """回退带原因成功且记录 kind=rollback、reason 落库"""
        self.request_a.stage = Stage.EVALUATING
        self.request_a.save(update_fields=["stage"])
        self.client.login(username="consultant_a", password="testpass123")
        response = self.client.post(self.process_url(self.request_a), {
            "action": "rollback",
            "to_stage": Stage.ACCEPTED,
            "reason": "企业资料不全，退回补充",
        })
        self.assertEqual(response.status_code, 302)
        self.request_a.refresh_from_db()
        self.assertEqual(self.request_a.stage, Stage.ACCEPTED)
        record = StageTransitionRecord.objects.get(request=self.request_a, kind="rollback")
        self.assertEqual(record.reason, "企业资料不全，退回补充")
        self.assertEqual(record.from_stage, Stage.EVALUATING)

    def test_delivered_has_no_advance_action(self):
        """delivered 后页面无推进按钮"""
        self.request_a.stage = Stage.DELIVERED
        self.request_a.save(update_fields=["stage"])
        self.client.login(username="consultant_a", password="testpass123")
        response = self.client.get(self.process_url(self.request_a))
        self.assertNotContains(response, 'name="action" value="advance"')


class NotesAndReportTest(TestCase):
    """纪要与报告（T019）"""

    def setUp(self):
        self.consultant = make_consultant("consultant_x")
        self.admin = User.objects.create_superuser("admin2", "admin2@example.com", "adminpass123")
        self.request = make_request("20261105-0010", owner=self.consultant, stage=Stage.DRAFTING)

    def process_url(self):
        return reverse("core:request_process", args=[self.request.pk])

    def test_add_note(self):
        """添加纪要成功且 recorder=当前用户"""
        self.client.login(username="consultant_x", password="testpass123")
        response = self.client.post(self.process_url(), {
            "action": "note",
            "communicated_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "channel": "phone",
            "summary": "电话沟通了需求范围",
        })
        self.assertEqual(response.status_code, 302)
        note = CommunicationNote.objects.get(request=self.request)
        self.assertEqual(note.recorder, self.consultant)
        self.assertEqual(note.summary, "电话沟通了需求范围")

    def test_add_note_saves_timezone_aware_datetime(self):
        """T033 回归：纪要时间必须为 aware datetime（USE_TZ=True）"""
        import warnings

        from django.utils import timezone as tz

        self.client.login(username="consultant_x", password="testpass123")
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)  # 任何 naive 告警都视为失败
            response = self.client.post(self.process_url(), {
                "action": "note",
                "communicated_at": "2026-11-05T10:30",
                "channel": "email",
                "summary": "邮件确认了报告范围",
            })
        self.assertEqual(response.status_code, 302)
        note = CommunicationNote.objects.get(request=self.request, summary="邮件确认了报告范围")
        self.assertTrue(tz.is_aware(note.communicated_at))

    def test_upload_pdf_generates_token_once(self):
        """上传 .pdf 成功→凭证明文仅首次响应可见，哈希落库，stage=delivered"""
        self.client.login(username="consultant_x", password="testpass123")
        pdf = SimpleUploadedFile("report.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        response = self.client.post(self.process_url(), {
            "action": "upload",
            "file": pdf,
            "title": "技术咨询报告",
        })
        self.assertEqual(response.status_code, 302)
        self.request.refresh_from_db()
        self.assertEqual(self.request.stage, Stage.DELIVERED)
        token_record = ReportAccessToken.objects.get(request=self.request)
        self.assertNotEqual(token_record.token_hash, "")
        self.assertEqual(len(token_record.token_hash), 64)

        # 首次跳转页面展示明文凭证
        first = self.client.get(response.url)
        self.assertContains(first, "新凭证")
        # 再次刷新不再展示
        second = self.client.get(response.url)
        self.assertNotContains(second, "新凭证")

    def test_upload_txt_rejected(self):
        """上传 .txt 被拒（FR-017）"""
        self.client.login(username="consultant_x", password="testpass123")
        txt = SimpleUploadedFile("report.txt", b"plain text", content_type="text/plain")
        response = self.client.post(self.process_url(), {
            "action": "upload",
            "file": txt,
            "title": "报告",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "仅允许 PDF / Word")
        self.assertEqual(ReportVersion.objects.filter(request=self.request).count(), 0)

    def test_upload_over_50mb_rejected(self):
        """上传 >50MB 被拒（FR-009；用缩小上限等价验证）"""
        from django.test import override_settings

        self.client.login(username="consultant_x", password="testpass123")
        big = SimpleUploadedFile("big.pdf", b"%PDF" + b"x" * 100, content_type="application/pdf")
        with override_settings(REPORT_MAX_UPLOAD_SIZE=10):
            response = self.client.post(self.process_url(), {
                "action": "upload",
                "file": big,
                "title": "大文件",
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "50MB")
        self.assertEqual(ReportVersion.objects.filter(request=self.request).count(), 0)

    def test_second_upload_archives_first(self):
        """二次上传→版本 2 且版本 1 归档（澄清 Q2）"""
        self.client.login(username="consultant_x", password="testpass123")
        pdf1 = SimpleUploadedFile("report_v1.pdf", b"%PDF-1.4 v1", content_type="application/pdf")
        self.client.post(self.process_url(), {"action": "upload", "file": pdf1, "title": "报告V1"})
        # 第二次上传时申请已 delivered，需要先回退到 drafting？不——上传新版本允许在 delivered 后
        pdf2 = SimpleUploadedFile("report_v2.pdf", b"%PDF-1.4 v2", content_type="application/pdf")
        self.client.post(self.process_url(), {"action": "upload", "file": pdf2, "title": "报告V2"})

        versions = ReportVersion.objects.filter(request=self.request).order_by("version_no")
        self.assertEqual(versions.count(), 2)
        self.assertEqual(versions[0].version_no, 1)
        self.assertTrue(versions[0].is_archived)
        self.assertEqual(versions[1].version_no, 2)
        self.assertFalse(versions[1].is_archived)

    def test_superuser_owner_change_keeps_operator(self):
        """重指派后原流转记录 operator 不变（FR-013）"""
        self.client.login(username="consultant_x", password="testpass123")
        self.client.post(self.process_url(), {"action": "advance"})
        record = StageTransitionRecord.objects.get(request=self.request)
        other = make_consultant("consultant_y")
        self.request.owner = other
        self.request.save(update_fields=["owner"])
        record.refresh_from_db()
        self.assertEqual(record.operator, self.consultant)
