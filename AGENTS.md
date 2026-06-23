# Repository Guidelines

## Project Structure & Module Organization

EduEvalAI has a FastAPI backend and Vue 3 frontend (the directory is named `fronted/`). In `backend/app/`, endpoints are under `api/routes/`, SQLAlchemy entities under `models/`, API types under `schemas/`, and business logic under `services/`. Vue code is in `fronted/src/`, with UI in `components/`, pages in `views/`, Pinia state in `stores/`, API wrappers in `services/`, and static files in `assets/` and `public/`. `project_blogs/` contains notes, not runtime code.

## Build, Test, and Development Commands

Run backend commands from `backend/`:

- `python -m venv .venv` creates an isolated environment.
- `pip install -r requirements.txt` installs backend dependencies.
- `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload` starts the API with reload.
- `python -m playwright install chromium` installs the optional blog-crawler browser.

Run frontend commands from `fronted/`:

- `npm ci` installs the locked dependency set.
- `npm run serve -- --port 8080` starts the development server.
- `npm run lint` runs ESLint for JavaScript and Vue files.
- `npm run build` creates the production bundle in `fronted/dist/`.

## Coding Style & Naming Conventions

Use four spaces and PEP 8 conventions in Python. Keep routes thin and reusable behavior in services. Use `snake_case` for Python modules/functions and `PascalCase` for models and schemas. In Vue, use two-space indentation, single quotes in JavaScript, `PascalCase.vue` components/views, and `camelCase` stores and services.

## Testing Guidelines

No automated test suite or coverage threshold is currently configured. For every change, run `npm run lint` and `npm run build`, start the API, and verify `GET /api` plus affected role-specific flows. New backend tests should go in `backend/tests/` as `test_<feature>.py`; frontend tests should use `*.spec.js` beside the feature or under `fronted/tests/`. Add the chosen runner to the relevant manifest when introducing tests.

## Commit & Pull Request Guidelines

History uses short imperative summaries, sometimes with a Conventional Commit prefix such as `feat:`. Prefer focused messages like `feat: add submission export` or `fix: enforce teacher access`. Pull requests should explain the user-visible change, list verification commands, link related issues, and include screenshots for UI changes. Note schema, environment-variable, or storage-format changes explicitly.

## Security & Configuration

Copy `backend/.env.example` to `.env` for local configuration. Never commit API keys, database credentials, SQLite files, browser profiles, uploaded content, or generated `dist/` output. Preserve role checks for `admin`, `teacher`, and `user` in both API routes and navigation.
