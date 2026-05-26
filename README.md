# EduEvalAI

EduEvalAI 是一个教学项目材料管理系统，包含 Vue 前端、FastAPI 后端、MySQL 存储，以及管理员侧的 CSDN 博客取证模块。

这版已经按当前业务规则收紧并整合：

- 管理员登录后默认进入后台管理页。
- 普通用户只能上传一次申请书并查看自己的材料。
- 普通用户不能看到评分结果。
- 普通用户不能查看其他用户的申请书。
- 申请书重传和电子签名更换都需要管理员审批。
- 博客抓取只能由管理员触发。
- 博客抓取目标只从数据库里的 `users.blog_home_url` 读取。
- `users.blog_home_url` 既支持保存完整 CSDN 博客主页地址，也支持只保存 CSDN 用户名。
- 用户、申请书草稿、任务书草稿都支持按组管理。

## 技术栈

- Python 3
- FastAPI
- SQLAlchemy
- MySQL
- Vue 3
- Playwright

## 目录结构

```text
EduevalAI-main/
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

## 角色与权限

### 普通用户

允许：

- 注册和登录
- 上传一次申请书
- 查看自己的申请书列表和详情
- 修改自己的密码
- 提交申请书重传申请
- 提交电子签名变更申请

不允许：

- 查看评分
- 触发评分
- 查看其他用户的申请书
- 未经审批直接重传
- 未经审批直接替换生效中的电子签名
- 进入管理员后台

### 管理员

允许：

- 登录后直接进入 `/admin/users`
- 查看用户列表
- 调整用户角色
- 创建分组、查看分组、给用户分配分组
- 审核申请书重传申请
- 审核电子签名变更申请
- 查看全局待审核申请页
- 查看用户申请书草稿和任务书草稿
- 配置每个用户的 CSDN 博客主页
- 触发单用户或多用户博客抓取
- 查看全局博客抓取任务页
- 查看博客正文预览、站内 HTML 归档预览和截图
- 标记博客正常/异常
- 执行评分、批量评分、导出

说明：

- 第一个注册账号会自动成为初始管理员。
- 初始管理员不能被降级。

## 分组模型

新增了用户分组能力，分组由管理员维护。

当前分组规则：

- 用户可被分配到一个组。
- 申请书草稿按用户所属组保存。
- 任务书草稿按用户所属组保存。
- 用户正式上传申请书时，也会把当前组写入申请记录。

当前管理员入口：

- `/admin/users`：查看用户、分配分组
- `/admin/groups`：创建和查看分组

## 数据库

### 1. 创建数据库

```sql
CREATE DATABASE edueval_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 自动建表 / 自动补列

后端启动时会执行：

- `Base.metadata.create_all()`
- `init_db()`

因此首次运行不需要手工逐表创建。

当前核心表包括：

- `users`
- `user_groups`
- `application_records`
- `score_results`
- `user_change_requests`
- `blog_posts`
- `blog_crawl_runs`
- `application_drafts`
- `task_drafts`

当前重点字段包括：

- `users.blog_home_url`
- `users.blog_enabled`
- `users.blog_crawl_status`
- `users.blog_last_crawled_at`
- `users.application_reupload_allowed`
- `users.group_id`
- `application_records.group_id`
- `application_drafts.group_id`
- `task_drafts.group_id`

## 配置文件

项目提供可修改的示例配置文件：

```text
backend/.env.example
```

复制为：

```text
backend/.env
```

### 最小必填配置

```env
DATABASE_URL=mysql+pymysql://root:123456@127.0.0.1:3306/edueval_ai?charset=utf8mb4
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
BLOG_CDP_URL=http://127.0.0.1:9222
BLOG_LAUNCH_CHROME=false
```

### 博客抓取相关配置

```env
BLOG_CRAWLER_ENABLED=true
BLOG_CRAWLER_SOURCE=csdn
BLOG_CDP_URL=http://127.0.0.1:9222
BLOG_LAUNCH_CHROME=false
BLOG_CHROME_EXE=
BLOG_PROFILE_DIR=./storage/browser_profile
BLOG_MAX_PAGES=100
BLOG_MIN_DELAY_SECONDS=2.0
BLOG_MAX_DELAY_SECONDS=5.0
BLOG_NAVIGATION_TIMEOUT_MS=45000
BLOG_PAGE_LOAD_WAIT_MS=2000
```

