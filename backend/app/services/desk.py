import hashlib
import json
import secrets
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.models import (
    Attachment,
    AttachmentPublic,
    AuthorKind,
    CaseEvent,
    CaseEventPublic,
    CaseMessage,
    CaseMessagePublic,
    CasePriority,
    CasePublic,
    CaseStatus,
    ClosureReason,
    ServiceCase,
    ServiceCategory,
    ServiceCategoryPublic,
    StaffCasePublic,
    User,
    UserPublic,
    Visibility,
)
from app.services.content import render_markdown
from app.services.storage import StoredImage
from app.services.webhooks import enqueue_for_event

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
REFERENCE_ATTEMPTS = 8


def now_utc() -> datetime:
    return datetime.now(UTC)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def generate_reference() -> str:
    return "TDK-" + "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(20))


def masked_email(value: str) -> str:
    local, _, domain = value.partition("@")
    visible = local[:1]
    return f"{visible}{'*' * max(3, len(local) - 1)}@{domain}"


def user_public(user: User) -> UserPublic:
    return UserPublic(
        **user.model_dump(),
        role="administrator" if user.is_superuser else "agent",
    )


def category_public(category: ServiceCategory) -> ServiceCategoryPublic:
    return ServiceCategoryPublic.model_validate(category)


def submission_digest(values: Mapping[str, object], images: list[StoredImage]) -> str:
    normalized = json.dumps(values, sort_keys=True, separators=(",", ":"))
    digests = ":".join(image.sha256 for image in images)
    return hashlib.sha256(f"{normalized}:{digests}".encode()).hexdigest()


def lock_case(session: Session, case_id: uuid.UUID) -> ServiceCase:
    case = session.exec(
        select(ServiceCase).where(ServiceCase.id == case_id).with_for_update()
    ).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def check_version(service_case: ServiceCase, expected: int | None) -> None:
    if expected is None:
        raise HTTPException(status_code=428, detail="If-Match is required")
    if expected != service_case.version:
        raise HTTPException(
            status_code=412, detail="Case changed; reload and try again"
        )


def require_case_owner(service_case: ServiceCase, user: User) -> None:
    if user.is_superuser:
        return
    if service_case.assigned_to_id != user.id:
        raise HTTPException(status_code=403, detail="Case is assigned to another agent")


def get_case_for_credentials(
    session: Session, *, reference: str, reporter_email: str, lock: bool = False
) -> ServiceCase:
    statement = select(ServiceCase).where(
        ServiceCase.reference == reference.strip().upper(),
        ServiceCase.reporter_email == normalize_email(reporter_email),
    )
    if lock:
        statement = statement.with_for_update()
    service_case = session.exec(statement).first()
    if service_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return service_case


def add_event(
    session: Session,
    *,
    service_case: ServiceCase,
    event_type: str,
    summary: str,
    visibility: Visibility = Visibility.public,
    actor_user_id: uuid.UUID | None = None,
    from_status: CaseStatus | None = None,
    to_status: CaseStatus | None = None,
    message_id: uuid.UUID | None = None,
) -> CaseEvent:
    event = CaseEvent(
        case_id=service_case.id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        visibility=visibility,
        from_status=from_status,
        to_status=to_status,
        summary=summary,
        message_id=message_id,
    )
    session.add(event)
    session.flush()
    enqueue_for_event(session, event=event, service_case=service_case)
    return event


def add_attachments(
    session: Session,
    *,
    service_case: ServiceCase,
    message_id: uuid.UUID | None,
    images: list[StoredImage],
    uploader_kind: AuthorKind,
    uploaded_by_user_id: uuid.UUID | None = None,
) -> None:
    existing = session.exec(
        select(func.count())
        .select_from(Attachment)
        .where(Attachment.case_id == service_case.id)
    ).one()
    if existing + len(images) > 8:
        raise HTTPException(
            status_code=409, detail="A case can contain at most eight photos"
        )
    existing_bytes = session.exec(
        select(func.coalesce(func.sum(Attachment.byte_count), 0)).where(
            Attachment.case_id == service_case.id
        )
    ).one()
    if existing_bytes + sum(image.byte_count for image in images) > 32 * 1024 * 1024:
        raise HTTPException(
            status_code=409, detail="A case can contain at most 32 MiB of photos"
        )
    for image in images:
        session.add(
            Attachment(
                case_id=service_case.id,
                message_id=message_id,
                uploaded_by_user_id=uploaded_by_user_id,
                uploader_kind=uploader_kind,
                storage_key=image.storage_key,
                display_name=image.display_name,
                media_type=image.media_type,
                byte_count=image.byte_count,
                sha256=image.sha256,
                width=image.width,
                height=image.height,
            )
        )


