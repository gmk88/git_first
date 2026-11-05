"""表单（T013）"""
import re
from django import forms


class ConsultationRequestForm(forms.Form):
    """咨询申请表单（FR-002/003）"""
    company_name = forms.CharField(
        max_length=200,
        required=True,
        label="企业名称",
        error_messages={"required": "请填写企业名称"},
    )
    contact_person = forms.CharField(
        max_length=100,
        required=True,
        label="联系人",
        error_messages={"required": "请填写联系人姓名"},
    )
    contact_phone = forms.CharField(
        max_length=30,
        required=True,
        label="联系电话",
        error_messages={"required": "请填写联系电话"},
    )
    contact_email = forms.EmailField(
        required=True,
        label="邮箱",
        error_messages={"required": "请填写邮箱", "invalid": "邮箱格式不正确"},
    )
    requirement = forms.CharField(
        max_length=5000,
        required=True,
        label="咨询需求描述",
        widget=forms.Textarea(attrs={"rows": 6}),
        error_messages={
            "required": "请填写咨询需求描述",
            "max_length": "需求描述不能超过 5000 字符",
        },
    )
    expected_date = forms.DateField(
        required=False,
        label="期望完成时间（可选）",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean_contact_phone(self):
        """电话格式校验：数字/+/-/空格"""
        phone = self.cleaned_data.get("contact_phone", "")
        if not re.match(r"^[0-9+\-\s]{5,30}$", phone):
            raise forms.ValidationError("电话格式不正确（仅允许数字、+、-、空格）")
        return phone
