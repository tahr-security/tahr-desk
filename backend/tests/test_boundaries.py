import asyncio
import io
import socket
import uuid
from datetime import timedelta
from pathlib import Path

import aiohttp
import jwt
import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app import worker
from app.core import security
from app.core.config import settings
from app.models import (
    CaseEvent,
    DeliveryStatus,
    ExportJob,
    ExportKind,
    ServiceCase,
    User,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.services import storage
from app.services.storage import ensure_storage, remove_stored_image, store_image
from app.services.webhooks import (
    deliver_webhook,
    encrypt_secret,
    enqueue_for_event,
    resolve_public_addresses,
    validate_event_types,
    validate_webhook_url,
)


def _image_bytes(image_format: str = "PNG", size: tuple[int, int] = (16, 16)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, "green").save(output, format=image_format)
    return output.getvalue()


def test_storage_rejections_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_root = settings.DATA_ROOT
    settings.DATA_ROOT = tmp_path
    ensure_storage()
    try:
        with pytest.raises(HTTPException):
            asyncio.run(
                store_image(UploadFile(filename="empty.png", file=io.BytesIO()))
            )
        with pytest.raises(HTTPException):
            asyncio.run(
                store_image(
                    UploadFile(
                        filename="large.png",
                        file=io.BytesIO(b"x" * (storage.MAX_IMAGE_BYTES + 1)),
                    )
                )
            )
        with pytest.raises(HTTPException):
            asyncio.run(
                store_image(
                    UploadFile(filename="invalid.png", file=io.BytesIO(b"not-image"))
                )
            )
        with pytest.raises(HTTPException):
            asyncio.run(
                store_image(
                    UploadFile(
                        filename="animation.gif",
                        file=io.BytesIO(_image_bytes("GIF")),
                    )
                )
            )

        monkeypatch.setattr(storage, "MAX_IMAGE_DIMENSION", 10)
        with pytest.raises(HTTPException):
            asyncio.run(
                store_image(
                    UploadFile(
                        filename="wide.png",
                        file=io.BytesIO(_image_bytes(size=(20, 5))),
                    )
                )
            )
        monkeypatch.setattr(storage, "MAX_IMAGE_DIMENSION", 12_000)
        monkeypatch.setattr(storage, "MAX_IMAGE_PIXELS", 100)
        with pytest.raises(HTTPException):
            asyncio.run(
                store_image(
                    UploadFile(
                        filename="pixels.png",
                        file=io.BytesIO(_image_bytes(size=(11, 11))),
                    )
                )
            )
        monkeypatch.setattr(storage, "MAX_IMAGE_PIXELS", 40_000_000)
        stored = asyncio.run(
            store_image(UploadFile(filename=None, file=io.BytesIO(_image_bytes("PNG"))))
        )
        assert stored.display_name == "photo.png"
        remove_stored_image(stored)
        assert not stored.path.exists()
    finally:
        settings.DATA_ROOT = original_root


def test_webhook_validation_enqueue_and_resolver(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    for events in ([], ["case.unknown"]):
        with pytest.raises(HTTPException):
            validate_event_types(events)
    for url in ("https:///missing", "ftp://example.com"):
        with pytest.raises(HTTPException):
            validate_webhook_url(url)
    original_environment = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        with pytest.raises(HTTPException):
            validate_webhook_url("https://example.com:444/hook")
    finally:
        settings.ENVIRONMENT = original_environment

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(socket.gaierror()),
    )
    with pytest.raises(HTTPException):
        resolve_public_addresses("missing.example", 443)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [])
    with pytest.raises(HTTPException):
        resolve_public_addresses("empty.example", 443)

    case = db.exec(select(ServiceCase).limit(1)).one()
    event = CaseEvent(
        case_id=case.id,
        event_type="assigned",
        visibility="public",
        summary="Assigned for webhook coverage",
    )
    endpoint = WebhookEndpoint(
        name=f"Coverage {uuid.uuid4().hex[:8]}",
        url="https://example.com/hook",
        secret_ciphertext=encrypt_secret("enqueue-secret"),
        subscribed_events=["case.assigned"],
    )
    db.add(event)
    db.add(endpoint)
    db.flush()
    original_enabled = settings.WEBHOOK_DELIVERY_ENABLED
    try:
        settings.WEBHOOK_DELIVERY_ENABLED = True
        enqueue_for_event(db, event=event, service_case=case)
        db.commit()
        delivery = db.exec(
            select(WebhookDelivery).where(
                WebhookDelivery.endpoint_id == endpoint.id,
                WebhookDelivery.case_event_id == event.id,
            )
        ).one()
        assert delivery.payload["event_type"] == "case.assigned"
    finally:
        settings.WEBHOOK_DELIVERY_ENABLED = original_enabled


