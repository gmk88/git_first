"""
业务逻辑层：可复用的服务函数
宪法 G1 复用记录：供 views 与 admin 动作复用
"""
import hashlib
import secrets
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from core.models import (
    ConsultationRequest,
    ReportAccessToken,
    Stage,
    StageTransitionRecord,
)

STAGE_ORDER = [
    Stage.PENDING,
    Stage.ACCEPTED,
    Stage.EVALUATING,
    Stage.CONSULTING,
    Stage.DRAFTING,
    Stage.DELIVERED,
]


def generate_request_no():
    """生成申请编号：YYYYMMDD-NNNN（当日递增序号，4 位补零）"""
    today = timezone.now().strftime("%Y%m%d")
    today_prefix = f"{today}-"
    latest = (
        ConsultationRequest.objects
        .filter(request_no__startswith=today_prefix)
        .order_by("-request_no")
        .first()
    )
    if latest:
        last_seq = int(latest.request_no.split("-")[1])
        seq = last_seq + 1
    else:
        seq = 1
    return f"{today_prefix}{seq:04d}"


def next_stage(current_stage):
    """推进：返回下一阶段，已交付则返回 None"""
    try:
        idx = STAGE_ORDER.index(current_stage)
        if idx < len(STAGE_ORDER) - 1:
            return STAGE_ORDER[idx + 1]
        return None
    except ValueError:
        return None


def previous_stages(current_stage):
    """回退：返回任意早前阶段列表"""
    try:
        idx = STAGE_ORDER.index(current_stage)
        return STAGE_ORDER[:idx]
    except ValueError:
        return []


def hash_token(raw_token):
    """凭证哈希（SHA-256）"""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def verify_token(raw_token, token_hash):
    """常数时间比较（宪法第 3 条）"""
    return secrets.compare_digest(hash_token(raw_token), token_hash)


def new_access_token(request):
    """生成新凭证：明文 + 哈希落库（FR-010）"""
    raw_token = secrets.token_urlsafe(24)  # 约 192 bit 熵
    token_hash = hash_token(raw_token)
    ReportAccessToken.objects.update_or_create(
        request=request,
        defaults={"token_hash": token_hash, "failed_attempts": 0, "locked_until": None}
    )
    return raw_token


@transaction.atomic
def create_request(form_data):
    """创建咨询申请（FR-004：事务内生成编号 + 创建申请）"""
    request_no = generate_request_no()
    request = ConsultationRequest.objects.create(
        request_no=request_no,
        company_name=form_data["company_name"],
        contact_person=form_data["contact_person"],
        contact_phone=form_data["contact_phone"],
        contact_email=form_data["contact_email"],
        requirement=form_data["requirement"],
        expected_date=form_data.get("expected_date"),
    )
    return request


@transaction.atomic
def advance_request(request, user):
    """推进阶段（FR-007）"""
    if request.stage == Stage.DELIVERED:
        raise ValueError("已交付的申请不可再流转")
    next_stg = next_stage(request.stage)
    if not next_stg:
        raise ValueError(f"当前阶段 {request.stage} 不可推进")

    StageTransitionRecord.objects.create(
        request=request,
        from_stage=request.stage,
        to_stage=next_stg,
        kind=StageTransitionRecord.TransitionKind.ADVANCE,
        operator=user,
    )
    request.stage = next_stg
    request.save(update_fields=["stage", "updated_at"])


@transaction.atomic
def rollback_request(request, user, to_stage, reason):
    """回退阶段（FR-007 + 澄清 Q1：必须填写原因）"""
    if not reason or not reason.strip():
        raise ValueError("回退原因必填")
    if to_stage not in previous_stages(request.stage):
        raise ValueError(f"不可回退到 {to_stage}")

    StageTransitionRecord.objects.create(
        request=request,
        from_stage=request.stage,
        to_stage=to_stage,
        kind=StageTransitionRecord.TransitionKind.ROLLBACK,
        reason=reason,
        operator=user,
    )
    request.stage = to_stage
    request.save(update_fields=["stage", "updated_at"])


@transaction.atomic
def claim_request(request, user):
    """认领申请（FR-006/013）"""
    StageTransitionRecord.objects.create(
        request=request,
        from_stage=request.stage,
        to_stage=request.stage,
        kind=StageTransitionRecord.TransitionKind.CLAIM,
        operator=user,
    )
    request.owner = user
    request.save(update_fields=["owner", "updated_at"])


@transaction.atomic
def add_note(request, user, communicated_at, channel, summary):
    """添加沟通纪要（FR-008：不可修改删除）"""
    from core.models import CommunicationNote
    note = CommunicationNote.objects.create(
        request=request,
        communicated_at=communicated_at,
        channel=channel,
        summary=summary,
        recorder=user,
    )
    return note


