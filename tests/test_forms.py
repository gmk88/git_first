"""测试表单（T011）"""
from django.test import TestCase
from core.forms import ConsultationRequestForm


class ConsultationRequestFormTest(TestCase):
    """咨询申请表单测试（FR-002/003）"""

    def test_empty_form_invalid(self):
        """全空提交逐字段报错"""
        form = ConsultationRequestForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("company_name", form.errors)
        self.assertIn("contact_person", form.errors)
        self.assertIn("contact_phone", form.errors)
        self.assertIn("contact_email", form.errors)
        self.assertIn("requirement", form.errors)
        # expected_date 非必填，不应在错误中
        self.assertNotIn("expected_date", form.errors)

    def test_invalid_phone(self):
        """电话含非法字符报错"""
        form = ConsultationRequestForm(data={
            "company_name": "测试企业",
            "contact_person": "张三",
            "contact_phone": "abc123",
            "contact_email": "test@example.com",
            "requirement": "技术咨询需求",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("contact_phone", form.errors)

    def test_valid_phone_formats(self):
        """合法电话格式通过"""
        valid_phones = ["13800138000", "+86-138-0013-8000", "010-12345678", "021 8888 9999"]
        for phone in valid_phones:
            form = ConsultationRequestForm(data={
                "company_name": "测试",
                "contact_person": "张三",
                "contact_phone": phone,
                "contact_email": "test@example.com",
                "requirement": "需求",
            })
            self.assertTrue(form.is_valid(), f"电话 {phone} 应通过校验")

    def test_invalid_email(self):
        """邮箱格式报错"""
        form = ConsultationRequestForm(data={
            "company_name": "测试",
            "contact_person": "张三",
            "contact_phone": "13800138000",
            "contact_email": "not-an-email",
            "requirement": "需求",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("contact_email", form.errors)

    def test_requirement_too_long(self):
        """requirement 超 5000 字符拒绝（非截断）"""
        long_text = "a" * 5001
        form = ConsultationRequestForm(data={
            "company_name": "测试",
            "contact_person": "张三",
            "contact_phone": "13800138000",
            "contact_email": "test@example.com",
            "requirement": long_text,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("requirement", form.errors)

    def test_valid_form(self):
        """合法数据通过"""
        form = ConsultationRequestForm(data={
            "company_name": "某某科技有限公司",
            "contact_person": "李四",
            "contact_phone": "13800138000",
            "contact_email": "lisi@company.com",
            "requirement": "希望评估我们的系统架构并提出优化建议。",
            "expected_date": "2026-12-31",
        })
        self.assertTrue(form.is_valid())
