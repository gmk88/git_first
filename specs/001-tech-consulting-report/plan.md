# Implementation Plan: 企业技术咨询报告系统

**Branch**: `001-tech-consulting-report` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-tech-consulting-report/spec.md`

## Summary

构建"企业官网 + 咨询后台 + 报告查询"一体化系统：访客浏览官网并提交咨询申请
（P1），顾问在后台推进申请阶段、记录沟通纪要、上传报告并交付（P2），客户凭
申请编号 + 凭证在线查询下载报告（P3）。技术方案采用 Django 5.2 LTS 单应用
全栈：其内置 Admin 后台、ORM、认证、CSRF/SQL 注入防护与 IT 资产最小化原则
（单一依赖）高度契合本项目"日申请 < 100"的规模；前台页面用 Django 模板 +
原生 CSS，数据库用 SQLite（标准库内置，零部署成本，规模充分够用），报告文件
与安全日志按 FR-009/014/018 约束实现。

## Technical Context

**Language/Version**: Python 3.14（本机已装 3.14.2）+ Django 5.2 LTS（已验证
5.2.19 支持 Python 3.14，安全支持至 2028-04）

**Primary Dependencies**: 仅 Django 5.2（全功能框架：ORM / 认证 / Admin /
表单校验 / CSRF / SQL 注入防护 / 会话 / 安全日志钩子）。前台样式为原生 CSS
（不引入前端框架）。零第三方运行时依赖。

**Storage**: SQLite（Django 内置，单文件，满足日申请 < 100 规模）；报告文件
存于 `media/reports/`（本地磁盘，非公开 URL，下载经视图鉴权后由 Django 流式
返回）

**Testing**: Django TestCase + 内置测试客户端（标准库，零额外依赖；覆盖
FR 验收场景与宪法 G3 门禁的测试/lint/类型检查要求——lint 用 `python -m
compileall` + `python -Wall -m pytest --collect-only` 级别的语法校验，类型
检查不适用 Python 动态模型时的替代方案为 Django system check
`manage.py check`）

**Target Platform**: Web 服务器（开发期 `runserver`；生产期 Linux + Nginx +
gunicorn，部署架构仅写入 research.md 供运维参考，不阻塞开发验证）

**Project Type**: web 应用（单 Django 项目 + 单 app `core`，含服务端渲染
前台 + Admin 后台定制）

**Performance Goals**: 100 并发访客浏览与提交无故障（SC-007）；页面打开
< 3 秒（SC-007）；SQLite 单文件在日申请 < 100 下无性能瓶颈

**Constraints**: 函数 ≤ 50 行（宪法 G2）；报告文件 ≤ 50MB（FR-009，PDF/doc/
docx）；凭证查询连续 5 次失败锁 15 分钟（FR-011）；安全日志 ≥ 180 天
（FR-014）；密码不可逆加密存储（FR-005，用 Django 内置 PBKDF2）；无正式
SLA，尽力而为（澄清 Q5）

**Scale/Scope**: 3 个用户故事、18 条功能需求、6 个数据实体、约 8 个页面
（首页/表单/受理确认/后台列表/后台详情/纪要/报告上传/报告查询），单租户
中文站点

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 宪法条款 | 检查结果 |
|---------|---------|
| 1. 行为边界：只实现 spec/tasks 中的行为 | ✅ 计划仅覆盖 spec 的 18 条 FR 与 3 个故事，无越界功能 |
| 1. 行为边界：沿用现有分层，禁止预设额外分层 | ✅ 仓库为空，从零建立；仅 Django 标准单 app 布局（models/views/forms/admin/urls），不引入 service/repository/adapter 层 |
| 1. 行为边界：需求冲突时停止修改 | ✅ spec 已经 /speckit-clarify 消歧（5 问），无遗留冲突 |
| 1. 行为边界：未经许可禁止 commit/push | ✅ 本计划不执行任何 git 写操作 |
| 2. 先读后写与强制复用 | ✅ 新项目无既有模块；复用 Django 内置能力（auth/admin/forms/ORM）而非自研，已在 research.md 记录决策 |
| 3. 函数 ≤ 50 行 | ✅ 设计约束写入实现规范，G2 门禁检查 |
| 3. 禁止空 catch/静默失败 | ✅ 表单错误逐字段返回（FR-003）；上传失败显式提示（Edge Cases） |
| 3. 边界校验/参数化/服务端鉴权/不可枚举标识 | ✅ Django Forms 边界校验；ORM 全参数化；报告下载视图服务端校验凭证；内部资源用 UUID 主键定位（编号仅参考号，见 FR-004） |
| 3. 禁止硬编码密钥 | ✅ SECRET_KEY 与 DEBUG 从环境变量读取，`.env` 不入库（research.md 决策 D4） |
| 3. 禁止未批准依赖 | ✅ 运行时零第三方依赖，仅 Django 一项且经本计划批准 |
| 4. 每个行为至少一个自动化测试 | ✅ Phase 1 产出 quickstart.md 验收路径；tasks.md 将为每条 FR 映射测试 |
| 5. Quality Gates G0–G4 | ✅ 计划不标记任何实现"完成"；任务生成后按门禁推进 |

**结论**: PASS——无宪法违规，无 Complexity Tracking 条目。

## Project Structure

### Documentation (this feature)

```text
specs/001-tech-consulting-report/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出：技术决策与依据
├── data-model.md        # Phase 1 输出：6 个实体的字段/关系/状态机
├── contracts/           # Phase 1 输出：页面路由与后台契约
│   └── http-api.md
├── quickstart.md        # Phase 1 输出：端到端验收指南
└── tasks.md             # Phase 2 输出（/speckit-tasks 生成，不在本命令范围）
```

### Source Code (repository root)

```text
D:\git_first\
├── manage.py
├── config/                  # 项目配置（settings/urls/wsgi/asgi）
│   ├── __init__.py
│   ├── settings.py          # 环境变量读取 SECRET_KEY/DEBUG；SQLite；中文时区
│   ├── urls.py              # 根路由：挂载 core + admin + media(仅开发)
│   └── wsgi.py
├── core/                    # 唯一应用：官网 + 后台 + 报告查询
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py            # 6 个实体（见 data-model.md）
│   ├── forms.py             # 咨询申请表单（FR-002/003）、报告上传表单（FR-009/017）
│   ├── views.py             # 前台：首页/表单/查询；后台：列表/详情/纪要/流转/报告
│   ├── urls.py
│   ├── admin.py             # Django Admin 定制：模型注册、站点标题、账户管理
│   ├── services.py          # 阶段流转/凭证生成与校验/编号生成/安全日志（供 views 复用）
│   └── migrations/
├── templates/core/          # 前台页面模板（namespaced）
│   ├── base.html
│   ├── home.html            # 四区块官网首页（FR-001/015）
│   ├── request_form.html    # 咨询申请表单（FR-002/003）
│   ├── request_done.html    # 受理确认 + 申请编号（FR-004）
│   ├── report_lookup.html   # 报告查询页（FR-011）
│   └── report_detail.html   # 报告详情/下载页（FR-012）
├── static/core/css/         # 原生 CSS
├── media/reports/           # 报告文件存储（.gitignore，非公开 URL）
├── tests/                   # 与宪法 G3 对应的测试
│   ├── test_models.py       # 实体约束/状态机/编号唯一性
│   ├── test_forms.py        # 表单校验（必填/格式/长度）
│   ├── test_views_public.py # 官网浏览/申请提交/编号展示/个人信息不泄露
│   ├── test_views_admin.py  # 登录/列表/流转/回退/纪要不可改/报告上传/版本归档
│   └── test_views_lookup.py # 编号+凭证查询/错误提示/5 次锁定/下载鉴权
├── .env.example             # SECRET_KEY/DEBUG 模板
├── .gitignore               # .env、.venv、media/reports/、db.sqlite3、.claude/
├── requirements.txt         # Django>=5.2,<6
└── README.md                # 启动与部署说明
```

**Structure Decision**: 采用"单项目 + 单 app（core）"的扁平布局——项目规模
（8 页面、6 实体、日申请 < 100）不足以支撑多 app 拆分；`services.py` 承载
可复用业务逻辑（流转/凭证/编号/日志），避免 views 膨胀，不引入额外架构分层
（符合宪法第 1 条）。Admin 直接定制而非自建后台，最大化复用框架能力
（符合宪法第 2 条）。

## Complexity Tracking

> 宪法检查无违规，本表为空。
