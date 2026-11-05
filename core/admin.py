"""
Admin 定制（T008 + T023）
"""
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from core.models import (
    CommunicationNote,
    ConsultationRequest,
    ReportAccessToken,
    ReportVersion,
    SecurityEvent,
    SiteContentBlock,
    StageTransitionRecord,
)

# 站点标题定制（中文）
admin.site.site_header = "咨询管理后台"
admin.site.site_title = "技术咨询"
admin.site.index_title = "后台管理"


@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(admin.ModelAdmin):
    """咨询申请管理（FR-006/013）"""
    list_display = ["request_no", "company_name", "contact_person", "stage", "owner", "submitted_at", "process_link"]
    list_filter = ["stage", "submitted_at"]
    search_fields = ["request_no", "company_name", "contact_person", "contact_email"]
    readonly_fields = ["uuid", "request_no", "submitted_at", "updated_at"]
    fields = [
        "uuid", "request_no", "company_name", "contact_person", "contact_phone",
        "contact_email", "requirement", "expected_date", "stage", "owner",
        "submitted_at", "updated_at",
    ]

    def process_link(self, obj):
        """T023：处理申请链接"""
        if obj.pk:
            url = reverse("core:request_process", args=[obj.pk])
            return format_html('<a href="{}" target="_blank">处理申请</a>', url)
        return "-"
    process_link.short_description = "操作"

    def get_queryset(self, request):
        """顾问仅见自己申请；管理员见全部（FR-006）"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(owner=request.user)

    def has_add_permission(self, request):
        """申请只能经前台表单产生"""
        return False

    def has_delete_permission(self, request, obj=None):
        """禁止删除申请"""
        return False


@admin.register(StageTransitionRecord)
class StageTransitionRecordAdmin(admin.ModelAdmin):
    """阶段流转记录（FR-008：只读不可变）"""
    list_display = ["request", "from_stage", "to_stage", "kind", "operator", "created_at"]
    list_filter = ["kind", "created_at"]
    readonly_fields = ["request", "from_stage", "to_stage", "kind", "reason", "operator", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommunicationNote)
class CommunicationNoteAdmin(admin.ModelAdmin):
    """沟通纪要（FR-008：只读不可变）"""
    list_display = ["request", "channel", "communicated_at", "recorder", "created_at"]
    list_filter = ["channel", "communicated_at"]
    readonly_fields = ["request", "communicated_at", "channel", "summary", "recorder", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReportVersion)
class ReportVersionAdmin(admin.ModelAdmin):
    """咨询报告版本（只读展示）"""
    list_display = ["request", "version_no", "title", "uploaded_by", "uploaded_at", "is_archived"]
    list_filter = ["is_archived", "uploaded_at"]
    readonly_fields = ["request", "version_no", "file", "title", "uploaded_by", "uploaded_at", "is_archived"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReportAccessToken)
class ReportAccessTokenAdmin(admin.ModelAdmin):
    """报告查询凭证（FR-010：管理员可重置）"""
    list_display = ["request", "token_hash_display", "failed_attempts", "locked_until", "created_at"]
    readonly_fields = ["request", "token_hash", "created_at", "last_queried_at"]
    actions = ["regenerate_token_action"]

    def token_hash_display(self, obj):
        return obj.token_hash[:16] + "..."
    token_hash_display.short_description = "凭证哈希"

    def regenerate_token_action(self, request, queryset):
        """T023：重置凭证（仅管理员）"""
        if not request.user.is_superuser:
            self.message_user(request, "仅管理员可重置凭证", level="error")
            return
        from core.services import regenerate_token
        for token_record in queryset:
            raw_token = regenerate_token(token_record, request.user)
            self.message_user(
                request,
                f"{token_record.request.request_no} 新凭证（仅显示一次，请记录）：{raw_token}",
                level="success"
            )
    regenerate_token_action.short_description = "重新生成凭证（管理员）"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    """安全事件日志（FR-014：只读）"""
    list_display = ["event_type", "actor", "source_ip", "created_at"]
    list_filter = ["event_type", "created_at"]
    readonly_fields = ["event_type", "actor", "source_ip", "detail", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SiteContentBlock)
class SiteContentBlockAdmin(admin.ModelAdmin):
    """官网内容区块（FR-015：仅可编辑，禁增删）"""
    list_display = ["key", "title", "updated_at"]
    readonly_fields = ["key", "updated_at"]
    fields = ["key", "title", "body", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# 用户管理（FR-016：仅管理员可创建顾问账户）
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """用户管理（FR-016）"""
    def has_module_permission(self, request):
        """仅 superuser 可见用户管理"""
        return request.user.is_superuser
