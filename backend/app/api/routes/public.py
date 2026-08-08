import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import (
    Attachment,
    AttachmentDownloadRequest,
    AuthorKind,
    CaseCredentials,
    CaseMessagePublic,
    CasePublic,
    CaseReceipt,
    ServiceCategory,
    ServiceCategoryPublic,
    ServicesPublic,
    SitePublic,
    SiteSettings,
    Visibility,
)
from app.services.desk import (
    add_message,
    get_case_for_credentials,
    masked_email,
    public_case,
)
from app.services.desk import create_case as create_service_case
from app.services.storage import remove_stored_image, storage_path, store_image

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/site", response_model=SitePublic)
def get_site(session: SessionDep) -> SitePublic:
    site = session.get(SiteSettings, 1)
    if site is None:
        raise HTTPException(status_code=503, detail="Site settings are unavailable")
    return SitePublic(
        **site.model_dump(), webhooks_enabled=settings.WEBHOOK_DELIVERY_ENABLED
    )


@router.get("/services", response_model=ServicesPublic)
def list_services(session: SessionDep) -> ServicesPublic:
    services = session.exec(
        select(ServiceCategory)
        .where(ServiceCategory.is_active == True)  # noqa: E712
        .order_by(col(ServiceCategory.sort_order), col(ServiceCategory.name))
    ).all()
    return ServicesPublic(
        data=[ServiceCategoryPublic.model_validate(item) for item in services],
        count=len(services),
    )


@router.get("/services/{slug}", response_model=ServiceCategoryPublic)
def get_service(slug: str, session: SessionDep) -> ServiceCategoryPublic:
    service = session.exec(
        select(ServiceCategory).where(
            ServiceCategory.slug == slug,
            ServiceCategory.is_active == True,  # noqa: E712
        )
    ).first()
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    return ServiceCategoryPublic.model_validate(service)


@router.post("/cases", response_model=CaseReceipt, status_code=201)
async def create_case(
    response: Response,
    session: SessionDep,
    submission_id: Annotated[uuid.UUID, Form()],
    reporter_name: Annotated[str, Form(min_length=2, max_length=160)],
    reporter_email: Annotated[str, Form(min_length=3, max_length=255)],
    category_id: Annotated[uuid.UUID, Form()],
    subject: Annotated[str, Form(min_length=5, max_length=180)],
    description: Annotated[str, Form(min_length=20, max_length=10000)],
    location_text: Annotated[str, Form(min_length=3, max_length=240)],
    photos: Annotated[list[UploadFile] | None, File()] = None,
) -> CaseReceipt:
    photos = photos or []
    if len(photos) > 4:
        raise HTTPException(status_code=422, detail="Add at most four photos")
    images = [await store_image(photo) for photo in photos]
    try:
        service_case, created = create_service_case(
            session,
            submission_id=submission_id,
            reporter_name=reporter_name,
            reporter_email=reporter_email,
            category_id=category_id,
            subject=subject,
            description=description,
            location_text=location_text,
            images=images,
        )
    except Exception:
        for image in images:
            remove_stored_image(image)
        raise
    if not created:
        for image in images:
            remove_stored_image(image)
        response.status_code = 200
    return CaseReceipt(
        reference=service_case.reference,
        status=service_case.status,
        created_at=service_case.created_at,
        reporter_email_masked=masked_email(service_case.reporter_email),
    )


@router.post("/cases/lookup", response_model=CasePublic)
def lookup_case(
    body: CaseCredentials, response: Response, session: SessionDep
) -> CasePublic:
    response.headers["Cache-Control"] = "no-store"
    service_case = get_case_for_credentials(
        session, reference=body.reference, reporter_email=str(body.reporter_email)
    )
    return public_case(session, service_case)


@router.post("/cases/messages", response_model=CaseMessagePublic, status_code=201)
async def create_public_message(
    response: Response,
    session: SessionDep,
    reference: Annotated[str, Form(min_length=1, max_length=40)],
    reporter_email: Annotated[str, Form(min_length=3, max_length=255)],
    body_markdown: Annotated[str, Form(min_length=1, max_length=10000)],
    photos: Annotated[list[UploadFile] | None, File()] = None,
) -> CaseMessagePublic:
    response.headers["Cache-Control"] = "no-store"
    photos = photos or []
    if len(photos) > 4:
        raise HTTPException(status_code=422, detail="Add at most four photos")
    images = [await store_image(photo) for photo in photos]
    try:
        service_case = get_case_for_credentials(
            session, reference=reference, reporter_email=reporter_email, lock=True
        )
        if service_case.status == "closed":
            raise HTTPException(
                status_code=409, detail="Closed cases cannot receive follow-up"
            )
        message = add_message(
            session,
            service_case=service_case,
            body_markdown=body_markdown,
            visibility=Visibility.public,
            author_kind=AuthorKind.reporter,
            images=images,
        )
    except Exception:
        for image in images:
            remove_stored_image(image)
        raise
    result = public_case(session, service_case)
    return next(item for item in result.messages if item.id == message.id)


@router.post("/attachments/download")
def download_attachment(
    body: AttachmentDownloadRequest, response: Response, session: SessionDep
) -> Response:
    response.headers["Cache-Control"] = "no-store"
    service_case = get_case_for_credentials(
        session, reference=body.reference, reporter_email=str(body.reporter_email)
    )
    attachment = session.get(Attachment, body.attachment_id)
    if attachment is None or attachment.case_id != service_case.id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = storage_path(attachment.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment not found")
    return Response(
        content=path.read_bytes(),
        media_type=attachment.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{attachment.display_name}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
