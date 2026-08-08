import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.config import settings
from app.models import CaseMessage, ServiceCase, ServiceCategory, Visibility
from app.seed import CATEGORIES, seed_catalog


def submit_case(client: TestClient) -> tuple[dict[str, object], str]:
    email = f"resident-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        f"{settings.API_V1_STR}/public/cases",
        data={
            "submission_id": str(uuid.uuid4()),
            "reporter_name": "Avery Resident",
            "reporter_email": email,
            "category_id": str(CATEGORIES[0].id),
            "subject": "Sidewalk panel is raised",
            "description": "One concrete panel is raised enough to create a clear tripping hazard.",
            "location_text": "12 Cedar Avenue",
        },
    )
    assert response.status_code == 201
    return response.json(), email


def test_seed_is_idempotent_and_complete(db: Session) -> None:
    before_cases = db.exec(select(func.count()).select_from(ServiceCase)).one()
    before_categories = db.exec(select(func.count()).select_from(ServiceCategory)).one()
    seed_catalog(db, anchor_date=date(2030, 1, 1))
    seed_catalog(db, anchor_date=date(2030, 1, 1))
    assert db.exec(select(func.count()).select_from(ServiceCase)).one() == before_cases
    assert (
        db.exec(select(func.count()).select_from(ServiceCategory)).one()
        == before_categories
    )
    for category in CATEGORIES:
        assert db.get(ServiceCategory, category.id) is not None


def test_public_submission_lookup_and_generic_failure(client: TestClient) -> None:
    receipt, email = submit_case(client)
    assert str(receipt["reference"]).startswith("TDK-")
    assert len(str(receipt["reference"])) == 24
    lookup = client.post(
        f"{settings.API_V1_STR}/public/cases/lookup",
        json={
            "reference": str(receipt["reference"]).lower(),
            "reporter_email": email.upper(),
        },
    )
    assert lookup.status_code == 200
    assert lookup.headers["cache-control"] == "no-store"
    wrong_reference = client.post(
        f"{settings.API_V1_STR}/public/cases/lookup",
        json={"reference": "TDK-00000000000000000000", "reporter_email": email},
    )
    wrong_email = client.post(
        f"{settings.API_V1_STR}/public/cases/lookup",
        json={"reference": receipt["reference"], "reporter_email": "other@example.com"},
    )
    assert wrong_reference.status_code == wrong_email.status_code == 404
    assert wrong_reference.json() == wrong_email.json()
    assert wrong_reference.headers["cache-control"] == "no-store"


def test_submission_id_is_retry_safe(client: TestClient) -> None:
    submission_id = str(uuid.uuid4())
    body = {
        "submission_id": submission_id,
        "reporter_name": "Retry Resident",
        "reporter_email": "retry@example.com",
        "category_id": str(CATEGORIES[1].id),
        "subject": "Damaged park bench",
        "description": "The eastern seat board is split and should be inspected by staff.",
        "location_text": "Riverside Park",
    }
    first = client.post(f"{settings.API_V1_STR}/public/cases", data=body)
    second = client.post(f"{settings.API_V1_STR}/public/cases", data=body)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["reference"] == second.json()["reference"]
    changed = client.post(
        f"{settings.API_V1_STR}/public/cases",
        data={**body, "description": body["description"] + " Changed."},
    )
    assert changed.status_code == 409


def test_claim_private_note_stale_version_and_public_isolation(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    receipt, email = submit_case(client)
    service_case = db.exec(
        select(ServiceCase).where(ServiceCase.reference == receipt["reference"])
    ).one()
    me = client.get(
        f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers
    ).json()
    claimed = client.patch(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/assignment",
        headers={**superuser_token_headers, "If-Match": 'W/"1"'},
        json={"assigned_to_id": me["id"]},
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "triaged"
    noted = client.post(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/messages",
        headers={**superuser_token_headers, "If-Match": 'W/"2"'},
        data={"body_markdown": "Internal inspection note", "visibility": "private"},
    )
    assert noted.status_code == 201
    assert noted.json()["version"] == 3
    stale = client.post(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/messages",
        headers={**superuser_token_headers, "If-Match": 'W/"2"'},
        data={"body_markdown": "Stale write", "visibility": "private"},
    )
    assert stale.status_code == 412
    assert stale.json()["code"] == "stale_case"
    public = client.post(
        f"{settings.API_V1_STR}/public/cases/lookup",
        json={"reference": receipt["reference"], "reporter_email": email},
    ).json()
    assert all("Internal" not in message["body_html"] for message in public["messages"])
    assert (
        db.exec(
            select(func.count())
            .select_from(CaseMessage)
            .where(CaseMessage.visibility == Visibility.private)
        ).one()
        >= 1
    )


def test_staff_mutations_require_if_match(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    service_case = db.exec(select(ServiceCase).limit(1)).one()
    response = client.patch(
        f"{settings.API_V1_STR}/staff/cases/{service_case.id}/classification",
        headers=superuser_token_headers,
        json={"priority": "high"},
    )
    assert response.status_code == 428
    assert response.json()["code"] == "precondition_required"
