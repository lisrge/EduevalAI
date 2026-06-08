# EduEvalAI

EduEvalAI 是一个教学项目材料管理与评审系统，当前包含：

- 学生侧：申请书/草稿管理、作业提交（上传任意材料并提交）
- 教师侧：移动端样式的评分端（只打分，不看后台/不交作业）
- 管理员侧：后台管理、作业总览、分配老师、导出成绩、博客总览与抓取（可选）

## 快速开始（本地开发）

默认端口约定：

- 后端：`http://127.0.0.1:8001`（API 前缀 `/api`）
- Vue 前端：`http://localhost:8080`
- Flutter Web（可选）：`http://localhost:8090`

### 1) 后端启动

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

说明：

- 数据库连接优先使用 `DATABASE_URL`；如果连接失败会自动回退到本地 SQLite（`./edueval_ai.sqlite3`），方便开发阶段无服务器运行。
- 首次启动会自动建表并执行初始化脚本（包含默认管理员、默认作业等）。

### 2) Vue 前端启动

```bash
cd fronted
npm install
npm run serve -- --port 8080
```

### 3) Flutter Web（可选，教师独立端）

此项目默认放在仓库同级目录（不是本仓库子目录）：

```text
../teacher_flutter_web
```

启动示例：

```bash
cd ../teacher_flutter_web
flutter pub get
flutter run -d chrome --web-port 8090
```

如果 Flutter Web 访问后端出现 `net::ERR_FAILED`，检查 `backend/.env` 的 `CORS_ORIGINS` 是否包含 `http://localhost:8090`。

## 目录结构

```text
EduevalAI/
├─ backend/
│  ├─ .env
│  ├─ .env.example
│  ├─ requirements.txt
│  └─ app/
├─ fronted/
│  ├─ package.json
│  └─ src/
└─ README.md
```

## 角色与权限（必读）

系统只有三种角色：

- **admin（管理员）**：拥有所有权限（后台、看全局、分配老师、导出、也可打分）
- **teacher（老师）**：只能打分（不能交作业、不能看后台）
- **user（学生）**：只能交作业/上传材料（不能打分、不能看后台）

规则：

- 第一个注册成功的账号会自动成为 **初始管理员**（`is_root_admin=true`）。
- 初始管理员不能被降级。

## 配置（backend/.env）

项目提供示例配置：

```text
backend/.env.example
```

复制为：

```text
backend/.env
```

开发期最小配置示例：

```env
DATABASE_URL=mysql+pymysql://root:123456@127.0.0.1:3306/edueval_ai?charset=utf8mb4
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://localhost:8090,http://127.0.0.1:8090
BLOG_CDP_URL=http://127.0.0.1:9222
BLOG_LAUNCH_CHROME=false
```

说明：

- 不配置 MySQL 也能跑：当 MySQL 不可用时后端自动回退到 SQLite。
- `BLOG_*` 仅在你需要管理员抓取/预览博客时才需要配置。

## 作业提交（学生）

入口：

- Vue 前端右上角菜单：`交作业`
- 直接访问：`/homework`

标准流程：

1. 选择作业
2. 填写小组信息 / 项目名 / 成员个人陈述
3. 选择文件上传（支持多次上传形成版本）
4. 点击“提交作业”（finalize）

当前内置了一个作业（启动时自动创建）：

- **2026项目实训末期检查**：允许上传任意类型文件（你可自定义“材料类型”，例如 `attachment`、`report`、`code_archive`）

## 教师评分（老师）

入口：

- Vue 前端：`/teacher/reviews`（移动端样式，顶部支持退出登录）
- Flutter Web（可选）：按你的 Flutter 项目实现为准

评分流程：

1. 查看待评队列
2. 进入某个提交详情
3. 填写评分项与评语并提交

## 后台查看（管理员）

主要入口：

- 用户与权限管理：`/admin/users`
- 作业统一看板（查看所有提交 / 导出 / 跳转仓库与工作量）：`/admin/submissions`
- 分配老师：从看板进入 `teacher-assignments`

## 文件存储与备份（无服务器场景）

开发阶段默认采用“本地磁盘落盘 + 数据库记录元数据”的方式：

- 上传文件落在：`backend/storage/submissions/`
- 路径结构：
  - `storage/submissions/{submission_id}/{asset_type}/v{version}_{uuid}{suffix}`

建议备份两样即可完成整站迁移/恢复：

1. `backend/storage/`（全部文件）
2. 数据库文件：
   - MySQL：备份数据库
   - SQLite：备份 `backend/edueval_ai.sqlite3`

## 常见问题

### 1) Flutter Web 调用后端报 `net::ERR_FAILED`

原因多半是跨域（CORS）未放行 `http://localhost:8090`。

处理：

- 在 `backend/.env` 的 `CORS_ORIGINS` 加上 `http://localhost:8090,http://127.0.0.1:8090`
- 重启后端

### 2) 老师登录后提示 `staff required`

含义：当前账号不是 `teacher/admin`。

处理：

- 管理员到 `/admin/users` 把该账号角色改为 `teacher`（初始管理员不可降级）

### 3) 博客抓取提示缺少 playwright

如果你需要启用博客抓取：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```
- 给博客取证页增加失败原因展开和异常页自动告警。
- 如果后续规模继续扩大，再把博客抓取升级为异步任务队列。
