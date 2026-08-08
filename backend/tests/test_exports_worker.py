import asyncio
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import worker
from app.core.config import settings
from app.models import (
    CaseEvent,
    DeliveryStatus,
    ExportJob,
    ExportKind,
    JobStatus,
    ServiceCase,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.services.exports import process_export, render_case_pdf, render_cases_csv
from app.services.storage import ensure_storage
from app.services.webhooks import (
    MAX_WEBHOOK_BYTES,
    PinnedResolver,
    canonical_payload,
    deliver_webhook,
    encrypt_secret,
    resolve_public_addresses,
)


def test_export_api_processing_and_downloads(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    original_root = settings.DATA_ROOT
    settings.DATA_ROOT = tmp_path
    ensure_storage()
    try:
        case = db.exec(select(ServiceCase).limit(1)).one()
        assert render_case_pdf(db, case).startswith(b"%PDF")
        assert render_cases_csv(db, {"status": str(case.status)}).startswith(
            b"\xef\xbb\xbf"
        )

        missing_case = client.post(
            f"{settings.API_V1_STR}/staff/exports",
            headers=superuser_token_headers,
            json={"kind": "case_pdf", "idempotency_key": str(uuid.uuid4())},
        )
        assert missing_case.status_code == 422
        unknown_case = client.post(
            f"{settings.API_V1_STR}/staff/exports",
            headers=superuser_token_headers,
            json={
                "kind": "case_pdf",
                "case_id": str(uuid.uuid4()),
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert unknown_case.status_code == 404

        key = str(uuid.uuid4())
        queued = client.post(
            f"{settings.API_V1_STR}/staff/exports",
            headers=superuser_token_headers,
            json={
                "kind": "case_pdf",
                "case_id": str(case.id),
                "idempotency_key": key,
            },
        )
        duplicate = client.post(
            f"{settings.API_V1_STR}/staff/exports",
            headers=superuser_token_headers,
            json={
                "kind": "case_pdf",
                "case_id": str(case.id),
                "idempotency_key": key,
            },
        )
        assert queued.status_code == duplicate.status_code == 202
        assert queued.json()["id"] == duplicate.json()["id"]
        export_id = uuid.UUID(queued.json()["id"])
        assert (
            client.get(
                f"{settings.API_V1_STR}/staff/exports", headers=superuser_token_headers
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"{settings.API_V1_STR}/staff/exports/{export_id}",
                headers=superuser_token_headers,
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"{settings.API_V1_STR}/staff/exports/{export_id}/download",
                headers=superuser_token_headers,
            ).status_code
            == 409
        )

        with Session(db.get_bind()) as session:
            job = session.get(ExportJob, export_id)
            assert job is not None
            process_export(session, job)
        downloaded = client.get(
            f"{settings.API_V1_STR}/staff/exports/{export_id}/download",
            headers=superuser_token_headers,
        )
        assert downloaded.status_code == 200
        assert downloaded.content.startswith(b"%PDF")

        csv_job = client.post(
            f"{settings.API_V1_STR}/staff/exports",
            headers=superuser_token_headers,
            json={
                "kind": "cases_csv",
                "idempotency_key": str(uuid.uuid4()),
                "filters": {"priority": "normal"},
            },
        )
        assert csv_job.status_code == 202
        with Session(db.get_bind()) as session:
            job = session.get(ExportJob, uuid.UUID(csv_job.json()["id"]))
            assert job is not None
            process_export(session, job)
            assert job.storage_key is not None
            (tmp_path / "exports" / job.storage_key).unlink()
        assert (
            client.get(
                f"{settings.API_V1_STR}/staff/exports/{csv_job.json()['id']}/download",
                headers=superuser_token_headers,
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"{settings.API_V1_STR}/staff/exports/{uuid.uuid4()}",
                headers=superuser_token_headers,
            ).status_code
            == 404
        )
    finally:
        settings.DATA_ROOT = original_root


def test_worker_leases_retries_delivery_and_cleanup(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_root = settings.DATA_ROOT
    settings.DATA_ROOT = tmp_path
    ensure_storage()
    try:
        requester = db.exec(select(ServiceCase).limit(1)).one().assigned_to_id
        if requester is None:
            from app.models import User

            superuser = db.exec(select(User).where(User.is_superuser)).first()
            assert superuser is not None
            requester = superuser.id
        case = db.exec(select(ServiceCase).limit(1)).one()

        with Session(db.get_bind()) as session:
            failed_job = ExportJob(
                requested_by_id=requester,
                kind=ExportKind.case_pdf,
                case_id=case.id,
                idempotency_key=uuid.uuid4(),
            )
            session.add(failed_job)
            session.commit()
            leased = worker.lease_export(session)
            assert leased is not None and leased.status == JobStatus.running
            worker.fail_export(session, leased, "first_failure")
            leased.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
            session.add(leased)
            session.commit()
            leased = worker.lease_export(session)
            assert leased is not None
            worker.fail_export(session, leased, "second_failure")
            assert leased.status == JobStatus.failed

            for existing_delivery in session.exec(select(WebhookDelivery)).all():
                existing_delivery.status = DeliveryStatus.suppressed
                session.add(existing_delivery)
            session.commit()
            event = session.exec(select(CaseEvent).limit(1)).one()
            endpoint = WebhookEndpoint(
                name=f"Inactive test {uuid.uuid4().hex[:8]}",
                url="https://example.com/hook",
                secret_ciphertext=encrypt_secret("worker-secret"),
                subscribed_events=["case.created"],
                is_active=False,
            )
            session.add(endpoint)
            session.flush()
            endpoint_id = endpoint.id
            delivery = WebhookDelivery(
                endpoint_id=endpoint.id,
                case_event_id=event.id,
                payload={"event_id": str(event.id)},
            )
            session.add(delivery)
            session.commit()
            leased_delivery = worker.lease_delivery(session)
            assert leased_delivery is not None
            worker.process_delivery(session, leased_delivery)
            assert leased_delivery.status == DeliveryStatus.suppressed

            endpoint.is_active = True
            retry_event = CaseEvent(
                case_id=case.id,
                event_type="worker_retry",
                visibility="private",
                summary="Retry delivery",
            )
            session.add(retry_event)
            session.flush()
            retry_delivery = WebhookDelivery(
                endpoint_id=endpoint.id,
                case_event_id=retry_event.id,
                payload={"event_id": "retry"},
                status=DeliveryStatus.delivering,
                attempts=1,
            )
            session.add(retry_delivery)
            session.commit()
            worker.finish_delivery(
                session,
                retry_delivery,
                response_status=503,
                error_code="http_503",
            )
            assert retry_delivery.status == DeliveryStatus.queued
            retry_delivery.attempts = 6
            worker.finish_delivery(
                session,
                retry_delivery,
                response_status=None,
                error_code="timeout",
            )
            assert retry_delivery.status == DeliveryStatus.failed

            ready = ExportJob(
                requested_by_id=requester,
                kind=ExportKind.cases_csv,
                idempotency_key=uuid.uuid4(),
                status=JobStatus.ready,
                storage_key="old/expired.csv",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
            old_file = tmp_path / "exports" / "old" / "expired.csv"
            old_file.parent.mkdir(parents=True)
            old_file.write_bytes(b"old")
            session.add(ready)
            session.commit()
            worker.expire_exports(session)
            assert ready.status == JobStatus.expired
            assert not old_file.exists()

            orphan = tmp_path / "uploads" / "old" / "orphan.png"
            orphan.parent.mkdir(parents=True)
            orphan.write_bytes(b"orphan")
            old = time.time() - 7200
            os.utime(orphan, (old, old))
            worker.cleanup_storage(session)
            assert not orphan.exists()

        async def successful_delivery(**_kwargs):
            return 204, None

        monkeypatch.setattr(worker, "deliver_webhook", successful_delivery)
        with Session(db.get_bind()) as session:
            endpoint = session.get(WebhookEndpoint, endpoint_id)
            assert endpoint is not None
            event = CaseEvent(
                case_id=case.id,
                event_type="worker_success",
                visibility="private",
                summary="Successful delivery",
            )
            session.add(event)
            session.flush()
            delivery = WebhookDelivery(
                endpoint_id=endpoint.id,
                case_event_id=event.id,
                payload={"event_id": str(event.id)},
                status=DeliveryStatus.delivering,
                attempts=1,
            )
            session.add(delivery)
            session.commit()
            worker.process_delivery(session, delivery)
            assert delivery.status == DeliveryStatus.delivered
    finally:
        settings.DATA_ROOT = original_root


def test_webhook_network_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = PinnedResolver("example.com", ["93.184.216.34", "2606:2800::1"])
    answers = asyncio.run(resolver.resolve("example.com", 443))
    assert len(answers) == 2
    with pytest.raises(OSError):
        asyncio.run(resolver.resolve("unexpected.example", 443))
    asyncio.run(resolver.close())

    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    assert resolve_public_addresses("example.com", 443) == ["93.184.216.34"]
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(HTTPException):
        resolve_public_addresses("example.com", 443)

    endpoint = WebhookEndpoint(
        name="Boundary",
        url="https://example.com/hook",
        secret_ciphertext=encrypt_secret("boundary-secret"),
        subscribed_events=["case.created"],
    )
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        case_event_id=uuid.uuid4(),
        payload={"data": "x" * (MAX_WEBHOOK_BYTES + 1)},
    )
    assert asyncio.run(deliver_webhook(endpoint=endpoint, delivery=delivery)) == (
        None,
        "payload_too_large",
    )
    assert canonical_payload({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
