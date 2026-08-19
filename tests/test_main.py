"""
Tests for the FastAPI application itself: metadata, routing and middleware.
"""
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.main import app

REQUIRED_PATHS = [
    "/",
    "/auth/register",
    "/auth/login",
    "/auth/refresh",
    "/auth/logout",
    "/auth/me",
    "/users/",
    "/users/change-password",
    "/users/reset-password",
    "/brands/",
    "/category/",
]


@pytest.mark.asyncio
async def test_root_endpoint(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"message": "FastAPI Cookie Auth is running"}


def test_app_metadata():
    assert app.title == "Inventory Management System"
    assert app.version == "1.0.0"
    assert isinstance(app, FastAPI)


def test_all_routers_registered():
    # app.openapi() flattens every included router into a {path: {...}} mapping,
    # which is robust even when routes are lazily wrapped (_IncludedRouter).
    paths = app.openapi().get("paths", {})
    for expected in REQUIRED_PATHS:
        assert expected in paths


def test_cors_middleware_enabled():
    assert any(middleware.cls is CORSMiddleware for middleware in app.user_middleware)


@pytest.mark.asyncio
async def test_cors_echoes_allowed_origin(client):
    resp = await client.get("/", headers={"Origin": "http://localhost:3000"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_rejects_unlisted_origin(client):
    resp = await client.get("/", headers={"Origin": "http://evil.example.com"})
    allowed = resp.headers.get("access-control-allow-origin")
    assert allowed != "http://evil.example.com"