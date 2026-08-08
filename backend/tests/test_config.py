from sqlalchemy.engine import make_url

from app.core.config import Settings


def test_database_uri_quotes_reserved_password_characters() -> None:
    password = "ci/password+with:@%reserved"  # pragma: allowlist secret
    test_settings = Settings(
        _env_file=None,
        PROJECT_NAME="Tahr Desk",
        POSTGRES_SERVER="db",
        POSTGRES_USER="tahr_desk",
        POSTGRES_PASSWORD=password,
        POSTGRES_DB="tahr_desk",
        FIRST_SUPERUSER="admin@example.com",
        FIRST_SUPERUSER_PASSWORD="unused-admin-password",  # pragma: allowlist secret
        SECRET_KEY="unused-secret-key",  # pragma: allowlist secret
    )

    assert make_url(str(test_settings.SQLALCHEMY_DATABASE_URI)).password == password
