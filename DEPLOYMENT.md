# Free Deployment Guide - Resume Tracker

Deploy the whole backend for free using:

- **Render** (Docker web service) - runs the API + Celery worker + APScheduler in one container
- **Neon** - free PostgreSQL
- **Upstash** - free Redis (Celery broker + cache)
- **Groq** - LLM, already configured in your database

There is no separate frontend; this deploys the FastAPI backend (Swagger UI at `/docs`).

---

## 1. PostgreSQL on Neon (free)

1. Sign up at https://neon.tech and create a project (pick a region near you).
2. Create a database (e.g. `resume_tracker`).
3. Copy the connection string. It looks like:
   ```
   postgresql://<user>:<password>@ep-xxxx.<region>.aws.neon.tech/resume_tracker?sslmode=require
   ```
   This is your `DATABASE_URL`.
4. Import your existing data (from the repo root, using your dump file):
   ```bash
   psql "postgresql://<user>:<password>@ep-xxxx.<region>.aws.neon.tech/resume_tracker?sslmode=require" -f resume_tracker.sql
   ```
   If that dump errors, try `backup.sql` instead. (Install `psql` locally if needed, or use Neon's SQL editor for smaller dumps.)

> Important: the API keys stored in the DB (e.g. your Groq key) are Fernet-encrypted with `SECRET_KEY`. Use the **same** `SECRET_KEY` value in Render that you used locally, or those keys won't decrypt.

---

## 2. Redis on Upstash (free)

1. Sign up at https://upstash.com and create a Redis database.
2. Copy the connection URL (choose the TLS one):
   ```
   rediss://default:<password>@<host>.upstash.io:6379
   ```
   This is your `REDIS_URL`.

---

## 3. Push code to GitHub

The code fixes for cloud hosting are already in this repo (env-driven DB URL, no hardcoded secrets, multi-process `start.sh`, updated `dockerfile`). Commit and push:

```bash
git add db/connection.py src/main.py start.sh dockerfile .env.example DEPLOYMENT.md
git commit -m "Add free cloud deployment setup (Render + Neon + Upstash)"
git push origin HEAD
```

---

## 4. Deploy on Render (free)

1. Sign up at https://render.com and connect your GitHub account.
2. **New +** -> **Web Service** -> select the `resume_tracker` repo.
3. Settings:
   - **Language / Runtime:** Docker (Render auto-detects the `dockerfile`)
   - **Instance Type:** Free
   - **Branch:** the branch you pushed
4. Add **Environment Variables** (from `.env.example`). At minimum:
   - `DATABASE_URL` - Neon URL from step 1
   - `REDIS_URL` - Upstash URL from step 2
   - `SECRET_KEY` - same Fernet key as local
   - `JWT_SECRET_KEY` - a strong random string
   - Email/OAuth vars you use: `EMAIL_ACCOUNT`, `PASSWORD`, `GMAIL_*`, `ZOHO_*`
5. Click **Create Web Service**. First build takes a few minutes (it installs LibreOffice).
6. When live, test:
   - `https://<your-app>.onrender.com/health`
   - `https://<your-app>.onrender.com/docs`

---

## 5. Post-deploy configuration

- **OAuth redirect URIs:** In Google Cloud Console (Gmail) and Zoho, add the exact callback URLs as authorized redirects, and set `GMAIL_REDIRECT_URI` / `ZOHO_REDIRECT_URI` to match. The callback routes are `https://<your-app>.onrender.com/api/auth/gmail/callback` and `https://<your-app>.onrender.com/api/auth/zoho/callback`.
- **CORS / allowed emails:** `CORSMiddleware` in `src/main.py` already allows `*`. If you lock it down later, add your frontend origin. `AllowedEmailMiddleware` reads allowed emails from the DB (`src/admin/dependencies.py`).

---

## Free-tier caveats

- **Sleeping:** Render free web services sleep after ~15 min of inactivity and cold-start in ~1 min. While asleep, the Celery worker and email scheduler don't run.
  - On Render, the API makes a best-effort request to its own `/health` endpoint every 3 minutes using Render's `RENDER_EXTERNAL_URL`. This is not an uptime guarantee and keeps the free instance active, consuming its monthly hours (~750 h/month is roughly one always-on service).
- **Memory:** Free instance ~512 MB RAM. Running API + worker + scheduler + occasional LibreOffice conversions is fine for light/demo use; heavy concurrent load may OOM.
- **Ephemeral storage:** Files written to `attachments/` are lost on every restart/redeploy. For durable storage, move to object storage (Supabase Storage, Cloudflare R2, or S3) later - Render persistent disks are paid.
- **Neon free:** Always-on with generous limits; fine for demo/low traffic.

---

## Local development (unchanged)

Docker Compose still works as before:

```bash
docker compose up --build
```

The env defaults in `db/connection.py`, `celery_app.py`, and `redis_client.py` fall back to the Compose service names (`db`, `redis`).
