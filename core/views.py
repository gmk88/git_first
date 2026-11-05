"""Core 视图"""
import re

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.forms import ConsultationRequestForm
from core.models import ConsultationRequest, SecurityEvent, SiteContentBlock
from core.services import (
    add_note,
    advance_request,
    claim_request,
    create_request,
    next_stage,
    previous_stages,
    rollback_request,
    upload_report,
    verify_lookup,
)

# ============ 公开视图（US1） ============


def home(request):
    """首页（FR-001：展示四个内容区块）"""
    blocks = SiteContentBlock.objects.all().order_by("key")
    return render(request, "core/home.html", {"blocks": blocks})


def request_form(request):
    """申请表单（FR-002/003：GET 渲染，POST 校验并创建申请）"""
    if request.method == "POST":
        form = ConsultationRequestForm(request.POST)
        if form.is_valid():
            new_request = create_request(form.cleaned_data)
            return redirect("core:request_done", request_no=new_request.request_no)
        # 校验失败：保留已填内容重新渲染（FR-003）
        return render(request, "core/request_form.html", {"form": form})
    else:
        form = ConsultationRequestForm()
        return render(request, "core/request_form.html", {"form": form})


def request_done(request, request_no):
    """受理确认页（FR-004/018：仅展示编号，不回显个人信息）"""
    return render(request, "core/request_done.html", {"request_no": request_no})


# ============ 后台处理页（US2） ============


def _can_operate(user, consultation_request):
    """权限：管理员全部；顾问仅本人申请或未认领申请"""
    if user.is_superuser:
        return True
    if consultation_request.owner_id is None:
        return True
    return consultation_request.owner_id == user.pk


def _render_process(request, consultation_request, error=None):
    """渲染处理页上下文"""
    raw_token = request.session.pop("new_access_token", None)
    context = {
        "req": consultation_request,
        "transitions": consultation_request.transitions.select_related("operator").all(),
        "notes": consultation_request.notes.select_related("recorder").all(),
        "versions": consultation_request.versions.select_related("uploaded_by").all(),
        "next_stage": next_stage(consultation_request.stage),
        "previous_stages": previous_stages(consultation_request.stage),
        "new_token": raw_token,
        "error": error,
    }
    return render(request, "core/request_process.html", context)


def _handle_claim(request, consultation_request):
    claim_request(consultation_request, request.user)
    return redirect("core:request_process", pk=consultation_request.pk)


def _handle_advance(request, consultation_request):
    advance_request(consultation_request, request.user)
    return redirect("core:request_process", pk=consultation_request.pk)


def _handle_rollback(request, consultation_request):
    reason = request.POST.get("reason", "").strip()
    if not reason:
        raise ValueError("回退原因必填")
    rollback_request(
        consultation_request,
        request.user,
        request.POST.get("to_stage", ""),
        reason,
    )
    return redirect("core:request_process", pk=consultation_request.pk)


def _handle_note(request, consultation_request):
    communicated_at = parse_datetime(request.POST.get("communicated_at", ""))
    channel = request.POST.get("channel", "")
    summary = request.POST.get("summary", "").strip()
    if not communicated_at or not channel or not summary:
        raise ValueError("请完整填写沟通时间、方式与内容摘要")
    if timezone.is_naive(communicated_at):
        communicated_at = timezone.make_aware(communicated_at)
    add_note(consultation_request, request.user, communicated_at, channel, summary)
    return redirect("core:request_process", pk=consultation_request.pk)


def _handle_upload(request, consultation_request):
    uploaded_file = request.FILES.get("file")
    title = request.POST.get("title", "").strip()
    if not uploaded_file or not title:
        raise ValueError("请选择报告文件并填写报告标题")
    _, raw_token = upload_report(consultation_request, request.user, uploaded_file, title)
    if raw_token:
        request.session["new_access_token"] = raw_token
    return redirect("core:request_process", pk=consultation_request.pk)


_ACTION_HANDLERS = {
    "claim": _handle_claim,
    "advance": _handle_advance,
    "rollback": _handle_rollback,
    "note": _handle_note,
    "upload": _handle_upload,
}


@staff_member_required
def request_process(request, pk):
    """申请处理页（T022：流转/纪要/报告上传）"""
    try:
        consultation_request = ConsultationRequest.objects.select_related("owner").get(pk=pk)
    except ConsultationRequest.DoesNotExist:
        raise PermissionDenied("申请不存在或无权访问")

    if not _can_operate(request.user, consultation_request):
        raise PermissionDenied("无权操作他人名下的申请")

    if request.method == "GET":
        return _render_process(request, consultation_request)

    handler = _ACTION_HANDLERS.get(request.POST.get("action", ""))
    if handler is None:
        return _render_process(request, consultation_request, error="未知操作")

    try:
        return handler(request, consultation_request)
    except ValueError as exc:
        return _render_process(request, consultation_request, error=str(exc))


# ============ 报告查询（US3） ============


def _client_ip(request):
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _session_verified_request(request, consultation_request):
    """校验 session 中记录的已验证申请"""
    return request.session.get("verified_request_pk") == consultation_request.pk


def report_lookup(request):
    """报告查询页（FR-010/011：编号 + 凭证）"""
    error = None
    if request.method == "POST":
        request_no = request.POST.get("request_no", "").strip()
        raw_token = request.POST.get("token", "").strip()
        ok, result = verify_lookup(request_no, raw_token, _client_ip(request))
        if ok:
            request.session["verified_request_pk"] = result.pk
            return redirect("core:report_detail", uuid=result.uuid)
        error = result
    return render(request, "core/report_lookup.html", {"error": error})


def report_detail(request, uuid):
    """报告详情页（FR-012：仅 session 已验证可访问）"""
    consultation_request = get_object_or_404(ConsultationRequest, uuid=uuid)
    if not _session_verified_request(request, consultation_request):
        return redirect("core:report_lookup")

    latest = consultation_request.versions.filter(is_archived=False).first()
    return render(request, "core/report_detail.html", {
        "req": consultation_request,
        "latest": latest,
        "delivered_at": latest.uploaded_at if latest else None,
    })


_ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _download_filename(consultation_request, version):
    """构造可识别的下载文件名：「申请编号-报告标题.扩展名」（T038）"""
    extension = version.file.name.rsplit(".", 1)[-1].lower()
    safe_title = _ILLEGAL_FILENAME_CHARS.sub("_", version.title).strip() or "报告"
    return f"{consultation_request.request_no}-{safe_title}.{extension}"


def report_download(request, uuid):
    """报告下载（FR-012：鉴权 + 流式返回最新版）"""
    consultation_request = get_object_or_404(ConsultationRequest, uuid=uuid)
    if not _session_verified_request(request, consultation_request):
        return redirect("core:report_lookup")

    latest = consultation_request.versions.filter(is_archived=False).first()
    if latest is None:
        raise Http404("报告不存在")

    SecurityEvent.objects.create(
        event_type=SecurityEvent.EventType.REPORT_DOWNLOAD,
        actor=consultation_request.request_no,
        source_ip=_client_ip(request),
        detail=f"下载报告 v{latest.version_no}",
    )

    filename = _download_filename(consultation_request, latest)
    return FileResponse(
        latest.file.open("rb"),
        as_attachment=True,
        filename=filename,
        content_type="application/octet-stream",
    )
