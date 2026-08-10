# Inventory BOS

A FastAPI-based backend for a cookie-based authentication system with JWT access and refresh tokens, role-based authorization, and basic user management.

## Overview

This app provides:
- User registration and login
- HTTP-only cookie authentication
- Access and refresh token support
- Role-based authorization (`superadmin`, `admin`, `editor`)
- User listing and retrieval endpoints
- Async SQLAlchemy database initialization on startup

## Tech Stack

- Python
- FastAPI
- SQLAlchemy (async)
- Pydantic
- PostgreSQL (`asyncpg` / `psycopg2`)
- `python-jose` for JWT handling
- `passlib` for password hashing

## Project Structure

- `app/main.py` - FastAPI app setup and lifecycle management
- `app/api/apis.py` - API router composition
- `app/api/deps.py` - authentication and role dependency helpers
- `app/api/endpoints/auth.py` - registration, login, refresh, logout, and current user
- `app/api/endpoints/users.py` - user listing and detail endpoints
- `app/core/config.py` - settings loaded from environment variables
- `app/db/base.py` - SQLAlchemy `DeclarativeBase` used by all models
- `app/db/database.py` - async database engine and session setup
- `app/models/user.py` - SQLAlchemy user model
- `app/schemas/auth.py` - request/response schemas for auth and user data
- `app/services/auth.py` - user creation and authentication logic
- `app/utils/security.py` - password hashing, JWT creation/validation, cookie helpers

## Requirements

Dependencies are listed in `app/requirements.txt`.

## Environment Variables

The app uses `pydantic-settings` and expects environment variables in a `.env` file or environment.

Required variables:
- `DATABASE_URL`
- `ASYNC_DATABASE_URL`
- `SECRET_KEY`

Optional variables with defaults:
- `ALGORITHM` (default: `HS256`)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default: `15`)
- `REFRESH_TOKEN_EXPIRE_DAYS` (default: `7`)
- `COOKIE_SECURE` (default: `False`)
- `COOKIE_SAMESITE` (default: `lax`)
- `COOKIE_DOMAIN` (default: `None`)
- `ACCESS_COOKIE_NAME` (default: `access_token`)
- `REFRESH_COOKIE_NAME` (default: `refresh_token`)

## Running the App

Install dependencies:

```bash
uv add -r app/requirements.txt
```

Start the application:

```bash
uvicorn app.main:app --reload
```

The root endpoint is available at `http://127.0.0.1:8000/`.

## API Endpoints

### Authentication

- `POST /auth/register`
  - Register a new user
  - The first user created when the database is empty becomes `superadmin`
  - Subsequent registrations require an authenticated `superadmin`

- `POST /auth/login`
  - Login with email and password
  - Sets `access_token` and `refresh_token` HTTP-only cookies

- `POST /auth/refresh`
  - Refresh the access token using the refresh cookie

- `POST /auth/logout`
  - Clear authentication cookies

- `GET /auth/me`
  - Return the current authenticated user

### Users

- `GET /users/`
  - List all users
  - Requires `admin` or `superadmin`

- `GET /users/{user_id}`
  - Get user details by ID
  - Requires `admin` or `superadmin`

## Authentication Flow

- Access tokens are stored in an HTTP-only cookie named by `ACCESS_COOKIE_NAME`.
- Refresh tokens are stored in an HTTP-only cookie named by `REFRESH_COOKIE_NAME` and scoped to `/auth/refresh`.
- The app verifies either the cookie or a Bearer token for protected endpoints.

## Notes

- On startup, the app creates database tables automatically using SQLAlchemy metadata.
- The app is currently focused on authentication and user management rather than inventory-specific features.
