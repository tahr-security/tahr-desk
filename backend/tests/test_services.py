import asyncio
import io
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.core.config import settings
from app.services.content import render_markdown
from app.services.exports import neutralize_csv
from app.services.storage import sanitized_filename, storage_path, store_image
from app.services.webhooks import (
    decrypt_secret,
    encrypt_secret,
    validate_event_types,
    validate_webhook_url,
    webhook_signature,
)


def test_markdown_is_sanitized_and_links_are_hardened() -> None:
    result = render_markdown("[safe](https://example.com) <script>alert(1)</script>")
    assert "<script" not in result
    assert "noopener" in result
    assert "https://example.com" in result


def test_csv_formula_neutralization() -> None:
    assert neutralize_csv("=2+2") == "'=2+2"
    assert neutralize_csv("@SUM(A1:A2)").startswith("'")
    assert neutralize_csv("ordinary") == "ordinary"


def test_image_is_reencoded_and_metadata_removed(tmp_path: Path) -> None:
    original_root = settings.DATA_ROOT
    settings.DATA_ROOT = tmp_path
    try:
        source = io.BytesIO()
        exif = Image.Exif()
        exif[0x010E] = "private metadata"
        Image.new("RGB", (24, 16), "red").save(source, format="JPEG", exif=exif)
        stored = asyncio.run(
            store_image(
                UploadFile(
                    filename="../resident photo.jpg",
                    file=io.BytesIO(source.getvalue()),
                )
            )
        )
        assert stored.path.is_file()
        assert ".." not in stored.display_name
        with Image.open(stored.path) as image:
            assert not image.getexif()
    finally:
        settings.DATA_ROOT = original_root


def test_storage_path_rejects_traversal(tmp_path: Path) -> None:
    original_root = settings.DATA_ROOT
    settings.DATA_ROOT = tmp_path
    try:
        with pytest.raises(RuntimeError):
            storage_path("../outside.jpg")
        assert sanitized_filename("../../odd?.png", "image/png") == "odd_.png"
    finally:
        settings.DATA_ROOT = original_root


def test_webhook_secret_signature_and_validation() -> None:
    encrypted = encrypt_secret("secret-value")
    assert decrypt_secret(encrypted) == "secret-value"
    first = webhook_signature(
        secret="secret-value", timestamp="1", event_id="event", body=b"{}"
    )
    second = webhook_signature(
        secret="secret-value", timestamp="1", event_id="event", body=b"{}"
    )
    assert first == second
    assert validate_event_types(["case.created", "case.created"]) == ["case.created"]
    assert (
        validate_webhook_url("https://example.com/hook") == "https://example.com/hook"
    )
    for invalid in (
        "http://example.com/hook",
        "https://user@example.com/hook",
        "https://127.0.0.1/hook",
        "https://example.com/hook?secret=x",
    ):
        with pytest.raises(HTTPException):
            validate_webhook_url(invalid)
