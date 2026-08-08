from fastapi.testclient import TestClient

from app.core.config import settings


def test_get_access_token(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={
            "username": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_incorrect_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": settings.FIRST_SUPERUSER, "password": "incorrect"},
    )
    assert response.status_code == 400


def test_recovery_endpoints_are_absent(client: TestClient) -> None:
    assert (
        client.post(
            f"{settings.API_V1_STR}/password-recovery/user@example.com"
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{settings.API_V1_STR}/reset-password/",
            json={"token": "nope", "new_password": "long-enough-password"},
        ).status_code
        == 404
    )
