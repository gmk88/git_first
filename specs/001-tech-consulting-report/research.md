# Research: 企业技术咨询报告系统

Feature: 001-tech-consulting-report | Date: 2026-11-05

本文件解决 plan.md Technical Context 中的全部技术决策。原 spec 无遗留
[NEEDS CLARIFICATION]（/speckit-clarify 已完成 5 问），此处仅记录技术选型。

## D1. Web 框架：Django 5.2 LTS（单一全功能框架）

**Decision**: Django 5.2 LTS（当前 5.2.19），Python 3.14。

**Rationale**:
- spec 要求的能力（认证、后台管理、表单校验、文件上传、访问控制、安全日志）
  全部命中 Django 内置能力：`contrib.auth`（密码 PBKDF2 不可逆加密，FR-005）、
  `contrib.admin`（后台 CRUD 骨架 + 账户管理，FR-005/006/016）、`forms`（边界
  校验，FR-003）、ORM 参数化查询（宪法第 3 条）、CSRF/点击劫持/SQL 注入默认防护。
- 项目规模（日申请 < 100、8 页面、6 实体）→ Admin 定制即可满足后台，避免自研
  后台的重实现（宪法第 2 条：强制复用）。
- LTS 支持至 2028-04；Django 5.2.8+ 官方支持 Python 3.14（本机 3.14.2，已本地
  安装 5.2.19 验证导入成功）。
- 运行时零第三方依赖——宪法第 3 条"新增未批准依赖"禁止项天然满足，供应链面
  最小化。

**Alternatives considered**:
- Next.js + Supabase：SaaS 快速栈，但需托管服务与外部账号，引入外部依赖与
  数据出境问题，与"单一咨询公司自用系统"不匹配。
- FastAPI + 自建前端：后台管理需自建（Admin 不可用），违背强制复用原则。
- Ruby on Rails：能力相当，但本机环境与后续维护者栈为 Python。

## D2. 数据库：SQLite（标准库内置）

**Decision**: SQLite，单文件 `db.sqlite3`。

**Rationale**: Django 官方支持的生产级选择（≤ 中等流量）；本项目日申请 < 100、
并发写入极低（顾问后台单写者场景），SQLite 完全够用；零安装、零运维、备份=
复制文件，符合"尽力而为"的可用性承诺（澄清 Q5）与最小部署成本。

**Alternatives considered**:
- PostgreSQL：能力溢出，需额外安装与运维；当并发写入成为瓶颈时可迁移（Django
  ORM 层屏蔽差异，迁移成本可控）。

## D3. 报告文件存储与下载：本地磁盘 `media/reports/` + 视图鉴权流式返回

**Decision**: 报告文件存 `media/reports/`（目录不开放静态服务），下载走
Django 视图：先校验"申请编号 + 凭证"（FR-011/012），通过后
`FileResponse` 流式返回。

**Rationale**: 50MB 上限（FR-009）在本地磁盘方案下无压力；关键安全约束是
"文件不可通过 URL 直接访问"——因此 `media/reports/` 不挂载任何静态路由，
唯一入口是鉴权视图，天然满足 FR-012 与 SC-006。资源定位用申请的 UUID 主键
（宪法第 3 条不可枚举标识），编号仅作参考号（FR-004）。

**Alternatives considered**:
- 对象存储（S3/OSS）：引入外部服务与密钥管理，规模不需要。
- `MEDIA_ROOT` 直接公开：违反 FR-012，直接否决。

## D4. 密钥与配置：环境变量 + `.env`（不入库）

**Decision**: `SECRET_KEY`、`DEBUG`、`ALLOWED_HOSTS` 从环境变量读取；
提供 `.env.example` 模板，`.env` 与 `db.sqlite3`、`media/reports/` 入
`.gitignore`。

**Rationale**: 宪法第 3 条禁止硬编码密钥；Django 官方推荐 env 注入并在缺失时
快速失败。生成方式 `get_random_secret_key()`（首次部署生成一次，轮换会使
会话与签名数据失效，属预期行为）。

**Alternatives considered**:
- `secret_key.py` 首次自动生成：与 env 方案二选一，env 更符合 12-factor 且
  便于生产部署。

## D5. 后台形态：Django Admin 定制（不自建后台 UI）

**Decision**: 顾问/管理员共用 `contrib.admin`：注册 6 个模型，定制
`list_display`/`list_filter`/只读字段；自建的自定义视图仅 3 个——申请详情
（含流转按钮 + 纪要表单 + 报告上传）、报告查询页、报告下载视图；账户由
Admin 内置用户管理承担（FR-016 仅管理员创建）。

**Rationale**: FR-005/006/013/016 的列表、筛选、指派、账户管理在 Admin 中
零代码获得（含中文 verbose_name 显示）；仅"阶段流转按钮 + 回退原因 +
纪要录入 + 报告上传"需要定制交互，以 admin 内嵌表单/自定义视图实现。
沟通纪要的"不可修改删除"（FR-008）通过 ModelAdmin `readonly_fields` +
模型层禁用来强制。

**Alternatives considered**:
- 完全自建后台（模板 + 视图）：重实现 Admin 已有能力，违背复用原则。
- 第三方 admin 皮肤（simpleui 等）：新增依赖未批准，且非必要。

## D6. 测试与验证：Django TestCase + system check

**Decision**: 用 Django 内置 `TestCase` 与测试客户端覆盖全部 FR 验收场景；
质量门禁执行 `manage.py check`（框架级静态检查）+ `manage.py test` +
`compileall` 语法检查。G3 门禁中的"类型检查"对本项目解释为 Django system
check + 严格运行测试（Python 动态类型 + 单一依赖栈下无独立类型检查工具，
不为此新增未批准依赖）。

**Rationale**: 零第三方测试依赖；内置测试客户端可覆盖认证/会话/CSRF/文件
上传全链路，与宪法第 4 条"每个行为至少一个自动化测试"对应。分 5 个测试
模块对应 spec 的 5 类验收路径（见 plan.md tests/ 结构）。

**Alternatives considered**:
- pytest + pytest-django：能力溢出（新增 2 个依赖），TestCase 足够。
- mypy：对 Django ORM 模型收益有限，需插件依赖，未批准。

## D7. 生产部署参考（不阻塞开发）

**Decision**: 记录目标架构为 Linux + Nginx（TLS 终结、`client_max_body_size
50M`、静态文件）+ gunicorn + SQLite；开发与验收全程用 `runserver`。部署
脚本不在本特性范围内。

**Rationale**: spec 的 Out of Scope 未排除部署，但澄清 Q5 确认"尽力而为"
可用性 → 不构建高可用架构；此决策仅作为 tasks 中"部署说明"任务的依据。
Nginx 默认 1MB 请求体限制必须调至 50M+，否则报告上传 413（FR-009 落地
要点）。

## D8. 前台形态：服务端渲染模板 + 原生 CSS

**Decision**: 8 个页面全部为 Django 模板服务端渲染，样式为单个原生 CSS
文件（`static/core/css/site.css`），不引入任何前端框架/构建工具。

**Rationale**: 官网四区块 + 表单 + 查询页均为内容型页面，SSR 天然满足
SC-007（100 并发、3 秒内打开）；无交互密集型 UI；宪法第 3 条禁止未批准
依赖 → 零 npm/构建链。

**Alternatives considered**:
- Tailwind/React SPA：对内容型官网是过度设计，引入构建链与依赖。
