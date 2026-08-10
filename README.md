# Inventory BOS

A **FastAPI** backend providing cookie-based authentication (JWT access + refresh tokens), role-based access control (RBAC), and user management. It is the foundation for a future inventory-management system built on async SQLAlchemy + PostgreSQL.

---

## ✨ Features

- 🔐 **HTTP-only cookie authentication** with JWT access & refresh tokens
- 🧾 **Role-based authorization** — `super_admin`, `admin`, `store_keeper`, `seller`
- 👤 **User management** — create, list, update, password change/reset
- 🗄️ **Async SQLAlchemy** with automatic table creation on startup
- 🔒 **API rate limiting** (`slowapi`) on auth endpoints
- 🧪 **Test suite** using `pytest` against an in-memory SQLite database

---

## 🧱 Tech Stack

| Layer     | Technology                                          |
| --------- | --------------------------------------------------- |
| Framework | [FastAPI](https://fastapi.tiangolo.com/)            |
| ORM       | SQLAlchemy 2.x (async)                              |
| Database  | PostgreSQL (`asyncpg` / `psycopg2`)                 |
| Validation| Pydantic v2 + `email-validator`                     |
| Auth      | `python-jose` (JWT), `passlib` (password hashing)   |
| Rate limit| `slowapi` (per-client-IP limits)                    |
| Testing   | `pytest`, `pytest-asyncio`, `httpx`, `aiosqlite`    |

---

## 📁 Project Structure

```
inventory-bos/
├── app/
│   ├── main.py                 # FastAPI app setup & startup/shutdown lifecycle
│   ├── api/
│   │   ├── apis.py             # Router composition
│   │   ├── deps.py             # Auth & role dependency helpers
│   │   └── endpoints/
│   │       ├── auth.py         # /auth endpoints
│   │       └── users.py        # /users endpoints
│   ├── core/
│   │   ├── config.py           # App settings (env vars)
│   │   └── limiter.py          # slowapi rate-limiter instance
│   ├── db/
│   │   ├── base.py             # SQLAlchemy DeclarativeBase
│   │   └── database.py         # Async engine, session, get_db dependency
│   ├── models/
│   │   └── user.py             # User model + Role enum
│   ├── schemas/
│   │   └── auth.py             # Request/response Pydantic schemas
│   ├── services/
│   │   └── auth.py             # Business logic (create/auth users)
│   ├── utils/
│   │   └── security.py         # Hashing, JWT, cookie helpers
│   └── scripts/
│       └── create_super_admin.py  # CLI to create the first super admin
├── tests/                      # pytest suite (unit + API integration)
├── requirements.txt
└── .env                        # Environment variables (not committed)
```

---

## 🚀 Getting Started

### 1. Prerequisites

- Python **3.14+**
- A running **PostgreSQL** instance

### 2. Install dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root (or export the variables):

```ini
# Database
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/inventory_bos
ASYNC_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/inventory_bos

# JWT
SECRET_KEY=change-me-to-a-long-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Cookies
COOKIE_SECURE=False
COOKIE_SAMESITE=lax
COOKIE_DOMAIN=
ACCESS_COOKIE_NAME=access_token
REFRESH_COOKIE_NAME=refresh_token

# Default password used when resetting user passwords
DEFAULT_RESET_PASSWORD=P@ssw0rd12345
```

> Setting `COOKIE_SECURE=True` is required in production when serving over HTTPS.

### 4. Create the first super admin

The app authenticates `admin`/`super_admin` roles to manage users, so the very
first account is created via the CLI script:

```bash
python -m app.scripts.create_super_admin
```

### 5. Run the app

```bash
uvicorn app.main:app --reload
```

- API docs (Swagger UI): <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- Root: <http://127.0.0.1:8000/>

---

## 🔑 Authentication Model

- Successful `POST /auth/login` sets two **HTTP-only cookies**:
  - `access_token` → scoped to `/`, short-lived (15 min by default)
  - `refresh_token` → scoped to `/auth/refresh`, long-lived (7 days by default)
- Protected endpoints accept either the cookie or a `Authorization: Bearer <token>` header.
- `POST /auth/refresh` exchanges a valid refresh token for a new access token.
- `POST /auth/logout` clears both cookies.

### Roles

| Role          | Value          | Capabilities                                             |
| ------------- | -------------- | -------------------------------------------------------- |
| `super_admin` | `super_admin`  | Full access; can create any role **except** super admin  |
| `admin`       | `admin`        | Can create `store_keeper` / `seller`; manage users       |
| `store_keeper`| `store_keeper` | Standard user                                           |
| `seller`      | `seller`       | Standard user (default role)                            |

---

## 🌐 API Endpoints

### Authentication (`/auth`)

| Method | Path               | Auth                        | Description                                                            |
| ------ | ------------------ | --------------------------- | ---------------------------------------------------------------------- |
| POST   | `/auth/register`   | `admin` / `super_admin`     | Create a new user (role restrictions apply)                            |
| POST   | `/auth/login`      | –                           | Authenticate and set auth cookies                                      |
| POST   | `/auth/refresh`    | –                           | Issue a new access token from the refresh cookie                       |
| POST   | `/auth/logout`     | –                           | Clear authentication cookies                                           |
| GET    | `/auth/me`         | any authenticated user      | Return the currently authenticated user                                |

### Users (`/users`)

| Method | Path                        | Auth                 | Description                                                          |
| ------ | --------------------------- | -------------------- | -------------------------------------------------------------------- |
| GET    | `/users/?skip=0&limit=20`   | `admin` / `super_admin` | List users (paginated → `{total, skip, limit, items}`) |
| GET    | `/users/{user_id}`          | `admin` / `super_admin` | Get a user by ID                                                   |
| PUT    | `/users/{user_id}`          | `admin` / `super_admin` | Update a user (no self-edit; admin can't edit other admins)        |
| POST   | `/users/change-password`    | any authenticated user | Change own password (body: `email`, `old_password`, `new_password`) |
| POST   | `/users/reset-password`     | `admin` / `super_admin` | Reset a user's password to `DEFAULT_RESET_PASSWORD` (query `email`) |

> **Note:** `POST /auth/register` requires an authenticated `admin` or `super_admin`.
> Use the `create_super_admin` script to bootstrap the first account.

---

## 🔒 Rate Limiting

Auth endpoints are protected by `slowapi`, keyed by client IP address. When a
limit is exceeded the API responds with `429 Rate Limit Exceeded`.

| Endpoint       | Limit      |
| -------------- | ---------- |
| `POST /auth/register`  | `10 / hour` |
| `POST /auth/login`     | `5 / minute` |
| `POST /auth/refresh`   | `20 / minute` |

### Password strength

`register` and `change-password` enforce strong passwords:

- At least **8 characters**
- At least one **uppercase** letter
- At least one **lowercase** letter
- At least one **number**
- At least one **special character** (e.g. `!@#$%^&*`)

---

## 🧪 Running Tests

The test suite runs against an in-memory SQLite database, so **no PostgreSQL is required**:

```bash
# From the project root (inventory-bos)
uv run pytest -v

# or
python -m pytest -v
```

What is covered:

- `tests/test_security.py` — password hashing, JWT encode/decode (valid, tampered, expired), cookie helpers
- `tests/test_services_auth.py` — service-layer logic and role rules
- `tests/test_api_auth.py` — `/auth` endpoints via the FastAPI test client
- `tests/test_api_users.py` — `/users` endpoints + RBAC (401 / 403 / 404 paths)

---

## 🛠️ Troubleshooting

- **Pydantic validation error on startup (missing fields)** — the app reads `.env`
  from the current working directory. Start it from the `inventory-bos` folder or
  ensure the variables are exported in your environment.

---

## 📌 Notes

- Tables are created automatically on startup via SQLAlchemy metadata
  (`Base.metadata.create_all`).
- The project currently focuses on **authentication and user management**;
  inventory-specific features will be layered on top of this foundation.