说明：

- `BLOG_CDP_URL` 是后端通过 Playwright 接管已登录 Chrome 的 CDP 地址。
- 默认是 `http://127.0.0.1:9222`，对应本机以远程调试模式启动的 Chrome。

## 安装与启动

### 后端

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### 前端

```bash
cd fronted
npm install
npm run serve
```

启动后访问：

- 前端：`http://127.0.0.1:8080`
- 后端 API：`http://127.0.0.1:8001/api`

## 首次初始化流程

1. 启动 MySQL。
2. 配置 `backend/.env`。
3. 启动后端。
4. 启动前端。
5. 注册第一个账号。
6. 第一个账号自动成为管理员。
7. 用管理员账号登录后台。
8. 在后台创建分组并给用户分配分组。

## 普通用户流程

### 上传申请书

规则：

- 第一次上传直接允许。
- 之后再次上传会被拒绝。
- 用户必须先提交重传申请。
- 管理员批准后，只放行一次重传。
- 新一次上传成功后，重传权限会自动消耗。

### 修改电子签名

在个人资料页中：

1. 选择新的签名图片。
2. 填写申请备注。
3. 提交申请。
4. 等待管理员批准。

只有管理员批准后，新的签名图片才会替换当前生效签名。

## 管理员流程

### 管理员落地页

管理员登录后默认进入：

```text
/admin/users
```

在这个页面可以：

- 查看用户博客主页配置
- 查看博客抓取状态
- 勾选哪些用户要抓博客
- 批量抓取所选用户
- 进入单个用户博客页
- 查看待审核申请数
- 给用户分配分组
- 进入草稿查看页

### 分组管理页

管理员可以进入：

```text
/admin/groups
```

这个页面可以：

- 创建新分组
- 查看已有分组
- 使用组名、组编码、描述管理业务分组

### 全局申请审核页

管理员可以进入：

```text
/admin/requests
```

这个页面显示：

- 全部待审核重传申请
- 全部待审核签名变更申请
- 已批准申请
- 已驳回申请

### 全局博客抓取任务页

管理员可以进入：

```text
/admin/blog-runs
```

这个页面显示：

- 哪个用户被抓取
- 任务状态
- 发现篇数 / 保存篇数 / 失败篇数
- 跳转到该用户博客页

### CSDN 博客配置与抓取

管理员配置博客主页时，支持两种输入：

```text
2301_82000924
```

或：

```text
https://blog.csdn.net/2301_82000924
```

也支持这类带查询参数的主页地址：

```text
https://blog.csdn.net/2301_82000924?type=blog
```

系统会统一规范化为：

```text
https://blog.csdn.net/2301_82000924
```

随后管理员可以：

- 抓取单个用户博客
- 在 `/admin/users` 勾选多个用户后批量抓取
- 查看某个用户的博客取证详情

关键规则：

- 前端不直接决定抓取目标。
- 后端只按 `user_id` 查询 `users.blog_home_url` 后再抓取。

## 博客预览说明

### 正文预览

管理员在用户博客页看到的是站内预览，不是简单纯文本输出。

当前已实现：

- 标题区
- 时间、抓取状态、审核状态
- 摘要区
- 简单标签提取
- 按段落和编号规则切分正文
- 阅读卡片样式展示

目标是让管理员在站内先完成快速核验，而不是面对一整块未切分文本。

### HTML 归档预览

HTML 归档预览不再直接打开原始文件后跳回 CSDN。

当前方案：

- 前端先从后端拿到 HTML 文件流
- 再在站内弹层中使用 `iframe srcdoc` 预览
- 预览前会移除脚本、移除 `base`、禁用外链跳转、注入基础样式

结果是：

- 可以在系统内部查看归档 HTML
- 不会轻易被页面链接带回 CSDN
- 更适合管理员做留痕核验

## Chrome 登录态复用

博客抓取依赖已登录的 Chrome 或 Chromium 会话。

