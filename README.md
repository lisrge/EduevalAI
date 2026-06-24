# EduEvalAI

教学项目材料管理与评审系统——学生提交作业 → 教师评分 → 管理员总览 + 博客抓取分析。

## 快速启动

### 环境要求

- Python 3.12+ / MySQL 5.7+
- Node.js 18+ / npm 9+
- Chrome 浏览器（用于 CSDN 博客抓取，可选）

### 1) 后端

如果你当前就在本 README 所在目录，也就是 `EduevalAI/` 目录下：

```powershell
cd .\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

如果你当前在更外层目录，例如 `d:\ModelHub\EduevalAI`，则先进入项目目录再启动：

```powershell
cd .\EduevalAI\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

说明：

- `Copy-Item` 是 Windows PowerShell 的复制命令，原来的 `cp` 在部分环境下不可直接用。
- 当前后端启动后，健康检查地址是 `http://127.0.0.1:8001/api/health`
- 看到返回 `{"status":"ok"}` 即表示启动成功。
- 如果 `.env` 中 MySQL 密码不正确，系统会打印数据库连接失败信息；当前项目代码仍会回退到本地 SQLite 继续启动，便于开发测试。

### 2) 前端

```powershell
cd .\fronted
npm install
npm run serve -- --port 8080
```

访问 `http://localhost:8080`

### 3) 博客抓取（可选，需要 Chrome）

```bash
# 安装 Playwright 浏览器
python -m playwright install chromium

# 启动带调试端口的 Chrome（CDP 模式）
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=backend\storage\browser_profile

# 在 Chrome 中登录 CSDN，然后在 .env 中启用
BLOG_CRAWLER_ENABLED=true
```

## 角色与权限

| 角色 | 权限 |
|------|------|
| admin | 全部：用户/分组管理、作业看板、评分分配、博客抓取审查、CSV 导出 |
| teacher | 仅评分（`/teacher/reviews`） |
| user | 仅交作业/上传材料（`/homework`） |

第一个注册的账号自动成为 root admin，不可降级。

## 主要页面

| 页面 | 说明 |
|------|------|
| `/admin/users` | 用户管理（角色、分组、博客配置、Gitee 仓库链接） |
| `/admin/groups` | 分组管理 |
| `/admin/blog-overview` | 博客总览（抓取状态、分类统计、搜索、CSV 导出） |
| `/admin/users/:id/blogs` | 用户博客详情（正文预览、分类切换） |
| `/admin/submissions` | 作业看板 |
| `/admin/document-import` | 文档批量导入（PDF 任务书/申请书解析） |
| `/teacher/reviews` | 教师评分 |
| `/homework` | 学生作业提交 |

## 配置（backend/.env）

```env
# 数据库（必填）
DATABASE_URL=mysql+pymysql://root:123456@127.0.0.1:3306/edueval_ai?charset=utf8mb4
CORS_ORIGINS=http://localhost:8080

# AI 模型（DeepSeek，用于博客分类和文档解析）
MODEL_BASE_URL=https://api.deepseek.com/v1
MODEL_API_KEY=sk-xxx
MODEL_NAME=deepseek-chat

# 博客抓取
BLOG_CRAWLER_ENABLED=false   # 启用设为 true
BLOG_CDP_URL=http://127.0.0.1:9222
BLOG_LAUNCH_CHROME=false     # CDP 模式关闭自动启动
```

## 博客系统架构

### 分类体系

| 分类 | 含义 |
|------|------|
| `project_update` | 项目实训工作记录（有描述和总结） |
| `project_code_dump` | 项目相关但几乎全是代码 |
| `project_science` | 项目相关但写成通用教程 |
| `unrelated` | 与项目实训完全无关 |

### 抓取流程

```
用户提供 CSDN 博客 URL → 管理员触发抓取 → Worker 队列
  → CDP Chrome 访问博客 → 逐篇提取内容 + 截图
  → DeepSeek 分析（项目/纯代码/科普/不相关）
  → 逐篇写入数据库
```

### DeepSeek 判断标准

- 有工作描述/总结/解释 → project_update
- 几乎全是代码无说明 → project_code_dump
- 通用教程风格无项目语境 → project_science
- 完全无关 → unrelated

## 数据库初始化

首次启动自动建表（`init_db.py`），并创建默认课程和作业。无需手动执行 SQL。

## 文件存储

```
backend/storage/
├── submissions/{id}/{type}/   # 作业附件
├── applications/              # 申请书
├── signatures/                # 签名
├── blogs/screenshots/         # 博客截图
├── blogs/html/                # 博客 HTML 存档
├── browser_profile/           # Chrome 用户数据
└── exports/                   # 导出文件
```

## 常见问题

- **博客抓取失败**：检查 CDP Chrome 是否在 9222 端口运行且已登录 CSDN
- **老师登录提示 staff required**：管理员在 `/admin/users` 改为 teacher 角色
- **前端目录名**：`fronted/` 是历史命名，非 `frontend/`
- **数据库回退**：不再支持 SQLite 回退，必须使用 MySQL
