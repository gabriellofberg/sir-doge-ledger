from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import APP_NAME, APP_VERSION, FRONTEND_DIST, ensure_dirs
from .db import get_db, init_db, set_demo_mode
from .routers import data, life, money, settings
from .services import auth
from .services.demo import ensure_demo_db
from .services.import_sessions import purge_old_sessions
from .services.money import sanitize_category_rules

CSRF_HEADER = "x-sir-doge"
_PROTECTED_METHODS = {"POST", "DELETE", "PATCH", "PUT"}
_AUTH_EXEMPT = {
    "/api/health",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
    "/api/auth/demo",
    "/api/auth/recover",
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_dirs()
    init_db()
    ensure_demo_db()
    purge_old_sessions()
    with get_db() as conn:
        sanitize_category_rules(conn)
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


def _session_from_request(request: Request) -> str | None:
    return request.cookies.get(auth.COOKIE_NAME)


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
    session = _session_from_request(request)
    set_demo_mode(auth.is_demo_session(session))
    if path.startswith("/api/"):
        if (
            auth.auth_enabled()
            and path not in _AUTH_EXEMPT
            and not auth.session_matches(session)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing session.", "code": "unauthorized"},
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
        **auth.auth_status(),
    }


class SetupBody(BaseModel):
    password: str


class LoginBody(BaseModel):
    password: str


class RecoverBody(BaseModel):
    recovery_key: str
    new_password: str


def _set_session_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 24 * auth.SESSION_DAYS,
        path="/",
    )


@app.get("/api/auth/status")
def auth_status():
    return auth.auth_status()


@app.post("/api/auth/setup")
def auth_setup(body: SetupBody):
    if not auth.needs_setup():
        raise HTTPException(400, "Already set up")
    try:
        result = auth.setup_password(body.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    response = JSONResponse(
        content={"status": "ok", "recovery_key": result["recovery_key"]}
    )
    _set_session_cookie(response, result["session"])
    return response


@app.post("/api/auth/login")
def auth_login(body: LoginBody):
    if auth.needs_setup():
        raise HTTPException(400, "Password not set up yet")
    if not auth.verify_password(body.password):
        return JSONResponse(status_code=401, content={"detail": "Wrong password.", "code": "unauthorized"})
    token = auth.create_login_session()
    response = JSONResponse(content={"status": "ok"})
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/demo")
def auth_demo():
    ensure_demo_db()
    token = auth.create_demo_session()
    response = JSONResponse(content={"status": "ok", "demo": True})
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/recover")
def auth_recover(body: RecoverBody):
    if not auth.recover_password(body.recovery_key, body.new_password):
        raise HTTPException(400, "Invalid recovery key")
    token = auth.create_login_session()
    response = JSONResponse(content={"status": "ok"})
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/logout")
async def logout(request: Request):
    auth.invalidate_session(_session_from_request(request))
    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return response


app.include_router(money.router)
app.include_router(life.router)
app.include_router(data.router)
app.include_router(settings.router)


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
