# fronted（Vue 前端）

默认开发端口：`http://localhost:8080`

## 安装依赖

```bash
npm install
```

## 开发启动（热更新）

```bash
npm run serve -- --port 8080
```

## 构建

```bash
npm run build
```

## Lint

```bash
npm run lint
```

## 主要入口

- 登录页：`/login`
- 学生交作业：`/homework`（需要学生账号，老师会被拦截到评分页）
- 教师评分端（移动样式）：`/teacher/reviews`（需要 teacher/admin）
- 管理后台：`/admin/users`、`/admin/submissions`（需要 admin）