def create_case(
    session: Session,
    *,
    submission_id: uuid.UUID,
    reporter_name: str,
    reporter_email: str,
    category_id: uuid.UUID,
    subject: str,
    description: str,
    location_text: str,
    images: list[StoredImage],
) -> tuple[ServiceCase, bool]:
    category = session.get(ServiceCategory, category_id)
    if category is None or not category.is_active:
        raise HTTPException(status_code=422, detail="Service category is unavailable")
    values = {
        "submission_id": str(submission_id),
        "reporter_name": " ".join(reporter_name.split()),
        "reporter_email": normalize_email(reporter_email),
        "category_id": str(category_id),
        "subject": " ".join(subject.split()),
        "description": description.strip(),
        "location_text": " ".join(location_text.split()),
    }
    digest = submission_digest(values, images)
    existing = session.exec(
        select(ServiceCase).where(ServiceCase.public_submission_id == submission_id)
    ).first()
    if existing is not None:
        if existing.submission_hash != digest:
            raise HTTPException(
                status_code=409, detail="Submission ID was already used"
            )
        return existing, False
    for _ in range(REFERENCE_ATTEMPTS):
        service_case = ServiceCase(
            reference=generate_reference(),
            public_submission_id=submission_id,
            submission_hash=digest,
            reporter_name=values["reporter_name"],
            reporter_email=values["reporter_email"],
            category_id=category.id,
            subject=values["subject"],
            description=values["description"],
            location_text=values["location_text"],
            target_resolution_at=now_utc()
            + timedelta(hours=category.response_target_hours),
        )
        try:
            with session.begin_nested():
                session.add(service_case)
                session.flush()
                add_attachments(
                    session,
                    service_case=service_case,
                    message_id=None,
                    images=images,
                    uploader_kind=AuthorKind.reporter,
                )
                add_event(
                    session,
                    service_case=service_case,
                    event_type="created",
                    summary="Request received",
                )
            session.commit()
            session.refresh(service_case)
            return service_case, True
        except IntegrityError as exc:
            session.rollback()
            if "reference" not in str(exc):
                raise
    raise HTTPException(status_code=503, detail="Could not allocate a case reference")


def add_message(
    session: Session,
    *,
    service_case: ServiceCase,
    body_markdown: str,
    visibility: Visibility,
    author_kind: AuthorKind,
    images: list[StoredImage],
    actor_user: User | None = None,
) -> CaseMessage:
    message = CaseMessage(
        case_id=service_case.id,
        author_kind=author_kind,
        author_user_id=actor_user.id if actor_user else None,
        visibility=visibility,
        body_markdown=body_markdown.strip(),
        body_html=render_markdown(body_markdown),
    )
    session.add(message)
    session.flush()
    add_attachments(
        session,
        service_case=service_case,
        message_id=message.id,
        images=images,
        uploader_kind=author_kind,
        uploaded_by_user_id=actor_user.id if actor_user else None,
    )
    from_status = service_case.status
    if (
        author_kind == AuthorKind.reporter
        and service_case.status == CaseStatus.waiting_on_reporter
    ):
        service_case.status = CaseStatus.in_progress
    service_case.version += 1
    service_case.updated_at = now_utc()
    session.add(service_case)
    add_event(
        session,
        service_case=service_case,
        event_type="message",
        summary=(
            "Reporter added information"
            if author_kind == AuthorKind.reporter
            else "Civic services posted an update"
        ),
        visibility=visibility,
        actor_user_id=actor_user.id if actor_user else None,
        from_status=from_status if from_status != service_case.status else None,
        to_status=service_case.status if from_status != service_case.status else None,
        message_id=message.id,
    )
    session.commit()
    session.refresh(message)
    return message


def _attachments_for_message(
    session: Session, message_id: uuid.UUID
) -> list[AttachmentPublic]:
    rows = session.exec(
        select(Attachment)
        .where(Attachment.message_id == message_id)
        .order_by(col(Attachment.created_at))
    ).all()
    return [AttachmentPublic.model_validate(row) for row in rows]


def _initial_attachments(
    session: Session, case_id: uuid.UUID
) -> list[AttachmentPublic]:
    rows = session.exec(
        select(Attachment)
        .where(
            Attachment.case_id == case_id,
            col(Attachment.message_id).is_(None),
        )
        .order_by(col(Attachment.created_at))
    ).all()
    return [AttachmentPublic.model_validate(row) for row in rows]


