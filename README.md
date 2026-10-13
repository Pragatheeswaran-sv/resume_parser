# Resume Tracker

A FastAPI-based backend system for tracking, filtering, parsing, and searching candidate resumes using AI/LLM-powered natural language queries.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Modules](#modules)
- [Third-Party Integrations](#third-party-integrations)
- [How Natural Language Search Works](#how-natural-language-search-works)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Running with Docker](#running-with-docker)
  - [Running Locally](#running-locally)
- [Database](#database)
- [Background Jobs](#background-jobs)
- [API Overview](#api-overview)

---

## Overview

Resume Tracker is a multi-service backend application that helps recruiters:

- **Parse** resumes (PDF, DOCX) and extract structured candidate data using LLMs
- **Search** candidates using natural language queries (e.g. *"Python developer with 3+ years of experience"*)
- **Filter** candidates by skills, education, roles, companies, experience, and more
- **Track** email interactions via Gmail and Zoho OAuth integrations
- **Share** candidate profiles and send email notifications
- **Manage** clients, interview rounds, and candidate pipelines

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.129 |
| Language | Python 3.12 |
| Database | PostgreSQL (SQLAlchemy ORM + Alembic migrations) |
| Cache / Queue Broker | Redis |
| Task Queue | Celery |
| Scheduler | APScheduler |
| LLM Support | Ollama, OpenAI, Anthropic (Claude) |
| Auth | JWT (python-jose) + OAuth2 (Gmail, Zoho) |
| File Storage | Supabase S3 (boto3) |
| PDF Processing | PyPDF, pikepdf, ReportLab |
| DOCX Processing | python-docx |
| Containerisation | Docker + Docker Compose |
| Dependency Management | Poetry |

---

## Project Structure

```
resume_tracker/
├── src/
│   ├── admin/              # Admin management (CRUD, login, user management)
│   ├── admin_dashboard/    # Admin analytics and dashboard APIs
│   ├── auth/               # JWT auth, OAuth SSO, token refresh, logout
│   ├── candidate/          # Core candidate search, profiles
│   ├── celery/             # Celery app configuration
│   ├── client_track/       # Client and job tracking
│   ├── email_reader/       # Email ingestion and parsing
│   ├── integrations/       # Third-party integrations
│   │   ├── attachment_storage.py   # Supabase S3 file storage
│   │   ├── email_sender.py         # SMTP email sending
│   │   ├── google.py               # Gmail OAuth integration
│   │   ├── llm.py                  # LLM abstraction (Ollama/OpenAI/Claude)
│   │   └── zoho.py                 # Zoho CRM/Mail OAuth integration
│   ├── jobs/               # APScheduler background jobs
│   ├── resume_download/    # Resume file download APIs
│   ├── resume_filter/      # Resume filter logic and NL search service
│   ├── resume_share/       # Candidate profile sharing via email
│   ├── services/           # Shared service utilities
│   ├── tailor_resume/      # AI-based resume tailoring
│   ├── user_dashboard/     # User-facing dashboard APIs
│   ├── utils/              # Helpers: Redis client, encryption, serializers
│   └── main.py             # FastAPI app entry point
├── db/
│   └── connection.py       # SQLAlchemy engine and session setup
├── alembic/                # Database migrations
├── test/                   # Pytest test suite
├── attachments/            # Local file storage (created at runtime)
├── docker-compose.yaml
├── dockerfile
├── pyproject.toml
└── .env                    # Environment variables (not committed)
```

---

## Modules

### `admin`
Manages admin accounts, user creation, AI model configuration, and role/skill/education master data.

### `auth`
Handles SSO login, Gmail/Zoho OAuth callbacks, and logout (token revocation).

### `candidate`
The core module. Provides:
- Natural language candidate search (`/api/candidate/profile_search`)
- Structured resume search with filters
- Candidate profile CRUD
- Resume upload and parsing
- Pagination using Redis-cached search sessions

### `resume_filter`
Contains the natural language search service logic — LLM extraction, keyword fallback, filter resolution, and DB querying.

### `email_reader`
Reads and parses emails from Gmail/Zoho to extract resume attachments and ingest candidate data.

### `resume_share`
Handles sharing candidate profiles with clients via email, with tracking logs.

### `client_track`
Manages client companies, job roles, interview rounds, and candidate-interview mappings.

### `admin_dashboard` / `user_dashboard`
Provides aggregated analytics (candidate counts, interview status, pipeline summaries) for admin and user roles.

### `jobs`
APScheduler-based background worker (`scheduler_worker.py`) for scheduled email polling and other periodic tasks.

### `celery`
Celery worker configuration for async task processing (resume parsing, email processing).

### `integrations`
Centralised third-party service wrappers:
- **`llm.py`** — unified LLM interface (Ollama, OpenAI, Claude)
- **`google.py`** — Gmail OAuth token exchange, email fetching
- **`zoho.py`** — Zoho OAuth token exchange, email fetching
- **`email_sender.py`** — SMTP email sending for notifications
- **`attachment_storage.py`** — Supabase S3 upload/download

---

## Third-Party Integrations

### Gmail (OAuth2)
Used to read candidate emails and fetch resume attachments.
- Set `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REDIRECT_URI` in `.env`
- Initiate flow: `GET /api/oauth/login/gmail`
- Callback: `GET /api/auth/gmail/callback?code=...`

### Zoho (OAuth2)
Alternative email provider for resume ingestion.
- Set `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REDIRECT_URI` in `.env`
- Initiate flow: `GET /api/oauth/login/zoho`
- Callback: `GET /api/auth/zoho/callback?code=...`

### Ollama (Local LLM)
Default LLM for NL search and resume parsing. Runs locally or via Docker.
- Set `OLLAMA_HOST=http://host.docker.internal:11434` in `.env`
- Download Ollama: https://ollama.com/download
- Pull a model: `ollama pull llama3`

### OpenAI / Claude
Supported as alternative LLM providers. Configure via the admin panel (AI Model Config).

### Supabase S3
Used for storing and retrieving resume attachment files.
- Set `SUPABASE_S3_ENDPOINT`, `SUPABASE_S3_ACCESS_KEY`, `SUPABASE_S3_SECRET_KEY`, `SUPABASE_S3_BUCKET` in `.env`

---

## How Natural Language Search Works

When a recruiter submits a query like *"Python developer with 3+ years of experience"*:

1. **LLM Extraction** — The query is sent to the configured AI model, which returns structured JSON filters:
   ```json
   { "skills": ["Python"], "roles": ["Developer"], "min_experience": 3 }
   ```

2. **UUID Resolution** — Human-readable names are resolved to database IDs (e.g. `"Python"` → `skill_id`).

3. **Redis Caching** — Resolved filters are stored in Redis with a `search_id`, so subsequent pages reuse the same filters without re-calling the LLM.

4. **SQL Query** — Filters are applied across `candidates`, `resumes`, `candidate_skills`, `work_experience`, and `candidate_education` tables.

5. **Paginated Response** — Returns candidates with a `search_id`. Pass `search_id` on the next request to paginate without re-querying the LLM.

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [Ollama](https://ollama.com/download) installed (for local LLM support)
- PostgreSQL database (local or remote)
- A `.env` file (see below)

### Environment Variables

Create a `.env` file in the project root. Refer to `.env.example` for all available keys.

Key variables:

```env
# Database
DATABASE_URL=postgresql://postgres:<password>@<host>:5432/<dbname>

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
SECRET_KEY=<your-secret-key>

# Ollama
OLLAMA_HOST=http://host.docker.internal:11434

# Gmail OAuth
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REDIRECT_URI=http://localhost:3000

# Zoho OAuth
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REDIRECT_URI=http://localhost:3000/login

# Supabase S3
SUPABASE_S3_ENDPOINT=...
SUPABASE_S3_ACCESS_KEY=...
SUPABASE_S3_SECRET_KEY=...
SUPABASE_S3_BUCKET=attachments

# Email (IMAP for reading)
IMAP_SERVER=imap.gmail.com
EMAIL_ACCOUNT=your@gmail.com
PASSWORD=your-app-password

# File Storage
ATTACHMENT_DIR=attachments
ATTACHMENT_STORAGE=supabase
```

### Running with Docker

```bash
# Build and start all services
docker compose up --build

# Services started:
# - fastapi_api  → http://localhost:8000
# - celery       → async task worker
# - worker       → APScheduler background jobs
# - redis        → cache and message broker
```

### Running Locally

```bash
# Install dependencies
pip install poetry
poetry install

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Start Celery worker (separate terminal)
celery -A src.celery.celery_app.celery worker --loglevel=info --pool=solo

# Start APScheduler worker (separate terminal)
python -m src.jobs.scheduler_worker
```

---

## Database

- **ORM**: SQLAlchemy 2.x
- **Migrations**: Alembic (`alembic/`)
- **Connection**: Configured via `DATABASE_URL` in `.env`

### Run Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"
```

## Background Jobs

| Service | Purpose |
|---|---|
| **Celery Worker** | Async resume parsing, email processing |
| **APScheduler Worker** | Periodic email polling from Gmail/Zoho |

Both services share the same Docker image (`resume-tracker:latest`) and read from the same `.env`.

---

## API Overview

| Prefix | Module | Description |
|---|---|---|
| `/api/admin` | admin | Admin login, user management, AI model config |
| `/api/candidate` | candidate | Candidate search, profiles, resume upload |
| `/api/` | auth | OAuth login/callback, logout, token refresh |
| `/api/` | email_reader | Email ingestion and processing |
| `/api/` | resume_share | Share candidate profiles via email |
| `/api/` | client_track | Client and interview management |
| `/api/admin/dashboard` | admin_dashboard | Admin analytics |
| `/api/user/dashboard` | user_dashboard | User analytics |
| `/health` | — | Health check |

Full interactive API docs available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`