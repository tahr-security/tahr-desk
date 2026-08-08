import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlmodel import col, func, or_, select

from app.api.deps import SessionDep, get_current_active_staff
from app.models import (
    AssignmentUpdate,
    Attachment,
    AuthorKind,
    CasePriority,
    CaseStatus,
    ClassificationUpdate,
    DashboardStats,
    ExportCreate,
    ExportJob,
    ExportPublic,
    ExportsPublic,
    JobStatus,
    ServiceCase,
    StaffCasePublic,
    StaffCasesPublic,
    TransitionRequest,
    User,
    Visibility,
)
from app.services.desk import (
    add_message,
    assign_case,
    check_version,
    classify_case,
    lock_case,
    require_case_owner,
    staff_case,
    transition_case,
)
from app.services.storage import remove_stored_image, storage_path, store_image

router = APIRouter(
    prefix="/staff",
    tags=["staff"],
    dependencies=[Depends(get_current_active_staff)],
)


def expected_version(if_match: str | None) -> int | None:
    if if_match is None:
        return None
    value = if_match.strip()
    if value.startswith('W/"') and value.endswith('"'):
        value = value[3:-1]
    elif value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    try:
        return int(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="If-Match is invalid")


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard(
    session: SessionDep, current_user: User = Depends(get_current_active_staff)
) -> DashboardStats:
    open_statuses = (
        CaseStatus.submitted,
        CaseStatus.triaged,
        CaseStatus.in_progress,
        CaseStatus.waiting_on_reporter,
    )
    now = datetime.now(UTC)
    mine = session.exec(
        select(func.count())
        .select_from(ServiceCase)
        .where(
            ServiceCase.assigned_to_id == current_user.id,
            col(ServiceCase.status).in_(open_statuses),
        )
    ).one()
    unassigned = session.exec(
        select(func.count())
        .select_from(ServiceCase)
        .where(
            col(ServiceCase.assigned_to_id).is_(None),
            ServiceCase.status == CaseStatus.submitted,
        )  # noqa: E711
    ).one()
    overdue = session.exec(
        select(func.count())
        .select_from(ServiceCase)
        .where(
            col(ServiceCase.status).in_(open_statuses),
            ServiceCase.target_resolution_at < now,
        )
    ).one()
    open_total = session.exec(
        select(func.count())
        .select_from(ServiceCase)
        .where(col(ServiceCase.status).in_(open_statuses))
    ).one()
    resolved = session.exec(
        select(func.count())
        .select_from(ServiceCase)
        .where(col(ServiceCase.resolved_at) >= now - timedelta(days=7))
    ).one()
    return DashboardStats(
        mine=mine,
        unassigned=unassigned,
        overdue=overdue,
        open_total=open_total,
        resolved_last_7_days=resolved,
    )


