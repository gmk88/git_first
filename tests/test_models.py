"""测试数据模型（T010）"""
from django.test import TestCase
from django.utils import timezone
from core.models import ConsultationRequest, SiteContentBlock, Stage
from core.services import generate_request_no


class ConsultationRequestModelTest(TestCase):
    """咨询申请模型测试"""

    def test_request_no_format(self):
        """request_no 格式为 YYYYMMDD-NNNN"""
        today = timezone.now().strftime("%Y%m%d")
        req_no = generate_request_no()
        self.assertTrue(req_no.startswith(f"{today}-"))
        self.assertEqual(len(req_no), 13)  # 8+1+4=13
        self.assertEqual(req_no.split("-")[1], "0001")

    def test_request_no_increment(self):
        """同日两单编号递增"""
        req1 = ConsultationRequest.objects.create(
            request_no=generate_request_no(),
            company_name="测试企业1",
            contact_person="张三",
            contact_phone="13800138000",
            contact_email="test1@example.com",
            requirement="技术咨询需求描述",
        )
        req2 = ConsultationRequest.objects.create(
            request_no=generate_request_no(),
            company_name="测试企业2",
            contact_person="李四",
            contact_phone="13900139000",
            contact_email="test2@example.com",
            requirement="另一个技术咨询需求",
        )
        self.assertEqual(req1.request_no.split("-")[1], "0001")
        self.assertEqual(req2.request_no.split("-")[1], "0002")

    def test_uuid_unique(self):
        """uuid 字段唯一且自动生成"""
        req1 = ConsultationRequest.objects.create(
            request_no="20261105-0001",
            company_name="企业1",
            contact_person="王五",
            contact_phone="13700137000",
            contact_email="test@example.com",
            requirement="需求",
        )
        req2 = ConsultationRequest.objects.create(
            request_no="20261105-0002",
            company_name="企业2",
            contact_person="赵六",
            contact_phone="13600136000",
            contact_email="test2@example.com",
            requirement="需求2",
        )
        self.assertNotEqual(req1.uuid, req2.uuid)
        self.assertIsNotNone(req1.uuid)

    def test_stage_default_pending(self):
        """stage 默认值为 pending"""
        req = ConsultationRequest.objects.create(
            request_no="20261105-0001",
            company_name="测试企业",
            contact_person="测试",
            contact_phone="13800138000",
            contact_email="test@example.com",
            requirement="需求",
        )
        self.assertEqual(req.stage, Stage.PENDING)

    def test_requirement_max_length(self):
        """requirement 字段上限 5000 字符（full_clean 校验）"""
        long_text = "a" * 5001
        req = ConsultationRequest(
            request_no="20261105-0001",
            company_name="测试",
            contact_person="测试",
            contact_phone="13800138000",
            contact_email="test@example.com",
            requirement=long_text,
        )
        with self.assertRaises(Exception):  # ValidationError
            req.full_clean()


class SiteContentBlockModelTest(TestCase):
    """官网内容区块测试"""

    def test_initial_blocks_created(self):
        """迁移后恰有 4 行初始区块"""
        count = SiteContentBlock.objects.count()
        self.assertEqual(count, 4)

    def test_block_keys(self):
        """4 个区块 key 为 services/process/about/contact"""
        keys = set(SiteContentBlock.objects.values_list("key", flat=True))
        self.assertEqual(keys, {"services", "process", "about", "contact"})
