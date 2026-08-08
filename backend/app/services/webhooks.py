import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
from datetime import UTC, datetime
from urllib.parse import urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import settings
from app.models import (
    CaseEvent,
    DeliveryStatus,
    ServiceCase,
    ServiceCategory,
    WebhookDelivery,
    WebhookEndpoint,
)

SUPPORTED_EVENTS = {
    "case.created",
    "case.assigned",
    "case.updated",
    "case.message.created",
    "case.resolved",
    "case.closed",
}
MAX_WEBHOOK_BYTES = 64 * 1024


class PinnedResolver(AbstractResolver):
    def __init__(self, hostname: str, addresses: list[str]) -> None:
        self.hostname = hostname
        self.addresses = addresses

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        if host != self.hostname:
            raise OSError("unexpected_webhook_host")
        return [
            ResolveResult(
                hostname=host,
                host=address,
                port=port,
                family=socket.AF_INET6 if ":" in address else socket.AF_INET,
                proto=socket.IPPROTO_TCP,
                flags=socket.AI_NUMERICHOST,
            )
            for address in self.addresses
        ]

    async def close(self) -> None:
        return None


def _encryption_key() -> bytes:
    return HKDF(
        algorithm=SHA256(),
        length=32,
        salt=b"tahr-desk-webhook-v1",
        info=b"webhook-signing-secret",
    ).derive(settings.SECRET_KEY.encode())


def encrypt_secret(secret: str) -> str:
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_encryption_key()).encrypt(
        nonce, secret.encode(), b"tahr-desk-webhook-v1"
    )
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_secret(ciphertext: str) -> str:
    raw = base64.urlsafe_b64decode(ciphertext.encode())
    return (
        AESGCM(_encryption_key())
        .decrypt(raw[:12], raw[12:], b"tahr-desk-webhook-v1")
        .decode()
    )


def validate_event_types(events: list[str]) -> list[str]:
    normalized = sorted(set(events))
    if not normalized or any(event not in SUPPORTED_EVENTS for event in normalized):
        raise HTTPException(status_code=422, detail="Unsupported webhook event")
    return normalized


def validate_webhook_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    allowed_schemes = {"https"}
    if settings.ENVIRONMENT == "local" and settings.WEBHOOK_ALLOW_HTTP:
        allowed_schemes.add("http")
    if parsed.scheme not in allowed_schemes:
        raise HTTPException(status_code=422, detail="Webhook URL must use HTTPS")
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise HTTPException(
            status_code=422, detail="Webhook URL contains forbidden components"
        )
    if not parsed.hostname:
        raise HTTPException(status_code=422, detail="Webhook URL must include a host")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise HTTPException(
            status_code=422, detail="Webhook URL cannot use an IP literal"
        )
    if settings.ENVIRONMENT != "local" and parsed.port not in {None, 443}:
        raise HTTPException(status_code=422, detail="Webhook URL must use port 443")
    return value.strip()


def resolve_public_addresses(hostname: str, port: int) -> list[str]:
    try:
        answers = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(
            status_code=422, detail="Webhook host could not be resolved"
        )
    addresses = sorted({str(answer[4][0]) for answer in answers})
    if not addresses:
        raise HTTPException(
            status_code=422, detail="Webhook host could not be resolved"
        )
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise HTTPException(
            status_code=422, detail="Webhook host must resolve publicly"
        )
    return addresses


def enqueue_for_event(
    session: Session, *, event: CaseEvent, service_case: ServiceCase
) -> None:
    if not settings.WEBHOOK_DELIVERY_ENABLED:
        return
    category = session.get(ServiceCategory, service_case.category_id)
    event_name = {
        "created": "case.created",
        "assigned": "case.assigned",
        "message": "case.message.created",
        "resolved": "case.resolved",
        "closed": "case.closed",
    }.get(event.event_type, "case.updated")
    payload = {
        "schema_version": 1,
        "event_id": str(event.id),
        "event_type": event_name,
        "case": {
            "reference": service_case.reference,
            "category": category.slug if category else "unknown",
            "status": str(service_case.status),
            "priority": str(service_case.priority),
            "summary": event.summary,
            "updated_at": service_case.updated_at.isoformat(),
        },
    }
    endpoints = session.exec(
        select(WebhookEndpoint).where(WebhookEndpoint.is_active == True)  # noqa: E712
    ).all()
    for endpoint in endpoints:
        if event_name in endpoint.subscribed_events:
            session.add(
                WebhookDelivery(
                    endpoint_id=endpoint.id,
                    case_event_id=event.id,
                    payload=payload,
                    status=DeliveryStatus.queued,
                    next_attempt_at=datetime.now(UTC),
                )
            )


def new_signing_secret() -> tuple[str, str]:
    secret = secrets.token_urlsafe(32)
    return secret, encrypt_secret(secret)


def canonical_payload(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def webhook_signature(
    *, secret: str, timestamp: str, event_id: str, body: bytes
) -> str:
    signed = timestamp.encode() + b"." + event_id.encode() + b"." + body
    return hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()


async def deliver_webhook(
    *, endpoint: WebhookEndpoint, delivery: WebhookDelivery
) -> tuple[int | None, str | None]:
    body = canonical_payload(delivery.payload)
    if len(body) > MAX_WEBHOOK_BYTES:
        return None, "payload_too_large"
    parsed = urlsplit(validate_webhook_url(endpoint.url))
    hostname = parsed.hostname
    if hostname is None:
        return None, "invalid_url"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = resolve_public_addresses(hostname, port)
    except HTTPException:
        return None, "address_rejected"
    timestamp = str(int(datetime.now(UTC).timestamp()))
    event_id = str(delivery.case_event_id)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Tahr-Desk-Webhook/1.0",
        "X-Tahr-Desk-Event": event_id,
        "X-Tahr-Desk-Timestamp": timestamp,
        "X-Tahr-Desk-Signature": "sha256="
        + webhook_signature(
            secret=decrypt_secret(endpoint.secret_ciphertext),
            timestamp=timestamp,
            event_id=event_id,
            body=body,
        ),
    }
    resolver = PinnedResolver(hostname, addresses)
    connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=False)
    timeout = aiohttp.ClientTimeout(total=10, connect=3)
    try:
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            trust_env=False,
            auto_decompress=False,
            cookie_jar=aiohttp.DummyCookieJar(),
        ) as client:
            async with client.post(
                endpoint.url,
                data=body,
                headers=headers,
                allow_redirects=False,
            ) as response:
                if (
                    len(await response.content.read(MAX_WEBHOOK_BYTES + 1))
                    > MAX_WEBHOOK_BYTES
                ):
                    return response.status, "response_too_large"
                if 200 <= response.status < 300:
                    return response.status, None
                return response.status, f"http_{response.status}"
    except TimeoutError:
        return None, "timeout"
    except aiohttp.ClientConnectorCertificateError:
        return None, "tls_certificate"
    except aiohttp.ClientSSLError:
        return None, "tls_error"
    except aiohttp.ClientError:
        return None, "connection_error"
