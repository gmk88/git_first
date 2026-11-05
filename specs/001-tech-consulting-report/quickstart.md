# Quickstart: 端到端验收指南

Feature: 001-tech-consulting-report | Date: 2026-11-05

本指南验证系统三大用户故事端到端可用，对应宪法 G3 门禁（spec 场景全部验收）。
全部命令在仓库根 `D:\git_first` 执行。

## 前置条件

- Python 3.14（本机已装）；Django 5.2 已安装到 `.venv`（plan 阶段完成）。
- 首次运行前完成初始化（若 tasks 未执行则先按 tasks 完成实现）。

## 1. 初始化与启动

```bash
# 虚拟环境（已存在则跳过）
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 环境变量
copy .env.example .env   # 按 .env.example 填 SECRET_KEY（可用下方命令生成）

# 生成密钥（一次性）
.venv/Scripts/python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 建库 + 初始数据
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py createsuperuser   # 管理员账户（FR-016）

# 启动
.venv/Scripts/python.exe manage.py runserver
```

预期：`http://127.0.0.1:8000/` 打开官网首页，4 个区块完整显示（Story 1
验收 1 ✅）。

## 2. 静态检查与自动化测试（宪法 G3）

```bash
.venv/Scripts/python.exe manage.py check        # 框架级检查，预期 0 issues
.venv/Scripts/python.exe -m compileall -q core config   # 语法检查
.venv/Scripts/python.exe manage.py test tests -v 2      # 全部测试通过
```

预期：三命令退出码 0；测试覆盖 spec 全部验收场景（详见 tests/ 五个模块）。

## 3. 用户故事 1：访客提交咨询申请（P1）

1. 打开 `http://127.0.0.1:8000/request/`。
2. 直接点提交（空表单）→ 预期：逐字段错误提示，已填内容保留（验收 3 ✅）。
3. 填写：企业名称、联系人、电话 `13800138000`、邮箱 `a@b.com`、需求描述
   ≥ 10 字 → 提交。
4. 预期：跳转受理确认页，显示格式为 `YYYYMMDD-NNNN` 的申请编号（验收 2 ✅，
   FR-004）。**记下该编号**，后续步骤要用。
5. 检查页面无任何个人信息回显（FR-018 ✅）。

## 4. 用户故事 2：顾问受理并交付报告（P2）

1. 打开 `http://127.0.0.1:8000/admin/`，用管理员登录（另观察：
   登录失败会记 SecurityEvent——可在 Admin 的 Security events 中查看，
   FR-014 ✅）。
2. Admin → 咨询申请列表：可见步骤 3 提交的申请，企业/联系人/时间/阶段
   （pending）/负责人列完整（验收 1 ✅）。
3. 进入申请处理页：认领（owner 变为当前顾问，kind=claim 记录产生）。
4. 依次推进：受理 → 评估 → 执行咨询 → 报告撰写（每次推进产生
   StageTransitionRecord）。
5. **回退测试（澄清 Q1）**：回退到"受理"，原因留空提交 → 预期：报错
   "回退原因必填"，无任何变更；填写原因再提交 → 预期：阶段回退 + 回退记录
   （验收 5 ✅）。
6. **纪要不可变测试（FR-008）**：添加一条纪要 → 预期：成功并出现在时间线；
   界面无修改/删除入口。
7. 重新推进至"报告撰写"，上传一个 PDF（>0 且 <50MB）+ 标题 → 预期：
   页面一次性展示查询凭证（明文）——**记下凭证**；申请阶段变为"已交付"
   （验收 4 ✅）。
8. **版本归档测试（澄清 Q2）**：再次上传新版本报告 → 预期：版本 2 出现，
   版本 1 标记归档；报告下载入口仅指向版本 2。

## 5. 用户故事 3：客户查询下载报告（P3）

1. 退出登录（或无痕窗口）打开 `http://127.0.0.1:8000/report/lookup/`。
2. 输入步骤 4 的编号 + 步骤 4.7 的凭证 → 预期：进入详情页，展示企业名称/
   报告标题/交付日期 + 下载入口（验收 1 ✅）。
3. 点击下载 → 预期：文件流式下载成功；Security events 中出现
   `report_download` 记录（FR-014 ✅）。
4. **错误提示测试**：新无痕窗口，输入正确编号 + 错误凭证 → 预期：
   "编号或凭证不正确"（验收 2 ✅）。重复 5 次 → 预期：第 5 次起提示
   锁定 15 分钟（验收 3 ✅，FR-011）；锁定期内即使输入正确凭证也被拒。
5. **防枚举测试（宪法第 3 条）**：直接访问一个随机 uuid 的
   `/report/detail/<random-uuid>/` → 预期：重定向回查询页，无存在性泄露。

## 6. 安全红线抽检（SC-006 / FR-018 / FR-012）

```bash
# 报告文件不得有公开静态路由：以下 URL 均不应返回报告文件
curl -s -o NUL -w "%{http_code}" http://127.0.0.1:8000/media/reports/
curl -s -o NUL -w "%{http_code}" http://127.0.0.1:8000/static/../media/reports/
```

预期：404/重定向，任何路径都不能绕过鉴权直接命中报告文件。

## 7. 验收完成标志

- 上述 1–6 全部符合预期。
- `manage.py test` 全绿。
- 未验证项（如有）在交付说明中标记"未验证"，禁止声称通过（宪法 G4）。
