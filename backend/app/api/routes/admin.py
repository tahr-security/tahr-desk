import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, select

from app import crud
from app.api.deps import SessionDep, get_current_active_superuser
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import (
    AgentCreate,
    AgentResetPassword,
    AgentUpdate,
    CaseEvent,
    DeliveryStatus,
    Message,
    ServiceCase,
    ServiceCategory,
    ServiceCategoryAdmin,
    ServiceCategoryCreate,
    ServiceCategoryPublic,
    ServiceCategoryUpdate,
    ServicesAdmin,
    SiteSettings,
    SiteSettingsPublic,
    SiteSettingsUpdate,
    User,
    UserCreate,
    UserPublic,
    UsersPublic,
    Visibility,
    WebhookCreate,
    WebhookCreated,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookPublic,
    WebhooksPublic,
    WebhookUpdate,
)
from app.services.content import render_markdown
from app.services.desk import user_public
from app.services.webhooks import (
    new_signing_secret,
    validate_event_types,
    validate_webhook_url,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_active_superuser)],
)


def require_webhooks() -> None:
    if not settings.WEBHOOK_DELIVERY_ENABLED:
        raise HTTPException(status_code=404, detail="Webhook delivery is disabled")


@router.get("/agents", response_model=UsersPublic)
def list_agents(session: SessionDep) -> UsersPublic:
    users = session.exec(
        select(User).where(User.is_superuser == False).order_by(col(User.full_name))  # noqa: E712
    ).all()
    return UsersPublic(data=[user_public(user) for user in users], count=len(users))


@router.post("/agents", response_model=UserPublic, status_code=201)
def create_agent(body: AgentCreate, session: SessionDep) -> UserPublic:
    if crud.get_user_by_email(session=session, email=str(body.email)):
        raise HTTPException(
            status_code=409, detail="A user with this email already exists"
        )
    user = crud.create_user(
        session=session,
        user_create=UserCreate(
            email=body.email,
            full_name=body.full_name,
            password=body.password,
            is_active=body.is_active,
            is_superuser=False,
        ),
    )
    return user_public(user)


@router.patch("/agents/{user_id}", response_model=UserPublic)
def update_agent(
    user_id: uuid.UUID, body: AgentUpdate, session: SessionDep
) -> UserPublic:
    user = session.get(User, user_id)
    if user is None or user.is_superuser:
        raise HTTPException(status_code=404, detail="Agent not found")
    changes = body.model_dump(exclude_unset=True)
    password = changes.pop("new_password", None)
    if changes.get("is_active") is True and not user.is_active and password is None:
        raise HTTPException(
            status_code=422, detail="Set a new password when activating an agent"
        )
    if password:
        user.hashed_password = get_password_hash(password)
        user.auth_version += 1
    if "is_active" in changes and changes["is_active"] != user.is_active:
        user.auth_version += 1
    user.sqlmodel_update(changes)
    user.updated_at = datetime.now(UTC)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user_public(user)


@router.post("/agents/{user_id}/reset-password", response_model=Message)
def reset_agent_password(
    user_id: uuid.UUID, body: AgentResetPassword, session: SessionDep
) -> Message:
    user = session.get(User, user_id)
    if user is None or user.is_superuser:
        raise HTTPException(status_code=404, detail="Agent not found")
    user.hashed_password = get_password_hash(body.new_password)
    user.auth_version += 1
    user.updated_at = datetime.now(UTC)
    session.add(user)
    session.commit()
    return Message(message="Agent password reset")


@router.get("/site", response_model=SiteSettingsPublic)
def get_site(session: SessionDep) -> SiteSettingsPublic:
    site = session.get(SiteSettings, 1)
    if site is None:
        raise HTTPException(status_code=404, detail="Site settings not found")
    return SiteSettingsPublic(
        **site.model_dump(), webhooks_enabled=settings.WEBHOOK_DELIVERY_ENABLED
    )


@router.patch("/site", response_model=SiteSettingsPublic)
def update_site(body: SiteSettingsUpdate, session: SessionDep) -> SiteSettingsPublic:
    site = session.get(SiteSettings, 1)
    if site is None:
        raise HTTPException(status_code=404, detail="Site settings not found")
    site.sqlmodel_update(
        body.model_dump(),
        update={
            "introduction_html": render_markdown(body.introduction_markdown),
            "updated_at": datetime.now(UTC),
        },
    )
    session.add(site)
    session.commit()
    session.refresh(site)
    return SiteSettingsPublic(
        **site.model_dump(), webhooks_enabled=settings.WEBHOOK_DELIVERY_ENABLED
    )


@router.get("/services", response_model=ServicesAdmin)
def list_services(session: SessionDep) -> ServicesAdmin:
    services = session.exec(
        select(ServiceCategory).order_by(
            col(ServiceCategory.sort_order), col(ServiceCategory.name)
        )
    ).all()
    return ServicesAdmin(
        data=[ServiceCategoryAdmin.model_validate(item) for item in services],
        count=len(services),
    )


