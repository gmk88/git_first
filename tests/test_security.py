"""测试安全红线（T026，先写后实现）"""
from urllib.parse import unquote

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import ConsultationRequest, ReportAccessToken, ReportVersion, Stage
from core.services import hash_token


class SecurityRedLineTest(TestCase):
    """SC-006 安全红线"""

    def setUp(self):
        self.owner = User.objects.create_user("owner2", password="pass12345", is_staff=True)
        self.request = ConsultationRequest.objects.create(
            request_no="20261105-0100",
            company_name="测试企业",
            contact_person="李四",
            contact_phone="13900139000",
            contact_email="test@example.com",
            requirement="需求",
            stage=Stage.DELIVERED,
            owner=self.owner,
        )
        self.raw_token = "token-xyz-789"
        ReportAccessToken.objects.create(
            request=self.request,
            token_hash=hash_token(self.raw_token),
        )
        ReportVersion.objects.create(
            request=self.request,
            version_no=1,
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4"),
            title="报告",
            uploaded_by=self.owner,
        )

    def test_media_reports_not_publicly_accessible(self):
        """/media/reports/ 不可达（报告文件无公开 URL）"""
        response = self.client.get("/media/reports/report.pdf")
        self.assertIn(response.status_code, (403, 404))

    def test_static_media_traversal_blocked(self):
        """/static/../media/ 路径不可达"""
        response = self.client.get("/static/../media/reports/report.pdf")
        self.assertIn(response.status_code, (400, 403, 404))

    def test_download_requires_verified_session(self):
        """下载需 session 验证（无 session 302）"""
        response = self.client.get(
            reverse("core:report_download", args=[self.request.uuid])
        )
        self.assertEqual(response.status_code, 302)

    def test_download_has_content_disposition(self):
        """下载响应带 Content-Disposition 文件名"""
        self.client.post(reverse("core:report_lookup"), {
            "request_no": "20261105-0100",
            "token": self.raw_token,
        })
        response = self.client.get(
            reverse("core:report_download", args=[self.request.uuid])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])

    def _verified_download(self):
        self.client.post(reverse("core:report_lookup"), {
            "request_no": "20261105-0100",
            "token": self.raw_token,
        })
        return self.client.get(
            reverse("core:report_download", args=[self.request.uuid])
        )

    def test_download_filename_contains_request_no_and_title(self):
        """T038 回归：下载文件名为「申请编号-报告标题.扩展名」"""
        response = self._verified_download()
        disposition = unquote(response["Content-Disposition"])
        self.assertIn("20261105-0100", disposition)
        self.assertIn("报告", disposition)
        self.assertIn(".pdf", disposition)

    def test_download_filename_strips_illegal_chars(self):
        """T038 回归：标题中的文件系统非法字符被替换，扩展名保留"""
        ReportVersion.objects.filter(request=self.request).update(
            title="技术/咨询:报告*?"
        )
        response = self._verified_download()
        filename = unquote(response["Content-Disposition"]).split("''")[-1]
        self.assertIn("技术_咨询_报告", filename)
        for bad_char in ("/", "\\", ":", "*", "?"):
            self.assertNotIn(bad_char, filename)
        self.assertIn(".pdf", filename)
