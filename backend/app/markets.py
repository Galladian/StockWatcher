"""Market overview: how the world's main indexes did, and an S&P 500 heatmap."""
import json
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait

import pandas as pd

from . import data, universe
from .config import DATA_DIR

PERIODS = ["1D", "1W", "1M", "3M", "YTD", "1Y"]

# (region, Yahoo symbol, name, country). Asia-Pacific first because it opens first for you.
INDICES = [
    ("Asia-Pacific", "^NZ50", "NZX 50", "New Zealand"), ("Asia-Pacific", "^AXJO", "S&P/ASX 200", "Australia"),
    ("Asia-Pacific", "^N225", "Nikkei 225", "Japan"), ("Asia-Pacific", "^KS11", "KOSPI", "South Korea"),
    ("Asia-Pacific", "^HSI", "Hang Seng", "Hong Kong"), ("Asia-Pacific", "000001.SS", "Shanghai Composite", "China"),
    ("Asia-Pacific", "399001.SZ", "Shenzhen Component", "China"), ("Asia-Pacific", "^TWII", "TAIEX", "Taiwan"),
    ("Asia-Pacific", "^NSEI", "Nifty 50", "India"), ("Asia-Pacific", "^BSESN", "BSE Sensex", "India"),
    ("Asia-Pacific", "^STI", "Straits Times", "Singapore"), ("Asia-Pacific", "^JKSE", "Jakarta Composite", "Indonesia"),
    ("Asia-Pacific", "^KLSE", "FTSE Bursa Malaysia KLCI", "Malaysia"),
    ("Europe", "^FTSE", "FTSE 100", "United Kingdom"), ("Europe", "^GDAXI", "DAX", "Germany"), ("Europe", "^FCHI", "CAC 40", "France"),
    ("Europe", "^STOXX50E", "Euro Stoxx 50", "Eurozone"), ("Europe", "^IBEX", "IBEX 35", "Spain"),
    ("Europe", "FTSEMIB.MI", "FTSE MIB", "Italy"), ("Europe", "^AEX", "AEX", "Netherlands"),
    ("Europe", "^SSMI", "SMI", "Switzerland"), ("Europe", "^OMXS30", "OMX Stockholm 30", "Sweden"),
    ("Americas", "^GSPC", "S&P 500", "United States"), ("Americas", "^DJI", "Dow Jones Industrial Average", "United States"),
    ("Americas", "^IXIC", "Nasdaq Composite", "United States"), ("Americas", "^RUT", "Russell 2000", "United States"),
    ("Americas", "^GSPTSE", "S&P/TSX Composite", "Canada"), ("Americas", "^BVSP", "Bovespa", "Brazil"), ("Americas", "^MXX", "IPC Mexico", "Mexico"),
    ("Middle East", "^TASI.SR", "Tadawul All Share", "Saudi Arabia"),
]
INDEX_SYMBOL = "^GSPC"

_OFFSETS = {"1W": pd.DateOffset(days=7), "1M": pd.DateOffset(months=1), "3M": pd.DateOffset(months=3), "1Y": pd.DateOffset(years=1)}


def period_change(close: pd.Series, period: str) -> dict | None:
    """Change from the close on or before the start of the period to the latest close.
    1D is the previous close; YTD is the last close of the previous year."""
    close = close.dropna()
    if len(close) < 2:
        return None
    last_date, last = close.index[-1], float(close.iloc[-1])
    if period == "1D":
        base = float(close.iloc[-2])
    else:
        if period == "YTD":
            before = close[close.index < pd.Timestamp(year=last_date.year, month=1, day=1)]
        else:
            cutoff = last_date - _OFFSETS[period]
            before = close[close.index <= cutoff]
            if before.empty and period == "1Y" and (close.index[0] - cutoff).days <= 5:
                before = close.iloc[:1]  # a year of history starts a day or two late
        if before.empty:
            return None
        base = float(before.iloc[-1])
    if base == 0:
        return None
    return {"last": last, "pct": (last / base - 1) * 100, "date": last_date.strftime("%Y-%m-%d")}


