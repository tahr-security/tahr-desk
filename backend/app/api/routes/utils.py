from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import SessionDep
from app.services.storage import ensure_storage

router = APIRouter(prefix="/utils", tags=["utils"])


@router.get("/health-check/")
def health_check(session: SessionDep) -> bool:
    session.exec(select(1))
    ensure_storage()
    return True
