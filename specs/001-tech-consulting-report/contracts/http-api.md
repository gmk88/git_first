# Contracts: 路由与交互契约

Feature: 001-tech-consulting-report | Date: 2026-11-05

本项目为服务端渲染 Web 应用，无外部程序消费的 JSON API；对外契约 = URL 路由
+ 页面行为 + 表单字段。后台复用 Django Admin（`/admin/`，框架自身契约），
自定义部分以"申请详情页"为主。

## 公开路由（无需登录）

### GET `/` 官网首页（FR-001, FR-015）

- 渲染 4 个内容区块：服务介绍 / 服务流程 / 关于我们 / 联系方式（读
  SiteContentBlock）。
- 顶部导航含"提交咨询申请""报告查询"入口。
- 200；内容区块缺失时按迁移内置文案兜底（不允许空白页）。

### GET/POST `/request/` 咨询申请表单（FR-002, FR-003, FR-018）

表单字段：

| 字段 | 必填 | 校验 |
|------|------|------|
| company_name | 是 | 非空，≤200 字符 |
| contact_person | 是 | 非空，≤100 字符 |
| contact_phone | 是 | 非空，≤30 字符，格式：数字/+/-/空格 |
| contact_email | 是 | Email 格式 |
| requirement | 是 | 非空，≤5000 字符 |
| expected_date | 否 | 日期格式 |

- POST 校验失败：200 + 逐字段错误信息 + 已填内容保留（不重定向）。
- POST 成功：302 → `/request/done/<request_no>/`；同事务创建申请 + 编号。
- 页面底部固定展示个人信息保护说明（FR-018：仅站内使用承诺）。
- 超长提交（>5000）被拒绝并提示上限，不静默截断（Edge Case 约定：拒绝并
  提示）。

### GET `/request/done/<request_no>/` 受理确认（FR-004）

- 展示申请编号与"顾问将尽快联系"提示。
- 仅展示编号本身，不回显任何个人信息（FR-018）。

### GET/POST `/report/lookup/` 报告查询（FR-010, FR-011, FR-012）

表单字段：`request_no`（申请编号）、`token`（凭证）。

- 校验流程：编号格式合法 → 查申请 → 锁定检查 → 哈希比对。
- 任一步失败：统一提示"编号或凭证不正确"（不区分具体原因，不泄露编号
  存在性）；失败计数 +1；写 SecurityEvent(lookup_failed)。
- 连续 5 次失败：`locked_until = now+15min`，写 SecurityEvent(lookup_locked)；
  锁定期内即使正确凭证也拒绝，提示"尝试次数过多，请 15 分钟后再试"。
- 成功：session 记录 `verified_request_pk`，302 → 详情页；清零计数；写
  SecurityEvent(report_download 之外的查询成功不强制记录，仅记录下载与失败)。
- POST 不受 CSRF 豁免（保持默认开启）。

### GET `/report/detail/<uuid>/` 报告详情（FR-012）

- 路由参数为申请 **uuid**（不可枚举标识，宪法第 3 条），非申请编号。
- 仅当 session 中 `verified_request_pk` 匹配该 uuid 对应申请时可见；
  未验证访问 → 302 回查询页（不透露存在性）。
- 展示：企业名称、报告标题、交付日期、最新版本下载入口；仅展示
  `is_archived=False` 版本（FR-009 + 澄清 Q2）。

### GET `/report/download/<uuid>/` 报告下载（FR-012）

- 同详情页鉴权（session 已验证）。
- 通过后以 `FileResponse` 流式返回最新版报告文件；写
  SecurityEvent(report_download)。
- 归档版本不可经此路由下载。

## 后台路由（需 is_staff 登录，FR-005）

### `/admin/` Django Admin（框架契约）

- 站点标题定制为"咨询管理后台"。
- 模型注册行为契约：
  - ConsultationRequest：列表显示企业/联系人/提交时间/阶段/负责人；
    筛选器 stage、submitted_at；superuser 可重指派 owner（FR-013）。
  - StageTransitionRecord / CommunicationNote / SecurityEvent：
    只读（无增删改按钮；纪要与流转只能经前台流程产生）。
  - ReportVersion：只读列表 + 归档标记展示。
  - ReportAccessToken：superuser 可见"重新生成凭证"动作（明文一次性展示，
    FR-010）。
  - User：仅 superuser 可见可管理（FR-016）。
  - SiteContentBlock：可编辑 title/body，禁用增删（FR-015）。

### GET/POST `/admin/core/consultationrequest/<id>/process/` 申请处理页（自定义）

顾问处理单条申请的核心工作台（从 Admin 列表链接进入）：

- 展示：申请全部信息、流转历史时间线、纪要列表、报告版本列表。
- 操作 1 —— 推进阶段：按钮显示下一阶段名；POST 后事务内更新 stage +
  写 StageTransitionRecord(kind=advance)。
- 操作 2 —— 回退阶段：阶段下拉（任意早前阶段）+ 原因必填文本；
  reason 为空 → 表单错误，不产生任何变更（澄清 Q1）。
- 操作 3 —— 添加纪要：时间/方式/摘要；成功后不可再修改删除（FR-008）。
- 操作 4 —— 上传报告：文件 + 标题；成功后首传生成凭证（明文一次性展示），
  申请流转至 delivered；再传生成新版本并归档旧版（澄清 Q2）。
- 权限：顾问仅能打开 owner=自己的申请；否则 403。

## 会话与安全契约

- 登录：Admin 内置 `/admin/login/`（FR-005），失败写
  SecurityEvent(login_failed/success)（经 admin 登录信号挂接）。
- 报告文件：`media/reports/` 不挂载任何静态/媒体路由（开发期亦不开放
  `MEDIA` serving），唯一入口为 `/report/download/<uuid>/`（FR-012, SC-006）。
- CSRF：全站默认开启；表单均带 token。
- Cookie：SESSION_COOKIE_HTTPONLY 默认；生产环境 SECURE_SSL_REDIRECT 等
  由部署配置承担（research.md D7）。

## 错误与边界契约

| 场景 | 行为 |
|------|------|
| 表单校验失败 | 200 + 逐字段错误 + 保留输入（FR-003） |
| 查询失败 | 统一"编号或凭证不正确"（Story3 验收 2） |
| 查询锁定 | "尝试次数过多，请 15 分钟后再试"（FR-011） |
| 未验证访问报告详情/下载 | 302 → 查询页，不透露存在性（FR-012） |
| 顾问访问非本人申请 | 403（宪法边界：越权阻断） |
| 报告上传失败/断网 | 申请保持 drafting，无 ReportVersion 落库，可重试（Edge Case） |
| 404/500 | 标准 Django 错误页（自定义模板可选，不阻塞验收） |
