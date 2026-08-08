import io
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import settings
from app.models import ServiceCase, User
from app.seed import CATEGORIES


def _png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 20), "#426e7d").save(output, format="PNG")
    return output.getvalue()


def _submit(client: TestClient, *, email: str | None = None, photo: bool = False):
    email = email or f"resident-{uuid.uuid4().hex[:10]}@example.com"
    files = {"photos": ("street.png", _png(), "image/png")} if photo else None
    response = client.post(
        f"{settings.API_V1_STR}/public/cases",
        data={
            "submission_id": str(uuid.uuid4()),
            "reporter_name": "Morgan Resident",
            "reporter_email": email,
            "category_id": str(CATEGORIES[0].id),
            "subject": "Streetlight remains dark",
            "description": "The streetlight beside the crossing has been dark for three nights.",
            "location_text": "48 Spruce Street",
        },
        files=files,
    )
    assert response.status_code == 201
    return response.json(), email


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_public_content_upload_followup_and_download(client: TestClient) -> None:
    site = client.get(f"{settings.API_V1_STR}/public/site")
    services = client.get(f"{settings.API_V1_STR}/public/services")
    service = client.get(f"{settings.API_V1_STR}/public/services/{CATEGORIES[0].slug}")
    missing = client.get(f"{settings.API_V1_STR}/public/services/not-a-service")
    assert site.status_code == services.status_code == service.status_code == 200
    assert services.json()["count"] >= 5
    assert missing.status_code == 404

    receipt, email = _submit(client, photo=True)
    lookup = client.post(
        f"{settings.API_V1_STR}/public/cases/lookup",
        json={"reference": receipt["reference"], "reporter_email": email},
    )
    attachment = lookup.json()["attachments"][0]
    downloaded = client.post(
        f"{settings.API_V1_STR}/public/attachments/download",
        json={
            "reference": receipt["reference"],
            "reporter_email": email,
            "attachment_id": attachment["id"],
        },
    )
    assert downloaded.status_code == 200
    assert (
        downloaded.headers["content-security-policy"] == "default-src 'none'; sandbox"
    )

    followup = client.post(
        f"{settings.API_V1_STR}/public/cases/messages",
        data={
            "reference": receipt["reference"],
            "reporter_email": email,
            "body_markdown": "The lamp is also flickering briefly at dusk.",
        },
        files={"photos": ("follow-up.png", _png(), "image/png")},
    )
    assert followup.status_code == 201
    assert followup.json()["attachments"][0]["media_type"] == "image/png"

    wrong_attachment = client.post(
        f"{settings.API_V1_STR}/public/attachments/download",
        json={
            "reference": receipt["reference"],
            "reporter_email": email,
            "attachment_id": str(uuid.uuid4()),
        },
    )
    assert wrong_attachment.status_code == 404


