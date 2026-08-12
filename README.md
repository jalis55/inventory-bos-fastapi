# Inventory BOS

A **FastAPI** backend for an **inventory management system**: cookie-based
authentication (JWT access + refresh tokens), role-based access control (RBAC),
user management, and full CRUD for companies, categories, products, product
variants, customers, suppliers and batches. Stock is tracked through an
**immutable, append-only stock-movement ledger** (bank-statement style).
Built on async SQLAlchemy + PostgreSQL.

---

## ✨ Features

- 🔐 **HTTP-only cookie authentication** with JWT access & refresh tokens
- 🧾 **Role-based authorization** — `super_admin`, `admin`, `store_keeper`, `seller`
- 👤 **User management** — create, list, update, password change/reset
- 🏷️ **Inventory master data** — companies, categories, products & product variants (paginated CRUD)
- 🤝 **Customers & suppliers** — paginated CRUD for both
- 📦 **Batches** — received stock per product/supplier lot, with auto-calculated quantities
- 📒 **Immutable stock-movement ledger** — every `in`/`out`/`adjustment` is a permanent, append-only entry with `prev_quantity` → `current_quantity` audit trail (bank-statement semantics; corrections are reversing entries, never edits)
- 🚫 **Account lockout** after repeated failed logins (`MAX_LOGIN_ATTEMPTS`, `LOCKOUT_DURATION_MINUTES`)
- 🗄️ **Async SQLAlchemy** with automatic table creation on startup + Alembic migrations
- 🔒 **API rate limiting** (`slowapi`) on auth and password endpoints
- 🧪 **Test suite** using `pytest` against an in-memory SQLite database

---

## 🧱 Tech Stack

