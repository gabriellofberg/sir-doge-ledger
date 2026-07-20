from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, APP_VERSION, FRONTEND_DIST, ensure_dirs
from .db import init_db
from .routers import data, life, money
from .services import auth
from .services.import_sessions import purge_old_sessions

CSRF_HEADER = "x-sir-doge"
_PROTECTED_METHODS = {"POST", "DELETE", "PATCH", "PUT"}
_AUTH_EXEMPT_PATHS = {"/api/health", "/api/auth"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_dirs()
    auth.ensure_token()
    init_db()
    purge_old_sessions()
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)

_LOCAL_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_LOCAL_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _request_has_valid_token(request: Request) -> bool:
    cookie = request.cookies.get(auth.COOKIE_NAME)
    if auth.token_matches(cookie):
        return True
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return auth.token_matches(header[7:])
    return auth.token_matches(request.headers.get("x-sir-doge-token"))


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def api_gatekeeper(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        if (
            auth.auth_enabled()
            and path not in _AUTH_EXEMPT_PATHS
            and not _request_has_valid_token(request)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing token.", "code": "unauthorized"},
            )
        if request.method in _PROTECTED_METHODS and not request.headers.get(CSRF_HEADER):
            return JSONResponse(
                status_code=403,
                content={"detail": "Missing X-Sir-Doge header.", "code": "missing_csrf_header"},
            )
    return await call_next(request)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": "sir-doge-ledger",
        "version": APP_VERSION,
        "auth_required": auth.auth_enabled(),
    }


@app.post("/api/auth")
async def authenticate(request: Request):
    candidate = request.query_params.get("token")
    if not candidate:
        try:
            body = await request.json()
            candidate = body.get("token") if isinstance(body, dict) else None
        except (ValueError, TypeError):
            candidate = None
    if not auth.token_matches(candidate):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token.", "code": "unauthorized"},
        )
    response = JSONResponse(content={"status": "ok"})
    response.set_cookie(
        auth.COOKIE_NAME,
        candidate.strip(),
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return response


@app.post("/api/auth/logout")
async def logout():
    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return response


app.include_router(money.router)
app.include_router(life.router)
app.include_router(data.router)


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str = ""):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST.resolve()):
                return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "Frontend not built"}, status_code=404)
