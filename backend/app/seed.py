import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlmodel import Session, select

from app.core.security import get_password_hash
from app.models import (
    CaseEvent,
    CasePriority,
    CaseStatus,
    ClosureReason,
    ServiceCase,
    ServiceCategory,
    SiteSettings,
    User,
    Visibility,
)
from app.services.content import render_markdown
from app.services.desk import generate_reference


@dataclass(frozen=True)
class SeedCategory:
    id: uuid.UUID
    slug: str
    name: str
    summary: str
    guidance: str
    hours: int
    order: int


CATEGORIES = (
    SeedCategory(
        uuid.UUID("10000000-0000-4000-8000-000000000001"),
        "streets-sidewalks",
        "Streets & sidewalks",
        "Report damaged pavement, signs, lighting, and pedestrian routes.",
        "## What to include\n\nGive the nearest address or intersection and describe the hazard clearly.",
        72,
        10,
    ),
    SeedCategory(
        uuid.UUID("10000000-0000-4000-8000-000000000002"),
        "parks-trees",
        "Parks & trees",
        "Share concerns about public trees, trails, playgrounds, and park fixtures.",
        "## What to include\n\nName the park or trail and add a photo when it helps identify the location.",
        120,
        20,
    ),
    SeedCategory(
        uuid.UUID("10000000-0000-4000-8000-000000000003"),
        "waste-recycling",
        "Waste & recycling",
        "Request help with missed collections, public bins, or illegal dumping.",
        "## What to include\n\nTell us the collection type, location, and when the issue was first noticed.",
        48,
        30,
    ),
    SeedCategory(
        uuid.UUID("10000000-0000-4000-8000-000000000004"),
        "public-facilities",
        "Public facilities",
        "Report maintenance issues at civic buildings and community spaces.",
        "## What to include\n\nName the facility and describe the room, entrance, or fixture involved.",
        96,
        40,
    ),
    SeedCategory(
        uuid.UUID("10000000-0000-4000-8000-000000000005"),
        "accessibility",
        "Accessibility",
        "Request review of barriers affecting access to municipal services.",
        "## What to include\n\nDescribe the barrier and the route or service it affects. Urgent safety matters should use emergency services.",
        48,
        50,
    ),
)


def seed_site(session: Session) -> None:
    if session.get(SiteSettings, 1) is None:
        introduction = (
            "Pinehaven Civic Services helps residents report everyday public-space "
            "issues and follow each request from intake to resolution."
        )
        session.add(
            SiteSettings(
                organization_name="Pinehaven Civic Services",
                service_area="Pinehaven, Canada",
                timezone="America/Toronto",
                introduction_markdown=introduction,
                introduction_html=render_markdown(introduction),
            )
        )
        session.commit()


def seed_categories(session: Session) -> None:
    for item in CATEGORIES:
        if session.get(ServiceCategory, item.id) is None:
            session.add(
                ServiceCategory(
                    id=item.id,
                    slug=item.slug,
                    name=item.name,
                    summary=item.summary,
                    guidance_markdown=item.guidance,
                    guidance_html=render_markdown(item.guidance),
                    response_target_hours=item.hours,
                    sort_order=item.order,
                )
            )
    session.commit()


def seed_agents(session: Session) -> list[User]:
    result: list[User] = []
    for identifier, email, name in (
        (
            uuid.UUID("20000000-0000-4000-8000-000000000001"),
            "maya.chen@example.invalid",
            "Maya Chen",
        ),
        (
            uuid.UUID("20000000-0000-4000-8000-000000000002"),
            "jonah.reed@example.invalid",
            "Jonah Reed",
        ),
    ):
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            user = User(
                id=identifier,
                email=email,
                full_name=name,
                is_active=False,
                is_superuser=False,
                hashed_password=get_password_hash(secrets.token_urlsafe(48)),
            )
            session.add(user)
        result.append(user)
    session.commit()
    return result


