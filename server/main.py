"""FastAPI application entry point.

Run with:
    uvicorn server.main:app --reload --port 8000

The Django Unfold admin panel is a separate process on port 8001; `/admin`
redirects there.
"""
from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from server.api import routes_admin, routes_attempts, routes_auth, routes_exams
from server.api import routes_questions, routes_users
from server.api.deps import require_admin
from server.core.config import audit_production_config, settings
from server.core.database import get_db, init_db
from server.services.seed import seed_if_empty

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("osh")

# Loud, but never fatal: a wrong env var must not take the whole site down.
_CONFIG_PROBLEMS = audit_production_config()
for _problem in _CONFIG_PROBLEMS:
    log.warning("XAVFSIZLIK: %s", _problem)
if _CONFIG_PROBLEMS:
    log.warning(
        "Ishlab chiqarish uchun .env faylini to‘ldiring "
        "(SECRET_KEY va kuchli parollar). Sayt ishlaydi, lekin internetga "
        "ochishdan oldin bu kamchiliklarni bartaraf eting."
    )

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Oilaviy shifokorlik testi — backend API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = settings.API_PREFIX
app.include_router(routes_auth.router, prefix=API)
app.include_router(routes_users.router, prefix=API)
app.include_router(routes_questions.router, prefix=API)
app.include_router(routes_exams.router, prefix=API)
app.include_router(routes_attempts.router, prefix=API)
app.include_router(routes_admin.router, prefix=API)


class NoCacheStaticFiles(StaticFiles):
    """Serve the frontend with caching effectively disabled.

    The student app is a set of plain .js/.css files with no build step and no
    fingerprinted names, so a browser that is allowed to cache them can keep
    running an old bundle after a file on disk has been edited — the page then
    silently behaves like the previous version. `must-revalidate` plus
    `no-cache` makes the browser revalidate on every load (a 304 is cheap),
    which keeps what is on screen in step with the files on disk.

    The ETag and Last-Modified headers are left in place, so an unchanged file
    still costs one conditional request and no body.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    created = seed_if_empty()
    if created:
        log.info("Seed ma'lumotlari yaratildi: %s", created)
    # Serve the frontend from the same origin so no CORS setup is needed.
    if settings.WEB_DIR.exists():
        app.mount("/static", NoCacheStaticFiles(directory=str(settings.WEB_DIR)), name="static")
        app.mount("/assets", NoCacheStaticFiles(directory=str(settings.WEB_DIR / "assets")), name="assets")
        app.mount("/css", NoCacheStaticFiles(directory=str(settings.WEB_DIR / "css")), name="css")
        app.mount("/js", NoCacheStaticFiles(directory=str(settings.WEB_DIR / "js")), name="js")


@app.get(f"{API}/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "version": settings.VERSION, "app": settings.PROJECT_NAME}


@app.post(f"{API}/bootstrap", tags=["meta"])
def bootstrap(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    """Re-run seeding: attach imported questions to the starter exam."""
    from server.services.seed import attach_questions_to_starter_exam

    result = attach_questions_to_starter_exam(db)
    db.commit()
    return result


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(settings.WEB_DIR / "index.html")


@app.get("/admin", include_in_schema=False)
def admin_page() -> RedirectResponse:
    """Send visitors to the Django Unfold panel (a separate process)."""
    target = os.getenv("DJANGO_ADMIN_URL", "http://127.0.0.1:8001/admin/")
    return RedirectResponse(target, status_code=307)


ICON_ROUTES = {
    "/favicon.ico": "favicon.ico",
    "/favicon.svg": "favicon.svg",
    "/manifest.webmanifest": "manifest.webmanifest",
}


def _register_icon_routes(application: FastAPI) -> None:
    """Expose each icon at the path browsers probe without reading the HTML.

    Browsers request /favicon.ico on their own. When that 404s, Edge and Chrome
    reuse whatever icon they cached for the same origin from an earlier page,
    which is how one project's icon ends up showing on another. Each route
    closes over its own filename because FastAPI would otherwise read
    `filename` as a query parameter and always return the default.
    """

    def make_handler(icon_name: str):
        def handler() -> FileResponse:
            icons_dir = settings.WEB_DIR / "assets" / "icons"
            target = icons_dir / icon_name
            media = (
                "application/manifest+json"
                if icon_name.endswith(".webmanifest")
                else None
            )
            return FileResponse(
                target,
                media_type=media,
                headers={"Cache-Control": "public, max-age=86400"},
            )

        return handler

    for path, icon_name in ICON_ROUTES.items():
        application.get(path, include_in_schema=False)(make_handler(icon_name))


_register_icon_routes(app)


@app.exception_handler(Exception)
def unhandled_error(request, exc: Exception) -> JSONResponse:  # pragma: no cover
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500, content={"detail": "Serverda xatolik yuz berdi"}
    )
