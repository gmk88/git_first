"""
数据模型：企业技术咨询报告系统
严格按 data-model.md 第 1-7 节实现
"""
import uuid
from django.contrib.auth.models import User
from django.core.validators import MaxLengthValidator
from django.db import models


class Stage(models.TextChoices):
    """阶段状态机：pending → accepted → evaluating → consulting → drafting → delivered"""
    PENDING = "pending", "待受理"
    ACCEPTED = "accepted", "受理"
    EVALUATING = "evaluating", "评估"
    CONSULTING = "consulting", "执行咨询"
    DRAFTING = "drafting", "报告撰写"
    DELIVERED = "delivered", "已交付"


class ConsultationRequest(models.Model):
    """咨询申请（FR-002/004/006/007）"""
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request_no = models.CharField(max_length=15, unique=True, verbose_name="申请编号")
    company_name = models.CharField(max_length=200, verbose_name="企业名称")
    contact_person = models.CharField(max_length=100, verbose_name="联系人")
    contact_phone = models.CharField(max_length=30, verbose_name="联系电话")
    contact_email = models.EmailField(verbose_name="邮箱")
    requirement = models.TextField(
        max_length=5000,
        validators=[MaxLengthValidator(5000)],
        verbose_name="咨询需求描述",
    )
    expected_date = models.DateField(null=True, blank=True, verbose_name="期望完成时间")
    stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        default=Stage.PENDING,
        verbose_name="当前阶段"
    )
    owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="负责顾问"
    )
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="提交时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "咨询申请"
        verbose_name_plural = verbose_name
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.request_no} - {self.company_name}"


class StageTransitionRecord(models.Model):
    """阶段流转记录（FR-007 + 澄清 Q1：回退必须填写原因）"""
    class TransitionKind(models.TextChoices):
        ADVANCE = "advance", "推进"
        ROLLBACK = "rollback", "回退"
        CLAIM = "claim", "认领"

    request = models.ForeignKey(
        ConsultationRequest,
        on_delete=models.PROTECT,
        related_name="transitions",
        verbose_name="所属申请"
    )
    from_stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        null=True,
        blank=True,
        verbose_name="前阶段"
    )
    to_stage = models.CharField(max_length=20, choices=Stage.choices, verbose_name="后阶段")
    kind = models.CharField(max_length=10, choices=TransitionKind.choices, verbose_name="流转类型")
    reason = models.TextField(blank=True, verbose_name="回退原因")
    operator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="transitions",
        verbose_name="操作人"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="操作时间")

    class Meta:
        verbose_name = "阶段流转记录"
        verbose_name_plural = verbose_name
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.request.request_no}: {self.from_stage} → {self.to_stage} ({self.kind})"


class CommunicationNote(models.Model):
    """沟通纪要（FR-008：不可修改、不可删除）"""
    class Channel(models.TextChoices):
        PHONE = "phone", "电话"
        WECHAT = "wechat", "微信"
        EMAIL = "email", "邮件"
        MEETING = "meeting", "会议"
        OTHER = "other", "其他"

    request = models.ForeignKey(
        ConsultationRequest,
        on_delete=models.PROTECT,
        related_name="notes",
        verbose_name="所属申请"
    )
    communicated_at = models.DateTimeField(verbose_name="沟通时间")
    channel = models.CharField(max_length=10, choices=Channel.choices, verbose_name="沟通方式")
    summary = models.TextField(
        max_length=2000,
        validators=[MaxLengthValidator(2000)],
        verbose_name="内容摘要",
    )
    recorder = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="notes",
        verbose_name="记录人"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "沟通纪要"
        verbose_name_plural = verbose_name
        ordering = ["-communicated_at"]

    def __str__(self):
        return f"{self.request.request_no} - {self.get_channel_display()} ({self.communicated_at.date()})"


class ReportVersion(models.Model):
    """咨询报告版本（FR-009 + 澄清 Q2：旧版本自动归档，客户仅见最新版）"""
    request = models.ForeignKey(
        ConsultationRequest,
        on_delete=models.PROTECT,
        related_name="versions",
        verbose_name="所属申请"
    )
    version_no = models.PositiveIntegerField(verbose_name="版本号")
    file = models.FileField(upload_to="reports/", verbose_name="报告文件")
    title = models.CharField(max_length=200, verbose_name="报告标题")
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="uploaded_reports",
        verbose_name="上传人"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")
    is_archived = models.BooleanField(default=False, verbose_name="已归档")

    class Meta:
        verbose_name = "咨询报告"
        verbose_name_plural = verbose_name
        ordering = ["-version_no"]
        unique_together = [["request", "version_no"]]

    def __str__(self):
        return f"{self.request.request_no} v{self.version_no} - {self.title}"


class ReportAccessToken(models.Model):
    """报告查询凭证（FR-010/011：哈希存储 + 失败锁定）"""
    request = models.OneToOneField(
        ConsultationRequest,
        on_delete=models.PROTECT,
        related_name="token",
        verbose_name="所属申请"
    )
    token_hash = models.CharField(max_length=64, unique=True, verbose_name="凭证哈希")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="生成时间")
    failed_attempts = models.PositiveIntegerField(default=0, verbose_name="连续失败次数")
    locked_until = models.DateTimeField(null=True, blank=True, verbose_name="锁定截止时间")
    last_queried_at = models.DateTimeField(null=True, blank=True, verbose_name="最近查询时间")

    class Meta:
        verbose_name = "报告查询凭证"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.request.request_no} - {self.token_hash[:16]}..."


class SecurityEvent(models.Model):
    """安全事件日志（FR-014：结构化记录，保留 ≥180 天）"""
    class EventType(models.TextChoices):
        LOGIN_SUCCESS = "login_success", "登录成功"
        LOGIN_FAILED = "login_failed", "登录失败"
        LOOKUP_FAILED = "lookup_failed", "凭证查询失败"
        LOOKUP_LOCKED = "lookup_locked", "凭证查询锁定"
        REPORT_DOWNLOAD = "report_download", "报告下载"

    event_type = models.CharField(max_length=20, choices=EventType.choices, verbose_name="事件类型")
    actor = models.CharField(max_length=150, blank=True, verbose_name="主体（账户名/申请编号）")
    source_ip = models.GenericIPAddressField(verbose_name="来源 IP")
    detail = models.CharField(max_length=500, blank=True, verbose_name="补充信息")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="时间")

    class Meta:
        verbose_name = "安全事件"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.actor} ({self.created_at})"


class SiteContentBlock(models.Model):
    """官网内容区块（FR-001/015：固定 4 块，仅可编辑不可增删）"""
    class BlockKey(models.TextChoices):
        SERVICES = "services", "服务介绍"
        PROCESS = "process", "服务流程"
        ABOUT = "about", "关于我们"
        CONTACT = "contact", "联系方式"

    key = models.CharField(
        max_length=20,
        choices=BlockKey.choices,
        unique=True,
        verbose_name="区块标识"
    )
    title = models.CharField(max_length=100, verbose_name="区块标题")
    body = models.TextField(verbose_name="区块正文")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "官网内容区块"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.get_key_display()} - {self.title}"
