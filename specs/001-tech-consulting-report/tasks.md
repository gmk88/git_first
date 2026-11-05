# Tasks: 企业技术咨询报告系统

**Input**: Design documents from `/specs/001-tech-consulting-report/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅,
contracts/http-api.md ✅, quickstart.md ✅

**Tests**: 宪法第 4 条（NON-NEGOTIABLE）要求"每个新增或修改行为至少对应一个
自动化测试"，因此本清单**包含测试任务**，且测试先于实现编写（TDD，宪法第 4 条
语义）；每个故事阶段的测试任务标注"先写，确认失败后实现"。

**Organization**: 任务按用户故事分组（US1 官网+申请 / US2 后台交付 /
US3 报告查询），支持独立实现与验收。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、不依赖未完成任务）
- **[Story]**: 所属用户故事（US1/US2/US3）
- 描述含精确文件路径；数据模型约束以"verbatim"引用写入任务，不得留给
  实现时自由发挥

## Path Conventions

单项目布局（plan.md 已定）：`config/`（Django 项目配置）、`core/`（唯一 app）、
`templates/core/`、`static/core/`、`tests/`（仓库根）。

---

## Phase 1: Setup（项目骨架）

**Purpose**: Django 项目初始化与基础设施文件

- [X] T001 在仓库根创建 Django 项目骨架：`django-admin startproject config`（仅保留
  `manage.py`、`config/`），并创建 `core` app（`startapp core`）、空目录
  `templates/core/`、`static/core/css/`、`tests/`（含 `tests/__init__.py`）
- [X] T002 编写 `config/settings.py` 基础配置：`SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`
  从环境变量读取（缺失 SECRET_KEY 时快速失败，禁止默认值回退）；`LANGUAGE_CODE =
  "zh-hans"`、`TIME_ZONE = "Asia/Shanghai"`、`USE_TZ = True`；SQLite 数据库；
  `FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024`；注册 `core`、`django.contrib.admin`
  等默认 app；`TEMPLATES[DIRS]` 含 `templates/`；`STATIC_URL = "static/"`；
  **不**配置任何 MEDIA 静态服务路由（contracts/http-api.md 安全契约：报告文件
  不得有公开 URL）
- [X] T003 [P] 编写 `.env.example`（SECRET_KEY=、DEBUG=、ALLOWED_HOSTS= 注释模板）、
  `.gitignore`（`.env`、`.venv/`、`db.sqlite3`、`media/`、`__pycache__/`、
  `.claude/`）、`requirements.txt`（`Django>=5.2,<6`）、`README.md`
  （初始化四步：venv→pip→migrate→createsuperuser，引用 quickstart.md）
- [X] T004 验证骨架：`.venv/Scripts/python.exe manage.py check` 0 issues、
  `manage.py migrate` 在无自建模型时成功、`runserver` 首页 404 但 admin 可达

**Checkpoint**: 空项目可启动，宪法 D4（env 密钥）与安全契约（无公开 media）
就位

---

## Phase 2: Foundational（阻塞前置，所有故事依赖）

**Purpose**: 全部数据模型 + 服务层骨架 + Admin 基础注册（US1/US2/US3 共同依赖）

**⚠️ CRITICAL**: 本阶段完成前禁止开始任何用户故事任务

- [X] T005 [P] 实现 `core/models.py` 全部模型字段（仅字段层，行为方法后置到各
  故事）：ConsultationRequest（uuid=UUIDField(default=uuid.uuid4, unique,
  editable=False)；request_no=CharField(15, unique)；company_name=CharField(200)；
  contact_person=CharField(100)；contact_phone=CharField(30)；contact_email=
  EmailField；requirement=TextField(5000 字符上限)；expected_date=DateField
  (null=True)；stage=CharField(choices=[(pending,待受理),(accepted,受理),
  (evaluating,评估),(consulting,执行咨询),(drafting,报告撰写),(delivered,已交付)]
  default=pending)；owner=ForeignKey(User, null=True, on_delete=PROTECT,
  related_name="requests")；submitted_at=auto_now_add；updated_at=auto_now；
  Meta.verbose_name="咨询申请"）、StageTransitionRecord（request=FK PROTECT；
  from_stage 同 stage choices null=True；to_stage 同 choices；kind=choices
  [advance/rollback/claim]；reason=TextField blank=True；operator=FK(User,
  PROTECT)；created_at=auto_now_add；Meta：verbose_name="阶段流转记录"、
  ordering=["created_at"]）、CommunicationNote（request=FK PROTECT；
  communicated_at=DateTimeField；channel=choices[phone/wechat/email/meeting/
  other]；summary=TextField(2000 字符上限)；recorder=FK(User, PROTECT)；
  created_at=auto_now_add；verbose_name="沟通纪要"）、ReportVersion（request=
  FK PROTECT related_name="versions"；version_no=PositiveIntegerField；file=
  FileField(upload_to="reports/")；title=CharField(200)；uploaded_by=FK(User,
  PROTECT)；uploaded_at=auto_now_add；is_archived=BooleanField(default=False)；
  verbose_name="咨询报告"）、ReportAccessToken（request=OneToOneField PROTECT
  related_name="token"；token_hash=CharField(64, unique)；created_at=
  auto_now_add；failed_attempts=PositiveIntegerField(default=0)；locked_until=
  DateTimeField(null=True)；last_queried_at=DateTimeField(null=True)；
  verbose_name="报告查询凭证"）、SecurityEvent（event_type=choices[login_success/
  login_failed/lookup_failed/report_download/lookup_locked]；actor=CharField(150,
  blank=True)；source_ip=GenericIPAddressField；detail=CharField(500, blank=True)；
  created_at=auto_now_add；verbose_name="安全事件"；ordering=["-created_at"]）、
  SiteContentBlock（key=CharField unique choices[services/process/about/contact]；
  title=CharField(100)；body=TextField；updated_at=auto_now；verbose_name=
  "官网内容区块"）——全部字段约束严格按 data-model.md 第 1–7 节
- [X] T006 [P] 实现 `core/services.py` 骨架与纯逻辑函数（供各故事复用，宪法
  G1 复用记录）：`generate_request_no()`（格式 `YYYYMMDD-NNNN`，当日最大序号
  +1，4 位补零）、`next_stage(stage)` 与 `previous_stages(stage)`（状态机
  顺序 pending→accepted→evaluating→consulting→drafting→delivered；推进仅
  相邻、回退目标=任意早前阶段）、`hash_token(raw)`（SHA-256 hexdigest）、
  `verify_token(raw, token_hash)`（`secrets.compare_digest` 常数时间比较）、
  `new_access_token()`（`secrets.token_urlsafe(24)` 生成明文并哈希落库）
- [X] T007 生成并检查迁移 + 初始数据迁移：`manage.py makemigrations core`；
  编写 data migration：写入 SiteContentBlock 4 行（key=services/process/about/
  contact，title/body 为占位中文文案）、创建 `consultant` Group；运行
  `manage.py migrate` 成功；`manage.py check` 0 issues
- [X] T008 [P] 编写 `core/admin.py` 基础注册：全部 7 个模型用
  `@admin.register` 注册；admin.site.site_header="咨询管理后台"、site_title=
  "技术咨询"、index_title="后台管理"；StageTransitionRecord/CommunicationNote/
  SecurityEvent/ReportVersion 设 `has_add_permission=has_change_permission=
  has_delete_permission=False`（只读，FR-008 不可变）；SiteContentBlock 仅允许
  change（禁增删，FR-015）；ConsultationRequest list_display=(request_no,
  company_name, contact_person, stage, owner, submitted_at)、list_filter=(stage,
  submitted_at)；verbose_name 已在模型中文（T005），Admin 界面全中文
- [X] T009 编写 `config/urls.py` 根路由（挂载 `core.urls` 于 `/`、admin 于
  `admin/`；**无** static/media serving 配置）与 `core/urls.py` 空urlpatterns
  占位；`core/views.py` 空 views 占位；运行 `manage.py check` 与
  `manage.py test`（无测试）确认通过

**Checkpoint**: 数据层 + 服务层 + Admin 骨架就绪；`manage.py migrate` +
`check` 全绿；用户故事可开始

---

## Phase 3: User Story 1 - 访客了解咨询服务并提交咨询申请 (Priority: P1) 🎯 MVP

**Goal**: 访客可浏览官网首页并提交咨询申请，获得申请编号确认——独立可上线的
最小官网。

**Independent Test**: 启动服务 → 首页四区块可见 → 表单校验与提交 → 获得编号
`YYYYMMDD-NNNN`，全程无需登录与其他故事组件。

### Tests for User Story 1（先写，确认失败后实现）

- [X] T010 [P] [US1] 编写 `tests/test_models.py`：request_no 生成唯一性（同日
  两单 0001/0002）、uuid 唯一、stage 默认 pending、requirement 5000 上限、
  SiteContentBlock 迁移后恰有 4 行
- [X] T011 [P] [US1] 编写 `tests/test_forms.py`：全空提交逐字段报错；电话含
  非法字符报错；邮箱格式报错；requirement 超 5000 报错（拒绝而非截断）；
  合法数据通过
- [X] T012 [P] [US1] 编写 `tests/test_views_public.py`：GET / 四区块标题可见；
  GET /request/ 含隐私说明（FR-018）；POST 合法数据 302 到
  `/request/done/<request_no>/` 且库中生成申请；POST 后确认页只显示编号不回显
  姓名/电话/邮箱（FR-018）；POST 非法数据 200 + 已填内容保留

### Implementation for User Story 1

- [X] T013 [P] [US1] 实现 `core/forms.py` ConsultationRequestForm：6 字段
  （expected_date 非必填），required/长度上限与 T005 模型一致；电话字段
  clean 校验正则 `^[0-9+\-\s]{5,30}$`；错误信息中文；`error_css_class` 逐
  字段展示
- [X] T014 [US1] 实现 `core/services.py::create_request()`：事务内
  generate_request_no + 创建 ConsultationRequest（uuid 自动）——供视图调用
  （依赖 T006）
- [X] T015 [US1] 实现 `core/views.py` 首页视图（读 SiteContentBlock 4 行渲染）
  与申请表单视图（GET 渲染 / POST 校验→create_request→302 确认页 / 失败
  200 保内容）+ `core/urls.py` 路由 `/`、`/request/`、`/request/done/
  <str:request_no>/`（依赖 T013, T014）
- [X] T016 [P] [US1] 编写 `templates/core/base.html`（导航：首页/提交申请/
  报告查询；页脚含个人信息保护说明——仅站内使用、不公开、不给第三方，FR-018）、
  `home.html`（循环渲染 4 区块）、`request_form.html`（表单+逐字段错误）、
  `request_done.html`（仅展示编号）；`static/core/css/site.css` 原生样式
  （简洁企业风，移动端可用）
- [X] T017 [US1] 运行 T010–T012 全部测试通过 + 手动走查 quickstart.md 第 3 节
  （用户故事 1 全流程）；`manage.py check` 0 issues

**Checkpoint**: 🎯 **MVP 达成**——官网+申请闭环独立可用，可单独演示

---

## Phase 4: User Story 2 - 顾问受理咨询并完成咨询交付报告 (Priority: P2)

**Goal**: 顾问登录后台，完成受理→阶段推进/回退→纪要→报告上传交付全流程。

**Independent Test**: 用管理员创建顾问账户并预置一条申请（可经 US1 表单或
fixture），登录后走完流转/回退/纪要/上传全流程，不依赖前台页面。

### Tests for User Story 2（先写，确认失败后实现）

- [X] T018 [P] [US2] 编写 `tests/test_views_admin.py` 流转与权限部分：顾问登录
  后 GET 申请处理页 200；未登录 302 到登录页；顾问 A 访问顾问 B 的申请 403；
  推进 pending→accepted 产生 StageTransitionRecord(kind=advance, operator=当
  前顾问)；回退缺原因报错且 stage 不变；回退带原因成功且记录 kind=rollback、
  reason 落库；delivered 后推进按钮消失
- [X] T019 [P] [US2] 编写 `tests/test_views_admin.py` 纪要与报告部分（同文件
  追加测试类）：添加纪要成功且列表按时间序；纪要记录 recorder=当前用户；
  上传 .pdf 成功→生成凭证明文仅首次响应可见（响应包含 token、再刷新不出现）、
  ReportAccessToken 落库且 token_hash≠明文、申请 stage=delivered；上传 .txt
  被拒（FR-017）；上传 >50MB 被拒（FR-009，用 settings 覆盖测试中模拟）；
  二次上传→version_no=2 且版本 1 is_archived=True、下载入口仅指向版本 2
  （澄清 Q2）；superuser 在 Admin 变更 owner 后原流转记录 operator 不变
  （FR-013）

### Implementation for User Story 2

- [X] T020 [US2] 实现 `core/services.py` 流转函数：`advance_request(request,
  user)`（校验当前阶段非 delivered→next_stage→事务内写 StageTransitionRecord
  kind=advance + 更新 stage）、`rollback_request(request, user, to_stage,
  reason)`（to_stage 必须在 previous_stages 内且 reason 非空→kind=rollback）、
  `claim_request(request, user)`（owner 置当前顾问 + kind=claim 记录）；全部
  `transaction.atomic`（依赖 T006）
- [X] T021 [US2] 实现 `core/services.py` 纪要与报告函数：`add_note(request,
  user, communicated_at, channel, summary)`；`upload_report(request, user,
  file, title)`——扩展名校验 [.pdf/.doc/.docx]（FR-017）、大小 ≤50MB（FR-009）、
  version_no=现有 max+1、事务内归档旧版本（is_archived=True）+ 创建新版本；
  首次上传时：new_access_token() 生成凭证 + advance 至 delivered；返回
  (version, 明文 token 或 None)（依赖 T006, T020）
- [X] T022 [US2] 实现 `core/views.py` 申请处理页视图 `request_process`（GET 渲染
  时间线/纪要列表/版本列表 + 4 类操作表单；POST 分发到 T020/T021 函数；顾问
  越权 403；`@staff_member_required`）+ `core/urls.py` 路由
  `/admin/core/consultationrequest/<int:pk>/process/`（依赖 T020, T021）
- [X] T023 [P] [US2] 编写 `templates/core/request_process.html`（申请信息卡、
  流转按钮——下一阶段名/回退下拉+原因框、纪要表单与时间线、报告上传表单与
  版本列表、首次上传后的一次性凭证高亮区）+ Admin 定制：ConsultationRequest
  change_form 加"处理申请"链接、ReportAccessToken Admin 加"重新生成凭证"
  动作（superuser 专用，明文一次性展示，FR-010；依赖 T022）
- [X] T024 [US2] 运行 T018–T019 全部测试通过 + 手动走查 quickstart.md 第 4 节
  （用户故事 2 全流程）；`manage.py check` 0 issues

**Checkpoint**: US1+US2 独立可用——后台全流程闭环

---

## Phase 5: User Story 3 - 客户在线查看已交付的咨询报告 (Priority: P3)

**Goal**: 客户凭申请编号+凭证查询并下载最新版报告；防枚举、防暴力、失败不
泄露存在性。

**Independent Test**: 使用 US2 交付产生的编号+凭证（或 fixture 预置），在
无痕会话完成查询→详情→下载，全程不登录。

### Tests for User Story 3（先写，确认失败后实现）

- [X] T025 [P] [US3] 编写 `tests/test_views_lookup.py`：正确编号+凭证 302 详情页
  且展示企业名/标题/交付日期；错误凭证统一提示"编号或凭证不正确"且不因编号
  存在与否变化文案（存在/不存在两种输入提示一致）；连续 5 次失败后第 6 次
  （含正确凭证）提示锁定 15 分钟；锁定窗口内 failed_attempts 不再增长；成功
  查询清零计数；SecurityEvent(lookup_failed/lookup_locked/report_download)
  按场景落库（FR-014）；未验证 GET /report/detail/<uuid>/ 302 回查询页；
  归档版本不可下载（FR-009+Q2）
- [X] T026 [P] [US3] 编写 `tests/test_security.py`：`/media/reports/` 与
  `/static/../media/` 路径均不可达（404/重定向，SC-006 红线）；报告下载响应
  Content-Disposition 带文件名；下载需 session 验证（无 session 302）

### Implementation for User Story 3

- [X] T027 [US3] 实现 `core/services.py` 查询函数：`verify_lookup(request_no,
  raw_token)`（编号格式预检→查申请→锁定检查（locked_until>now 拒绝）→哈希
  compare_digest 比对→成功清零 failed_attempts 并记 last_queried_at，失败
  +1 且达 5 次置 locked_until=now+15min；全程写 SecurityEvent；统一返回
  (ok, error_code) 不区分失败原因文案）；`regenerate_token(token_record)`
  （superuser 重置：新明文一次展示、旧哈希失效、计数清零——供 T023 的 Admin
  动作复用）（依赖 T006）
- [X] T028 [US3] 实现 `core/views.py` 查询视图 `report_lookup`（GET 表单/POST
  verify_lookup→成功时 session["verified_request_pk"]=申请 pk，302 详情）与
  详情视图 `report_detail`（校验 session 匹配 uuid 对应申请，否则 302 查询页；
  仅展示 is_archived=False 版本）与下载视图 `report_download`（同鉴权→
  FileResponse 流式最新版 + SecurityEvent(report_download)）+ `core/urls.py`
  路由 `/report/lookup/`、`/report/detail/<uuid:uuid>/`、
  `/report/download/<uuid:uuid>/`（依赖 T027）
- [X] T029 [P] [US3] 编写 `templates/core/report_lookup.html`（编号+凭证表单，
  统一错误提示区）与 `report_detail.html`（报告信息卡+下载按钮+锁定/失败
  提示样式）（依赖 T028）
- [X] T030 [US3] 运行 T025–T026 全部测试通过 + 手动走查 quickstart.md 第 5–6 节
  （用户故事 3 全流程+安全红线抽检）；`manage.py check` 0 issues

**Checkpoint**: 三个故事全部独立可用

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: 跨故事收尾与交付证据

- [X] T031 [P] 补全 `README.md`：本地运行四步、测试命令、Admin 使用说明、
  （引用 research.md D7 的）生产部署要点（Nginx `client_max_body_size 50M`、
  gunicorn、TLS、SECRET_KEY 轮换影响）
- [X] T032 宪法 G4 交付审查：对照 spec.md 逐条核验 FR-001~018 与 SC-001~008
  的测试覆盖映射（在 PR/交付说明中列出 FR→测试清单）；运行
  `manage.py check` + `compileall` + `manage.py test` 并记录命令与结果；
  标记所有"未验证"项（禁止声称通过）；列出改动文件清单与残余风险

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**（T001–T004）：无依赖，立即开始
- **Phase 2 Foundational**（T005–T009）：依赖 Phase 1；**阻塞全部用户故事**
- **Phase 3 US1**（T010–T017）：依赖 Phase 2；MVP
- **Phase 4 US2**（T018–T024）：依赖 Phase 2（数据/服务层）与 US1 的
  编号生成（T014 的 create_request 供 fixture 用，但 US2 测试可用 Django
  ORM 直接造数，故仅建议顺序执行）
- **Phase 5 US3**（T025–T030）：依赖 Phase 2 与 US2 的凭证/交付语义
  （T021/T023 的凭证生成与 Admin 动作）；查询页 UI 不依赖前台
- **Phase 6 Polish**（T031–T032）：依赖全部故事

### User Story Dependencies

- **US1**: Foundational 后即可独立实现测试（官网+表单闭环）
- **US2**: Foundational 后可独立实现测试（用 ORM 预置申请数据）
- **US3**: 依赖 US2 的凭证语义与交付动作（同 story 链内 T021→T027），
  但其页面与测试可用 fixture 独立验收

### Within Each Story

- 测试先行（T010 类任务）→ 确认失败 → 实现（模型/服务 → 视图/URL → 模板）
  → 测试转绿 → checkpoint 手动走查

### Parallel Opportunities

- Phase 2：T005/T006 并行（不同文件）；T008 并行
- Phase 3：T010/T011/T012 三个测试文件并行；T013/T016 并行
- Phase 4：T018/T019 并行；T023 与 T022 完成后可并行
- Phase 5：T025/T026 并行；T029 与 T028 完成后可并行
- 单人执行时按 T 编号顺序即可（编号即执行序）

---

## Implementation Strategy

### MVP First（仅 US1）

1. Phase 1 + Phase 2 完成 → 基础就绪
2. Phase 3 完成 → **STOP**：T017 手动走查 + 全测试绿 → 官网+申请可演示上线
3. （宪法 G4：此状态下交付说明标注 US2/US3 未实现）

### Incremental Delivery

1. Setup + Foundational → 基础
2. US1 → 独立验收 → MVP
3. US2 → 后台闭环 → 独立验收
4. US3 → 客户交付闭环 → 独立验收
5. Polish → G4 审查与交付证据

### Parallel Team Strategy

三人分工：A=US1（前台），B=US2（后台流转/报告），C=US3（查询/安全）；
共享契约 = data-model.md 与 contracts/http-api.md（T005/T006 完成后即可
并行开发，接口以 services 函数签名为界）。

---

## Notes

- [P] = 不同文件、无未完成依赖，可并行
- [Story] 标签保证 FR→故事→任务可追溯（G0 门禁：每个改动文件可映射到任务）
- 测试先写后实现（宪法第 4 条）；每故事 checkpoint 做手动走查（quickstart.md）
- 函数 ≤50 行约束（宪法 G2）贯穿所有实现任务，review 时检查
- 不执行任何 git commit（宪法第 1 条：未经明确许可）

---

## Phase 7: Convergence

> 由 /speckit-converge 于 2026-11-05 追加：对照 spec/plan/constitution 评估当前
> 代码库后的剩余缺口。前置任务 T001–T032 已完成（46/46 测试通过基线）。

- [X] T033 修复沟通纪要时间时区缺陷：`core/views.py::_handle_note` 中
  `parse_datetime` 返回 naive datetime，在 `USE_TZ=True` 下保存触发
  RuntimeWarning；改为 `timezone.make_aware(...)`（或 `is_aware` 判断后处理）
  确保 aware datetime 落库，并在 `tests/test_views_admin.py` 补回归测试
  （添加纪要后断言 `communicated_at` 为 aware 且无告警） per FR-008 (partial)
- [X] T034 编写 `tests/test_signals.py`：登录成功（`client.force_login` 或
  登录视图）断言 SecurityEvent(login_success) 落库；错误密码登录断言
  SecurityEvent(login_failed) 落库且 actor=提交的用户名 per FR-014 (partial)
- [X] T035 编写 `tests/test_admin_permissions.py`：断言 ConsultationRequest
  Admin has_add_permission=False、StageTransitionRecord/CommunicationNote/
  SecurityEvent/ReportVersion 增改删均禁止、SiteContentBlock 禁增删、
  UserAdmin 仅 superuser 有模块权限；顾问（非 superuser）的 ConsultationRequest
  查询集仅含 owner=自己 的申请 per FR-006/008/015/016 (partial)
- [X] T036 编写 `tests/test_load.py` 并执行 SC-007 负载验证：以
  `concurrent.futures.ThreadPoolExecutor`（100 线程）并发 GET `/`、
  GET `/request/`、POST `/request/`（合法数据），断言全部响应 <3 秒且无 5xx；
  在交付说明记录命令与结果（若本机环境无法等价模拟，记录实测条件与结论，
  禁止声称通过未执行的验证） per SC-007 (missing)

---

## Phase 8: Convergence

> 由 /speckit-converge 于 2026-11-05 追加：第二轮评估，含 1 个实测确认的缺陷。

- [X] T037 修复凭证锁定到期后计数未清零的缺陷：`core/services.py::verify_lookup`
  在 `locked_until` 已过期（`locked_until <= now`）时 MUST 先将
  `failed_attempts` 重置为 0 并清空 `locked_until`，再执行本次比对；否则锁定期
  满后用户一次输错即 `attempts>=5` 立刻再锁 15 分钟（已实测复现：锁定期满后
  第 1 次错误 → attempts=6 → 立即再锁）。在 `tests/test_views_lookup.py` 补
  回归测试：模拟 `locked_until` 过期后连续 4 次错误不得触发锁定，第 5 次才锁定
  per FR-011 (partial)
- [X] T038 修复报告下载文件名不可识别问题：`core/views.py::report_download`
  当前以 Django 存储的随机文件名（如 `report_rLpLkGO.pdf`）作为下载文件名；
  改为按「申请编号-报告标题.扩展名」构造（保留原扩展名，去除标题中的文件系统
  非法字符），并在 `tests/test_security.py` 补测试断言 Content-Disposition
  包含申请编号与标题
  per US3/AC1 (partial)
- [X] T039 清理死代码：删除 `core/services.py::claim_request` 中未使用的局部变量
  `old_owner = request.owner`，以及 `core/views.py` 中未使用的
  `from django.views.decorators.http import require_http_methods` 导入
  per Constitution 3 (unrequested)
