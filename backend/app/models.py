import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import EmailStr, field_validator, model_validator
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


def normalize_text(value: str) -> str:
    return " ".join(value.split())


class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> EmailStr:
        return str(value).strip().lower()


class UserCreate(UserBase):
    password: str = Field(min_length=12, max_length=128)


class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=12, max_length=128)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=12, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class User(UserBase, table=True):
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_user_email_lowercase"),
        CheckConstraint("auth_version >= 0", name="ck_user_auth_version"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    auth_version: int = Field(default=0, ge=0)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class UserPublic(SQLModel):
    email: str
    is_active: bool
    is_superuser: bool
    full_name: str | None
    id: uuid.UUID
    role: str
    created_at: datetime


class AgentCreate(SQLModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=12, max_length=128)
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> EmailStr:
        return str(value).strip().lower()

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_text(value)


class AgentUpdate(SQLModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None
    new_password: str | None = Field(default=None, min_length=12, max_length=128)


class AgentResetPassword(SQLModel):
    new_password: str = Field(min_length=12, max_length=128)


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class SiteSettings(SQLModel, table=True):
    __table_args__ = (CheckConstraint("id = 1", name="ck_site_settings_singleton"),)

    id: int = Field(default=1, primary_key=True)
    organization_name: str = Field(max_length=120)
    service_area: str = Field(max_length=160)
    timezone: str = Field(max_length=64)
    introduction_markdown: str = Field(sa_column=Column(Text, nullable=False))
    introduction_html: str = Field(sa_column=Column(Text, nullable=False))
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class SiteSettingsUpdate(SQLModel):
    organization_name: str = Field(min_length=2, max_length=120)
    service_area: str = Field(min_length=2, max_length=160)
    timezone: str = Field(min_length=1, max_length=64)
    introduction_markdown: str = Field(min_length=1, max_length=5000)


class SitePublic(SQLModel):
    organization_name: str
    service_area: str
    timezone: str
    introduction_html: str
    webhooks_enabled: bool


class SiteSettingsPublic(SitePublic):
    introduction_markdown: str


class ServiceCategoryBase(SQLModel):
    slug: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=10, max_length=500)
    guidance_markdown: str = Field(min_length=1, max_length=10000)
    response_target_hours: int = Field(ge=1, le=8760)
    sort_order: int = Field(default=0, ge=0, le=10000)
    is_active: bool = True

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        import re

        normalized = value.strip().lower()
        if re.fullmatch(r"[a-z][a-z0-9-]+", normalized) is None:
            raise ValueError(
                "Slug must contain lowercase letters, numbers, and hyphens"
            )
        return normalized


class ServiceCategory(ServiceCategoryBase, table=True):
    __table_args__ = (
        CheckConstraint("slug = lower(slug)", name="ck_service_category_slug_lower"),
        CheckConstraint(
            "response_target_hours BETWEEN 1 AND 8760",
            name="ck_service_category_response_target",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    slug: str = Field(unique=True, index=True, min_length=2, max_length=64)
    guidance_html: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ServiceCategoryCreate(ServiceCategoryBase):
    pass


class ServiceCategoryUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    summary: str | None = Field(default=None, min_length=10, max_length=500)
    guidance_markdown: str | None = Field(default=None, min_length=1, max_length=10000)
    response_target_hours: int | None = Field(default=None, ge=1, le=8760)
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None


class ServiceCategoryPublic(SQLModel):
    id: uuid.UUID
    slug: str
    name: str
    summary: str
    guidance_html: str
    response_target_hours: int
    sort_order: int
    is_active: bool


class ServiceCategoryAdmin(ServiceCategoryPublic):
    guidance_markdown: str


class ServicesPublic(SQLModel):
    data: list[ServiceCategoryPublic]
    count: int


class ServicesAdmin(SQLModel):
    data: list[ServiceCategoryAdmin]
    count: int


class CaseStatus(StrEnum):
    submitted = "submitted"
    triaged = "triaged"
    in_progress = "in_progress"
    waiting_on_reporter = "waiting_on_reporter"
    resolved = "resolved"
    closed = "closed"


class CasePriority(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class ClosureReason(StrEnum):
    resolved = "resolved"
    duplicate = "duplicate"
    out_of_scope = "out_of_scope"
    withdrawn = "withdrawn"


class Visibility(StrEnum):
    public = "public"
    private = "private"


class AuthorKind(StrEnum):
    reporter = "reporter"
    staff = "staff"
    system = "system"


class ServiceCase(SQLModel, table=True):
    __tablename__ = "service_case"
    __table_args__ = (
        CheckConstraint("reference = upper(reference)", name="ck_case_reference_upper"),
        CheckConstraint(
            "reporter_email = lower(reporter_email)", name="ck_case_email_lower"
        ),
        CheckConstraint("version >= 1", name="ck_case_version"),
        CheckConstraint(
            "status IN ('submitted','triaged','in_progress','waiting_on_reporter','resolved','closed')",
            name="ck_case_status",
        ),
        CheckConstraint(
            "priority IN ('low','normal','high','urgent')", name="ck_case_priority"
        ),
        CheckConstraint(
            "status NOT IN ('in_progress','waiting_on_reporter','resolved','closed') OR assigned_to_id IS NOT NULL",
            name="ck_case_active_assignment",
        ),
        CheckConstraint(
            "status <> 'resolved' OR resolved_at IS NOT NULL",
            name="ck_case_resolved_timestamp",
        ),
        CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL)",
            name="ck_case_closed_timestamp",
        ),
        Index("ix_case_queue", "status", "priority", "created_at"),
        Index("ix_case_assignee_queue", "assigned_to_id", "status", "updated_at"),
        Index("ix_case_category_status", "category_id", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    reference: str = Field(unique=True, index=True, min_length=24, max_length=24)
    public_submission_id: uuid.UUID = Field(unique=True, index=True)
    submission_hash: str = Field(min_length=64, max_length=64)
    reporter_name: str = Field(min_length=2, max_length=160)
    reporter_email: str = Field(index=True, max_length=255)
    category_id: uuid.UUID = Field(foreign_key="servicecategory.id", nullable=False)
    subject: str = Field(min_length=5, max_length=180)
    description: str = Field(sa_column=Column(Text, nullable=False))
    location_text: str = Field(min_length=3, max_length=240)
    status: CaseStatus = Field(
        default=CaseStatus.submitted,
        sa_column=Column(String(32), nullable=False),
    )
    priority: CasePriority = Field(
        default=CasePriority.normal,
        sa_column=Column(String(16), nullable=False),
    )
    assigned_to_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True
    )
    target_resolution_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    resolved_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    closed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    closure_reason: ClosureReason | None = Field(
        default=None, sa_column=Column(String(32), nullable=True)
    )
    duplicate_case_id: uuid.UUID | None = Field(
        default=None, foreign_key="service_case.id", nullable=True
    )
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CaseMessage(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "author_kind IN ('reporter','staff','system')",
            name="ck_message_author_kind",
        ),
        CheckConstraint(
            "visibility IN ('public','private')", name="ck_message_visibility"
        ),
        Index("ix_case_message_timeline", "case_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="service_case.id", nullable=False)
    author_kind: AuthorKind = Field(sa_column=Column(String(16), nullable=False))
    author_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    visibility: Visibility = Field(sa_column=Column(String(16), nullable=False))
    body_markdown: str = Field(sa_column=Column(Text, nullable=False))
    body_html: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CaseEvent(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('public','private')", name="ck_event_visibility"
        ),
        Index("ix_case_event_timeline", "case_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="service_case.id", nullable=False)
    actor_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    event_type: str = Field(min_length=2, max_length=64)
    visibility: Visibility = Field(sa_column=Column(String(16), nullable=False))
    from_status: CaseStatus | None = Field(
        default=None, sa_column=Column(String(32), nullable=True)
    )
    to_status: CaseStatus | None = Field(
        default=None, sa_column=Column(String(32), nullable=True)
    )
    summary: str = Field(max_length=500)
    message_id: uuid.UUID | None = Field(default=None, foreign_key="casemessage.id")
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Attachment(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "byte_count > 0 AND byte_count <= 8388608", name="ck_attachment_size"
        ),
        CheckConstraint(
            "media_type IN ('image/jpeg','image/png')", name="ck_attachment_media_type"
        ),
        Index("ix_attachment_case_created", "case_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="service_case.id", nullable=False)
    message_id: uuid.UUID | None = Field(default=None, foreign_key="casemessage.id")
    uploaded_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    uploader_kind: AuthorKind = Field(sa_column=Column(String(16), nullable=False))
    storage_key: str = Field(unique=True, max_length=120)
    display_name: str = Field(max_length=180)
    media_type: str = Field(max_length=32)
    byte_count: int = Field(gt=0, le=8 * 1024 * 1024)
    sha256: str = Field(min_length=64, max_length=64)
    width: int = Field(gt=0, le=12000)
    height: int = Field(gt=0, le=12000)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ExportKind(StrEnum):
    case_pdf = "case_pdf"
    cases_csv = "cases_csv"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    ready = "ready"
    failed = "failed"
    expired = "expired"


class ExportJob(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "requested_by_id", "idempotency_key", name="uq_export_idempotency"
        ),
        Index("ix_export_work", "status", "next_attempt_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    requested_by_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    kind: ExportKind = Field(sa_column=Column(String(24), nullable=False))
    case_id: uuid.UUID | None = Field(default=None, foreign_key="service_case.id")
    filter_snapshot: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=False)
    )
    idempotency_key: uuid.UUID
    status: JobStatus = Field(
        default=JobStatus.queued, sa_column=Column(String(16), nullable=False)
    )
    attempts: int = Field(default=0, ge=0, le=2)
    next_attempt_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    lease_owner: str | None = Field(default=None, max_length=120)
    lease_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    storage_key: str | None = Field(default=None, max_length=120)
    byte_count: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, max_length=64)
    error_code: str | None = Field(default=None, max_length=64)
    expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class WebhookEndpoint(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(min_length=2, max_length=120)
    url: str = Field(max_length=2048)
    secret_ciphertext: str = Field(max_length=1024)
    subscribed_events: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )
    is_active: bool = True
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class DeliveryStatus(StrEnum):
    queued = "queued"
    delivering = "delivering"
    delivered = "delivered"
    failed = "failed"
    suppressed = "suppressed"


class WebhookDelivery(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "endpoint_id", "case_event_id", name="uq_delivery_event_endpoint"
        ),
        Index("ix_webhook_delivery_work", "status", "next_attempt_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    endpoint_id: uuid.UUID = Field(foreign_key="webhookendpoint.id", nullable=False)
    case_event_id: uuid.UUID = Field(foreign_key="caseevent.id", nullable=False)
    payload: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
    status: DeliveryStatus = Field(
        default=DeliveryStatus.queued, sa_column=Column(String(16), nullable=False)
    )
    attempts: int = Field(default=0, ge=0, le=6)
    next_attempt_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    lease_owner: str | None = Field(default=None, max_length=120)
    lease_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    response_status: int | None = Field(default=None, ge=100, le=599)
    error_code: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CaseCredentials(SQLModel):
    reference: str = Field(min_length=1, max_length=40)
    reporter_email: EmailStr

    @field_validator("reference")
    @classmethod
    def clean_reference(cls, value: str) -> str:
        return value.strip().upper()


class AttachmentDownloadRequest(CaseCredentials):
    attachment_id: uuid.UUID


class CaseReceipt(SQLModel):
    reference: str
    status: CaseStatus
    created_at: datetime
    reporter_email_masked: str


class CaseMessagePublic(SQLModel):
    id: uuid.UUID
    author_label: str
    body_html: str
    created_at: datetime
    attachments: list[AttachmentPublic] = Field(default_factory=list)


class CaseEventPublic(SQLModel):
    id: uuid.UUID
    event_type: str
    summary: str
    from_status: CaseStatus | None
    to_status: CaseStatus | None
    created_at: datetime


class AttachmentPublic(SQLModel):
    id: uuid.UUID
    display_name: str
    media_type: str
    byte_count: int
    width: int
    height: int


class CasePublic(SQLModel):
    reference: str
    category: ServiceCategoryPublic
    subject: str
    description: str
    location_text: str
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentPublic]
    messages: list[CaseMessagePublic]
    events: list[CaseEventPublic]


class StaffCasePublic(SQLModel):
    id: uuid.UUID
    reference: str
    reporter_name: str
    reporter_email: str
    category: ServiceCategoryPublic
    subject: str
    description: str
    location_text: str
    status: CaseStatus
    priority: CasePriority
    assigned_to: UserPublic | None
    target_resolution_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    closure_reason: ClosureReason | None
    duplicate_case_id: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentPublic]
    messages: list[CaseMessagePublic]
    events: list[CaseEventPublic]


class StaffCasesPublic(SQLModel):
    data: list[StaffCasePublic]
    count: int


class DashboardStats(SQLModel):
    mine: int
    unassigned: int
    overdue: int
    open_total: int
    resolved_last_7_days: int


class AssignmentUpdate(SQLModel):
    assigned_to_id: uuid.UUID | None = None


class ClassificationUpdate(SQLModel):
    category_id: uuid.UUID | None = None
    priority: CasePriority | None = None

    @model_validator(mode="after")
    def require_change(self) -> ClassificationUpdate:
        if self.category_id is None and self.priority is None:
            raise ValueError("Provide category_id or priority")
        return self


class TransitionRequest(SQLModel):
    status: CaseStatus
    summary_markdown: str = Field(min_length=2, max_length=5000)
    closure_reason: ClosureReason | None = None
    duplicate_case_id: uuid.UUID | None = None


class StaffMessageCreate(SQLModel):
    body_markdown: str = Field(min_length=1, max_length=10000)
    visibility: Visibility = Visibility.public


class ExportCreate(SQLModel):
    kind: ExportKind
    idempotency_key: uuid.UUID
    case_id: uuid.UUID | None = None
    filters: dict[str, str] = Field(default_factory=dict)


class ExportPublic(SQLModel):
    id: uuid.UUID
    kind: ExportKind
    status: JobStatus
    error_code: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExportsPublic(SQLModel):
    data: list[ExportPublic]
    count: int


class WebhookCreate(SQLModel):
    name: str = Field(min_length=2, max_length=120)
    url: str = Field(max_length=2048)
    subscribed_events: list[str] = Field(min_length=1, max_length=10)


class WebhookUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    url: str | None = Field(default=None, max_length=2048)
    subscribed_events: list[str] | None = None
    is_active: bool | None = None


class WebhookPublic(SQLModel):
    id: uuid.UUID
    name: str
    url: str
    subscribed_events: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WebhookCreated(WebhookPublic):
    signing_secret: str


class WebhooksPublic(SQLModel):
    data: list[WebhookPublic]
    count: int


class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: uuid.UUID
    ver: int = 0
