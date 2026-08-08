import asyncio
import logging
import os
import socket
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlmodel import Session, col, or_, select

from app.core.config import settings
from app.core.db import engine
from app.models import (
    Attachment,
    DeliveryStatus,
    ExportJob,
    JobStatus,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.services.exports import process_export
from app.services.storage import ensure_storage
from app.services.webhooks import deliver_webhook

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tahr-desk-worker")
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
DELIVERY_RETRY_SECONDS = (30, 120, 600, 3600, 21600)


def lease_export(session: Session) -> ExportJob | None:
    now = datetime.now(UTC)
    job = session.exec(
        select(ExportJob)
        .where(
            or_(
                (
                    (col(ExportJob.status) == JobStatus.queued)
                    & (ExportJob.next_attempt_at <= now)
                ),
                (
                    (col(ExportJob.status) == JobStatus.running)
                    & (col(ExportJob.lease_expires_at) <= now)
                ),
            )
        )
        .order_by(col(ExportJob.created_at))
        .with_for_update(skip_locked=True)
        .limit(1)
    ).first()
    if job is None:
        return None
    job.status = JobStatus.running
    job.attempts += 1
    job.lease_owner = WORKER_ID
    job.lease_expires_at = now + timedelta(minutes=3)
    job.updated_at = now
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def fail_export(session: Session, job: ExportJob, code: str) -> None:
    job.error_code = code[:64]
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = datetime.now(UTC)
    if job.attempts >= 2:
        job.status = JobStatus.failed
    else:
        job.status = JobStatus.queued
        job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=30)
    session.add(job)
    session.commit()


def lease_delivery(session: Session) -> WebhookDelivery | None:
    now = datetime.now(UTC)
    delivery = session.exec(
        select(WebhookDelivery)
        .where(
            or_(
                (
                    (col(WebhookDelivery.status) == DeliveryStatus.queued)
                    & (WebhookDelivery.next_attempt_at <= now)
                ),
                (
                    (col(WebhookDelivery.status) == DeliveryStatus.delivering)
                    & (col(WebhookDelivery.lease_expires_at) <= now)
                ),
            )
        )
        .order_by(col(WebhookDelivery.created_at))
        .with_for_update(skip_locked=True)
        .limit(1)
    ).first()
    if delivery is None:
        return None
    delivery.status = DeliveryStatus.delivering
    delivery.attempts += 1
    delivery.lease_owner = WORKER_ID
    delivery.lease_expires_at = now + timedelta(seconds=30)
    delivery.updated_at = now
    session.add(delivery)
    session.commit()
    session.refresh(delivery)
    return delivery


def finish_delivery(
    session: Session,
    delivery: WebhookDelivery,
    *,
    response_status: int | None,
    error_code: str | None,
) -> None:
    delivery.response_status = response_status
    delivery.error_code = error_code
    delivery.lease_owner = None
    delivery.lease_expires_at = None
    delivery.updated_at = datetime.now(UTC)
    if error_code is None:
        delivery.status = DeliveryStatus.delivered
    elif delivery.attempts >= 6:
        delivery.status = DeliveryStatus.failed
    else:
        delivery.status = DeliveryStatus.queued
        delivery.next_attempt_at = datetime.now(UTC) + timedelta(
            seconds=DELIVERY_RETRY_SECONDS[delivery.attempts - 1]
        )
    session.add(delivery)
    session.commit()


def process_delivery(session: Session, delivery: WebhookDelivery) -> None:
    endpoint = session.get(WebhookEndpoint, delivery.endpoint_id)
    if endpoint is None or not endpoint.is_active:
        delivery.status = DeliveryStatus.suppressed
        delivery.error_code = "endpoint_inactive"
        delivery.lease_owner = None
        delivery.lease_expires_at = None
        delivery.updated_at = datetime.now(UTC)
        session.add(delivery)
        session.commit()
        return
    status, code = asyncio.run(deliver_webhook(endpoint=endpoint, delivery=delivery))
    finish_delivery(session, delivery, response_status=status, error_code=code)


def expire_exports(session: Session) -> None:
    now = datetime.now(UTC)
    jobs = session.exec(
        select(ExportJob).where(
            ExportJob.status == JobStatus.ready,
            col(ExportJob.expires_at) <= now,
        )
    ).all()
    for job in jobs:
        if job.storage_key:
            (settings.DATA_ROOT / "exports" / job.storage_key).unlink(missing_ok=True)
        job.status = JobStatus.expired
        job.storage_key = None
        job.updated_at = now
        session.add(job)
    session.commit()


def cleanup_storage(session: Session) -> None:
    acquired = (
        session.connection()
        .execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": 843_737_001})
        .scalar_one()
    )
    if not acquired:
        return
    try:
        expire_exports(session)
        cutoff = datetime.now(UTC).timestamp() - 3600
        referenced = set(session.exec(select(Attachment.storage_key)).all())
        for root_name in ("uploads", "exports"):
            root = settings.DATA_ROOT / root_name
            for path in root.rglob("*"):
                if not path.is_file() or path.stat().st_mtime >= cutoff:
                    continue
                relative = str(path.relative_to(root))
                if path.name.startswith(("upload-", "export-")):
                    path.unlink(missing_ok=True)
                elif root_name == "uploads" and relative not in referenced:
                    path.unlink(missing_ok=True)
            for directory in sorted(root.rglob("*"), reverse=True):
                if directory.is_dir():
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
    finally:
        session.connection().execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": 843_737_001}
        )
        session.commit()


def run_once() -> bool:
    with Session(engine) as session:
        job = lease_export(session)
        if job is not None:
            try:
                process_export(session, job)
            except Exception as exc:
                logger.warning("Export job failed: %s", type(exc).__name__)
                fail_export(session, job, "export_failed")
            return True
        delivery = (
            lease_delivery(session) if settings.WEBHOOK_DELIVERY_ENABLED else None
        )
        if delivery is None:
            return False
        process_delivery(session, delivery)
        return True


def main() -> None:
    ensure_storage()
    last_cleanup = 0.0
    while True:
        worked = run_once()
        if time.monotonic() - last_cleanup > 3600:
            with Session(engine) as session:
                cleanup_storage(session)
            last_cleanup = time.monotonic()
        if not worked:
            time.sleep(settings.WORKER_POLL_SECONDS)


if __name__ == "__main__":
    main()