| Layer     | Technology                                                       |
| --------- | ---------------------------------------------------------------- |
| Framework | [FastAPI](https://fastapi.tiangolo.com/)                         |
| ORM       | SQLAlchemy 2.x (async)                                           |
| Database  | PostgreSQL (`asyncpg` / `psycopg2`), SQLite in tests             |
| Validation| Pydantic v2 + `email-validator`                                  |
| Auth      | `python-jose` (JWT), `passlib` (password hashing)                |
| Rate limit| `slowapi` (per-client-IP limits)                                 |
| Migrations| Alembic                                                          |
| Testing   | `pytest`, `pytest-asyncio`, `httpx`, `aiosqlite`                 |

---

## 📁 Project Structure

```
inventory-bos/
├── app/
│   ├── main.py                 # FastAPI app setup & startup/shutdown lifecycle
│   ├── api/
│   │   ├── apis.py             # Router composition
│   │   ├── deps.py             # Auth & role dependency helpers (get_current_user, require_roles)
│   │   └── endpoints/
│   │       ├── auth.py         # /auth endpoints
│   │       ├── users.py        # /users endpoints
│   │       ├── category.py     # /categories endpoints
│   │       ├── company.py      # /companies endpoints
│   │       ├── product.py      # /products endpoints
│   │       ├── product_variant.py  # /product-variants endpoints
│   │       ├── customer.py     # /customers endpoints
│   │       ├── supplier.py     # /suppliers endpoints
│   │       ├── batch.py        # /batches endpoints
│   │       └── stock_movement.py   # /stock-movements endpoints (ledger)
│   ├── core/
│   │   ├── config.py           # App settings (env vars)
│   │   └── limiter.py          # slowapi rate-limiter instance
│   ├── db/
│   │   ├── base.py             # SQLAlchemy DeclarativeBase
│   │   └── database.py         # Async engine, session, get_db dependency
│   ├── models/
│   │   ├── user.py             # User model + Role enum
│   │   ├── category.py         # Category model
│   │   ├── company.py          # Company model
│   │   ├── product.py          # Product model (FK → company/category/variant)
│   │   ├── product_variant.py  # ProductVariant model
│   │   ├── customer.py         # Customer model + CustomerType enum
│   │   ├── supplier.py         # Supplier model
│   │   ├── batch.py            # Batch model (FK → product/supplier/user)
│   │   └── stock_movement.py   # StockMovement model + MovementType (immutable ledger)
│   ├── schemas/
│   │   ├── auth.py             # User/auth Pydantic schemas
│   │   ├── category.py         # Category schemas
│   │   ├── company.py          # Company schemas
│   │   ├── product.py          # Product schemas
│   │   ├── product_variant.py  # Product variant schemas
│   │   ├── customer.py         # Customer schemas
│   │   ├── supplier.py         # Supplier schemas
│   │   ├── batch.py            # Batch schemas
│   │   └── stock_movement.py   # Stock movement schemas
│   ├── services/
│   │   └── auth.py             # Business logic (create/auth users)
│   ├── utils/
│   │   └── security.py         # Hashing, JWT, cookie helpers
│   └── scripts/
│       └── create_super_admin.py  # CLI to create the first super admin
├── migrations/                 # Alembic migrations
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

> Run these commands from the `inventory-bos` folder where the app lives.

### 3. Configure environment variables

Create a `.env` file in the project root (`inventory-bos/.env`) or export the
variables:

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

# Login hardening
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=15
```

> Setting `COOKIE_SECURE=True` is required in production when serving over HTTPS.

### 4. Create the first super admin

The app restricts user management to `admin` / `super_admin`, so the very first
account is created via the CLI script:

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
- Protected endpoints accept either the cookie or an
  `Authorization: Bearer <token>` header.
- `POST /auth/refresh` exchanges a valid refresh token for a new access token.
- `POST /auth/logout` clears both cookies.
- After `MAX_LOGIN_ATTEMPTS` (default 5) failed logins the account is locked for
  `LOCKOUT_DURATION_MINUTES` (default 15) minutes.

### Roles

| Role          | Value          | Capabilities                                             |
| ------------- | -------------- | -------------------------------------------------------- |
| `super_admin` | `super_admin`  | Full access; can create any role **except** super admin  |
| `admin`       | `admin`        | Can create `store_keeper` / `seller`; manage users       |
| `store_keeper`| `store_keeper` | Standard user                                            |
| `seller`      | `seller`       | Standard user (default role)                             |

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

| Method | Path                        | Auth                        | Description                                                       |
| ------ | --------------------------- | --------------------------- | ----------------------------------------------------------------- |
| GET    | `/users/?skip=0&limit=20`   | `admin` / `super_admin`     | List users (paginated → `{total, skip, limit, items}`)            |
| GET    | `/users/{user_id}`          | `admin` / `super_admin`     | Get a user by ID                                                  |
| PUT    | `/users/{user_id}`          | `admin` / `super_admin`     | Update a user (no self-edit; admin can't edit other admins)       |
| POST   | `/users/change-password`    | any authenticated user      | Change own password (body: `email`, `old_password`, `new_password`) |
| POST   | `/users/reset-password`     | `admin` / `super_admin`     | Reset a user's password to `DEFAULT_RESET_PASSWORD` (query `email`) |

> **Note:** `POST /auth/register` requires an authenticated `admin` or `super_admin`.
> Use the `create_super_admin` script to bootstrap the first account.

---
### Categories (`/categories`)

| Method | Path                 | Auth                    | Description                                 |
| ------ | -------------------- | ----------------------- | ------------------------------------------- |
| GET    | `/categories/`       | any authenticated user  | List categories (paginated, `skip`/`limit`) |
| GET    | `/categories/{id}`   | any authenticated user  | Get a category by ID                        |
| POST   | `/categories/`       | `admin` / `super_admin` | Create a category (`name`)                  |
| PUT    | `/categories/{id}`   | `admin` / `super_admin` | Update `name` / `is_active`                 |
| DELETE | `/categories/{id}`   | `admin` / `super_admin` | Delete a category                           |

### Companies (`/companies`)

| Method | Path                | Auth                    | Description                                 |
| ------ | ------------------- | ----------------------- | ------------------------------------------- |
| GET    | `/companies/`       | any authenticated user  | List companies (paginated, `skip`/`limit`)  |
| GET    | `/companies/{id}`   | any authenticated user  | Get a company by ID                         |
| POST   | `/companies/`       | `admin` / `super_admin` | Create a company (`name`) — returns `201`   |
| PUT    | `/companies/{id}`   | `admin` / `super_admin` | Update `name` / `is_active`                 |
| DELETE | `/companies/{id}`   | `admin` / `super_admin` | Delete a company                            |

### Products (`/products`)

Products reference an existing `company`, `category` and `product variant`.

| Method | Path                | Auth                    | Description                                                                 |
| ------ | ------------------- | ----------------------- | --------------------------------------------------------------------------- |
| GET    | `/products/`        | any authenticated user  | List products (paginated) with nested `company` / `category` / `variant`    |
| GET    | `/products/{id}`    | any authenticated user  | Get a product with its nested relations                                     |
| POST   | `/products/`        | `admin` / `super_admin` | Create a product (`name`, `company_id`, `category_id`, `product_variant_id`, `unit_of_measure`) — returns `201` |
| PUT    | `/products/{id}`    | `admin` / `super_admin` | Update product fields                                                       |
| DELETE | `/products/{id}`    | `admin` / `super_admin` | Delete a product                                                            |

### Product Variants (`/product-variants`)

| Method | Path                       | Auth                    | Description                                  |
| ------ | -------------------------- | ----------------------- | -------------------------------------------- |
| GET    | `/product-variants/`       | any authenticated user  | List product variants (paginated)            |
| GET    | `/product-variants/{id}`   | any authenticated user  | Get a product variant by ID                  |
| POST   | `/product-variants/`       | `admin` / `super_admin` | Create a product variant (`name`) — returns `201` |
| PUT    | `/product-variants/{id}`   | `admin` / `super_admin` | Update `name` / `is_active`                  |
| DELETE | `/product-variants/{id}`   | `admin` / `super_admin` | Delete a product variant                     |

### Customers (`/customers`)

| Method | Path                  | Auth                    | Description                                                            |
| ------ | --------------------- | ----------------------- | ---------------------------------------------------------------------- |
| GET    | `/customers/`         | any authenticated user  | List customers (paginated)                                             |
| GET    | `/customers/{id}`     | any authenticated user  | Get a customer by ID                                                   |
| POST   | `/customers/`         | `admin` / `super_admin` | Create a customer (`name`, `phone`, `email?`, `nid?`, `customer_type`) — returns `201` |
| PUT    | `/customers/{id}`     | `admin` / `super_admin` | Update customer fields                                                 |
| DELETE | `/customers/{id}`     | `admin` / `super_admin` | Delete a customer                                                      |

### Suppliers (`/suppliers`)

| Method | Path                  | Auth                    | Description                                                            |
| ------ | --------------------- | ----------------------- | ---------------------------------------------------------------------- |
| GET    | `/suppliers/`         | any authenticated user  | List suppliers (paginated)                                             |
| GET    | `/suppliers/{id}`     | any authenticated user  | Get a supplier by ID                                                   |
| POST   | `/suppliers/`         | `admin` / `super_admin` | Create a supplier (`name`, `phone`, `email?`) — returns `201`          |
| PUT    | `/suppliers/{id}`     | `admin` / `super_admin` | Update supplier fields                                                 |
| DELETE | `/suppliers/{id}`     | `admin` / `super_admin` | Delete a supplier                                                      |

### Batches (`/batches`)

Batches record received stock for a specific product + supplier lot.

| Method | Path              | Auth                    | Description                                                                       |
| ------ | ----------------- | ----------------------- | --------------------------------------------------------------------------------- |
| GET    | `/batches/`        | any authenticated user  | List batches (paginated) with nested `product` / `supplier` / `user`              |
| GET    | `/batches/{id}`    | any authenticated user  | Get a batch with its nested relations                                             |
| POST   | `/batches/`        | `admin` / `super_admin` | Create a batch (`product_id`, `supplier_id`, packaging & pricing fields) — returns `201`; **also writes the origin `IN` ledger entry** |
| PUT    | `/batches/{id}`    | `admin` / `super_admin` | Update batch fields                                                               |
| DELETE | `/batches/{id}`    | `admin` / `super_admin` | Delete a batch                                                                    |

### Stock Movements (`/stock-movements`) — immutable ledger

Movements are **append-only**: you can create them and read them, but they can
never be edited or deleted. Creating a movement atomically adjusts the parent
batch balance (`Batch.quantity`); an `OUT`/`ADJUSTMENT` that would drive the
balance below zero is rejected with `400`.

| Method | Path                          | Auth                                       | Description                                                                              |
| ------ | ----------------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------- |
| POST   | `/stock-movements/`           | `super_admin` / `admin` / `store_keeper`   | Record a movement (`batch_id`, `movement_type`, `quantity`, `reference?`, `supplier_id?`, `customer_id?`, `reverses_id?`) — returns `201` |
| GET    | `/stock-movements/`           | any authenticated user                     | List movements (paginated, optional `?batch_id=`)                                        |
| GET    | `/stock-movements/{id}`       | any authenticated user                     | Get a movement by ID                                                                     |

**Semantics**

- `movement_type = in` → balance **increases**; `out` / `adjustment` → **decreases**.
- Each row stores `prev_quantity` (balance before) and `current_quantity`
  (balance after), so the ledger is self-verifying:
  `prev_quantity ± quantity == current_quantity`.
- To correct a mistaken entry, **append a reversing entry** (set `reverses_id`
  to the original movement's ID) rather than editing it — bank-statement style.

---

## 🔒 Rate Limiting

Auth and password endpoints are protected by `slowapi`, keyed by client IP
address. When a limit is exceeded the API responds with `429 Rate Limit Exceeded`.

| Endpoint                       | Limit         |
| ------------------------------ | ------------- |
| `POST /auth/register`          | `10 / hour`   |
| `POST /auth/login`             | `5 / minute`  |
| `POST /auth/refresh`           | `20 / minute` |
| `POST /users/change-password`  | `10 / minute` |
| `POST /users/reset-password`   | `10 / minute` |

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
# From the `inventory-bos` folder
uv run pytest -v

# or
python -m pytest -v
```

Current coverage — **215 tests** across 11 files:

- `tests/test_security.py` — password hashing, JWT encode/decode (valid, tampered, expired), cookie helpers
- `tests/test_services_auth.py` — service-layer logic and role rules
- `tests/test_api_auth.py` — `/auth` endpoints via the FastAPI test client
- `tests/test_api_users.py` — `/users` endpoints + RBAC (401 / 403 / 404 paths)
- `tests/test_api_category.py` — `/categories` endpoints + RBAC
- `tests/test_api_company.py` — `/companies` endpoints + RBAC
- `tests/test_api_product.py` — `/products` endpoints + RBAC + nested relations
- `tests/test_api_product_variant.py` — `/product-variants` endpoints + RBAC
- `tests/test_api_customer.py` — `/customers` endpoints + RBAC
- `tests/test_api_supplier.py` — `/suppliers` endpoints + RBAC
- `tests/test_api_stock_movement.py` — `/stock-movements` ledger: create in/out, overdraw rejection, reversal, immutability (405 on PUT/DELETE), RBAC

---

## 🛠️ Troubleshooting

- **Pydantic validation error on startup (missing fields)** — the app reads `.env`
  from the current working directory. Start it from the `inventory-bos` folder or
  ensure the variables are exported in your environment.

---

## 📌 Notes

- Tables are created automatically on startup via SQLAlchemy metadata
  (`Base.metadata.create_all`); Alembic migrations are included under `migrations/`.
- All list endpoints return paginated responses shaped as
  `{total, skip, limit, items}`.
- When a record references another table (e.g. a product → `company` /
  `category` / `product variant`, a batch → `product` / `supplier`, or a stock
  movement → `batch`), the referenced rows must already exist — the API relies
  on database foreign keys for that integrity (create the master data first,
  then the dependent record).
- Stock balance is derived from the `stock_movements` ledger: each batch
  creation writes an origin `IN` entry, and later `in`/`out`/`adjustment`
  movements update the batch balance. Never delete or edit a movement — append
  a reversing entry instead (see Stock Movements above).

