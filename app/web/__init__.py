"""FastAPI web ilovasi (WebApp + Admin panel + API)."""
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR
from app.partner.client import PartnerError
from app.web.auth import ApiError


def _err_body(code: str, message: str, extra=None):
    body = {"ok": False, "error": {"code": code, "message": message}}
    if extra:
        body["error"].update(extra)
    return body


def create_app() -> FastAPI:
    app = FastAPI(title="Hamyon", docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(ApiError)
    async def _api_error_handler(_: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status, content=_err_body(exc.code, exc.message, exc.extra)
        )

    @app.exception_handler(PartnerError)
    async def _partner_error_handler(_: Request, exc: PartnerError):
        return JSONResponse(
            status_code=exc.status or 502,
            content=_err_body(exc.code, exc.message, exc.extra),
        )

    from app.web.api import router as api_router
    from app.web.admin_api import router as admin_router

    app.include_router(api_router)
    app.include_router(admin_router)

    @app.get("/admin", include_in_schema=False)
    async def admin_page():
        return FileResponse(STATIC_DIR / "admin.html")

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
