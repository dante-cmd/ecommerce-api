import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_update_me(async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    headers = {k: v for k, v in auth_headers.items() if k != "user_id"}
    response = await async_client.patch(
        "/api/v1/users/me",
        json={"first_name": "Updated"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"


@pytest.mark.asyncio
async def test_create_address(async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    headers = {k: v for k, v in auth_headers.items() if k != "user_id"}
    response = await async_client.post(
        "/api/v1/users/me/addresses",
        json={
            "street": "123 Main",
            "city": "City",
            "state": "ST",
            "postal_code": "12345",
            "country": "US",
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["street"] == "123 Main"
