---
title: Zalazar Bookkeeping
emoji: 💰
colorFrom: yellow
colorTo: indigo
sdk: docker
pinned: false
---

# Zalazar Bookkeeping System

AI-powered bookkeeping and transaction categorization system built for Zalazar Holdings LLC.

## Overview
This system automates the ingestion, classification, property allocation, and reconciliation of banking transactions using Plaid and OpenAI. 

It completely replaces previous manual N8N workflows with a native, robust Python backend (FastAPI + APScheduler + SQLAlchemy + Supabase).

## Key Features
1. **Plaid Sync Engine:** Fetches transactions from connected bank accounts idempotently.
2. **AI Categorization Pipeline:** Deterministic vendor/description normalization, rule-based matching (GIN trigram indexed), and fallback to structured AI JSON outputs via GPT-4o-mini.
3. **Property Allocation:** Multi-layer attribution engine supporting direct assignments and penny-perfect 'even splits'.
4. **Mortgage Splitter:** Complex handling of principal vs. interest transaction child splitting.
5. **Reconciliation:** Daily jobs to ensure the database ledger perfectly matches the true bank balance.
6. **JARVIS Q&A Agent:** Interactive conversational AI connected directly to the monthly P&L and SQL ledger.
7. **Unified Notifications:** Throttled SMS (RingCentral) and Email (Gmail) alerts for large expenses, cash flow changes, and sync issues.

## Technology Stack
- **Language:** Python 3.11+
- **Database:** PostgreSQL (Supabase hosted) + `asyncpg`
- **Web/API:** FastAPI
- **Background Jobs:** APScheduler
- **AI/LLM:** OpenAI SDK
- **Integrations:** Plaid, RingCentral, Gmail API

## Getting Started

1. **Install Dependencies:**
   ```bash
   poetry install
   ```
2. **Environment Variables:**
   Copy `.env.example` to `.env` and fill in the required credentials.
3. **Database Setup:**
   Apply the migrations located in `migrations/` against your Supabase project.
4. **Run Locally:**
   ```bash
   docker-compose up --build
   ```

## Development & Testing
Run unit tests and the QA accuracy harness:
```bash
pytest tests/unit/
python scripts/run_qa.py
```

## Documentation
- **Runbook:** See `RUNBOOK.md` for operations, incident response, and key rotation.
- **QA Baseline:** See `qa_report_v1.md` for the accuracy baseline.