def _messages(
    session: Session, case_id: uuid.UUID, *, public_only: bool
) -> list[CaseMessagePublic]:
    filters = [CaseMessage.case_id == case_id]
    if public_only:
        filters.append(CaseMessage.visibility == Visibility.public)
    rows = session.exec(
        select(CaseMessage).where(*filters).order_by(col(CaseMessage.created_at))
    ).all()
    result: list[CaseMessagePublic] = []
    for row in rows:
        author_label = (
            "Resident"
            if row.author_kind == AuthorKind.reporter
            else "Civic services team"
        )
        result.append(
            CaseMessagePublic(
                id=row.id,
                author_label=author_label,
                body_html=row.body_html,
                created_at=row.created_at,
                attachments=_attachments_for_message(session, row.id),
            )
        )
    return result


def _events(
    session: Session, case_id: uuid.UUID, *, public_only: bool
) -> list[CaseEventPublic]:
    filters = [CaseEvent.case_id == case_id]
    if public_only:
        filters.append(CaseEvent.visibility == Visibility.public)
    rows = session.exec(
        select(CaseEvent).where(*filters).order_by(col(CaseEvent.created_at))
    ).all()
    return [CaseEventPublic.model_validate(row) for row in rows]


def public_case(session: Session, service_case: ServiceCase) -> CasePublic:
    category = session.get(ServiceCategory, service_case.category_id)
    if category is None:
        raise RuntimeError("Case category is missing")
    return CasePublic(
        reference=service_case.reference,
        category=category_public(category),
        subject=service_case.subject,
        description=service_case.description,
        location_text=service_case.location_text,
        status=service_case.status,
        created_at=service_case.created_at,
        updated_at=service_case.updated_at,
        attachments=_initial_attachments(session, service_case.id),
        messages=_messages(session, service_case.id, public_only=True),
        events=_events(session, service_case.id, public_only=True),
    )


def staff_case(session: Session, service_case: ServiceCase) -> StaffCasePublic:
    category = session.get(ServiceCategory, service_case.category_id)
    if category is None:
        raise RuntimeError("Case category is missing")
    assignee = (
        session.get(User, service_case.assigned_to_id)
        if service_case.assigned_to_id
        else None
    )
    return StaffCasePublic(
        **service_case.model_dump(warnings=False),
        category=category_public(category),
        assigned_to=user_public(assignee) if assignee else None,
        attachments=_initial_attachments(session, service_case.id),
        messages=_messages(session, service_case.id, public_only=False),
        events=_events(session, service_case.id, public_only=False),
    )


def assign_case(
    session: Session,
    *,
    case_id: uuid.UUID,
    target_user_id: uuid.UUID | None,
    actor: User,
    expected_version: int | None,
) -> ServiceCase:
    service_case = lock_case(session, case_id)
    check_version(service_case, expected_version)
    if target_user_id is None:
        if service_case.status != CaseStatus.submitted:
            raise HTTPException(
                status_code=409, detail="Active cases must remain assigned"
            )
    else:
        target = session.get(User, target_user_id)
        if target is None or not target.is_active:
            raise HTTPException(status_code=422, detail="Assignee must be active")
        if not actor.is_superuser and target.id != actor.id:
            raise HTTPException(
                status_code=403, detail="Agents can assign only to themselves"
            )
    if not actor.is_superuser and service_case.assigned_to_id not in {None, actor.id}:
        raise HTTPException(status_code=409, detail="Case was claimed by another agent")
    from_status = service_case.status
    service_case.assigned_to_id = target_user_id
    if target_user_id and service_case.status == CaseStatus.submitted:
        service_case.status = CaseStatus.triaged
    service_case.version += 1
    service_case.updated_at = now_utc()
    session.add(service_case)
    add_event(
        session,
        service_case=service_case,
        event_type="assigned",
        summary="Request assigned to civic services staff",
        actor_user_id=actor.id,
        from_status=from_status if from_status != service_case.status else None,
        to_status=service_case.status if from_status != service_case.status else None,
    )
    session.commit()
    session.refresh(service_case)
    return service_case


