# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

```
# Backend (from backend/)
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
python -m playwright install chromium   # only if blog crawling is needed

# Frontend (from fronted/)
npm ci              # install locked deps
npm run serve -- --port 8080
npm run lint
npm run build
```

Backend at `http://127.0.0.1:8001/api`. Frontend at `http://localhost:8080`.

## Project Overview

EduEvalAI is a teaching project material management & review system with three roles:

- **admin** — full control: manage users/roles/groups, view all submissions, assign teachers, export scores, manage blogs
- **teacher** — only scores submissions (no homework submission, no backend access)
- **user (student)** — submits homework/upload materials (no scoring, no backend access)

The first registered account becomes the **root admin** (`is_root_admin=true`) and cannot be downgraded.

## Architecture

### Backend (FastAPI + SQLAlchemy)

**Database resilience**: The app tries the configured `DATABASE_URL` (typically MySQL). On connection failure, it auto-falls back to SQLite (`edueval_ai.sqlite3`). See `backend/app/db/base.py:10-16`. This means the app starts without any configured database.

**Database migration**: There is no Alembic. Schema changes are applied in `init_db.py` via `ALTER TABLE` with column-existence checks (`inspector.get_columns()`). Add new columns there following the existing pattern (check column exists → `ALTER TABLE ADD COLUMN` → create index → backfill data).

**Auth flow**: Token-based, NOT JWT. Passwords: PBKDF2-SHA256 with 200k iterations + per-user random salt. Login creates a `UserSession` with a random 64-char hex token whose SHA-256 hash is stored. Tokens expire after 1 day (or 30 if "remember me"). See `backend/app/services/auth_service.py`.

**Role guards in routes**: Each route file handles its own authorization — check for patterns like `if current_user.role != "admin": raise 403`. There's no centralized middleware for role checks.

**Background workers** (both daemon threads started in `main.py` `startup`):
- **Blog crawl worker** (`blog_crawl_job_service.py`) — queue-based, serial execution. Admin triggers a crawl job which gets enqueued; single daemon thread processes one crawl at a time.
- **Repo sync scheduler** (`repo_scheduler_service.py`) — polling loop that checks every N minutes whether any repo bindings are due for weekly sync (configurable weekday/hour).

**File storage layout** under `backend/storage/`:
```
storage/
├── submissions/{submission_id}/{asset_type}/v{version}_{uuid}{suffix}
├── applications/    # uploaded application files
├── signatures/      # user signature images
├── blogs/screenshots/  # Playwright screenshots
├── blogs/html/         # saved HTML snapshots
├── previews/        # converted preview files
├── exports/         # generated export files
└── upload_sessions/ # temporary upload chunks
```

### Frontend (Vue 3 + Pinia + Tailwind CSS 4 + Vue Router)

**Directory naming**: The frontend directory is `fronted/` (a typo preserved in the repo).

**Route guard pattern** (`router/index.js`): Meta fields on routes control access — `requiresAuth`, `requiresAdmin`, `requiresStudent`, `requiresStaff`, `guestOnly`. The `beforeEach` guard redirects based on role. Admins landing on `/` get redirected to `/admin/users`; teachers to `/teacher/reviews`; students stay.

**API client** (`services/eduevalApi.js`): Auto-fallback mechanism — tries configured API base, then same-origin `/api`, then `localhost:8001/api`. Auth token passed as `Authorization: Bearer <token>` header. All functions take `token` as the first parameter.

**State management**: Only one Pinia store — `authStore` (`stores/authStore.js`). Token persisted to localStorage (remember me) or sessionStorage. Other state (applications, etc.) is managed locally in views.

**Styling**: Tailwind CSS v4 via `@tailwindcss/postcss` plugin. Lucide icons via `lucide-vue-next`.

### Key Feature Pipelines

**Student homework submission flow**:
1. Student navigates to `/homework`
2. Selects an assignment → creates/updates `AssignmentSubmission` (draft)
3. Uploads files as `SubmissionAsset` (versioned)
4. Fills group info, project name, member statements
5. Clicks "finalize" → status changes from `draft` to `submitted`

**Teacher scoring flow**:
1. Teacher visits `/teacher/reviews` (mobile-styled)
2. Sees review queue filtered by assignment
3. Opens a submission detail → views files, members
4. Submits scores/notes → creates `TeacherScoreRecord`
5. Admin assigns which teachers review which submissions via `/admin/submissions/:id/teacher-assignments`

**Blog crawling flow** (`blog_crawl_job_service.py` → `blog_crawler_service.py` → `csdn_crawler_service.py`):
1. Admin triggers crawl for a user (or batch) via API
2. A `BlogCrawlRun` record is created and enqueued
3. The daemon worker picks it up, uses Playwright to scrape the user's CSDN blog
4. Each post is saved as `BlogPost` with HTML/screenshot evidence
5. Admin reviews posts (approve/reject) via `/admin/blog-overview`

**Repository sync flow** (Gitee only):
1. Admin binds a Gitee repo URL to a submission via `/admin/submissions/:id/repo`
2. The scheduler (or manual trigger) syncs commits via Gitee API
3. Commits stored as `RepoCommitSnapshot`, weekly stats computed
4. Member email/name mappings link commits to submission members

### Model Hierarchy (most important relationships)

- `User` → `UserSession` (1:N), `UserGroup` (N:1), `BlogPost` (1:N)
- `Assignment` → `AssignmentSubmission` (1:N)
- `AssignmentSubmission` → `SubmissionAsset`, `SubmissionMember`, `TeacherScoreRecord`, `RepoBinding`, `SubmissionCodeAnalysis` (all 1:N)
- `UserGroup` → `User` (1:N)
- `RepoBinding` → `RepoCommitSnapshot` (1:N)

### Running Tests

No test runner is configured in `package.json` or a `pyproject.toml`. Tests exist in `backend/tests/` as standalone `test_<feature>.py` files. Run them directly:
```bash
cd backend
python -m pytest tests/ -v
# or individually:
python tests/test_workload_summary.py
```

## Key Conventions

- Python: 4-space indent, PEP 8, `snake_case` functions/modules, `PascalCase` models/schemas
- Vue: 2-space indent, single quotes, `PascalCase.vue` components/views, `camelCase` stores/services
- Routes stay thin; business logic lives in `services/`
- New features need: model, schema, service function, route handler, API client function
- Database changes: add column migration in `init_db.py` (not Alembic)
- Role checks: verify admin/teacher/user boundaries in both API routes and Vue router meta
- `.env` is gitignored; use `.env.example` as template
