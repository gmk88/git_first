# 初始数据迁移（T007）
from django.db import migrations


def create_initial_data(apps, schema_editor):
    """写入 SiteContentBlock 4 行 + consultant Group"""
    SiteContentBlock = apps.get_model("core", "SiteContentBlock")
    Group = apps.get_model("auth", "Group")

    # 官网四区块占位文案
    blocks = [
        {
            "key": "services",
            "title": "技术咨询服务",
            "body": "我们为企业提供专业技术咨询服务，涵盖技术架构评估、系统优化建议、技术选型指导等多个领域，最终交付详尽的书面报告。",
        },
        {
            "key": "process",
            "title": "服务流程",
            "body": "1. 提交咨询申请\n2. 顾问受理并评估需求\n3. 执行咨询与沟通\n4. 撰写并交付报告\n5. 客户在线查询下载报告",
        },
        {
            "key": "about",
            "title": "关于我们",
            "body": "我们是一支经验丰富的技术顾问团队，致力于为企业提供高质量的技术咨询服务，助力企业数字化转型与技术升级。",
        },
        {
            "key": "contact",
            "title": "联系方式",
            "body": "邮箱：consult@example.com\n电话：400-xxx-xxxx\n地址：[待补充]",
        },
    ]

    for block_data in blocks:
        SiteContentBlock.objects.get_or_create(key=block_data["key"], defaults=block_data)

    # 顾问组
    Group.objects.get_or_create(name="consultant")


def reverse_initial_data(apps, schema_editor):
    """回滚：删除初始数据"""
    SiteContentBlock = apps.get_model("core", "SiteContentBlock")
    Group = apps.get_model("auth", "Group")
    SiteContentBlock.objects.all().delete()
    Group.objects.filter(name="consultant").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_initial_data, reverse_initial_data),
    ]
