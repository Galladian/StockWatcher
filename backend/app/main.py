from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from . import auth, portfolio
from .config import get_secret_key
from .data import TickerNotFound
from .db import init_db
from .metrics import build_metrics
from .screener import build_screen
from .service import TIMEFRAMES, build_chart


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Stock Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
# Signed, httpOnly login cookie (page scripts can't read it)
app.add_middleware(
    SessionMiddleware,
    secret_key=get_secret_key(),
    session_cookie="sw_session",
    max_age=14 * 24 * 3600,
    same_site="lax",
    https_only=False,  # local http; set True if you ever serve over HTTPS
)

app.include_router(auth.router)
app.include_router(portfolio.router)


@app.get("/api/health")
def health():
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
        raise HTTPException(502, f"Data provider error: {e}")


@app.get("/api/metrics/{ticker}")
def metrics(ticker: str):
    try:
        return build_metrics(ticker)
    except TickerNotFound:
        raise HTTPException(404, f"No data found for '{ticker.upper()}'")
    except Exception as e:  # provider/network failure
        raise HTTPException(502, f"Data provider error: {e}")


@app.get("/api/screener/{ticker}")
def screener(ticker: str):
    try:
        return build_screen(ticker)
    except TickerNotFound:
        raise HTTPException(404, f"No data found for '{ticker.upper()}'")
    except Exception as e:  # provider/network failure
        raise HTTPException(502, f"Data provider error: {e}")
