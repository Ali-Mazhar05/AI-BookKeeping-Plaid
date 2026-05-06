# Files to Commit to GitHub

Below is the definitive list of files and directories that you should commit to your repository for a successful Vercel deployment and clean codebase.

## 🟢 Core Project Files (Root)
- `.gitignore`
- `Design.md`
- `implementation_plan.md`
- `README.md`

## 🟢 Backend & Logic (`zalazar-bookkeeping/`)
- `src/` (Entire directory - Core logic)
- `services/` (Entire directory - Backend services)
- `scripts/` (Entire directory - Database and utility scripts)
- `migrations/` (Entire directory - DB Schema changes)
- `pyproject.toml` (Python dependencies)
- `package.json` (Backend tools)
- `package-lock.json`
- `docker-compose.yml`
- `README.md`
- `RUNBOOK.md`
- `.env.example` (Template for secrets)
- `.github/` (GitHub Actions / Workflows)

## 🟢 Frontend (`zalazar-bookkeeping/frontend/`)
- `src/` (Entire directory - React/Vite components and logic)
- `public/` (Entire directory - Static assets)
- `index.html`
- `package.json`
- `package-lock.json`
- `vite.config.js`
- `eslint.config.js`
- `.gitignore`

---

## 🔴 DO NOT COMMIT (Already handled by .gitignore)
- `.env` (Sensitive keys)
- `node_modules/` (Dependencies)
- `dist/` (Build output)
- `__pycache__/` (Python cache)
- `uploads/` (User data)
- `*.txt` (DB exports/logs)
- `*.pdf` (Financial statements)
- `scratch/` (Temporary scripts)
