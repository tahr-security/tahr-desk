from fastapi.testclient import TestClient

from app.core.config import settings


def test_superuser_can_read_self(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["email"] == settings.FIRST_SUPERUSER
    assert response.json()["is_superuser"] is True


def test_public_signup_is_absent(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/users/signup",
        json={"email": "user@example.com", "password": "long-enough-password"},
    )
    assert response.status_code == 404