推荐在本机启动方式：

```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="D:\Code\eduevalAI\EduevalAI-main\backend\storage\browser_profile"
```

然后：

1. 手动登录 CSDN。
2. 保持这个 Chrome 窗口不关闭。
3. 再从管理员后台触发抓取。

## Windows / Linux 支持

### 主系统

主系统本身不是 Windows 专用。

前后端都支持：

- Windows
- Linux
- macOS

前提是本机具备：

- Python 依赖
- Node 依赖
- MySQL

### 博客抓取

博客抓取也不是严格只能在 Windows 上跑，但当前默认工作流偏桌面环境：

- 使用 Playwright
- 通过 CDP 接管已登录浏览器
- 依赖人工登录
- 不绕过验证码

因此实践上：

- Windows 桌面最省事
- 有 GUI 或远程桌面的 Linux 也可用
- 纯无头 Linux 服务器不适合当前默认抓取方案

总结：

- 主项目支持 Linux
- 当前博客抓取方案更适合 Windows 桌面或带 GUI 的 Linux

## API 概览

### 普通用户接口

- `GET /api/applications`
- `GET /api/applications/{id}`
- `POST /api/applications/upload`
- `GET /api/applications/me/status`
- `GET /api/applications/me/requests`
- `POST /api/applications/me/reupload-request`
- `POST /api/applications/me/signature-request`
- `GET /api/users/me/profile`
- `GET /api/users/me/signature`
- `POST /api/users/me/password`

### 管理员接口

- `GET /api/users/admin/users`
- `PUT /api/users/admin/users/{user_id}/role`
- `GET /api/users/admin/groups`
- `POST /api/users/admin/groups`
- `PUT /api/users/admin/users/{user_id}/group`
- `GET /api/users/admin/requests`
- `GET /api/users/admin/users/{user_id}/requests`
- `PUT /api/users/admin/users/{user_id}/requests/{request_id}/review`
- `GET /api/users/admin/users/{user_id}/blog-profile`
- `PUT /api/users/admin/users/{user_id}/blog-profile`
- `POST /api/users/admin/users/{user_id}/blogs/crawl`
- `POST /api/users/admin/blogs/crawl-batch`
- `GET /api/users/admin/blogs/crawl-runs`
- `GET /api/users/admin/users/{user_id}/blogs`
- `GET /api/users/admin/users/{user_id}/blogs/{blog_id}`
- `PUT /api/users/admin/users/{user_id}/blogs/{blog_id}/review`

## 存储目录

主存储根目录：

```text
backend/storage/
```

重点子目录：

- `backend/storage/applications/`
- `backend/storage/signatures/`
- `backend/storage/pending_signatures/`
- `backend/storage/blogs/user_<id>/screenshots/`
- `backend/storage/blogs/user_<id>/html/`
- `backend/storage/browser_profile/`

## 已验证内容

目前已验证通过：

- 后端 Python 编译
- 前端 `npm run build`
- 前端 `npm run lint`
- MySQL 自动建表 / 自动补列
- 普通用户首次上传成功
- 重复上传被拒绝
- 重传申请成功
- 管理员批准后放行一次重传
- 重传成功后权限被消耗
- 普通用户看不到评分
- 普通用户不能查看其他用户申请书
- 签名变更申请成功
- 管理员批准后更新生效签名
- 分组创建接口可用
- 用户分组分配接口可用
- 申请书草稿、任务书草稿会继承用户分组
- 博客主页既支持用户名也支持完整 URL 输入
- 用户博客页正文站内预览可用
- 用户博客页 HTML 沙箱预览可用
- 管理员全局申请页接口可用
- 管理员全局博客任务页接口可用

说明：

- 上面的回归不包含完整 Chrome/CDP 实时抓取链路，除非你本机已准备好登录态并主动执行抓取测试。

## 后续建议

- 把当前 `prompt` 式分组分配和审核操作升级成正式弹窗表单。
- 给管理员增加分组筛选、组内批量操作和组维度统计。
- 给博客取证页增加失败原因展开和异常页自动告警。
- 如果后续规模继续扩大，再把博客抓取升级为异步任务队列。