def seed_cases(
    session: Session,
    *,
    superuser: User,
    anchor_date: date | None = None,
) -> None:
    if session.exec(select(ServiceCase.id).limit(1)).first() is not None:
        return
    anchor = anchor_date or datetime.now(UTC).date()
    statuses = (
        CaseStatus.submitted,
        CaseStatus.submitted,
        CaseStatus.triaged,
        CaseStatus.in_progress,
        CaseStatus.waiting_on_reporter,
        CaseStatus.resolved,
        CaseStatus.closed,
        CaseStatus.in_progress,
        CaseStatus.triaged,
        CaseStatus.resolved,
        CaseStatus.closed,
        CaseStatus.waiting_on_reporter,
        CaseStatus.in_progress,
        CaseStatus.submitted,
    )
    priorities = (
        CasePriority.normal,
        CasePriority.high,
        CasePriority.low,
        CasePriority.urgent,
    )
    subjects = (
        "Streetlight flickering near the library",
        "Pothole beside the eastbound bicycle lane",
        "Playground gate does not close securely",
        "Overflowing public bin at Station Square",
        "Need a curb-ramp review at Cedar and Third",
        "Graffiti removal at the community centre",
        "Duplicate report for fallen branch",
        "Loose handrail at the arena entrance",
        "Trail marker missing in Riverside Park",
        "Missed recycling collection on Pine Street",
        "Public fountain unavailable for winter",
        "More details needed for damaged bench",
        "Crosswalk signal button responds slowly",
        "Broken glass near the south bus shelter",
    )
    locations = (
        "14 Civic Way",
        "Cedar Avenue at Third Street",
        "Riverside Park north entrance",
        "Station Square",
    )
    for index, status in enumerate(statuses):
        created = datetime.combine(anchor - timedelta(days=14 - index), time(14), UTC)
        assigned = None if status == CaseStatus.submitted else superuser.id
        resolved_at = (
            created + timedelta(days=2)
            if status in {CaseStatus.resolved, CaseStatus.closed}
            else None
        )
        closed_at = created + timedelta(days=3) if status == CaseStatus.closed else None
        service_case = ServiceCase(
            id=uuid.UUID(f"30000000-0000-4000-8000-{index + 1:012d}"),
            reference=generate_reference(),
            public_submission_id=uuid.UUID(f"40000000-0000-4000-8000-{index + 1:012d}"),
            submission_hash=secrets.token_hex(32),
            reporter_name=("Avery Morgan", "Samir Patel", "Noah Tremblay")[index % 3],
            reporter_email=(
                "avery@example.invalid",
                "samir@example.invalid",
                "noah@example.invalid",
            )[index % 3],
            category_id=CATEGORIES[index % len(CATEGORIES)].id,
            subject=subjects[index],
            description="A resident submitted a clear description so civic services can inspect and respond.",
            location_text=locations[index % len(locations)],
            status=status,
            priority=priorities[index % len(priorities)],
            assigned_to_id=assigned,
            target_resolution_at=created
            + timedelta(hours=CATEGORIES[index % len(CATEGORIES)].hours),
            resolved_at=resolved_at,
            closed_at=closed_at,
            closure_reason=ClosureReason.resolved
            if status == CaseStatus.closed
            else None,
            created_at=created,
            updated_at=closed_at or resolved_at or created,
        )
        session.add(service_case)
        session.flush()
        session.add(
            CaseEvent(
                case_id=service_case.id,
                event_type="created",
                visibility=Visibility.public,
                summary="Request received",
                to_status=CaseStatus.submitted,
                created_at=created,
            )
        )
    session.commit()


def seed_catalog(
    session: Session, *, superuser: User | None = None, anchor_date: date | None = None
) -> None:
    seed_site(session)
    seed_categories(session)
    seed_agents(session)
    if superuser is None:
        superuser = session.exec(select(User).where(User.is_superuser == True)).first()  # noqa: E712
    if superuser is not None:
        seed_cases(session, superuser=superuser, anchor_date=anchor_date)