# ---------- world indexes ----------
def get_indices(period: str) -> dict:
    closes = data.get_closes([s for _, s, _, _ in INDICES], "1y")
    regions: dict[str, list] = {}
    for region, sym, name, country in INDICES:
        res = period_change(closes[sym], period) if sym in closes.columns else None
        regions.setdefault(region, []).append({
            "symbol": sym, "name": name, "country": country,
            "last": res["last"] if res else None, "change_pct": res["pct"] if res else None, "date": res["date"] if res else None,
        })
    return {"period": period, "regions": [{"name": r, "items": items} for r, items in regions.items()]}


# ---------- S&P 500 heatmap ----------
# Market cap = shares x price. Share counts barely move, so they are looked up once and kept for 30 days
# (on disk, so a restart doesn't repeat it). The first load fetches them in batches, so the page may
# show a partial map for a minute and fill in.
_SHARES_FILE = DATA_DIR / "sp500_shares.json"
_SHARES_TTL = 30 * 86400
_MAX_FAILS = 3
FETCH_BUDGET_SECONDS = 20.0
_lock = threading.Lock()
_shares: dict[str, dict] | None = None
_fails: dict[str, int] = defaultdict(int)
_inflight: set[str] = set()


def _cache() -> dict[str, dict]:
    global _shares
    if _shares is None:
        try:
            _shares = json.loads(_SHARES_FILE.read_text())
        except Exception:
            _shares = {}
    return _shares


def _save() -> None:
    with _lock:
        snapshot = dict(_cache())
    try:
        _SHARES_FILE.write_text(json.dumps(snapshot))
    except Exception:
        pass


def ensure_shares(symbols: list[str]) -> tuple[dict[str, float], int]:
    """Share counts for the symbols that have one, and how many are still being fetched."""
    cache, now = _cache(), time.time()
    with _lock:
        todo = [s for s in symbols if (s not in cache or now - cache[s]["at"] > _SHARES_TTL)
                and _fails[s] < _MAX_FAILS and s not in _inflight]
        _inflight.update(todo)

    def work(sym: str) -> None:
        try:
            value = data.get_shares(sym)
            with _lock:
                if value:
                    cache[sym] = {"shares": value, "at": time.time()}
                else:
                    _fails[sym] += 1
        finally:
            with _lock:
                _inflight.discard(sym)

    if todo:
        pool = ThreadPoolExecutor(max_workers=16)
        wait([pool.submit(work, s) for s in todo], timeout=FETCH_BUDGET_SECONDS)
        pool.shutdown(wait=False, cancel_futures=True)
        _save()

    with _lock:
        have = {s: cache[s]["shares"] for s in symbols if s in cache}
        pending = sum(1 for s in symbols if s not in cache and (s in _inflight or _fails[s] < _MAX_FAILS))
    return have, pending


def build_heatmap(period: str) -> dict:
    uni = universe.load_universe()
    meta = {s: (n, sec) for s, n, sec in uni["stocks"]}
    symbols = list(meta)
    closes = data.get_closes(symbols + [INDEX_SYMBOL], "1y")

    changes = {}
    for sym in symbols:
        if sym in closes.columns:
            res = period_change(closes[sym], period)
            if res:
                changes[sym] = res

    shares, pending = ensure_shares(list(changes))
    by_sector: dict[str, list] = defaultdict(list)
    for sym, res in changes.items():
        if sym in shares:
            name, sector = meta[sym]
            by_sector[sector].append({"symbol": sym, "name": name, "price": res["last"], "change_pct": res["pct"],
                                      "market_cap": shares[sym] * res["last"]})
    sectors = []
    for name, items in by_sector.items():
        items.sort(key=lambda x: -x["market_cap"])
        total = sum(i["market_cap"] for i in items)
        sectors.append({"name": name, "market_cap": total,
                        "change_pct": sum(i["market_cap"] * i["change_pct"] for i in items) / total, "stocks": items})
    sectors.sort(key=lambda s: -s["market_cap"])

    index = period_change(closes[INDEX_SYMBOL], period) if INDEX_SYMBOL in closes.columns else None
    return {
        "period": period,
        "as_of": max((r["date"] for r in changes.values()), default=None),
        "index_change_pct": index["pct"] if index else None,
        "sectors": sectors,
        "loaded": sum(len(s["stocks"]) for s in sectors),
        "total": len(symbols),
        "partial": pending > 0,
        "source": uni["source"],
    }
