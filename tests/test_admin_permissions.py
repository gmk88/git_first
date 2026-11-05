"""Admin 权限约束测试（T035，FR-006/008/015/016）"""
from django.contrib.admin.sites import site as admin_site
from django.contrib.auth.models import Group, User
from django.test import RequestFactory, TestCase

from core.admin import ConsultationRequestAdmin
from core.models import ConsultationRequest


def _admin_instance(model):
    return admin_site._registry[model]


def _fake_request(user):
    request = RequestFactory().post("/")
    request.user = user
    return request


class AdminPermissionTest(TestCase):
    """ModelAdmin 权限约束（宪法第 4 条：可复现验收步骤）"""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser("root", "root@example.com", "rootpass123")
        cls.consultant = User.objects.create_user("worker", password="pass12345", is_staff=True)
        group, _ = Group.objects.get_or_create(name="consultant")
        cls.consultant.groups.add(group)

    def test_request_no_direct_add(self):
        """ConsultationRequest 禁止在 Admin 直接新增（申请仅经前台表单产生）"""
        admin = _admin_instance(ConsultationRequest)
        self.assertFalse(admin.has_add_permission(_fake_request(self.superuser)))

    def test_request_no_delete(self):
        """ConsultationRequest 禁止删除"""
        admin = _admin_instance(ConsultationRequest)
        self.assertFalse(admin.has_delete_permission(_fake_request(self.superuser)))

    def test_immutable_models_readonly(self):
        """流转记录/纪要/安全事件/报告版本：增改删全禁（FR-008 不可变）"""
        from core.models import (
            CommunicationNote,
            ReportVersion,
            SecurityEvent,
            StageTransitionRecord,
        )
        for model in (StageTransitionRecord, CommunicationNote, SecurityEvent, ReportVersion):
            admin = _admin_instance(model)
            request = _fake_request(self.superuser)
            self.assertFalse(admin.has_add_permission(request), model.__name__)
            self.assertFalse(admin.has_change_permission(request), model.__name__)
            self.assertFalse(admin.has_delete_permission(request), model.__name__)

    def test_site_block_no_add_no_delete(self):
        """官网内容区块：仅可编辑文案，禁增删（FR-015）"""
        from core.models import SiteContentBlock
        admin = _admin_instance(SiteContentBlock)
        request = _fake_request(self.superuser)
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_delete_permission(request))

    def test_user_module_superusers_only(self):
        """用户管理仅 superuser 可见（FR-016）"""
        from core.admin import CustomUserAdmin
        admin = CustomUserAdmin(User, admin_site)
        self.assertTrue(admin.has_module_permission(_fake_request(self.superuser)))
        self.assertFalse(admin.has_module_permission(_fake_request(self.consultant)))


class ConsultantQuerysetTest(TestCase):
    """顾问数据隔离（FR-006：仅见自己名下申请）"""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser("root2", "root2@example.com", "rootpass123")
        cls.owning = User.objects.create_user("owner1", password="pass12345", is_staff=True)
        cls.other = User.objects.create_user("owner2", password="pass12345", is_staff=True)
        cls.mine = ConsultationRequest.objects.create(
            request_no="20261105-0001",
            company_name="我的申请企业",
            contact_person="甲",
            contact_phone="13800138000",
            contact_email="a@example.com",
            requirement="需求",
            owner=cls.owning,
        )
        ConsultationRequest.objects.create(
            request_no="20261105-0002",
            company_name="别人的申请企业",
            contact_person="乙",
            contact_phone="13900139000",
            contact_email="b@example.com",
            requirement="需求",
            owner=cls.other,
        )

    def test_consultant_sees_only_own_requests(self):
        admin = _admin_instance(ConsultationRequest)
        qs = admin.get_queryset(_fake_request(self.owning))
        self.assertEqual(list(qs), [self.mine])

    def test_superuser_sees_all(self):
        admin = _admin_instance(ConsultationRequest)
        qs = admin.get_queryset(_fake_request(self.superuser))
        self.assertEqual(qs.count(), 2)