@transaction.atomic
def upload_report(request, user, uploaded_file, title):
    """
    上传报告（FR-009 + 澄清 Q2：版本归档 + 首次生成凭证）

    Returns:
        (version, raw_token or None)
    """
    from core.models import ReportVersion

    # 扩展名校验（FR-017）
    file_ext = uploaded_file.name.lower().split(".")[-1]
    if file_ext not in ["pdf", "doc", "docx"]:
        raise ValueError("仅允许 PDF / Word（doc/docx）格式")

    # 大小校验（FR-009：默认 50MB，经 settings 可配置）
    from django.conf import settings
    max_size = getattr(settings, "REPORT_MAX_UPLOAD_SIZE", 50 * 1024 * 1024)
    if uploaded_file.size > max_size:
        raise ValueError("文件大小超过 50MB 上限")

    # 版本号
    latest = request.versions.order_by("-version_no").first()
    version_no = (latest.version_no + 1) if latest else 1

    # 归档旧版本
    request.versions.update(is_archived=True)

    # 创建新版本
    version = ReportVersion.objects.create(
        request=request,
        version_no=version_no,
        file=uploaded_file,
        title=title,
        uploaded_by=user,
        is_archived=False,
    )

    # 首次上传：生成凭证 + 推进到已交付
    raw_token = None
    if version_no == 1:
        raw_token = new_access_token(request)
        if request.stage == Stage.DRAFTING:
            advance_request(request, user)

    return version, raw_token


def _lookup_failure(request_no, source_ip, detail):
    """记录查询失败并返回统一错误（不泄露编号存在性）"""
    from core.models import SecurityEvent
    SecurityEvent.objects.create(
        event_type=SecurityEvent.EventType.LOOKUP_FAILED,
        actor=(request_no or "")[:50],
        source_ip=source_ip,
        detail=detail,
    )
    return False, "编号或凭证不正确"


def _record_failed_attempt(token_record, request_no, source_ip):
    """失败计数 +1；达 5 次锁定 15 分钟并记事件"""
    from core.models import SecurityEvent
    token_record.failed_attempts += 1
    if token_record.failed_attempts >= 5:
        token_record.locked_until = timezone.now() + timedelta(minutes=15)
        SecurityEvent.objects.create(
            event_type=SecurityEvent.EventType.LOOKUP_LOCKED,
            actor=request_no,
            source_ip=source_ip,
            detail=f"连续 {token_record.failed_attempts} 次失败，锁定 15 分钟",
        )
    token_record.save(update_fields=["failed_attempts", "locked_until"])
    SecurityEvent.objects.create(
        event_type=SecurityEvent.EventType.LOOKUP_FAILED,
        actor=request_no,
        source_ip=source_ip,
        detail="凭证错误",
    )
    return False, "编号或凭证不正确"


def _resolve_lookup_request(request_no, source_ip):
    """解析编号与凭证记录；失败返回 (None, error)"""
    if not request_no or "-" not in request_no:
        return None, _lookup_failure(request_no, source_ip, "编号格式错误")
    try:
        request = ConsultationRequest.objects.get(request_no=request_no)
    except ConsultationRequest.DoesNotExist:
        return None, _lookup_failure(request_no, source_ip, "编号不存在")
    try:
        token_record = request.token
    except ReportAccessToken.DoesNotExist:
        return None, _lookup_failure(request_no, source_ip, "凭证未生成")
    return (request, token_record), None


def verify_lookup(request_no, raw_token, source_ip):
    """凭证查询验证（FR-010/011 + 宪法第 3 条）"""
    resolved, error = _resolve_lookup_request(request_no, source_ip)
    if error:
        return error
    request, token_record = resolved

    now = timezone.now()
    if token_record.locked_until and token_record.locked_until > now:
        return False, "尝试次数过多，请 15 分钟后再试"
    if token_record.locked_until:
        # T037：锁定期已满，计数清零并解除锁定，重新给予 5 次机会
        token_record.failed_attempts = 0
        token_record.locked_until = None
        token_record.save(update_fields=["failed_attempts", "locked_until"])

    if verify_token(raw_token, token_record.token_hash):
        token_record.failed_attempts = 0
        token_record.last_queried_at = now
        token_record.save(update_fields=["failed_attempts", "last_queried_at"])
        return True, request
    return _record_failed_attempt(token_record, request_no, source_ip)


@transaction.atomic
def regenerate_token(token_record, user):
    """管理员重置凭证（FR-010 + Edge Case：凭证泄露）"""
    if not user.is_superuser:
        raise PermissionError("仅管理员可重置凭证")
    raw_token = secrets.token_urlsafe(24)
    token_hash = hash_token(raw_token)
    token_record.token_hash = token_hash
    token_record.failed_attempts = 0
    token_record.locked_until = None
    token_record.save(update_fields=["token_hash", "failed_attempts", "locked_until"])
    return raw_token
