from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .data import TickerNotFound
from .metrics import build_metrics
from .service import TIMEFRAMES, build_chart

app = FastAPI(title="Stock Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


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