def classify_case(
    session: Session,
    *,
    case_id: uuid.UUID,
    category_id: uuid.UUID | None,
    priority: CasePriority | None,
    actor: User,
    expected_version: int | None,
) -> ServiceCase:
    service_case = lock_case(session, case_id)
    check_version(service_case, expected_version)
    require_case_owner(service_case, actor)
    if category_id is not None:
        category = session.get(ServiceCategory, category_id)
        if category is None or not category.is_active:
            raise HTTPException(
                status_code=422, detail="Service category is unavailable"
            )
        service_case.category_id = category.id
        service_case.target_resolution_at = service_case.created_at + timedelta(
            hours=category.response_target_hours
        )
    if priority is not None:
        service_case.priority = priority
    service_case.version += 1
    service_case.updated_at = now_utc()
    session.add(service_case)
    add_event(
        session,
        service_case=service_case,
        event_type="classified",
        summary="Request classification updated",
        visibility=Visibility.private,
        actor_user_id=actor.id,
    )
    session.commit()
    session.refresh(service_case)
    return service_case


def transition_case(
    session: Session,
    *,
    case_id: uuid.UUID,
    new_status: CaseStatus,
    summary_markdown: str,
    closure_reason: ClosureReason | None,
    duplicate_case_id: uuid.UUID | None,
    actor: User,
    expected_version: int | None,
) -> ServiceCase:
    service_case = lock_case(session, case_id)
    check_version(service_case, expected_version)
    require_case_owner(service_case, actor)
    allowed = {
        CaseStatus.submitted: {CaseStatus.triaged},
        CaseStatus.triaged: {
            CaseStatus.in_progress,
            CaseStatus.waiting_on_reporter,
            CaseStatus.resolved,
            CaseStatus.closed,
        },
        CaseStatus.in_progress: {
            CaseStatus.waiting_on_reporter,
            CaseStatus.resolved,
            CaseStatus.closed,
        },
        CaseStatus.waiting_on_reporter: {
            CaseStatus.in_progress,
            CaseStatus.resolved,
            CaseStatus.closed,
        },
        CaseStatus.resolved: {CaseStatus.closed, CaseStatus.in_progress},
        CaseStatus.closed: {CaseStatus.in_progress},
    }
    if new_status not in allowed[service_case.status]:
        raise HTTPException(status_code=409, detail="Invalid case transition")
    if new_status == CaseStatus.triaged and service_case.assigned_to_id is None:
        raise HTTPException(status_code=409, detail="Triaged cases require an assignee")
    if service_case.status == CaseStatus.closed and not actor.is_superuser:
        raise HTTPException(
            status_code=403, detail="Only administrators can reopen closed cases"
        )
    if new_status == CaseStatus.closed:
        reason = closure_reason or (
            ClosureReason.resolved
            if service_case.status == CaseStatus.resolved
            else None
        )
        if reason is None:
            raise HTTPException(status_code=422, detail="Closure reason is required")
        if (
            service_case.status != CaseStatus.resolved
            and reason == ClosureReason.resolved
        ):
            raise HTTPException(
                status_code=422,
                detail="Unresolved work requires duplicate, out_of_scope, or withdrawn",
            )
        if (
            service_case.status == CaseStatus.resolved
            and reason != ClosureReason.resolved
        ):
            raise HTTPException(
                status_code=422,
                detail="Resolved work must use the resolved closure reason",
            )
        if reason == ClosureReason.duplicate:
            if duplicate_case_id is None or duplicate_case_id == service_case.id:
                raise HTTPException(
                    status_code=422, detail="Duplicate case is required"
                )
            if session.get(ServiceCase, duplicate_case_id) is None:
                raise HTTPException(
                    status_code=422, detail="Duplicate case was not found"
                )
        service_case.closure_reason = reason
        service_case.duplicate_case_id = duplicate_case_id
        service_case.closed_at = now_utc()
    else:
        service_case.closed_at = None
        service_case.closure_reason = None
        service_case.duplicate_case_id = None
    if new_status == CaseStatus.resolved:
        service_case.resolved_at = now_utc()
    elif new_status == CaseStatus.in_progress:
        service_case.resolved_at = None
    previous = service_case.status
    service_case.status = new_status
    service_case.version += 1
    service_case.updated_at = now_utc()
    session.add(service_case)
    add_event(
        session,
        service_case=service_case,
        event_type=(
            "resolved"
            if new_status == CaseStatus.resolved
            else "closed"
            if new_status == CaseStatus.closed
            else "status_changed"
        ),
        summary=" ".join(summary_markdown.split()),
        actor_user_id=actor.id,
        from_status=previous,
        to_status=new_status,
    )
    session.commit()
    session.refresh(service_case)
    return service_case