@router.get("/cases", response_model=StaffCasesPublic)
def list_cases(
    session: SessionDep,
    current_user: User = Depends(get_current_active_staff),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    status_filter: CaseStatus | None = Query(default=None, alias="status"),
    priority: CasePriority | None = None,
    assignment: str | None = Query(default=None, pattern=r"^(mine|unassigned|all)$"),
    search: str | None = Query(default=None, min_length=2, max_length=120),
) -> StaffCasesPublic:
    filters: list[Any] = []
    if status_filter:
        filters.append(ServiceCase.status == status_filter)
    if priority:
        filters.append(ServiceCase.priority == priority)
    if assignment == "mine":
        filters.append(ServiceCase.assigned_to_id == current_user.id)
    elif assignment == "unassigned":
        filters.append(col(ServiceCase.assigned_to_id).is_(None))
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                col(ServiceCase.reference).ilike(pattern),
                col(ServiceCase.subject).ilike(pattern),
                col(ServiceCase.location_text).ilike(pattern),
                col(ServiceCase.reporter_name).ilike(pattern),
                col(ServiceCase.reporter_email).ilike(pattern),
            )
        )
    count = session.exec(
        select(func.count()).select_from(ServiceCase).where(*filters)
    ).one()
    cases = session.exec(
        select(ServiceCase)
        .where(*filters)
        .order_by(col(ServiceCase.updated_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return StaffCasesPublic(
        data=[staff_case(session, item) for item in cases], count=count
    )


@router.get("/cases/{case_id}", response_model=StaffCasePublic)
def get_case(
    case_id: uuid.UUID, response: Response, session: SessionDep
) -> StaffCasePublic:
    service_case = session.get(ServiceCase, case_id)
    if service_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    response.headers["ETag"] = f'W/"{service_case.version}"'
    return staff_case(session, service_case)


@router.patch("/cases/{case_id}/assignment", response_model=StaffCasePublic)
def update_assignment(
    case_id: uuid.UUID,
    body: AssignmentUpdate,
    session: SessionDep,
    current_user: User = Depends(get_current_active_staff),
    if_match: Annotated[str | None, Header()] = None,
) -> StaffCasePublic:
    item = assign_case(
        session,
        case_id=case_id,
        target_user_id=body.assigned_to_id,
        actor=current_user,
        expected_version=expected_version(if_match),
    )
    return staff_case(session, item)


@router.patch("/cases/{case_id}/classification", response_model=StaffCasePublic)
def update_classification(
    case_id: uuid.UUID,
    body: ClassificationUpdate,
    session: SessionDep,
    current_user: User = Depends(get_current_active_staff),
    if_match: Annotated[str | None, Header()] = None,
) -> StaffCasePublic:
    item = classify_case(
        session,
        case_id=case_id,
        category_id=body.category_id,
        priority=body.priority,
        actor=current_user,
        expected_version=expected_version(if_match),
    )
    return staff_case(session, item)


@router.post("/cases/{case_id}/transition", response_model=StaffCasePublic)
def update_status(
    case_id: uuid.UUID,
    body: TransitionRequest,
    session: SessionDep,
    current_user: User = Depends(get_current_active_staff),
    if_match: Annotated[str | None, Header()] = None,
) -> StaffCasePublic:
    item = transition_case(
        session,
        case_id=case_id,
        new_status=body.status,
        summary_markdown=body.summary_markdown,
        closure_reason=body.closure_reason,
        duplicate_case_id=body.duplicate_case_id,
        actor=current_user,
        expected_version=expected_version(if_match),
    )
    return staff_case(session, item)


@router.post(
    "/cases/{case_id}/messages", response_model=StaffCasePublic, status_code=201
)
async def create_message(
    case_id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_active_staff),
    body_markdown: Annotated[str, Form(min_length=1, max_length=10000)] = "",
    visibility: Annotated[Visibility, Form()] = Visibility.public,
    photos: Annotated[list[UploadFile] | None, File()] = None,
    if_match: Annotated[str | None, Header()] = None,
) -> StaffCasePublic:
    photos = photos or []
    if len(photos) > 4:
        raise HTTPException(status_code=422, detail="Add at most four photos")
    service_case = lock_case(session, case_id)
    check_version(service_case, expected_version(if_match))
    require_case_owner(service_case, current_user)
    images = [await store_image(photo) for photo in photos]
    try:
        add_message(
            session,
            service_case=service_case,
            body_markdown=body_markdown,
            visibility=visibility,
            author_kind=AuthorKind.staff,
            images=images,
            actor_user=current_user,
        )
    except Exception:
        for image in images:
            remove_stored_image(image)
        raise
    return staff_case(session, service_case)


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: uuid.UUID, session: SessionDep) -> Response:
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = storage_path(attachment.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment not found")
    return Response(
        content=path.read_bytes(),
        media_type=attachment.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="{attachment.display_name}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/exports", response_model=ExportPublic, status_code=202)
def create_export(
    body: ExportCreate,
    session: SessionDep,
    current_user: User = Depends(get_current_active_staff),
) -> ExportPublic:
    existing = session.exec(
        select(ExportJob).where(
            ExportJob.requested_by_id == current_user.id,
            ExportJob.idempotency_key == body.idempotency_key,
        )
    ).first()
    if existing:
        return ExportPublic.model_validate(existing)
    if body.kind == "case_pdf" and body.case_id is None:
        raise HTTPException(
            status_code=422, detail="case_id is required for PDF exports"
        )
    if body.case_id is not None and session.get(ServiceCase, body.case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    job = ExportJob(
        requested_by_id=current_user.id,
        kind=body.kind,
        case_id=body.case_id,
        filter_snapshot=body.filters,
        idempotency_key=body.idempotency_key,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return ExportPublic.model_validate(job)


@router.get("/exports", response_model=ExportsPublic)
def list_exports(
    session: SessionDep,
    current_user: User = Depends(get_current_active_staff),
) -> ExportsPublic:
    jobs = session.exec(
        select(ExportJob)
        .where(ExportJob.requested_by_id == current_user.id)
        .order_by(col(ExportJob.created_at).desc())
        .limit(100)
    ).all()
    return ExportsPublic(
        data=[ExportPublic.model_validate(job) for job in jobs], count=len(jobs)
    )


@router.get("/exports/{export_id}", response_model=ExportPublic)
def get_export(
    export_id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_active_staff),
) -> ExportPublic:
    job = session.get(ExportJob, export_id)
    if job is None or job.requested_by_id != current_user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    return ExportPublic.model_validate(job)


@router.get("/exports/{export_id}/download")
def download_export(
    export_id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_active_staff),
) -> Response:
    job = session.get(ExportJob, export_id)
    if job is None or job.requested_by_id != current_user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    if job.status != JobStatus.ready or not job.storage_key:
        raise HTTPException(status_code=409, detail="Export is not ready")
    path = storage_path(job.storage_key, export=True)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found")
    suffix = "pdf" if job.kind == "case_pdf" else "csv"
    media_type = "application/pdf" if suffix == "pdf" else "text/csv; charset=utf-8"
    return Response(
        content=path.read_bytes(),
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="tahr-desk-export.{suffix}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