@router.post("/services", response_model=ServiceCategoryPublic, status_code=201)
def create_service(
    body: ServiceCategoryCreate, session: SessionDep
) -> ServiceCategoryPublic:
    if session.exec(
        select(ServiceCategory).where(ServiceCategory.slug == body.slug)
    ).first():
        raise HTTPException(status_code=409, detail="Service slug already exists")
    item = ServiceCategory(
        **body.model_dump(),
        guidance_html=render_markdown(body.guidance_markdown),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return ServiceCategoryPublic.model_validate(item)


@router.patch("/services/{service_id}", response_model=ServiceCategoryPublic)
def update_service(
    service_id: uuid.UUID, body: ServiceCategoryUpdate, session: SessionDep
) -> ServiceCategoryPublic:
    item = session.get(ServiceCategory, service_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Service not found")
    changes = body.model_dump(exclude_unset=True)
    if "guidance_markdown" in changes:
        changes["guidance_html"] = render_markdown(changes["guidance_markdown"])
    changes["updated_at"] = datetime.now(UTC)
    item.sqlmodel_update(changes)
    session.add(item)
    session.commit()
    session.refresh(item)
    return ServiceCategoryPublic.model_validate(item)


@router.get("/webhooks", response_model=WebhooksPublic)
def list_webhooks(session: SessionDep) -> WebhooksPublic:
    require_webhooks()
    items = session.exec(
        select(WebhookEndpoint).order_by(col(WebhookEndpoint.created_at))
    ).all()
    return WebhooksPublic(
        data=[WebhookPublic.model_validate(item) for item in items], count=len(items)
    )


@router.post("/webhooks", response_model=WebhookCreated, status_code=201)
def create_webhook(body: WebhookCreate, session: SessionDep) -> WebhookCreated:
    require_webhooks()
    secret, ciphertext = new_signing_secret()
    item = WebhookEndpoint(
        name=body.name,
        url=validate_webhook_url(body.url),
        secret_ciphertext=ciphertext,
        subscribed_events=validate_event_types(body.subscribed_events),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return WebhookCreated(
        **WebhookPublic.model_validate(item).model_dump(), signing_secret=secret
    )


@router.patch("/webhooks/{endpoint_id}", response_model=WebhookPublic)
def update_webhook(
    endpoint_id: uuid.UUID, body: WebhookUpdate, session: SessionDep
) -> WebhookPublic:
    require_webhooks()
    item = session.get(WebhookEndpoint, endpoint_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    changes = body.model_dump(exclude_unset=True)
    if "url" in changes:
        changes["url"] = validate_webhook_url(changes["url"])
    if "subscribed_events" in changes:
        changes["subscribed_events"] = validate_event_types(
            changes["subscribed_events"]
        )
    changes["updated_at"] = datetime.now(UTC)
    item.sqlmodel_update(changes)
    session.add(item)
    session.commit()
    session.refresh(item)
    return WebhookPublic.model_validate(item)


@router.post("/webhooks/{endpoint_id}/rotate-secret", response_model=WebhookCreated)
def rotate_webhook_secret(
    endpoint_id: uuid.UUID, session: SessionDep
) -> WebhookCreated:
    require_webhooks()
    item = session.get(WebhookEndpoint, endpoint_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    secret, item.secret_ciphertext = new_signing_secret()
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)
    return WebhookCreated(
        **WebhookPublic.model_validate(item).model_dump(), signing_secret=secret
    )


@router.post("/webhooks/{endpoint_id}/test", response_model=Message, status_code=202)
def test_webhook(endpoint_id: uuid.UUID, session: SessionDep) -> Message:
    require_webhooks()
    endpoint = session.get(WebhookEndpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    service_case = session.exec(
        select(ServiceCase).order_by(col(ServiceCase.created_at)).limit(1)
    ).first()
    if service_case is None:
        raise HTTPException(
            status_code=409, detail="A case is required for a test event"
        )
    category = session.get(ServiceCategory, service_case.category_id)
    event = CaseEvent(
        case_id=service_case.id,
        event_type="webhook_test",
        visibility=Visibility.private,
        summary="Webhook test requested",
    )
    session.add(event)
    session.flush()
    session.add(
        WebhookDelivery(
            endpoint_id=endpoint.id,
            case_event_id=event.id,
            status=DeliveryStatus.queued,
            payload={
                "schema_version": 1,
                "event_id": str(event.id),
                "event_type": "case.updated",
                "case": {
                    "reference": service_case.reference,
                    "category": category.slug if category else "unknown",
                    "status": str(service_case.status),
                    "priority": str(service_case.priority),
                    "summary": "Webhook test requested",
                    "updated_at": service_case.updated_at.isoformat(),
                },
            },
        )
    )
    session.commit()
    return Message(message="Test delivery will be sent with the next worker cycle")
