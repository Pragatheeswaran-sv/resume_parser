# Resume Tracker API Documentation

> **Version:** 1.0.0  
> **Generated from codebase analysis:** April 2026  
> **Framework:** FastAPI (Python)

---

## Table of Contents

1. [API Overview](#1-api-overview)
2. [Application Workflows](#2-application-workflows)
3. [Endpoint Documentation](#3-endpoint-documentation)
4. [Data Models / Schemas](#4-data-models--schemas)
5. [Authentication & Authorization](#5-authentication--authorization)
6. [Validation Rules](#6-validation-rules)
7. [Pagination, Filtering, Sorting](#7-pagination-filtering-sorting)
8. [Error Handling Standard](#8-error-handling-standard)
9. [Rate Limiting / Throttling](#9-rate-limiting--throttling)
10. [File Upload / Download](#10-file-upload--download)
11. [Background Processing](#11-background-processing)

---

## 1. API Overview

### Base URL

```
http://localhost:8000
```

The API server runs via Uvicorn on port `8000` inside Docker. In production, substitute with the deployed hostname.

### Authentication Mechanism

| Mechanism | Details |
|-----------|---------|
| **Type** | JWT Bearer Token |
| **Algorithm** | HS256 (configurable via `JWT_ALGORITHM` env var) |
| **Token Lifetime** | 60 minutes (configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` env var) |
| **Password Hashing** | bcrypt |
| **Library** | `python-jose` for JWT, `bcrypt` for passwords |

### Common Headers

| Header | Value | Required |
|--------|-------|----------|
| `Content-Type` | `application/json` | Yes (for POST/PUT/PATCH) |
| `Authorization` | `Bearer <jwt_token>` | Yes (for protected endpoints) |

### Versioning Strategy

No explicit API versioning is implemented. All endpoints are served under `/api` prefix (admin/candidate/resume modules) or at root level (OAuth/health).

### CORS Configuration

| Setting | Value |
|---------|-------|
| Allowed Origins | `http://localhost:3000`, `*` |
| Credentials | Enabled |
| Methods | All (`*`) |
| Headers | All (`*`) |

### Interactive Documentation

| URL | Description |
|-----|-------------|
| `GET /docs` | Swagger UI |
| `GET /redoc` | ReDoc UI |
| `GET /openapi.json` | OpenAPI schema |

---

## 2. Application Workflows

### 2.1 Admin Authentication Flow

The admin authentication is a traditional email + password flow that returns a JWT.

```
┌─────────────┐     POST /api/create_admin      ┌──────────┐
│   Frontend   │ ──────────────────────────────► │  Backend │
│              │ ◄────────────────────────────── │          │
│              │     { admin_id, name }          │          │
│              │                                 │          │
│              │     POST /api/admin/login       │          │
│              │ ──────────────────────────────► │          │
│              │ ◄────────────────────────────── │          │
│              │     { access_token, role }      │          │
│              │                                 │          │
│              │     GET /api/admin/*            │          │
│              │     Authorization: Bearer <jwt> │          │
│              │ ──────────────────────────────► │          │
│              │ ◄────────────────────────────── │          │
└─────────────┘     { data }                    └──────────┘
```

**Step-by-step:**

| Step | API Call | Description |
|------|----------|-------------|
| 1 | `POST /api/create_admin` | Register a new admin (one-time setup). Provide `email`, `password`, optional `name`. |
| 2 | `POST /api/admin/login` | Authenticate with `email` + `password`. Returns JWT with `role: "admin"`. |
| 3 | Use `Authorization: Bearer <token>` | Include the token in all subsequent admin-protected requests (`/api/admin/*`). |

**JWT Claims (Admin):**

```json
{
  "sub": "<admin_id (UUID)>",
  "email": "admin@example.com",
  "role": "admin",
  "exp": 1714000000
}
```

---

### 2.2 User (SSO) Authentication Flow

Users authenticate via an external SSO provider (Google, Zoho, or Microsoft). The frontend handles the SSO verification, then exchanges the verified email for a backend JWT.

```
┌──────────┐     SSO Login      ┌────────────┐     Verify Token     ┌──────────┐
│ Frontend │ ─────────────────► │ SSO Provider│ ──────────────────► │ Frontend │
│          │ ◄───────────────── │ (Google/    │                     │          │
│          │   SSO Token        │  Zoho/MS)   │                     │          │
│          │                    └────────────┘                      │          │
│          │                                                        │          │
│          │    POST /api/auth/sso/login                           │          │
│          │    { email, provider }                                 │          │
│          │ ────────────────────────────────────────────────────► │ Backend  │
│          │ ◄──────────────────────────────────────────────────── │          │
│          │    { access_token, role: "user" }                     │          │
└──────────┘                                                       └──────────┘
```

**Step-by-step:**

| Step | Action | Description |
|------|--------|-------------|
| 1 | Frontend authenticates with SSO provider | User logs in via Google/Zoho/Microsoft on the client side. |
| 2 | Frontend verifies SSO token | Extract verified email from the SSO token. |
| 3 | `POST /api/auth/sso/login` | Send `{ email, provider }` to the backend. Backend validates that the email exists in `auth_mail` and is not blocked. |
| 4 | Receive JWT | Backend returns a JWT with `role: "user"`. |
| 5 | Use `Authorization: Bearer <token>` | Include token in subsequent requests. The middleware validates the email claim against `auth_mail`. |

**Prerequisites:** The user's email must be pre-registered in the `auth_mail` table (by an admin) and must not be blocked.

**JWT Claims (User):**

```json
{
  "sub": "<auth_mail_id (UUID)>",
  "email": "user@example.com",
  "role": "user",
  "provider": "google",
  "exp": 1714000000
}
```

---

### 2.3 OAuth Email Account Connection Flow

Admins connect email accounts (Gmail/Zoho) for automated resume ingestion via OAuth.

**Gmail OAuth Flow:**

| Step | API Call | Description |
|------|----------|-------------|
| 1 | `GET /oauth/login/gmail` | Returns a Google OAuth authorization URL. Frontend redirects user to this URL. |
| 2 | User authorizes on Google | Google redirects back with an authorization `code`. |
| 3 | `GET /auth/gmail/callback?code=<code>` | Backend exchanges code for tokens, stores OAuth credentials, returns connected email. |

**Zoho OAuth Flow:**

| Step | API Call | Description |
|------|----------|-------------|
| 1 | `GET /oauth/login/zoho` | Returns a Zoho OAuth authorization URL. Frontend redirects user to this URL. |
| 2 | User authorizes on Zoho | Zoho redirects back with an authorization `code`. |
| 3 | `GET /auth/zoho/callback?code=<code>` | Backend exchanges code for tokens, stores OAuth credentials, returns connected email. |

---

### 2.4 Resume Ingestion & Processing Pipeline

This is the core business workflow that operates both on-demand and on a schedule.

```
┌──────────────┐    ┌───────────────┐    ┌────────────┐    ┌────────────┐
│ Email Source  │───►│ Fetch Emails  │───►│ Save       │───►│ Celery     │
│ (IMAP/Gmail/ │    │ & Attachments │    │ to DB      │    │ resume_    │
│  Zoho)       │    │               │    │            │    │ track task │
└──────────────┘    └───────────────┘    └────────────┘    └─────┬──────┘
                                                                  │
                                                                  ▼
                                                          ┌────────────┐
                                                          │ Parse      │
                                                          │ Resume     │
                                                          │ (PDF/DOCX) │
                                                          └─────┬──────┘
                                                                │
                                                                ▼
                                                          ┌────────────┐
                                                          │ LLM        │
                                                          │ Extract    │
                                                          │ (OpenAI/   │
                                                          │ Anthropic/ │
                                                          │ Ollama)    │
                                                          └─────┬──────┘
                                                                │
                                                                ▼
                                                          ┌────────────┐
                                                          │ Store      │
                                                          │ Candidate  │
                                                          │ + Embedding│
                                                          │ (pgvector) │
                                                          └────────────┘
```

**Trigger Methods:**

| Method | API/Process | Description |
|--------|-------------|-------------|
| Manual (all accounts) | `POST /api/admin/extraction/trigger` | Admin manually triggers extraction for all accounts. |
| Manual (single account) | `POST /api/admin/extraction/trigger/{auth_mail_id}` | Admin triggers extraction for a specific account. |
| IMAP direct | `POST /api/fetch_email` | Directly fetch from IMAP mailbox. |
| OAuth (all active) | `POST /emails` | Fetch from all active OAuth-connected accounts (Gmail + Zoho). |
| Scheduled | APScheduler (`scheduler_worker.py`) | Automatic periodic extraction based on `extraction_config` interval. |

---

### 2.5 Resume Search & Filtering Flow

Frontend users search for candidates using either structured filters or natural-language semantic search.

| Step | API Call | Description |
|------|----------|-------------|
| 1 | `GET /api/filter_options` | Load master data for filter dropdowns (roles, education, skills). |
| 2a | `POST /api/filter_resumes` (structured) | Apply field-based filters (skills, experience, education, etc.) with pagination. |
| 2b | `POST /api/filter_resumes` (semantic) | Send a `query` string for vector-similarity search via pgvector. |
| Alt | `POST /api/semantic_search` | Dedicated semantic search endpoint. |

---

### 2.6 Admin Email Account Management Flow

| Step | API Call | Description |
|------|----------|-------------|
| 1 | `POST /api/create_auth_mail` | Register an authorized email for the system. |
| 2 | `GET /api/admin/email-accounts` | View all connected accounts with status. |
| 3 | `PATCH /api/admin/email-accounts/{id}/extraction` | Toggle extraction on/off for an account. |
| 4 | `PATCH /api/admin/email-accounts/{id}/block` | Block/unblock an account. |
| 5 | `PATCH /api/delete_auth_mail/?auth_mail_id=<id>` | Soft-delete an account. |
| 6 | `PATCH /api/update_auth_mail/?auth_mail_id=<id>` | Update account details. |

---

### 2.7 Extraction Schedule Configuration Flow

| Step | API Call | Description |
|------|----------|-------------|
| 1 | `GET /api/admin/extraction/config` | Retrieve current schedule config (interval, pause, time window). |
| 2 | `PUT /api/admin/extraction/config` | Update schedule settings. |
| 3 | `POST /api/admin/extraction/pause` | Globally pause all extraction. |
| 4 | `POST /api/admin/extraction/resume` | Resume extraction. |

---

### 2.8 AI Model Configuration Flow

| Step | API Call | Description |
|------|----------|-------------|
| 1 | `GET /api/list_model/` | List available AI models. |
| 2 | `POST /api/create_model/` | Create a new AI model entry. |
| 3 | `GET /api/list_model_versions/?model_id=<id>` | List versions for a model. |
| 4 | `POST /api/new_model_version/?model_id=<id>` | Create a new model version. |
| 5 | `POST /api/model_config/?admin_id=<id>` | Create a model configuration (links model + version + API key). |
| 6 | `GET /api/get_model_config/?admin_id=<id>` | Retrieve active model config for an admin. |

---

## 3. Endpoint Documentation

### 3.1 Health Check

---

#### `GET /health`

**Description:** Simple health check to verify the API is running.

**Auth Required:** No

**Workflow:** Infrastructure monitoring

**Request:** No parameters.

**Success Response:**

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Status message |

```json
{
  "message": "Resume tracker application running successful"
}
```

**Status Code:** `200 OK`

---

### 3.2 Admin Module

---

#### `POST /api/create_admin`

**Description:** Register a new administrator account.

**Auth Required:** No (public endpoint)

**Workflow:** Admin Authentication Flow (Step 1)

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Admin email address |
| `password` | string | Yes | Plain-text password (hashed via bcrypt before storage) |
| `name` | string | No | Admin display name |

**Example Request:**

```json
{
  "email": "admin@company.com",
  "password": "secureP@ssw0rd",
  "name": "John Admin"
}
```

**Success Response (201):**

```json
{
  "status": 201,
  "message": "Admin created successfully",
  "data": {
    "admin_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "John Admin"
  }
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Email/password missing | `{"status": "error", "message": "Email and password are required"}` |
| 400 | Duplicate email | `{"status": "error", "message": "Admin with this email already exists"}` |

---

#### `POST /api/admin/login`

**Description:** Authenticate admin with email + password and return a JWT.

**Auth Required:** No (public endpoint)

**Workflow:** Admin Authentication Flow (Step 2)

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Admin email address |
| `password` | string | Yes | Plain-text password |

**Example Request:**

```json
{
  "email": "admin@company.com",
  "password": "secureP@ssw0rd"
}
```

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Admin logged in successfully",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "role": "admin",
    "name": "John Admin",
    "email": "admin@company.com"
  }
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 401 | Invalid credentials | `{"status": "error", "message": "Invalid email or password"}` |
| 401 | Missing fields | `{"status": "error", "message": "Email and password must be provided"}` |

---

#### `POST /api/auth/sso/login`

**Description:** Accept an SSO-verified email and return a JWT for the user. The frontend must verify the SSO token with the identity provider first.

**Auth Required:** No (public endpoint)

**Workflow:** User (SSO) Authentication Flow (Step 3)

**Request Body:**

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `email` | string | Yes | Verified email from SSO provider | Must not be empty; auto-lowercased and trimmed |
| `provider` | string | No | SSO provider identifier | Enum: `"google"`, `"zoho"`, `"microsoft"` |

**Example Request:**

```json
{
  "email": "user@company.com",
  "provider": "google"
}
```

**Success Response (200):**

```json
{
  "status": 200,
  "message": "User logged in successfully",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "role": "user",
    "email": "user@company.com",
    "provider": "google"
  }
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 401 | Email not in auth_mail / blocked | `{"status": "error", "message": "Access denied: email not approved or account blocked"}` |
| 401 | Unsupported provider | `{"status": "error", "message": "Unsupported SSO provider: github. Supported providers: google, microsoft, zoho"}` |
| 401 | Empty email | `{"status": "error", "message": "Email must be provided"}` |

---

#### `GET /api/list_auth_mail`

**Description:** List all active authorized email accounts.

**Auth Required:** No (legacy endpoint — not explicitly guarded, but protected by `AllowedEmailMiddleware`)

**Workflow:** Admin Email Account Management

**Request:** No parameters.

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Auth mails retrieved successfully",
  "data": [
    {
      "auth_mail_id": "uuid-string",
      "email_address": "hr@company.com",
      "connect_with": "gmail"
    }
  ]
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | No active records | `{"status": "error", "message": "No auth mails found"}` |

---

#### `POST /api/create_auth_mail`

**Description:** Register a new authorized email account.

**Auth Required:** Protected by `AllowedEmailMiddleware` (requires valid JWT)

**Workflow:** Admin Email Account Management (Step 1)

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Email address to authorize |
| `imap_password` | string | No | IMAP password for direct mailbox access |
| `connect_with` | string | Yes | Connection method identifier (e.g., `"gmail"`, `"zoho"`, `"imap"`) |

**Example Request:**

```json
{
  "email": "hr@company.com",
  "imap_password": "app-specific-password",
  "connect_with": "gmail"
}
```

**Success Response (201):**

```json
{
  "status": 201,
  "message": "Auth mail created successfully",
  "data": {
    "auth_mail_id": "uuid-string",
    "email_address": "hr@company.com",
    "connect_with": "gmail"
  }
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Missing email | `{"status": "error", "message": "Email must be provided"}` |
| 400 | Duplicate | `{"status": "error", "message": "Auth mail with this email already exists"}` |

---

#### `PATCH /api/delete_auth_mail/`

**Description:** Soft-delete an authorized email account (sets `is_active = false`).

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** Admin Email Account Management (Step 5)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `auth_mail_id` | string (UUID) | Yes | UUID of the auth mail to deactivate |

**Example Request:**

```
PATCH /api/delete_auth_mail/?auth_mail_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Auth mail deleted successfully"
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Missing ID | `{"status": "error", "message": "auth_mail_id is required"}` |
| 400 | Not found | `{"status": "error", "message": "Auth mail not found"}` |

---

#### `PATCH /api/update_auth_mail/`

**Description:** Update fields on an existing authorized email account.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** Admin Email Account Management (Step 6)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `auth_mail_id` | string (UUID) | Yes | UUID of the auth mail to update |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | No | New email address |
| `imap_password` | string | No | New IMAP password |
| `connect_with` | dict | No | Updated connection metadata |

**Example Request:**

```
PATCH /api/update_auth_mail/?auth_mail_id=uuid-here
```

```json
{
  "email": "new-hr@company.com"
}
```

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Auth mail updated successfully"
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Missing ID | `{"status": "error", "message": "auth_mail_id is required"}` |
| 400 | Not found | `{"status": "error", "message": "Auth mail not found"}` |
| 400 | Duplicate | `{"status": "error", "message": "Auth mail with this email and IMAP password already exists, nothing to update"}` |

---

### 3.3 Admin-Protected Endpoints (require admin JWT)

All endpoints under `/api/admin/*` require `Authorization: Bearer <admin_jwt>` where the JWT has `role: "admin"`.

---

#### `GET /api/admin/email-accounts`

**Description:** List all connected email accounts with extraction status.

**Auth Required:** Admin JWT

**Workflow:** Admin Email Account Management (Step 2)

**Request:** No parameters.

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Email accounts retrieved",
  "data": [
    {
      "auth_mail_id": "uuid-string",
      "email_address": "hr@company.com",
      "is_active": true,
      "is_blocked": false,
      "extraction_enabled": true,
      "last_extraction_at": "2026-04-09T10:30:00",
      "connect_with": "gmail"
    }
  ]
}
```

---

#### `PATCH /api/admin/email-accounts/{auth_mail_id}/extraction`

**Description:** Enable or disable extraction for a specific email account.

**Auth Required:** Admin JWT

**Workflow:** Admin Email Account Management (Step 3)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `auth_mail_id` | string (UUID) | Target email account ID |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `extraction_enabled` | boolean | Yes | `true` to enable, `false` to disable |

**Example Request:**

```json
{
  "extraction_enabled": false
}
```

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Extraction disabled"
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Account not found | `{"status": "error", "message": "Email account not found"}` |
| 401/403 | Invalid/missing admin token | See [Auth Errors](#auth-error-responses) |

---

#### `PATCH /api/admin/email-accounts/{auth_mail_id}/block`

**Description:** Block or unblock a specific email account. Blocked accounts cannot be used for SSO login or extraction.

**Auth Required:** Admin JWT

**Workflow:** Admin Email Account Management (Step 4)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `auth_mail_id` | string (UUID) | Target email account ID |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `is_blocked` | boolean | Yes | `true` to block, `false` to unblock |

**Example Request:**

```json
{
  "is_blocked": true
}
```

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Account blocked"
}
```

---

#### `GET /api/admin/extraction/config`

**Description:** Retrieve global extraction schedule configuration.

**Auth Required:** Admin JWT

**Workflow:** Extraction Schedule Configuration (Step 1)

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Extraction config retrieved",
  "data": {
    "config_id": "uuid-string",
    "is_paused": false,
    "interval_minutes": 15,
    "window_enabled": true,
    "window_start_time": "09:00",
    "window_end_time": "18:00",
    "window_timezone": "Asia/Kolkata"
  }
}
```

> If no configuration exists, a default one is auto-created with `is_paused=false`, `interval_minutes=15`, `window_enabled=false`.

---

#### `PUT /api/admin/extraction/config`

**Description:** Update extraction schedule settings (interval, pause, time window).

**Auth Required:** Admin JWT

**Workflow:** Extraction Schedule Configuration (Step 2)

**Request Body:**

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `interval_minutes` | integer | No | Polling interval in minutes | Must be >= 1 |
| `is_paused` | boolean | No | Global pause flag | — |
| `window_enabled` | boolean | No | Enable time-window restriction | — |
| `window_start_time` | string | No | Window start (`"HH:MM"` format) | Valid ISO time |
| `window_end_time` | string | No | Window end (`"HH:MM"` format) | Valid ISO time |
| `window_timezone` | string | No | IANA timezone name | Valid timezone (e.g., `"Asia/Kolkata"`) |

**Example Request:**

```json
{
  "interval_minutes": 30,
  "window_enabled": true,
  "window_start_time": "09:00",
  "window_end_time": "18:00",
  "window_timezone": "Asia/Kolkata"
}
```

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Extraction config updated",
  "data": {
    "config_id": "uuid-string",
    "is_paused": false,
    "interval_minutes": 30,
    "window_enabled": true,
    "window_start_time": "09:00",
    "window_end_time": "18:00",
    "window_timezone": "Asia/Kolkata"
  }
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Interval < 1 | `{"status": "error", "message": "Interval must be at least 1 minute"}` |
| 400 | Invalid time format | `{"status": "error", "message": "Invalid isoformat string: '25:00'"}` |

---

#### `POST /api/admin/extraction/pause`

**Description:** Globally pause all extraction jobs.

**Auth Required:** Admin JWT

**Workflow:** Extraction Schedule Configuration (Step 3)

**Request:** No body required.

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Extraction config updated",
  "data": {
    "config_id": "uuid-string",
    "is_paused": true,
    "interval_minutes": 15,
    "window_enabled": false,
    "window_start_time": null,
    "window_end_time": null,
    "window_timezone": "Asia/Kolkata"
  }
}
```

---

#### `POST /api/admin/extraction/resume`

**Description:** Globally resume extraction jobs.

**Auth Required:** Admin JWT

**Workflow:** Extraction Schedule Configuration (Step 4)

**Request:** No body required.

**Success Response (200):** Same structure as pause, with `"is_paused": false`.

---

#### `POST /api/admin/extraction/trigger`

**Description:** Manually trigger extraction for all accounts. Respects time-window unless `force=true`.

**Auth Required:** Admin JWT

**Workflow:** Resume Ingestion Pipeline (Manual trigger)

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `force` | boolean | No | `false` | If `true`, bypass time-window restriction |

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Extraction triggered successfully",
  "data": {
    "message": "Emails processed",
    "last_uid": 42
  }
}
```

**Skipped Response (200 — outside time window):**

```json
{
  "status": 200,
  "message": "Skipping extraction: outside configured time window"
}
```

---

#### `POST /api/admin/extraction/trigger/{auth_mail_id}`

**Description:** Manually trigger extraction for a specific email account.

**Auth Required:** Admin JWT

**Workflow:** Resume Ingestion Pipeline (Manual single-account trigger)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `auth_mail_id` | string (UUID) | Target email account |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `force` | boolean | No | `false` | Bypass time-window |

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Account not found | `{"status": "error", "message": "Email account not found"}` |
| 400 | Account blocked | `{"status": "error", "message": "Account is blocked — cannot trigger extraction"}` |
| 400 | Extraction disabled | `{"status": "error", "message": "Extraction is disabled for this account"}` |

---

### 3.4 AI Model Management

---

#### `GET /api/list_model/`

**Description:** List all active AI models configured in the system.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** AI Model Configuration (Step 1)

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Models retrieved successfully",
  "data": [
    {
      "model_id": "uuid-string",
      "model_name": "OpenAI"
    },
    {
      "model_id": "uuid-string",
      "model_name": "Anthropic"
    }
  ]
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | No models found | `{"status": "error", "message": "No models found"}` |

---

#### `POST /api/create_model/`

**Description:** Create a new AI model entry.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** AI Model Configuration (Step 2)

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_name` | string | Yes | Name of the AI model |

**Example Request:**

```json
{
  "model_name": "OpenAI"
}
```

**Success Response (201):**

```json
{
  "status": 201,
  "message": "Model created successfully",
  "data": {
    "model_id": "uuid-string",
    "model_name": "OpenAI"
  }
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Missing name | `{"status": "error", "message": "Model name must be provided"}` |
| 400 | Duplicate | `{"status": "error", "message": "Model with this name already exists"}` |

---

#### `GET /api/list_model_versions/`

**Description:** List all active versions for a given AI model.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** AI Model Configuration (Step 3)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model_id` | string (UUID) | Yes | AI model UUID |

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Model versions retrieved successfully",
  "data": [
    {
      "model_version_id": "uuid-string",
      "version_name": "gpt-4o"
    },
    {
      "model_version_id": "uuid-string",
      "version_name": "gpt-4-turbo"
    }
  ]
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Model not found | `{"status": "error", "message": "No model found for the given model ID"}` |
| 400 | No versions | `{"status": "error", "message": "No model versions found for the given model ID"}` |

---

#### `POST /api/new_model_version/`

**Description:** Create a new version entry for an AI model.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** AI Model Configuration (Step 4)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model_id` | string (UUID) | Yes | Parent AI model UUID |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version_name` | string | Yes | Version identifier (e.g., `"gpt-4o"`) |

**Example Request:**

```
POST /api/new_model_version/?model_id=uuid-here
```

```json
{
  "version_name": "gpt-4o"
}
```

**Success Response (201):**

```json
{
  "status": 201,
  "message": "Model version created successfully",
  "data": {
    "model_version_id": "uuid-string",
    "version_name": "gpt-4o"
  }
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Model not found | `{"status": "error", "message": "No model found for the given model ID"}` |
| 400 | Missing version name | `{"status": "error", "message": "Version name must be provided"}` |

---

#### `POST /api/model_config/`

**Description:** Create a new AI model configuration linking a model, version, API key, and settings to an admin.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** AI Model Configuration (Step 5)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `admin_id` | string (UUID) | Yes | Admin UUID |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_id` | string (UUID) | Yes | AI model UUID |
| `model_version_id` | string (UUID) | Yes | Model version UUID |
| `apikey` | string | No | API key for the provider |
| `version` | string | No | External version identifier |
| `max_tokens` | integer | No | Maximum token limit |
| `temperature` | float | No | Model temperature |

**Example Request:**

```
POST /api/model_config/?admin_id=admin-uuid
```

```json
{
  "model_id": "model-uuid",
  "model_version_id": "version-uuid",
  "apikey": "sk-...",
  "max_tokens": 4096,
  "temperature": 0.7
}
```

**Success Response (201):**

```json
{
  "status": 201,
  "message": "Model config created successfully",
  "data": {
    "model_config_id": "uuid-string",
    "model_id": "uuid-string",
    "model_name": "OpenAI",
    "model_version_id": "uuid-string",
    "model_version_name": "gpt-4o",
    "admin_id": "uuid-string",
    "apikey": "sk-...",
    "max_tokens": 4096
  }
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Missing admin ID | `{"status": "error", "message": "Admin ID must be provided"}` |
| 400 | Model not found | `{"status": "error", "message": "No model found for the given model ID"}` |
| 400 | Version not found | `{"status": "error", "message": "No model version found for the given model version ID"}` |

---

#### `GET /api/get_model_config/`

**Description:** Retrieve the active AI model configuration for an admin.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** AI Model Configuration (Step 6)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `admin_id` | string (UUID) | Yes | Admin UUID |

**Success Response (200):**

```json
{
  "status": 200,
  "message": "Model config retrieved successfully",
  "data": {
    "model_config_id": "uuid-string",
    "model_id": "uuid-string",
    "model_name": "OpenAI",
    "model_version_id": "uuid-string",
    "model_version_name": "gpt-4o",
    "admin_id": "uuid-string",
    "apikey": "sk-...",
    "max_tokens": 4096,
    "temparature": 0.7
  }
}
```

> **Note:** The field name `temparature` (with typo) is preserved as-is from the database column name. Frontend should use this exact key.

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Missing admin ID | `{"status": "error", "message": "Admin ID must be provided"}` |
| 400 | No config found | `{"status": "error", "message": "No model config found for the given admin ID"}` |

---

### 3.5 OAuth Module

---

#### `GET /oauth/login/gmail`

**Description:** Initiate Gmail OAuth flow. Returns the Google authorization URL for the frontend to redirect the user to.

**Auth Required:** No (open path)

**Workflow:** OAuth Email Account Connection (Gmail Step 1)

**Success Response (200):**

```json
{
  "status": "success",
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&response_type=code&scope=https://www.googleapis.com/auth/gmail.readonly&access_type=offline&prompt=consent"
}
```

**Frontend Action:** Redirect the user to `auth_url`.

---

#### `GET /auth/gmail/callback`

**Description:** Handle Google OAuth callback. Exchanges the authorization code for tokens and stores OAuth credentials.

**Auth Required:** No (callback from Google)

**Workflow:** OAuth Email Account Connection (Gmail Step 3)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | string | Yes | Authorization code from Google |

**Success Response (200):**

```json
{
  "status": "success",
  "email": "user@gmail.com",
  "message": "OAuth connected successfully"
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Failed token exchange | `{"status": "error", "message": "Failed to get access token"}` |
| 400 | Provider error | `{"status": "error", "message": "OAuth provider error"}` |
| 500 | Network error | `{"status": "error", "message": "Network error during OAuth"}` |

---

#### `GET /oauth/login/zoho`

**Description:** Initiate Zoho OAuth flow. Returns the Zoho authorization URL.

**Auth Required:** No (open path)

**Workflow:** OAuth Email Account Connection (Zoho Step 1)

**Success Response (200):**

```json
{
  "status": "success",
  "auth_url": "https://accounts.zoho.in/oauth/v2/auth?scope=ZohoMail.messages.ALL,ZohoMail.accounts.READ,ZohoMail.folders.READ&client_id=...&response_type=code&access_type=offline&prompt=consent&redirect_uri=..."
}
```

---

#### `GET /auth/zoho/callback`

**Description:** Handle Zoho OAuth callback. Exchanges the authorization code for tokens and stores OAuth credentials.

**Auth Required:** No (callback from Zoho)

**Workflow:** OAuth Email Account Connection (Zoho Step 3)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | string | Yes | Authorization code from Zoho |

**Success Response (200):**

```json
{
  "status": "success",
  "email": "user@zoho.com",
  "message": "Zoho OAuth connected successfully"
}
```

---

#### `POST /emails`

**Description:** Fetch emails from all active OAuth-connected accounts (Gmail and Zoho). Iterates through all active `auth_mail` entries, finds their OAuth credentials, and fetches emails using the respective provider API.

**Auth Required:** No (open path)

**Workflow:** Resume Ingestion Pipeline (OAuth trigger)

**Request:** No body required.

**Success Response (200):**

```json
{
  "message": "Email fetching completed",
  "results": [
    {
      "email": "hr@company.com",
      "source": "gmail",
      "status": "success"
    },
    {
      "email": "recruiter@company.com",
      "source": "zoho",
      "status": "success"
    }
  ]
}
```

**No Active Accounts Response (200):**

```json
{
  "message": "No active email accounts found",
  "results": []
}
```

---

### 3.6 Email Reader Module

---

#### `POST /api/fetch_email`

**Description:** Fetch new emails via IMAP and process attachments. Uses environment-configured IMAP credentials. Triggers Celery background task for each email.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** Resume Ingestion Pipeline (IMAP trigger)

**Request:** No body required.

**Success Response (200):**

```json
{
  "status": "success",
  "data": {
    "message": "Emails processed",
    "last_uid": 42
  }
}
```

**First Run Response:**

```json
{
  "status": "success",
  "data": {
    "message": "Initialized last_uid = 42"
  }
}
```

**No New Emails Response:**

```json
{
  "status": "success",
  "data": {
    "message": "No new emails"
  }
}
```

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 500 | IMAP/processing failure | `{"status": "error", "message": "Failed to process emails"}` |

---

### 3.7 Resume Filter Module

---

#### `POST /api/filter_resumes`

**Description:** Filter or search resumes. Supports two modes: **structured filter search** (field-based) and **semantic search** (natural-language vector similarity via pgvector).

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** Resume Search & Filtering

**Query Parameters:**

| Parameter | Type | Required | Default | Description | Validation |
|-----------|------|----------|---------|-------------|------------|
| `page` | integer | No | `1` | Page number | >= 1 |
| `page_size` | integer | No | `20` | Results per page | 1–100 |

**Request Body (Structured Filter):**

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `skills` | string[] (UUIDs) | No | Filter by skill UUIDs | Each must be valid UUID |
| `education` | string[] (UUIDs) | No | Filter by education UUIDs | Each must be valid UUID |
| `roles` | string[] (UUIDs) | No | Filter by role UUIDs | Each must be valid UUID |
| `companies` | string[] | No | Filter by company names | Non-empty strings |
| `name` | string | No | Filter by candidate name | Max 255 chars |
| `file_name` | string | No | Filter by resume filename | Max 255 chars |
| `min_experience` | float | No | Minimum years of experience | 0–50 |
| `max_experience` | float | No | Maximum years of experience | 0–50; must be >= min |
| `passout_start_year` | integer | No | Earliest graduation year | 1950–2100 |
| `passout_end_year` | integer | No | Latest graduation year | 1950–2100; must be >= start |
| `percentage` | float | No | Minimum percentage | 0–100 |
| `sort_by` | string | No | Sort field | Enum: `"name"`, `"total_experience"`, `"created_at"`, `"updated_at"` |
| `sort_order` | string | No | `"asc"` | Enum: `"asc"`, `"desc"` |

**Example Request (Structured):**

```json
{
  "skills": ["uuid-1", "uuid-2"],
  "min_experience": 3,
  "max_experience": 8,
  "sort_by": "total_experience",
  "sort_order": "desc"
}
```

**Request Body (Semantic Search):**

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `query` | string | Yes | Natural language search query | Non-empty, max 1000 chars |
| `limit` / `top_k` | integer | No | Max results to return | 1–50, default 5 |

**Example Request (Semantic):**

```json
{
  "query": "Python developer with FastAPI and machine learning experience",
  "limit": 10
}
```

**Success Response (200) — Structured:**

```json
[
  {
    "candidate_id": "uuid-string",
    "name": "John Doe",
    "email": "john@example.com",
    "phone_number": "1234567890",
    "location": "New York",
    "total_experience": 5,
    "education": [
      {
        "education_id": "uuid-string",
        "education": "B.Tech",
        "institution": "MIT",
        "percentage": 8.5,
        "year_of_passed": 2020
      }
    ],
    "skills": [
      {
        "skill_id": "uuid-string",
        "skill": "Python"
      }
    ],
    "work_experience": [
      {
        "role_id": "uuid-string",
        "role": "Senior Developer",
        "company_name": "TechCorp",
        "company_location": "New York",
        "start_date": "2020-01-15",
        "end_date": null,
        "is_present": true
      }
    ]
  },
  {
    "total_record": 150
  }
]
```

> **Note:** The last element in the structured response array is always `{"total_record": N}` containing the total count for pagination.

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Empty body | `"Request body must be a non-empty JSON object"` |
| 400 | Invalid filters | `{"status": "error", "message": "Invalid filter parameters", "errors": [...]}` |
| 500 | Server error | `{"status": "error", "message": "Failed to filter resumes"}` |

---

#### `POST /api/semantic_search`

**Description:** Dedicated semantic (vector-similarity) search endpoint for resumes.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** Resume Search & Filtering (dedicated semantic)

**Request Body:**

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `query` | string | Yes | Natural language search query | Non-empty, max 1000 chars |
| `top_k` | integer | No | Max results | 1–50, default 5 |

**Example Request:**

```json
{
  "query": "Data scientist with NLP experience",
  "top_k": 5
}
```

**Success Response (200):**

Returns a list of matching candidate objects ranked by embedding similarity.

```json
[
  {
    "candidate_id": "uuid-string",
    "name": "Jane Smith",
    "email": "jane@example.com",
    "total_experience": 4,
    "skills": ["Python", "NLP", "TensorFlow"],
    "education": [...]
  }
]
```

---

#### `GET /api/filter_options`

**Description:** Fetch master data for filter dropdowns — roles, education types, and skills.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** Resume Search & Filtering (Step 1 — populate dropdowns)

**Success Response (200):**

```json
{
  "status": "success",
  "data": {
    "roles": [
      {"id": "uuid-string", "name": "Software Engineer"},
      {"id": "uuid-string", "name": "Data Scientist"}
    ],
    "education": [
      {"id": "uuid-string", "name": "B.Tech"},
      {"id": "uuid-string", "name": "M.Sc"}
    ],
    "skills": [
      {"id": "uuid-string", "name": "Python"},
      {"id": "uuid-string", "name": "React"}
    ]
  }
}
```

---

### 3.8 Candidates Module

---

#### `GET /api/candidates`

**Description:** Retrieve paginated candidate details with education, skills, and work experience.

**Auth Required:** Protected by `AllowedEmailMiddleware`

**Workflow:** Candidate browsing

**Query Parameters:**

| Parameter | Type | Required | Default | Description | Validation |
|-----------|------|----------|---------|-------------|------------|
| `page` | string | No | `"1"` | Page number (converted to int internally) | Must be valid integer |
| `sort_by` | string | No | `"None"` | Sort field | Enum: `"name"`, `"experience"`, `"year"`, `"percentage"`, or `"None"` |
| `sort_type` | string | No | `"None"` | Sort direction | Enum: `"asc"`, `"desc"`, or `"None"` |

> **Note:** Page size is fixed at **10 records per page** (hardcoded).

**Example Request:**

```
GET /api/candidates?page=2&sort_by=experience&sort_type=desc
```

**Success Response (200):**

```json
[
  {
    "candidate_id": "uuid-string",
    "name": "John Doe",
    "email": "john@example.com",
    "phone_number": "9876543210",
    "location": "Bangalore",
    "total_experience": 5,
    "education": [
      {
        "education_id": "uuid-string",
        "education": "B.Tech",
        "institution": "IIT Madras",
        "percentage": 85.5,
        "year_of_passed": 2019
      }
    ],
    "skills": [
      {
        "skill_id": "uuid-string",
        "skill": "Python"
      },
      {
        "skill_id": "uuid-string",
        "skill": "FastAPI"
      }
    ],
    "work_experience": [
      {
        "role_id": "uuid-string",
        "role": "Backend Developer",
        "company_name": "TechCorp",
        "company_location": "Bangalore",
        "start_date": "2019-07-01",
        "end_date": null,
        "is_present": true
      }
    ]
  },
  {
    "total_record": 150
  }
]
```

> **Note:** The last element is always `{"total_record": N}` for pagination metadata.

**Error Responses:**

| Status | Condition | Example |
|--------|-----------|---------|
| 400 | Invalid page | `{"status": "error", "message": "Invalid page number"}` |
| 400 | Invalid sort | `{"status": "error", "message": "Invalid sorting operation"}` |
| 404 | No data | `{"status": "error", "message": "No data found"}` |
| 500 | Server error | `{"status": "error", "message": "Failed to get candidate information"}` |

---

## 4. Data Models / Schemas

### 4.1 Admin

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `admin_id` | UUID | PK, auto-generated | Unique admin identifier |
| `name` | text | nullable | Display name |
| `email_address` | string(255) | nullable | Login email |
| `password` | string(255) | nullable, bcrypt-hashed | Hashed password |
| `phone_number` | string(20) | nullable | Phone number |
| `created_at` | datetime | auto (IST) | Creation timestamp |
| `updated_at` | datetime | auto (IST) | Last update timestamp |
| `is_active` | boolean | default `true` | Soft-delete flag |

### 4.2 AuthMail (Authorized Email Account)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `auth_mail_id` | UUID | PK, auto-generated | Unique identifier |
| `email_address` | string(255) | nullable | Authorized email |
| `imap_password` | string(255) | nullable, column name `password` | IMAP app password |
| `connect_with` | string(255) | nullable, default `""` | Connection method (`"gmail"`, `"zoho"`, `"imap"`) |
| `is_blocked` | boolean | default `false` | Whether account is blocked |
| `extraction_enabled` | boolean | default `true` | Whether extraction is active |
| `last_extraction_at` | datetime | nullable | Timestamp of last extraction |
| `is_active` | boolean | default `true` | Soft-delete flag |

### 4.3 Candidate

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `candidate_id` | UUID | PK, auto-generated | Unique identifier |
| `name` | text | — | Full name |
| `email_address` | string(255) | nullable | Email address |
| `email_from_sender` | boolean | default `false` | Whether email was from sender |
| `phone_number` | string(20) | nullable | Phone number |
| `location` | string(255) | nullable | Location/city |
| `total_experience` | integer | — | Years of experience |
| `is_active` | boolean | default `true` | Soft-delete flag |

### 4.4 Education

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `education_id` | UUID | PK | Unique identifier |
| `education` | string(255) | not null, unique | Degree name (e.g., "B.Tech") |

### 4.5 CandidateEducation (Junction)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `candidate_education_id` | UUID | PK | Unique identifier |
| `candidate_id` | UUID | FK → candidates | Candidate reference |
| `education_id` | UUID | FK → education | Education reference |
| `institution` | string(255) | nullable | Institution name |
| `percentage` | float | — | Grade/percentage |
| `year_of_passed` | integer | — | Graduation year |

### 4.6 Skill

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `skill_id` | UUID | PK | Unique identifier |
| `skill` | string(255) | not null, unique | Skill name (e.g., "Python") |

### 4.7 CandidateSkills (Junction)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `candidate_skills_id` | UUID | PK | Unique identifier |
| `candidate_id` | UUID | FK → candidates | Candidate reference |
| `skill_id` | UUID | FK → skills | Skill reference |

### 4.8 Role

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `role_id` | UUID | PK | Unique identifier |
| `role` | string(255) | not null, unique | Role title |

### 4.9 Company

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `company_id` | UUID | PK | Unique identifier |
| `company_name` | string(255) | not null, unique | Company name |
| `company_location` | string(255) | not null | Company location |

### 4.10 WorkExperience

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `experience_id` | UUID | PK | Unique identifier |
| `candidate_id` | UUID | FK → candidates | Candidate reference |
| `company_id` | UUID | FK → company | Company reference |
| `role_id` | UUID | FK → roles | Role reference |
| `start_date` | date | default today | Employment start date |
| `end_date` | date | nullable | Employment end date (null = current) |

### 4.11 Resume

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `resume_id` | UUID | PK | Unique identifier |
| `embedding` | Vector(384) | pgvector | Sentence-transformer embedding |
| `attachment_id` | UUID | FK → attachments | Source attachment |
| `candidate_id` | UUID | FK → candidates | Linked candidate |

### 4.12 EmailLogs

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `email_id` | UUID | PK | Unique identifier |
| `message_id` | string | — | Provider message ID |
| `uid` | integer | — | IMAP UID |
| `subject` | string | — | Email subject line |
| `sender` | string | — | Sender address |

### 4.13 Attachment

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `attachment_id` | UUID | PK | Unique identifier |
| `email_id` | UUID | FK → email_logs | Parent email |
| `file_name` | string | — | Stored filename |
| `is_resume` | boolean | default `false` | Resume detection flag |

### 4.14 AiModel

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `ai_model_id` | UUID | PK | Unique identifier |
| `model_name` | string(255) | nullable | Model name (e.g., "OpenAI") |
| `is_active` | boolean | default `true` | Active flag |

### 4.15 AiModelVersion

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `ai_model_version_id` | UUID | PK | Unique identifier |
| `ai_model_id` | UUID | FK → ai_models | Parent model |
| `version_name` | string(255) | nullable | Version name (e.g., "gpt-4o") |
| `is_active` | boolean | default `true` | Active flag |

### 4.16 AiModelConfig

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `ai_model_config_id` | UUID | PK | Unique identifier |
| `ai_model_id` | UUID | FK → ai_models | Model reference |
| `ai_model_version_id` | UUID | FK → ai_model_version | Version reference |
| `admin_id` | UUID | FK → admin | Admin who created config |
| `apikey` | string(255) | nullable | Provider API key |
| `version` | string(255) | nullable | External version name |
| `max_tokens` | integer | nullable | Max token limit |
| `temparature` | integer | nullable | Temperature setting |
| `is_active` | boolean | default `true` | Active flag |

> **Note:** The column `temparature` contains a typo (should be "temperature"). This is intentional from the codebase and must be used as-is.

### 4.17 ExtractionConfig

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `config_id` | UUID | PK | Unique identifier |
| `is_paused` | boolean | default `false` | Global pause flag |
| `interval_minutes` | integer | default `15` | Polling interval |
| `window_enabled` | boolean | default `false` | Time-window restriction |
| `window_start_time` | string(5) | nullable | Window start (`"HH:MM"`) |
| `window_end_time` | string(5) | nullable | Window end (`"HH:MM"`) |
| `window_timezone` | string(50) | default `"Asia/Kolkata"` | IANA timezone |

### 4.18 OauthSource

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `source_id` | UUID | PK | Unique identifier |
| `source_name` | string(255) | nullable | Provider name (`"gmail"`, `"zoho"`) |

### 4.19 OauthCredentials

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `credential_id` | UUID | PK | Unique identifier |
| `email` | string | — | User email |
| `access_token` | string | — | OAuth access token |
| `refresh_token` | string | — | OAuth refresh token |
| `expires_in` | integer | — | Token TTL in seconds |
| `source_id` | UUID | FK → oauth_source | Provider reference |
| `last_uid` | integer | — | Last processed UID |

---

## 5. Authentication & Authorization

### Token Format

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Claims

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string (UUID) | Subject — `admin_id` for admins, `auth_mail_id` for users |
| `email` | string | User/admin email address |
| `role` | string | `"admin"` or `"user"` |
| `provider` | string (optional) | SSO provider name (user tokens only) |
| `exp` | integer | Expiration timestamp (UTC) |

### Token Lifecycle

| Property | Value |
|----------|-------|
| Algorithm | HS256 |
| Default Expiry | 60 minutes |
| Secret Key | `JWT_SECRET_KEY` env var |
| Refresh Token | Not implemented — issue a new token via login/SSO |

### Role-Based Access Control (RBAC)

| API Category | Required Role | Enforcement Mechanism |
|--------------|---------------|----------------------|
| `/api/admin/*` endpoints | `admin` | `get_current_admin` dependency (checks JWT `role == "admin"` + active admin in DB) |
| User-facing endpoints (`/api/candidates`, `/api/filter_*`, etc.) | `admin` or `user` | `AllowedEmailMiddleware` (checks JWT email against `auth_mail`) |
| Public endpoints | None | Listed in `OPEN_PATHS` set |

### Open Paths (No Authentication Required)

| Path | Purpose |
|------|---------|
| `/health` | Health check |
| `/docs`, `/redoc`, `/openapi.json` | API documentation |
| `/api/create_admin` | Admin registration |
| `/api/admin/login` | Admin login |
| `/api/auth/sso/login` | User SSO login |
| `/oauth/login/gmail` | Gmail OAuth initiation |
| `/oauth/login/zoho` | Zoho OAuth initiation |
| `/auth/gmail/callback` | Gmail OAuth callback |
| `/auth/zoho/callback` | Zoho OAuth callback |
| `/emails` | OAuth email fetch trigger |

### <a name="auth-error-responses"></a>Auth Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 401 | Missing Authorization header | `{"status": "error", "message": "Authorization header required"}` |
| 401 | Invalid/expired token | `{"status": "error", "message": "Invalid or expired token"}` |
| 401 | Token missing email claim | `{"status": "error", "message": "Token missing email claim"}` |
| 401 | Authentication required (dependency) | `{"status": "error", "message": "Authentication required"}` |
| 403 | Non-admin accessing admin route | `{"status": "error", "message": "Admin access required"}` |
| 403 | Admin not found/deactivated | `{"status": "error", "message": "Admin account not found or deactivated"}` |
| 403 | User not found/blocked | `{"status": "error", "message": "User account not found, blocked, or deactivated"}` |
| 403 | Email not in allowlist | `{"status": "error", "message": "Access denied: email not approved"}` |

### AllowedEmailMiddleware Logic

```
Request received
  ├── Path in OPEN_PATHS? → Pass through
  ├── Path starts with /api/admin? → Pass through (admin deps handle auth)
  ├── No Authorization header? → 401
  ├── Token invalid/expired? → 401
  ├── Token missing email? → 401
  ├── Email not in auth_mail (active + unblocked)? → 403 (unless role=admin)
  └── All checks pass → Forward to route handler
```

---

## 6. Validation Rules

### 6.1 Admin / Auth Schemas

| Schema | Field | Rule |
|--------|-------|------|
| `AdminCreate` | `email` | Required, string |
| `AdminCreate` | `password` | Required, string |
| `AdminCreate` | `name` | Optional, string |
| `AdminLoginRequest` | `email` | Required, string |
| `AdminLoginRequest` | `password` | Required, string |
| `SSOLoginRequest` | `email` | Required, non-empty, auto-lowercased + trimmed |
| `SSOLoginRequest` | `provider` | Optional, enum: `"google"`, `"zoho"`, `"microsoft"` |

### 6.2 Resume Filter Schemas

| Field | Rule |
|-------|------|
| `skills`, `education`, `roles` | Must be list of valid UUID strings |
| `min_experience`, `max_experience` | Numeric, 0–50 range; min <= max |
| `percentage` | Numeric, 0–100 |
| `passout_start_year`, `passout_end_year` | Integer, 1950–2100; start <= end |
| `page` | Integer >= 1 (default 1) |
| `page_size` | Integer 1–100 (default 20) |
| `sort_by` | Enum: `"name"`, `"total_experience"`, `"created_at"`, `"updated_at"` |
| `sort_order` | Enum: `"asc"`, `"desc"` (default `"asc"`) |
| `companies` | List of non-empty strings |
| `name`, `file_name` | String, max 255 characters |

### 6.3 Semantic Search Schema

| Field | Rule |
|-------|------|
| `query` | Required, non-empty string, max 1000 characters |
| `top_k` | Integer 1–50 (default 5) |

### 6.4 Extraction Config

| Field | Rule |
|-------|------|
| `interval_minutes` | Integer >= 1 |
| `window_start_time` | Valid ISO time format (`"HH:MM"`) |
| `window_end_time` | Valid ISO time format (`"HH:MM"`) |
| `window_timezone` | Valid IANA timezone string |

---

## 7. Pagination, Filtering, Sorting

### Resume Filter Pagination

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `page` | int (query param) | 1 | >= 1 | Page number |
| `page_size` | int (query param) | 20 | 1–100 | Results per page |

**Response format:** The response array ends with a metadata object:

```json
[
  { /* candidate 1 */ },
  { /* candidate 2 */ },
  { "total_record": 150 }
]
```

**Calculating total pages:**

```javascript
const totalPages = Math.ceil(totalRecord / pageSize);
```

### Candidate List Pagination

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | string | `"1"` | Page number (string, converted to int) |

Fixed page size of **10 records**. Response uses same trailing `{"total_record": N}` pattern.

### Sorting

**Candidates endpoint (`/api/candidates`):**

| `sort_by` Value | Sorts By |
|-----------------|----------|
| `"name"` | Candidate name alphabetically |
| `"experience"` | Total experience (years) |
| `"year"` | Latest graduation year (excludes SSLC/HSE) |
| `"percentage"` | Highest education percentage |

| `sort_type` Value | Direction |
|-------------------|-----------|
| `"asc"` | Ascending |
| `"desc"` | Descending |

**Resume filter endpoint (`/api/filter_resumes`):**

| `sort_by` Value | Sorts By |
|-----------------|----------|
| `"name"` | Candidate name |
| `"total_experience"` | Years of experience |
| `"created_at"` | Record creation date |
| `"updated_at"` | Record update date |

---

## 8. Error Handling Standard

### Global Error Response Structure

All errors follow one of these structures:

**Standard error (most endpoints):**

```json
{
  "status": "error",
  "message": "Human-readable error description"
}
```

> Returned via `HTTPException(detail={"status": "error", "message": "..."})`.

**Validation error (422 — Pydantic/FastAPI):**

```json
{
  "status": "error",
  "message": "Request validation failed",
  "errors": [
    {
      "field": "body.email",
      "message": "field required",
      "type": "missing"
    }
  ]
}
```

**Internal server error (500 — catch-all):**

```json
{
  "status": "error",
  "message": "Internal server error"
}
```

### HTTP Status Code Usage

| Code | Usage |
|------|-------|
| `200` | Successful GET/POST/PATCH/PUT operations |
| `201` | Resource created (returned in body `status` field, not HTTP code) |
| `400` | Business logic errors (invalid data, not found, duplicates) |
| `401` | Missing or invalid authentication |
| `403` | Insufficient permissions (wrong role, blocked account) |
| `404` | Resource not found (candidate data) |
| `422` | Request body validation failure |
| `500` | Unhandled server errors |

> **Important:** Some endpoints return `status: 201` in the JSON body while the HTTP status code remains `200`. The frontend should check the body `status` field for resource creation confirmation.

---

## 9. Rate Limiting / Throttling

No rate limiting or throttling is currently implemented in the codebase.

> ⚠️ **Inferred behavior – verify with backend team:** Consider implementing rate limits before production deployment, especially on:
> - Login endpoints (`/api/admin/login`, `/api/auth/sso/login`)
> - Extraction trigger endpoints
> - Search endpoints

---

## 10. File Upload / Download

### File Processing (Server-Side Only)

The system processes resume files that arrive via email attachments — there are no direct file upload/download API endpoints exposed to the frontend.

**Supported file formats for resume processing:**

| MIME Type | Extension | Description |
|-----------|-----------|-------------|
| `application/pdf` | `.pdf` | PDF documents |
| `application/msword` | `.doc` | Microsoft Word (legacy) |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `.docx` | Microsoft Word (modern) |

**Storage:** Attachments are saved to the `attachments/` directory (configurable via `ATTACHMENT_DIR` env var). Files are given unique names to avoid collisions.

> There is no frontend-facing file upload or download endpoint. Resume files enter the system exclusively through the email ingestion pipeline.

---

## 11. Background Processing

### Architecture

| Component | Technology | Purpose |
|-----------|------------|---------|
| Task Queue | Celery + Redis | Async resume processing |
| Scheduler | APScheduler (BlockingScheduler) | Periodic email fetching |
| Broker | Redis (port 6379) | Message broker for Celery |

### Celery Task: `resume_track`

**Trigger:** Called automatically after each email is processed (via `resume_track.delay(email_id)`).

**Pipeline:**
1. Parse resume file (PDF/DOCX)
2. Extract structured data using LLM (OpenAI / Anthropic / Ollama based on `AiModelConfig`)
3. Create/update Candidate, Education, Skills, WorkExperience records
4. Generate embedding (384-dim via `all-MiniLM-L6-v2` sentence-transformer)
5. Store embedding in pgvector for semantic search

### Scheduler: `scheduler_worker.py`

**Behavior:**
1. Reads `ExtractionConfig` from the database
2. Runs `fetch_emails()` on the configured `interval_minutes` (default: 15 min)
3. Respects `is_paused` flag — skips cycle if paused
4. Respects time-window settings — skips if outside `[window_start_time, window_end_time)` in the configured timezone
5. Supports cross-midnight windows (e.g., 22:00 → 08:00)

---

## Appendix: Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET_KEY` | JWT signing secret | `"change-me-to-a-strong-random-secret-key"` |
| `JWT_ALGORITHM` | JWT algorithm | `"HS256"` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime in minutes | `60` |
| `GMAIL_AUTH_URL` | Google OAuth auth URL | — |
| `GMAIL_TOKEN_URL` | Google OAuth token URL | — |
| `GMAIL_CLIENT_ID` | Google OAuth client ID | — |
| `GMAIL_CLIENT_SECRET` | Google OAuth client secret | — |
| `GMAIL_REDIRECT_URI` | Google OAuth redirect URI | — |
| `GMAIL_LIST_URL` | Gmail API messages URL | `https://gmail.googleapis.com/gmail/v1/users/me/messages` |
| `ZOHO_CLIENT_ID` | Zoho OAuth client ID | — |
| `ZOHO_CLIENT_SECRET` | Zoho OAuth client secret | — |
| `ZOHO_REDIRECT_URI` | Zoho OAuth redirect URI | — |
| `IMAP_SERVER` | IMAP server hostname | `"imap.gmail.com"` |
| `EMAIL_ACCOUNT` | IMAP login email | `""` |
| `PASSWORD` | IMAP login password | `""` |
| `ATTACHMENT_DIR` | File storage directory | `"attachments"` |
| `REDIS_URL` | Redis connection URL | — |
| `DATABASE_URL` | PostgreSQL connection string | Hardcoded: `postgresql://postgres:2023@db:5432/resume_tracker` |

> ⚠️ `DATABASE_URL` is currently hardcoded in `db/connection.py`. This should be moved to an environment variable for production.

---

## Appendix: Complete Endpoint Reference Table

| # | Method | Path | Auth | Module | Description |
|---|--------|------|------|--------|-------------|
| 1 | GET | `/health` | None | Core | Health check |
| 2 | POST | `/api/create_admin` | None | Admin | Register admin |
| 3 | POST | `/api/admin/login` | None | Admin | Admin login |
| 4 | POST | `/api/auth/sso/login` | None | Admin | User SSO login |
| 5 | GET | `/api/list_auth_mail` | Middleware | Admin | List authorized emails |
| 6 | POST | `/api/create_auth_mail` | Middleware | Admin | Create authorized email |
| 7 | PATCH | `/api/delete_auth_mail/` | Middleware | Admin | Soft-delete authorized email |
| 8 | PATCH | `/api/update_auth_mail/` | Middleware | Admin | Update authorized email |
| 9 | GET | `/api/admin/email-accounts` | Admin JWT | Admin | List email accounts with status |
| 10 | PATCH | `/api/admin/email-accounts/{id}/extraction` | Admin JWT | Admin | Toggle extraction |
| 11 | PATCH | `/api/admin/email-accounts/{id}/block` | Admin JWT | Admin | Toggle block |
| 12 | GET | `/api/admin/extraction/config` | Admin JWT | Admin | Get extraction config |
| 13 | PUT | `/api/admin/extraction/config` | Admin JWT | Admin | Update extraction config |
| 14 | POST | `/api/admin/extraction/pause` | Admin JWT | Admin | Pause extraction |
| 15 | POST | `/api/admin/extraction/resume` | Admin JWT | Admin | Resume extraction |
| 16 | POST | `/api/admin/extraction/trigger` | Admin JWT | Admin | Trigger all extraction |
| 17 | POST | `/api/admin/extraction/trigger/{id}` | Admin JWT | Admin | Trigger single extraction |
| 18 | GET | `/api/list_model/` | Middleware | AI Model | List AI models |
| 19 | POST | `/api/create_model/` | Middleware | AI Model | Create AI model |
| 20 | GET | `/api/list_model_versions/` | Middleware | AI Model | List model versions |
| 21 | POST | `/api/new_model_version/` | Middleware | AI Model | Create model version |
| 22 | POST | `/api/model_config/` | Middleware | AI Model | Create model config |
| 23 | GET | `/api/get_model_config/` | Middleware | AI Model | Get model config |
| 24 | GET | `/oauth/login/gmail` | None | OAuth | Gmail OAuth start |
| 25 | GET | `/auth/gmail/callback` | None | OAuth | Gmail OAuth callback |
| 26 | GET | `/oauth/login/zoho` | None | OAuth | Zoho OAuth start |
| 27 | GET | `/auth/zoho/callback` | None | OAuth | Zoho OAuth callback |
| 28 | POST | `/emails` | None | OAuth | Fetch all OAuth emails |
| 29 | POST | `/api/fetch_email` | Middleware | Email | IMAP email fetch |
| 30 | POST | `/api/filter_resumes` | Middleware | Resume | Filter/search resumes |
| 31 | POST | `/api/semantic_search` | Middleware | Resume | Semantic search |
| 32 | GET | `/api/filter_options` | Middleware | Resume | Filter dropdown data |
| 33 | GET | `/api/candidates` | Middleware | Candidate | List candidates |
