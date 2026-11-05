# Data Model: 企业技术咨询报告系统

Feature: 001-tech-consulting-report | Date: 2026-11-05
Source: spec.md Key Entities + FR-001~018 + 澄清记录

实体共 6 个。主键策略：所有实体用 Django 默认自增主键做内部关联；**咨询申请
额外持有 `uuid` 字段（UUID v4，唯一）作为对外资源定位标识**——宪法第 3 条
"对外资源标识必须不可枚举"；申请编号（日期+序号）仅作业务参考号展示
（FR-004）。

## 实体关系总览

```text
UserAccount (Django User)
    │ 1        * 负责人/操作人/记录人/上传人
    ▼
ConsultationRequest ──1:N── StageTransitionRecord
    │  1:N── CommunicationNote
    │  1:N── ReportVersion
    └ 1:1..N── ReportAccessToken (每申请一张，重置即换新)
SiteContentBlock (独立，4 行固定)
```

## 1. ConsultationRequest 咨询申请

| 字段 | 类型/约束 | 说明 |
|------|----------|------|
| id | 自增主键 | 内部关联用 |
| uuid | UUID v4, unique, 不可编辑 | 对外资源定位（下载/详情路由用此值） |
| request_no | CharField(15), unique | 业务参考号，格式 `YYYYMMDD-NNNN`（当日递增，FR-004） |
| company_name | CharField(200) | 企业名称（必填） |
| contact_person | CharField(100) | 联系人（必填） |
| contact_phone | CharField(30) | 联系电话（必填，格式校验 FR-003） |
| contact_email | EmailField | 邮箱（必填） |
| requirement | TextField(上限 5000 字符) | 咨询需求描述（必填，超长拒绝并提示） |
| expected_date | DateField, null=True | 期望完成时间（非必填） |
| stage | CharField, choices=Stage | 当前阶段，初始 `pending` |
| owner | FK(User), null=True | 负责顾问（认领/指派 FR-006/013） |
| submitted_at | DateTimeField(auto_now_add) | 提交时间 |
| updated_at | DateTimeField(auto_now) | 最近变更时间 |

**Stage 状态机**（FR-007 + 澄清 Q1）：

```text
pending(待受理) → accepted(受理) → evaluating(评估) → consulting(执行咨询)
→ drafting(报告撰写) → delivered(已交付, 终态)
```

- 推进：仅可 `stage → 下一相邻阶段`。
- 回退：任意阶段可回退到任意早前阶段，**必须提供原因**（回退原因写入
  StageTransitionRecord.reason）。
- 终态 `delivered` 不可再流转。
- 任何流转（推进/回退/认领）产生一条 StageTransitionRecord；状态变更与
  流转记录在同一事务内（`transaction.atomic`），不允许出现无记录的阶段变更。

**校验规则**：
- request_no 生成规则：`当日日期 + '-' + 当日序号(4位, 从0001起)`；生成于
  事务内取当日最大序号 +1（并发场景由 SQLite 写锁天然串行化保证唯一）。
- requirement 长度 > 5000 → 表单层拒绝并逐字段提示（Edge Case：超长文本）。
- 个人信息字段不出现在任何公开序列化/模板上下文之外（FR-018，测试覆盖）。

## 2. StageTransitionRecord 阶段流转记录（不可变/追加-only）

| 字段 | 类型/约束 | 说明 |
|------|----------|------|
| id | 自增主键 | |
| request | FK(ConsultationRequest), PROTECT | 所属申请 |
| from_stage | CharField(Stage), null=True | 前阶段（创建时无前阶段，null） |
| to_stage | CharField(Stage) | 后阶段 |
| kind | CharField, choices=advance/rollback/claim | 流转类型：推进/回退/认领 |
| reason | TextField, blank=True | 回退原因（kind=rollback 时 MUST 非空，模型层 clean 强制） |
| operator | FK(User) | 操作人（重指派不改写本字段，FR-013） |
| created_at | DateTimeField(auto_now_add) | 操作时间 |

**约束**：无 update/delete 路径（Admin readonly + 无编辑视图 + 测试断言
不可变）。

## 3. CommunicationNote 沟通纪要（不可变/追加-only）

| 字段 | 类型/约束 | 说明 |
|------|----------|------|
| id | 自增主键 | |
| request | FK, PROTECT | 所属申请 |
| communicated_at | DateTimeField | 沟通时间（顾问填写，默认当前） |
| channel | CharField, choices=phone/wechat/email/meeting/other | 沟通方式 |
| summary | TextField(上限 2000 字符) | 内容摘要 |
| recorder | FK(User) | 记录人（=当前登录者，自动填充不可改） |
| created_at | DateTimeField(auto_now_add) | 创建时间 |

**约束**：同 StageTransitionRecord——无 update/delete 路径（FR-008）。

## 4. ReportVersion 咨询报告（多版本，澄清 Q2）

| 字段 | 类型/约束 | 说明 |
|------|----------|------|
| id | 自增主键 | |
| request | FK, PROTECT | 所属申请 |
| version_no | PositiveIntegerField | 版本号，从 1 递增（同申请内唯一） |
| file | FileField(upload_to="reports/") | 报告文件（PDF/doc/docx，≤50MB，FR-009/017） |
| title | CharField(200) | 报告标题 |
| uploaded_by | FK(User) | 上传人 |
| uploaded_at | DateTimeField(auto_now_add) | 上传时间 |
| is_archived | BooleanField(default=False) | 归档标记：新版本上传时旧版本置 True |

