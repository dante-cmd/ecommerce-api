import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "apiuser@example.com", "password": "Password123!"},
    )
    assert response.status_code == 201
    assert "Registration successful" in response.json()["message"]


@pytest.mark.asyncio
async def test_login(async_client: AsyncClient):
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "loginapi@example.com", "password": "Password123!"},
    )
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "loginapi@example.com", "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_invalid(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "none@example.com", "password": "Password123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(async_client: AsyncClient, auth_headers: dict):
    headers = {k: v for k, v in auth_headers.items() if k != "user_id"}
    response = await async_client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
