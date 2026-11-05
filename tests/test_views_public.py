"""测试公开视图（T012）"""
from django.test import TestCase
from django.urls import reverse
from core.models import ConsultationRequest


class HomeViewTest(TestCase):
    """首页测试（FR-001）"""

    def test_home_page_renders_four_blocks(self):
        """GET / 四区块标题可见"""
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "技术咨询服务")
        self.assertContains(response, "服务流程")
        self.assertContains(response, "关于我们")
        self.assertContains(response, "联系方式")


class RequestFormViewTest(TestCase):
    """申请表单视图测试（FR-002/003/004/018）"""

    def test_get_form_page(self):
        """GET /request/ 含隐私说明"""
        response = self.client.get(reverse("core:request_form"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "仅用于本次咨询服务联系")
        self.assertContains(response, "不在官网公开展示")
        self.assertContains(response, "不提供给第三方")

    def test_post_valid_data_redirects_to_done(self):
        """POST 合法数据 302 到确认页且生成申请"""
        response = self.client.post(reverse("core:request_form"), data={
            "company_name": "某某企业",
            "contact_person": "王五",
            "contact_phone": "13800138000",
            "contact_email": "wangwu@example.com",
            "requirement": "技术架构评估咨询",
        })
        req = ConsultationRequest.objects.first()
        self.assertIsNotNone(req)
        self.assertRedirects(response, reverse("core:request_done", args=[req.request_no]))

    def test_done_page_only_shows_request_no(self):
        """确认页只显示编号不回显个人信息（FR-018）"""
        response = self.client.post(reverse("core:request_form"), data={
            "company_name": "某某企业",
            "contact_person": "王五",
            "contact_phone": "13800138000",
            "contact_email": "wangwu@example.com",
            "requirement": "技术咨询需求",
        })
        req = ConsultationRequest.objects.first()
        done_response = self.client.get(reverse("core:request_done", args=[req.request_no]))
        self.assertContains(done_response, req.request_no)
        self.assertNotContains(done_response, "王五")
        self.assertNotContains(done_response, "13800138000")
        self.assertNotContains(done_response, "wangwu@example.com")

    def test_post_invalid_data_preserves_input(self):
        """POST 非法数据 200 + 已填内容保留"""
        response = self.client.post(reverse("core:request_form"), data={
            "company_name": "测试企业",
            "contact_person": "",
            "contact_phone": "abc",
            "contact_email": "invalid",
            "requirement": "需求",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "测试企业")  # 已填内容保留
        self.assertContains(response, "请填写联系人姓名")  # 逐字段错误提示