**约束与校验**：
- 文件扩展名白名单 `.pdf/.doc/.docx`（表单层拒绝其他格式，FR-017）。
- 文件大小 ≤ 50MB（表单 + settings 上限，FR-009；Django 大文件自动落盘临时
  文件，内存不炸）。
- 上传新版本 = 创建新 ReportVersion + 事务内将同申请其余版本 `is_archived=True`
  （客户查询页仅展示/下载 `is_archived=False` 的最新版，FR-009 + 澄清 Q2）。
- 首次上传报告时同时：生成 ReportAccessToken、申请流转 `drafting → delivered`
  （触发 StageTransitionRecord）。
- 归档版本顾问可在后台查看历史，下载入口仅对最新版开放。

## 5. ReportAccessToken 报告查询凭证

| 字段 | 类型/约束 | 说明 |
|------|----------|------|
| id | 自增主键 | |
| request | OneToOne(FK) | 所属申请（每申请一张有效凭证） |
| token_hash | CharField(64), unique | 凭证 SHA-256 哈希（不可逆存储，FR-010） |
| created_at | DateTimeField(auto_now_add) | 生成时间 |
| failed_attempts | PositiveIntegerField(default=0) | 连续失败计数 |
| locked_until | DateTimeField, null=True | 锁定截止时间 |
| last_queried_at | DateTimeField, null=True | 最近成功查询时间 |

**凭证规则**（FR-010/011 + 宪法第 3 条）：
- 生成：`secrets.token_urlsafe(24)`（约 192 bit 熵），**明文仅在上传报告的
  响应页展示一次**，即时哈希落库；明文不可恢复。
- 校验：输入凭证 SHA-256 后与 `token_hash` 比对（常数时间比较
  `secrets.compare_digest`）。
- 锁定：同一申请编号连续 5 次失败 → `locked_until = now + 15min`，锁定期内
  一律拒绝（含正确凭证）；成功查询清零计数。
- 重置：管理员在 Admin 中"重新生成凭证"→ 新明文展示一次，旧凭证失效，
  计数清零（Edge Case：凭证泄露）。
- 查询失败（编号不存在/凭证错/锁定中）统一返回"编号或凭证不正确"，
  不泄露编号存在性（Story 3 验收 2）；失败尝试写安全日志（FR-014）。

## 6. UserAccount 用户账户（复用 Django User）

**Decision**: 直接使用 `django.contrib.auth.models.User`（不建自定义表），
角色用 `is_staff` + Group 区分：

| 角色 | 实现方式 | 权限 |
|------|---------|------|
| 顾问 | is_staff=True，加入 `consultant` Group | 访问 Admin；仅操作 owner=自己的申请 |
| 管理员 | is_staff=True, is_superuser=True | 全部权限 + 账户管理（FR-016）+ 重指派（FR-013）+ 凭证重置 |

**Rationale**: FR-005 密码不可逆加密由 Django PBKDF2 内置满足；Admin 登录/
会话/CSRF 开箱即用；"仅管理员创建账户" = Admin 用户表只对 superuser 可见
（ModelAdmin 权限控制）。顾问仅见自己申请 → 自定义视图与 Admin queryset
均按 `owner=request.user` 过滤（superuser 例外）。

## 7. SiteContentBlock 官网内容区块

| 字段 | 类型/约束 | 说明 |
|------|----------|------|
| id | 自增主键 | |
| key | CharField, unique, choices=services/process/about/contact | 区块标识，固定 4 行（FR-001/015） |
| title | CharField(100) | 区块标题 |
| body | TextField | 区块正文（模板按需换行渲染） |
| updated_at | DateTimeField(auto_now) | 最近更新时间 |

**约束**：数据迁移内置 4 条初始行；Admin 可编辑标题/正文，不可增删区块
（FR-015 限定为"编辑文案"）；首页模板读取 4 行渲染，保存后立即生效
（无缓存层，直接查库）。

## 8. SecurityEvent 安全事件日志（FR-014，附加表）

> spec Key Entities 未列出，但 FR-014 要求结构化留存 ≥180 天，用一张表
> 而非文件日志以满足"可追溯"（SC-004/SC-006 验收需要查询能力）。

| 字段 | 类型/约束 | 说明 |
|------|----------|------|
| id | 自增主键 | |
| event_type | CharField, choices=login_success/login_failed/lookup_failed/report_download/lookup_locked | 事件类型 |
| actor | CharField(150), blank | 账户名或申请编号（失败尝试可能无有效主体） |
| source_ip | GenericIPAddressField | 来源 |
| detail | CharField(500), blank | 补充信息 |
| created_at | DateTimeField(auto_now_add) | 时间 |

**约束**：追加-only；180 天保留由运维清理策略承担（数据模型保证可按
created_at 过滤）；Admin 只读展示。

## 迁移与初始数据

1. `makemigrations core` 生成 schema。
2. Data migration 写入：SiteContentBlock 4 条初始行、`consultant` Group、
   一个占位管理员账户（密码首次部署时经 `createsuperuser` 设置，不预置弱
   密码）。
3. `media/reports/` 目录由 FileField 自动创建，git 忽略。
