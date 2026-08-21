# Inventory BOS — Backend

A **FastAPI** backend for a computer-accessories inventory & accounts system: purchases, sales, stock batches with FIFO, purchase/sales returns, invoice-wise payments and refunds, a party ledger, and per-invoice report endpoints. Built on async SQLAlchemy + PostgreSQL with cookie-based JWT auth and role-based access control.

![stack](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)
![sqlalchemy](https://img.shields.io/badge/SQLAlchemy%202.x-async-d71f00)

---

## ✨ Features

- 🔐 **HTTP-only cookie auth** — JWT access + refresh tokens; bearer header also accepted
- 🧾 **RBAC** — `super_admin`, `admin`, `store_keeper`, `seller`
- 🧱 **Master data** — categories, brands, products, product variants (SKU/barcode/reorder level)
- 🤝 **Parties** — suppliers, customers, walk-ins, with a **party ledger** and cached running balance (credit/debit sign convention is party-type aware)
- 📦 **Purchases** — draft → receive (creates **batches** + stock-in movements + supplier ledger) → received. Per-invoice `amount_paid` tracking
- ↩️ **Purchase returns** — multi-invoice documents, per-line reasons, restocks the original batch, deducts the invoice's `returned_amount`, credits the supplier ledger
- 🛍️ **Sales** — draft → complete (FIFO batch allocation, stock-out movements) with per-order `amount_paid` / `returned_amount`
- 🔁 **Sales returns** — restock the same batch, per-line reasons, ledger credit for customers or an auto-generated **cash refund Payment** for walk-ins
- 💳 **Payments** — invoice-wise: `PAID_TO_SUPPLIER`, `RECEIVED_FROM_CUSTOMER`, `REFUND_FROM_SUPPLIER`, `REFUND_TO_CUSTOMER`, each tieable to a `purchase_id` / `sale_id` with overpayment/over-refund caps
- 📈 **Stock & audit** — product batches (`qty_remaining`), FIFO query, and a stock-movement audit log
- 📊 **Reports** — `/invoice-ledger` (a single invoice's full statement, or a party's invoice-wise ledger by party id), plus searchable purchase-return / sales-return listing endpoints
- 🧪 **Test suite** — `pytest` against in-memory SQLite
- 🌱 **Seed script** — `seed_catalog.py` populates a computer-accessories catalog idempotently

---

## 🧱 Tech Stack

| Layer     | Technology                                        |
| --------- | ------------------------------------------------- |
| Framework | [FastAPI](https://fastapi.tiangolo.com/)          |
| ORM       | SQLAlchemy 2.x (async)                            |
| Database  | PostgreSQL (`asyncpg` / `psycopg2`)               |
| Validation| Pydantic v2 + `email-validator`                   |
| Auth      | `python-jose` (JWT), `passlib` (password hashing) |
| Testing   | `pytest`, `pytest-asyncio`, `httpx`, `aiosqlite`  |

---

## 📁 Project Structure

```
inventory-bos/
├── app/
│   ├── main.py                    # FastAPI app, CORS + startup table creation
│   ├── api/
│   │   ├── apis.py                # router composition
│   │   ├── deps.py                # auth & role dependency helpers
│   │   └── endpoints/             # auth, users, brand, category, party,
│   │                              # party_ledger_entry, product, product_variant,
│   │                              # product_batch, purchase, purchase_return,
│   │                              # payment, stock_movement, sale, sales_return,
│   │                              # invoice_ledger
│   ├── core/
│   │   ├── config.py              # settings (env vars)
│   │   └── base_model.py          # BaseSkeleton (shared id/name/is_active cols)
│   ├── db/
│   │   ├── base.py                # DeclarativeBase
│   │   └── database.py            # async engine, session, get_db
│   ├── models/                    # SQLAlchemy models per resource
│   ├── schemas/                   # Pydantic request/response schemas
│   ├── services/                  # business logic (purchase, sale, payment,
│   │                              # party_ledger, purchase_return, sales_return...)
│   ├── utils/
│   │   └── security.py            # hashing, JWT, cookie helpers
│   └── scripts/
│       └── create_super_admin.py  # CLI to create the first super admin
├── tests/                         # pytest suite
├── seed_catalog.py                # optional demo-catalog seeder
├── requirements.txt
└── .env                           # env vars (not committed)
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python **3.14+**
- A running **PostgreSQL** instance

### 2. Install dependencies
```bash
uv sync            # recommended
# or
pip install -r requirements.txt
```

### 3. Configure `.env`
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

DEFAULT_RESET_PASSWORD=password12345
```

> Set `COOKIE_SECURE=True` in production (HTTPS).

### 4. Create the first super admin
```bash
python -m app.scripts.create_super_admin
```

### 5. Run the app
```bash
uvicorn app.main:app --reload
```
- Swagger UI: <http://127.0.0.1:8000/docs> · ReDoc: <http://127.0.0.1:8000/redoc>

### 6. (Optional) Seed demo catalog
```bash
python seed_catalog.py
```
Idempotent — creates categories, brands, products and variants for a
computer-accessories catalog. Restartable; reuses existing rows by name/SKU.

---

## 🔑 Authentication & Roles

- `POST /auth/login` sets `access_token` / `refresh_token` **HTTP-only cookies**; protected endpoints also accept `Authorization: Bearer <token>`.
- `POST /auth/refresh` rotates tokens; `POST /auth/logout` clears cookies.

| Role          | Capabilities                                                        |
| ------------- | ------------------------------------------------------------------- |
| `super_admin` | Full access; can create any role except super admin                 |
| `admin`       | Can create `store_keeper` / `seller`; manage users                  |
| `store_keeper`| Can create/receive purchases, build/complete sales, stock mgmt      |
| `seller`      | Read most data, create sales; no master-data or user management     |

---

## 🌐 API Endpoints

| Resource        | Method / Path                                    | Notes |
| --------------- | ------------------------------------------------ | ----- |
| Auth            | `POST /auth/{register,login,refresh,logout}`, `GET /auth/me` | RBAC for register |
| Users           | `GET /users/`, `GET/PUT /users/{id}`, `POST /users/{change,reset}-password` | |
| Categories      | `GET /category/`, `POST /category/create`, `PUT/DELETE /category/{id}` | |
| Brands          | `GET/POST /brands/`, `PUT/DELETE /brands/{id}`    | |
| Products        | `GET/POST /products/`, `GET/PUT /products/{id}`, `PATCH /products/{id}/{activate,deactivate}` | unique `(name, brand, category)` |
| Variants        | `GET /variants/`, `GET /variants/{id}`, `GET /variants/barcode/{barcode}`, `POST /products/{id}/variants`, `PUT /variants/{id}` | list exposes `qty_in_stock` |
| Parties         | `GET/POST /party/`, `GET /party/{id}`, `PUT/PATCH /party/{id}`, `GET /party/{id}/balance`, `GET /party/{id}/ledger` | |
| Party Ledger    | `GET /party-ledger/{party_id}`                    | |
| Purchases       | `GET/POST /purchases/`, `GET/PUT /purchases/{id}`, `POST /purchases/{id}/{receive,cancel}` | list supports `status`, `supplier_id`, `search` |
| Purchase Returns| `GET/POST /purchase-returns/`, `GET /purchase-returns/{id}` | list supports `search` (supplier/return id, name, email, phone) |
| Sales           | `GET/POST /sales/`, `GET/PUT /sales/{id}`, `POST /sales/{id}/{complete,cancel}` | list supports `search` (sale id) |
| Sales Returns   | `GET/POST /sales-returns/`, `GET /sales-returns/{id}` | list supports `search` (customer/return id, name, email, phone) |
| Payments        | `GET/POST /payments/`, `GET /payments/{id}`       | invoice-wise (`purchase_id` / `sale_id`) |
| Batches         | `GET/POST /batches/`, `GET /batches/{id}`, `GET /batches/variant/{id}/fifo`, `PATCH /batches/{id}/expiry` | FIFO allocation |
| Stock Movements | `GET /stock-movements/`, `GET /stock-movements/{id}` | audit log |
| Invoice Ledger  | `GET /invoice-ledger?invoice_number=...`          | invoice statement **or** party's invoice-wise ledger (party id, name, email, phone) |

---

## 🧮 Key Business Rules

- **Inventory cycle** — Purchase receive puts stock into a **batch** (`qty_remaining` ↑); sales consume it FIFO (↓); a sales return puts it back **into the same batch** (↑); a purchase return takes it back out (↓) and credits the supplier. Only lines with `qty_remaining > 0` are returnable to a supplier.
- **Per-invoice money tracking** — `purchase.amount_paid` / `purchase.returned_amount` and `sale.amount_paid` / `sale.returned_amount` are maintained in-transaction by the payment & return services, so `due = total − paid − returned` holds invoice-by-invoice (negative = a credit).
- **Ledger sign convention** — SUPPLIER: `credit` ↑ what you owe, `debit` ↓. CUSTOMER: `debit` ↑ what they owe, `credit` ↓ (see `app/services/party_ledger.py`). `balance_cached` is updated in the same transaction.
- **Payments / refunds** — `PAID_TO_SUPPLIER` / `REFUND_FROM_SUPPLIER` tie to `purchase_id`; `RECEIVED_FROM_CUSTOMER` / `REFUND_TO_CUSTOMER` tie to `sale_id`. Both directions enforce overpayment/over-refund caps.

> **Schema changes on an existing DB** — startup only creates **new** tables (`Base.metadata.create_all`); it does **not** alter existing ones. Column/constraint changes (e.g. adding `reason` to a return line) require a manual `ALTER TABLE` (see the git history / seed script for examples).

---

## 🧪 Running Tests
```bash
uv run pytest -v     # or: python -m pytest -v
```
Runs against in-memory SQLite — no PostgreSQL needed. Covers security helpers, auth service/API, and user RBAC (`401/403/404`).