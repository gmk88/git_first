# 企业技术咨询报告系统

企业官网 + 咨询后台 + 报告查询一体化系统（Django 5.2 LTS + SQLite）。

## 快速启动

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env  # 编辑 .env 填入 SECRET_KEY

# 生成密钥（一次性）
.venv/Scripts/python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 3. 初始化数据库
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py createsuperuser  # 管理员账户

# 4. 启动开发服务器
.venv/Scripts/python.exe manage.py runserver
```

访问 `http://127.0.0.1:8000/` 查看官网首页。

## 测试

```bash
# 框架检查
.venv/Scripts/python.exe manage.py check

# 语法检查
.venv/Scripts/python.exe -m compileall -q core config

# 运行全部测试
.venv/Scripts/python.exe manage.py test tests -v 2
```

## Admin 后台

访问 `http://127.0.0.1:8000/admin/` 使用管理员或顾问账户登录。

- **管理员**：可创建顾问账户（FR-016）、重新指派申请（FR-013）、重置报告凭证（FR-010）
- **顾问**：仅可操作自己名下的申请（FR-006/007/008/009）

## 生产部署要点

详见 [research.md D7](specs/001-tech-consulting-report/research.md)：

1. **Nginx 配置**：
   - TLS 终结（HTTPS）
   - `client_max_body_size 50M;`（FR-009 报告上传必需，默认 1MB 会导致 413）
   - 静态文件服务（`static/`）
   - **不要**配置 `media/` 的公开路由（FR-012 安全红线）

2. **Gunicorn**：WSGI 应用服务器，绑定本地端口由 Nginx 反向代理

3. **环境变量**：`DJANGO_SECRET_KEY`、`DJANGO_DEBUG=False`、`DJANGO_ALLOWED_HOSTS`

4. **SECRET_KEY 轮换影响**：会使所有 session、签名数据、密码重置链接失效（预期行为）

## 项目结构

```
config/          # Django 项目配置
core/            # 唯一应用：模型/视图/表单/Admin
templates/core/  # 前台模板
static/core/     # 原生 CSS
media/reports/   # 报告文件（git 忽略，无公开 URL）
tests/           # 测试套件
specs/           # Spec Kit 文档（plan/spec/tasks/data-model/contracts）
```

## 功能范围

- **P1**：访客浏览官网并提交咨询申请
- **P2**：顾问后台推进阶段、记录纪要、上传报告交付
- **P3**：客户凭编号+凭证在线查询下载报告

详见 [spec.md](specs/001-tech-consulting-report/spec.md)。