class _FakeContent:
    def __init__(self, body: bytes) -> None:
        self.body = body

    async def read(self, _limit: int) -> bytes:
        return self.body


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.content = _FakeContent(body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _FakeClient:
    status = 204
    body = b"ok"
    exception: Exception | None = None

    def __init__(self, **_kwargs) -> None:
        pass

    async def __aenter__(self):
        if self.exception:
            raise self.exception
        return self

    async def __aexit__(self, *_args):
        return None

    def post(self, *_args, **_kwargs):
        return _FakeResponse(self.status, self.body)


def test_webhook_delivery_response_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = WebhookEndpoint(
        name="Delivery boundary",
        url="https://example.com/hook",
        secret_ciphertext=encrypt_secret("delivery-secret"),
        subscribed_events=["case.created"],
    )
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        case_event_id=uuid.uuid4(),
        payload={"event_id": "event", "case": {"reference": "TDK-TEST"}},
    )
    monkeypatch.setattr(
        "app.services.webhooks.resolve_public_addresses",
        lambda *_args: ["93.184.216.34"],
    )
    monkeypatch.setattr(aiohttp, "ClientSession", _FakeClient)

    _FakeClient.status, _FakeClient.body, _FakeClient.exception = 204, b"ok", None
    assert asyncio.run(deliver_webhook(endpoint=endpoint, delivery=delivery)) == (
        204,
        None,
    )
    _FakeClient.status = 503
    assert asyncio.run(deliver_webhook(endpoint=endpoint, delivery=delivery)) == (
        503,
        "http_503",
    )
    _FakeClient.status, _FakeClient.body = 200, b"x" * (64 * 1024 + 1)
    assert asyncio.run(deliver_webhook(endpoint=endpoint, delivery=delivery)) == (
        200,
        "response_too_large",
    )
    _FakeClient.exception = TimeoutError()
    assert asyncio.run(deliver_webhook(endpoint=endpoint, delivery=delivery)) == (
        None,
        "timeout",
    )
    _FakeClient.exception = aiohttp.ClientConnectionError()
    assert asyncio.run(deliver_webhook(endpoint=endpoint, delivery=delivery)) == (
        None,
        "connection_error",
    )


def test_token_version_and_password_change(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    email = f"password-{uuid.uuid4().hex[:8]}@example.com"
    old_password = "Password-before-change-42"
    new_password = "Password-after-change-42"
    created = client.post(
        f"{settings.API_V1_STR}/admin/agents",
        headers=superuser_token_headers,
        json={"email": email, "full_name": "Password Agent", "password": old_password},
    )
    assert created.status_code == 201
    login = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": old_password},
    )
    old_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    changed = client.patch(
        f"{settings.API_V1_STR}/users/me/password",
        headers=old_headers,
        json={"current_password": old_password, "new_password": new_password},
    )
    assert changed.status_code == 200
    assert (
        client.get(f"{settings.API_V1_STR}/users/me", headers=old_headers).status_code
        == 403
    )
    assert (
        client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": email, "password": new_password},
        ).status_code
        == 200
    )

    unknown = security.create_access_token(
        subject=str(uuid.uuid4()),
        expires_delta=timedelta(minutes=5),
        auth_version=0,
    )
    assert (
        client.get(
            f"{settings.API_V1_STR}/users/me",
            headers={"Authorization": f"Bearer {unknown}"},
        ).status_code
        == 404
    )
    bad = jwt.encode({"sub": "not-a-uuid"}, settings.SECRET_KEY, algorithm="HS256")
    assert (
        client.get(
            f"{settings.API_V1_STR}/users/me",
            headers={"Authorization": f"Bearer {bad}"},
        ).status_code
        == 403
    )
    assert client.get(f"{settings.API_V1_STR}/utils/health-check/").status_code == 200


def test_worker_run_once_branches(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    case = db.exec(select(ServiceCase).limit(1)).one()
    requester = db.exec(select(User).where(User.is_superuser)).first()
    assert requester is not None
    export = ExportJob(
        requested_by_id=requester.id,
        kind=ExportKind.case_pdf,
        case_id=case.id,
        idempotency_key=uuid.uuid4(),
    )
    monkeypatch.setattr(worker, "lease_export", lambda _session: export)
    monkeypatch.setattr(worker, "process_export", lambda _session, _job: None)
    assert worker.run_once() is True

    monkeypatch.setattr(
        worker, "process_export", lambda *_args: (_ for _ in ()).throw(RuntimeError())
    )
    monkeypatch.setattr(worker, "fail_export", lambda *_args: None)
    assert worker.run_once() is True

    delivery = WebhookDelivery(
        endpoint_id=uuid.uuid4(),
        case_event_id=uuid.uuid4(),
        payload={},
        status=DeliveryStatus.queued,
    )
    monkeypatch.setattr(worker, "lease_export", lambda _session: None)
    monkeypatch.setattr(worker, "lease_delivery", lambda _session: delivery)
    monkeypatch.setattr(worker, "process_delivery", lambda _session, _delivery: None)
    original_enabled = settings.WEBHOOK_DELIVERY_ENABLED
    try:
        settings.WEBHOOK_DELIVERY_ENABLED = True
        assert worker.run_once() is True
        monkeypatch.setattr(worker, "lease_delivery", lambda _session: None)
        assert worker.run_once() is False
    finally:
        settings.WEBHOOK_DELIVERY_ENABLED = original_enabled