def test_admin_agent_content_and_webhook_workflows(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    agent_email = f"agent-{uuid.uuid4().hex[:10]}@example.com"
    password = "Initial-agent-password-42"
    created = client.post(
        f"{settings.API_V1_STR}/admin/agents",
        headers=superuser_token_headers,
        json={
            "email": agent_email,
            "full_name": "  Casey   Agent  ",
            "password": password,
            "is_active": True,
        },
    )
    assert created.status_code == 201
    agent_id = created.json()["id"]
    assert created.json()["full_name"] == "Casey Agent"
    assert (
        client.post(
            f"{settings.API_V1_STR}/admin/agents",
            headers=superuser_token_headers,
            json={
                "email": agent_email,
                "full_name": "Duplicate Agent",
                "password": password,
            },
        ).status_code
        == 409
    )
    assert (
        client.get(
            f"{settings.API_V1_STR}/admin/agents", headers=superuser_token_headers
        ).status_code
        == 200
    )

    agent_headers = _login(client, agent_email, password)
    assert (
        client.get(
            f"{settings.API_V1_STR}/admin/agents", headers=agent_headers
        ).status_code
        == 403
    )
    deactivated = client.patch(
        f"{settings.API_V1_STR}/admin/agents/{agent_id}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert (
        client.get(f"{settings.API_V1_STR}/users/me", headers=agent_headers).status_code
        == 400
    )
    assert (
        client.patch(
            f"{settings.API_V1_STR}/admin/agents/{agent_id}",
            headers=superuser_token_headers,
            json={"is_active": True},
        ).status_code
        == 422
    )
    reactivated = client.patch(
        f"{settings.API_V1_STR}/admin/agents/{agent_id}",
        headers=superuser_token_headers,
        json={"is_active": True, "new_password": "Reactivated-password-42"},
    )
    assert reactivated.status_code == 200
    reset = client.post(
        f"{settings.API_V1_STR}/admin/agents/{agent_id}/reset-password",
        headers=superuser_token_headers,
        json={"new_password": "Reset-agent-password-42"},
    )
    assert reset.status_code == 200
    agent_headers = _login(client, agent_email, "Reset-agent-password-42")
    assert (
        client.patch(
            f"{settings.API_V1_STR}/admin/agents/{uuid.uuid4()}",
            headers=superuser_token_headers,
            json={"full_name": "Missing Agent"},
        ).status_code
        == 404
    )

    site = client.get(
        f"{settings.API_V1_STR}/admin/site", headers=superuser_token_headers
    )
    assert site.status_code == 200
    updated_site = client.patch(
        f"{settings.API_V1_STR}/admin/site",
        headers=superuser_token_headers,
        json={
            "organization_name": "Pinehaven Civic Services",
            "service_area": "Pinehaven, Ontario",
            "timezone": "America/Toronto",
            "introduction_markdown": "## Welcome\n\nSubmit a **local** request.",
        },
    )
    assert updated_site.status_code == 200
    assert "<strong>local</strong>" in updated_site.json()["introduction_html"]

    slug = f"test-service-{uuid.uuid4().hex[:8]}"
    new_service = client.post(
        f"{settings.API_V1_STR}/admin/services",
        headers=superuser_token_headers,
        json={
            "slug": slug,
            "name": "Community Tests",
            "summary": "A deterministic category used by integration tests.",
            "guidance_markdown": "Use this category for **testing**.",
            "response_target_hours": 48,
            "sort_order": 900,
            "is_active": True,
        },
    )
    assert new_service.status_code == 201
    service_id = new_service.json()["id"]
    assert (
        client.post(
            f"{settings.API_V1_STR}/admin/services",
            headers=superuser_token_headers,
            json={
                "slug": slug,
                "name": "Community Tests",
                "summary": "A deterministic category used by integration tests.",
                "guidance_markdown": "Duplicate.",
                "response_target_hours": 48,
            },
        ).status_code
        == 409
    )
    assert (
        client.get(
            f"{settings.API_V1_STR}/admin/services", headers=superuser_token_headers
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"{settings.API_V1_STR}/admin/services/{service_id}",
            headers=superuser_token_headers,
            json={"guidance_markdown": "Updated **guidance**.", "is_active": False},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"{settings.API_V1_STR}/admin/services/{uuid.uuid4()}",
            headers=superuser_token_headers,
            json={"is_active": False},
        ).status_code
        == 404
    )

    original_enabled = settings.WEBHOOK_DELIVERY_ENABLED
    try:
        settings.WEBHOOK_DELIVERY_ENABLED = False
        assert (
            client.get(
                f"{settings.API_V1_STR}/admin/webhooks", headers=superuser_token_headers
            ).status_code
            == 404
        )
        settings.WEBHOOK_DELIVERY_ENABLED = True
        assert (
            client.get(
                f"{settings.API_V1_STR}/admin/webhooks", headers=superuser_token_headers
            ).status_code
            == 200
        )
        webhook = client.post(
            f"{settings.API_V1_STR}/admin/webhooks",
            headers=superuser_token_headers,
            json={
                "name": "Municipal event log",
                "url": "https://example.com/desk-hook",
                "subscribed_events": ["case.created", "case.updated"],
            },
        )
        assert webhook.status_code == 201
        webhook_id = webhook.json()["id"]
        assert webhook.json()["signing_secret"]
        changed = client.patch(
            f"{settings.API_V1_STR}/admin/webhooks/{webhook_id}",
            headers=superuser_token_headers,
            json={"name": "Updated event log", "subscribed_events": ["case.closed"]},
        )
        assert changed.status_code == 200
        rotated = client.post(
            f"{settings.API_V1_STR}/admin/webhooks/{webhook_id}/rotate-secret",
            headers=superuser_token_headers,
        )
        assert rotated.status_code == 200
        assert rotated.json()["signing_secret"] != webhook.json()["signing_secret"]
        assert (
            client.post(
                f"{settings.API_V1_STR}/admin/webhooks/{webhook_id}/test",
                headers=superuser_token_headers,
            ).status_code
            == 202
        )
        assert (
            client.patch(
                f"{settings.API_V1_STR}/admin/webhooks/{uuid.uuid4()}",
                headers=superuser_token_headers,
                json={"is_active": False},
            ).status_code
            == 404
        )
    finally:
        settings.WEBHOOK_DELIVERY_ENABLED = original_enabled


def test_staff_lifecycle_permissions_and_account(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    receipt, email = _submit(client)
    service_case = db.exec(
        select(ServiceCase).where(ServiceCase.reference == receipt["reference"])
    ).one()
    agent_email = f"owner-{uuid.uuid4().hex[:10]}@example.com"
    password = "Owner-agent-password-42"
    agent = client.post(
        f"{settings.API_V1_STR}/admin/agents",
        headers=superuser_token_headers,
        json={"email": agent_email, "full_name": "Jordan Owner", "password": password},
    ).json()
    other = client.post(
        f"{settings.API_V1_STR}/admin/agents",
        headers=superuser_token_headers,
        json={
            "email": f"other-{uuid.uuid4().hex[:10]}@example.com",
            "full_name": "Taylor Other",
            "password": "Other-agent-password-42",
        },
    ).json()
    agent_headers = _login(client, agent_email, password)

    assert (
        client.get(
            f"{settings.API_V1_STR}/staff/dashboard", headers=agent_headers
        ).status_code
        == 200
    )
    listing = client.get(
        f"{settings.API_V1_STR}/staff/cases",
        headers=agent_headers,
        params={
            "assignment": "unassigned",
            "search": "Streetlight",
            "priority": "normal",
        },
    )
    assert listing.status_code == 200
    detail = client.get(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}", headers=agent_headers
    )
    assert detail.status_code == 200
    assert detail.headers["etag"] == 'W/"1"'
    assert (
        client.get(
            f"{settings.API_V1_STR}/staff/cases/{uuid.uuid4()}", headers=agent_headers
        ).status_code
        == 404
    )

    assert (
        client.patch(
            f"{settings.API_V1_STR}/staff/cases/{service_case.id}/assignment",
            headers={**agent_headers, "If-Match": "not-an-etag"},
            json={"assigned_to_id": agent["id"]},
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"{settings.API_V1_STR}/staff/cases/{service_case.id}/assignment",
            headers={**agent_headers, "If-Match": 'W/"1"'},
            json={"assigned_to_id": other["id"]},
        ).status_code
        == 403
    )
    claimed = client.patch(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/assignment",
        headers={**agent_headers, "If-Match": '"1"'},
        json={"assigned_to_id": agent["id"]},
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "triaged"
    assert (
        client.patch(
            f"{settings.API_V1_STR}/staff/cases/{service_case.id}/assignment",
            headers={**agent_headers, "If-Match": 'W/"2"'},
            json={"assigned_to_id": None},
        ).status_code
        == 409
    )

    classified = client.patch(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/classification",
        headers={**agent_headers, "If-Match": 'W/"2"'},
        json={"category_id": str(CATEGORIES[1].id), "priority": "urgent"},
    )
    assert classified.status_code == 200
    assert classified.json()["priority"] == "urgent"
    assert (
        client.post(
            f"{settings.API_V1_STR}/staff/cases/{service_case.id}/transition",
            headers={**agent_headers, "If-Match": 'W/"3"'},
            json={"status": "triaged", "summary_markdown": "No change"},
        ).status_code
        == 409
    )
    waiting = client.post(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/transition",
        headers={**agent_headers, "If-Match": 'W/"3"'},
        json={
            "status": "waiting_on_reporter",
            "summary_markdown": "Please add a pole number.",
        },
    )
    assert waiting.status_code == 200

    reporter = client.post(
        f"{settings.API_V1_STR}/public/cases/messages",
        data={
            "reference": receipt["reference"],
            "reporter_email": email,
            "body_markdown": "The pole number is P-184.",
        },
    )
    assert reporter.status_code == 201
    refreshed = client.get(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}", headers=agent_headers
    ).json()
    assert refreshed["status"] == "in_progress"
    version = refreshed["version"]

    staff_message = client.post(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/messages",
        headers={**agent_headers, "If-Match": f'W/"{version}"'},
        data={"body_markdown": "Crew inspection photo.", "visibility": "public"},
        files={"photos": ("inspection.png", _png(), "image/png")},
    )
    assert staff_message.status_code == 201
    staff_photo = staff_message.json()["messages"][-1]["attachments"][0]
    assert (
        client.get(
            f"{settings.API_V1_STR}/staff/attachments/{staff_photo['id']}",
            headers=agent_headers,
        ).status_code
        == 200
    )
    version = staff_message.json()["version"]

    resolved = client.post(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/transition",
        headers={**agent_headers, "If-Match": f'W/"{version}"'},
        json={"status": "resolved", "summary_markdown": "The photocell was replaced."},
    )
    assert resolved.status_code == 200
    closed = client.post(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/transition",
        headers={**agent_headers, "If-Match": f'W/"{resolved.json()["version"]}"'},
        json={"status": "closed", "summary_markdown": "Work confirmed complete."},
    )
    assert closed.status_code == 200
    assert (
        client.post(
            f"{settings.API_V1_STR}/public/cases/messages",
            data={
                "reference": receipt["reference"],
                "reporter_email": email,
                "body_markdown": "A late follow-up.",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{settings.API_V1_STR}/staff/cases/{service_case.id}/transition",
            headers={**agent_headers, "If-Match": f'W/"{closed.json()["version"]}"'},
            json={"status": "in_progress", "summary_markdown": "Reopen request."},
        ).status_code
        == 403
    )
    reopened = client.post(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/transition",
        headers={
            **superuser_token_headers,
            "If-Match": f'W/"{closed.json()["version"]}"',
        },
        json={
            "status": "in_progress",
            "summary_markdown": "Administrator reopened the case.",
        },
    )
    assert reopened.status_code == 200

    current_password = settings.FIRST_SUPERUSER_PASSWORD
    assert (
        client.patch(
            f"{settings.API_V1_STR}/users/me/password",
            headers=superuser_token_headers,
            json={
                "current_password": "incorrect-password",
                "new_password": "Another-password-42",
            },
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"{settings.API_V1_STR}/users/me/password",
            headers=superuser_token_headers,
            json={
                "current_password": current_password,
                "new_password": current_password,
            },
        ).status_code
        == 400
    )

    with Session(db.get_bind()) as session:
        stored_agent = session.get(User, uuid.UUID(agent["id"]))
        assert stored_agent is not None and stored_agent.is_active
        assert stored_agent.updated_at <= datetime.now(UTC)
