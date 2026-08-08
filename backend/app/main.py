from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings

FRONTEND_DIR = Path(__file__).parent / "frontend"


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.1",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    412: "stale_case",
    413: "payload_too_large",
    428: "precondition_required",
    503: "service_unavailable",
}


@app.exception_handler(HTTPException)
async def handled_error(request: Request, exc: HTTPException) -> JSONResponse:
    headers = dict(exc.headers or {})
    if request.url.path.startswith(f"{settings.API_V1_STR}/public/cases"):
        headers["Cache-Control"] = "no-store"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "code": ERROR_CODES.get(exc.status_code, "request_failed"),
        },
        headers=headers,
    )


# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
if FRONTEND_DIR.is_dir():
    app.frontend("/", directory=FRONTEND_DIR)
