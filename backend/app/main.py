import logging
from contextlib import asynccontextmanager
from math import ceil
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from . import auth, config, portfolio
from .data import TickerNotFound
from .db import SessionLocal, init_db
from .markets import PERIODS, build_heatmap, get_indices
from .metrics import build_metrics
from .ratelimit import client_ip, expensive_limiter, general_limiter
from .screener import build_screen
from .service import TIMEFRAMES, build_chart

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("stockwatcher")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Stock Dashboard API",
    lifespan=lifespan,
    docs_url="/docs" if config.ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if config.ENABLE_DOCS else None,
)

if not config.IS_PRODUCTION:
    # In development the frontend runs on another port. In production everything is served from one address,
    # so no cross-origin access is allowed at all.
    app.add_middleware(CORSMiddleware, allow_origins=sorted(config.ALLOWED_ORIGINS), allow_methods=["GET"], allow_headers=["*"])

# Signed, httpOnly login cookie. The __Host- prefix makes browsers insist on HTTPS and no cross-subdomain sharing.
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    session_cookie="__Host-sw_session" if config.COOKIE_SECURE else "sw_session",
    max_age=14 * 24 * 3600,
    same_site="lax",
    https_only=config.COOKIE_SECURE,
)

# ---------- security headers, rate limits, cross-site request check ----------
_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
_EXPENSIVE = ("/api/chart/", "/api/metrics/", "/api/screener/", "/api/markets/")  # each can trigger calls to Yahoo
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _origin_allowed(request: Request) -> bool:
    """A browser tags state-changing requests with where they came from. Refuse ones from other sites."""
    origin = request.headers.get("origin")
    if not origin:
        return True  # not a browser (curl, tests)
    if origin.rstrip("/") in config.ALLOWED_ORIGINS:
        return True
    return urlparse(origin).netloc == request.headers.get("host", "")


@app.middleware("http")
async def guard(request: Request, call_next):
    path, response = request.url.path, None

    if path.startswith("/api/"):
        if request.method not in _SAFE_METHODS and not _origin_allowed(request):
            response = JSONResponse({"detail": "Cross-site request blocked."}, status_code=403)
        elif path != "/api/health":
            ip = client_ip(request)
            wait = general_limiter.hit(ip)
            if wait == 0 and path.startswith(_EXPENSIVE):
                wait = expensive_limiter.hit(ip)
            if wait > 0:
                response = JSONResponse({"detail": "Too many requests. Please slow down and try again shortly."},
                                        status_code=429, headers={"Retry-After": str(ceil(wait))})

    if response is None:
        response = await call_next(request)

    for name, value in _HEADERS.items():
        response.headers.setdefault(name, value)
    if not path.startswith(("/docs", "/redoc")):  # the API docs page loads scripts from a CDN
        response.headers.setdefault("Content-Security-Policy", _CSP)
    if path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")  # private data should not be cached
    elif path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # file names change with content
    elif config.STATIC_DIR:
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


app.include_router(auth.router)
app.include_router(portfolio.router)


def _provider_error(e: Exception) -> HTTPException:
    log.exception("data provider error")
    if config.IS_PRODUCTION:  # don't hand internal details to visitors
        return HTTPException(502, "The data provider had a problem. Please try again in a moment.")
    return HTTPException(502, f"Data provider error: {e}")


@app.get("/api/health")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"ok": True}


@app.get("/api/chart/{ticker}")
def chart(ticker: str, timeframe: str = Query("D")):
    if timeframe not in TIMEFRAMES:
        raise HTTPException(400, f"timeframe must be one of {list(TIMEFRAMES)}")
    try:
        return build_chart(ticker, timeframe)
    except TickerNotFound:
        raise HTTPException(404, f"No data found for '{ticker.upper()}'")
    except Exception as e:  # provider/network failure
        raise _provider_error(e)


@app.get("/api/metrics/{ticker}")
def metrics(ticker: str):
    try:
        return build_metrics(ticker)
    except TickerNotFound:
        raise HTTPException(404, f"No data found for '{ticker.upper()}'")
    except Exception as e:
        raise _provider_error(e)


@app.get("/api/screener/{ticker}")
def screener(ticker: str):
    try:
        return build_screen(ticker)
    except TickerNotFound:
        raise HTTPException(404, f"No data found for '{ticker.upper()}'")
    except Exception as e:
        raise _provider_error(e)


def _check_period(period: str) -> None:
    if period not in PERIODS:
        raise HTTPException(400, f"period must be one of {PERIODS}")


@app.get("/api/markets/indices")
def market_indices(period: str = Query("1D")):
    _check_period(period)
    try:
        return get_indices(period)
    except Exception as e:
        raise _provider_error(e)


@app.get("/api/markets/heatmap")
def market_heatmap(period: str = Query("1D")):
    _check_period(period)
    try:
        return build_heatmap(period)
    except Exception as e:
        raise _provider_error(e)


# ---------- the built frontend (production: one container serves both) ----------
if config.STATIC_DIR and config.STATIC_DIR.is_dir():
    _root = config.STATIC_DIR.resolve()
    if (_root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (_root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(_root):  # never serve anything outside the folder
            return FileResponse(candidate)
        return FileResponse(_root / "index.html")  # let the React router handle /portfolio, /overview, ...
