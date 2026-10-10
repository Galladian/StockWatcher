"""The list of S&P 500 companies: read from Wikipedia (kept for a week), with a built-in fallback
of the largest US companies if Wikipedia can't be reached."""
import io
import json
import time
import urllib.request

import pandas as pd

from .config import DATA_DIR

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_CACHE_FILE = DATA_DIR / "sp500_constituents.json"
_FRESH_SECONDS = 7 * 86400
_mem: dict = {"until": 0.0, "value": None}

# (symbol, name, GICS sector). About 150 of the largest names, used only when the live list is unavailable.
FALLBACK = [
    ("AAPL", "Apple", "Information Technology"), ("MSFT", "Microsoft", "Information Technology"), ("NVDA", "NVIDIA", "Information Technology"),
    ("AVGO", "Broadcom", "Information Technology"), ("ORCL", "Oracle", "Information Technology"), ("CRM", "Salesforce", "Information Technology"),
    ("AMD", "AMD", "Information Technology"), ("CSCO", "Cisco", "Information Technology"), ("ADBE", "Adobe", "Information Technology"),
    ("ACN", "Accenture", "Information Technology"), ("IBM", "IBM", "Information Technology"), ("QCOM", "Qualcomm", "Information Technology"),
    ("TXN", "Texas Instruments", "Information Technology"), ("INTU", "Intuit", "Information Technology"), ("NOW", "ServiceNow", "Information Technology"),
    ("AMAT", "Applied Materials", "Information Technology"), ("MU", "Micron", "Information Technology"), ("LRCX", "Lam Research", "Information Technology"),
    ("KLAC", "KLA", "Information Technology"), ("ADI", "Analog Devices", "Information Technology"), ("PANW", "Palo Alto Networks", "Information Technology"),
    ("CRWD", "CrowdStrike", "Information Technology"), ("SNPS", "Synopsys", "Information Technology"), ("CDNS", "Cadence", "Information Technology"),
    ("INTC", "Intel", "Information Technology"), ("APH", "Amphenol", "Information Technology"), ("ANET", "Arista Networks", "Information Technology"),
    ("PLTR", "Palantir", "Information Technology"),
    ("GOOGL", "Alphabet (A)", "Communication Services"), ("GOOG", "Alphabet (C)", "Communication Services"), ("META", "Meta Platforms", "Communication Services"),
    ("NFLX", "Netflix", "Communication Services"), ("DIS", "Walt Disney", "Communication Services"), ("CMCSA", "Comcast", "Communication Services"),
    ("T", "AT&T", "Communication Services"), ("VZ", "Verizon", "Communication Services"), ("TMUS", "T-Mobile US", "Communication Services"),
    ("AMZN", "Amazon", "Consumer Discretionary"), ("TSLA", "Tesla", "Consumer Discretionary"), ("HD", "Home Depot", "Consumer Discretionary"),
    ("MCD", "McDonald's", "Consumer Discretionary"), ("BKNG", "Booking Holdings", "Consumer Discretionary"), ("LOW", "Lowe's", "Consumer Discretionary"),
    ("TJX", "TJX Companies", "Consumer Discretionary"), ("NKE", "Nike", "Consumer Discretionary"), ("SBUX", "Starbucks", "Consumer Discretionary"),
    ("ABNB", "Airbnb", "Consumer Discretionary"), ("CMG", "Chipotle", "Consumer Discretionary"), ("ORLY", "O'Reilly Automotive", "Consumer Discretionary"),
    ("MAR", "Marriott", "Consumer Discretionary"), ("GM", "General Motors", "Consumer Discretionary"), ("F", "Ford", "Consumer Discretionary"),
    ("RCL", "Royal Caribbean", "Consumer Discretionary"),
    ("BRK-B", "Berkshire Hathaway", "Financials"), ("JPM", "JPMorgan Chase", "Financials"), ("V", "Visa", "Financials"), ("MA", "Mastercard", "Financials"),
    ("BAC", "Bank of America", "Financials"), ("WFC", "Wells Fargo", "Financials"), ("GS", "Goldman Sachs", "Financials"),
    ("MS", "Morgan Stanley", "Financials"), ("AXP", "American Express", "Financials"), ("C", "Citigroup", "Financials"),
    ("SCHW", "Charles Schwab", "Financials"), ("BLK", "BlackRock", "Financials"), ("SPGI", "S&P Global", "Financials"),
    ("PGR", "Progressive", "Financials"), ("CB", "Chubb", "Financials"), ("USB", "U.S. Bancorp", "Financials"), ("PNC", "PNC Financial", "Financials"),
    ("COF", "Capital One", "Financials"), ("ICE", "Intercontinental Exchange", "Financials"), ("CME", "CME Group", "Financials"), ("AON", "Aon", "Financials"),
    ("LLY", "Eli Lilly", "Health Care"), ("UNH", "UnitedHealth", "Health Care"), ("JNJ", "Johnson & Johnson", "Health Care"), ("ABBV", "AbbVie", "Health Care"),
    ("MRK", "Merck", "Health Care"), ("TMO", "Thermo Fisher", "Health Care"), ("ABT", "Abbott", "Health Care"), ("DHR", "Danaher", "Health Care"),
    ("ISRG", "Intuitive Surgical", "Health Care"), ("AMGN", "Amgen", "Health Care"), ("PFE", "Pfizer", "Health Care"),
    ("BSX", "Boston Scientific", "Health Care"), ("GILD", "Gilead", "Health Care"), ("SYK", "Stryker", "Health Care"), ("VRTX", "Vertex", "Health Care"),
    ("REGN", "Regeneron", "Health Care"), ("MDT", "Medtronic", "Health Care"), ("BMY", "Bristol-Myers Squibb", "Health Care"),
    ("CVS", "CVS Health", "Health Care"), ("ELV", "Elevance Health", "Health Care"), ("CI", "Cigna", "Health Care"), ("ZTS", "Zoetis", "Health Care"),
    ("GE", "GE Aerospace", "Industrials"), ("CAT", "Caterpillar", "Industrials"), ("RTX", "RTX", "Industrials"), ("HON", "Honeywell", "Industrials"),
    ("UNP", "Union Pacific", "Industrials"), ("BA", "Boeing", "Industrials"), ("DE", "Deere", "Industrials"), ("LMT", "Lockheed Martin", "Industrials"),
    ("ETN", "Eaton", "Industrials"), ("UPS", "UPS", "Industrials"), ("ADP", "ADP", "Industrials"), ("WM", "Waste Management", "Industrials"),
    ("GD", "General Dynamics", "Industrials"), ("NOC", "Northrop Grumman", "Industrials"), ("UBER", "Uber", "Industrials"),
    ("WMT", "Walmart", "Consumer Staples"), ("COST", "Costco", "Consumer Staples"), ("PG", "Procter & Gamble", "Consumer Staples"),
    ("KO", "Coca-Cola", "Consumer Staples"), ("PEP", "PepsiCo", "Consumer Staples"), ("PM", "Philip Morris", "Consumer Staples"),
    ("MDLZ", "Mondelez", "Consumer Staples"), ("MO", "Altria", "Consumer Staples"), ("CL", "Colgate-Palmolive", "Consumer Staples"),
    ("TGT", "Target", "Consumer Staples"),
    ("XOM", "Exxon Mobil", "Energy"), ("CVX", "Chevron", "Energy"), ("COP", "ConocoPhillips", "Energy"), ("SLB", "SLB", "Energy"),
    ("EOG", "EOG Resources", "Energy"), ("WMB", "Williams", "Energy"), ("KMI", "Kinder Morgan", "Energy"), ("PSX", "Phillips 66", "Energy"),
    ("OXY", "Occidental", "Energy"),
    ("NEE", "NextEra Energy", "Utilities"), ("SO", "Southern Company", "Utilities"), ("DUK", "Duke Energy", "Utilities"),
    ("CEG", "Constellation Energy", "Utilities"), ("AEP", "American Electric Power", "Utilities"),
    ("PLD", "Prologis", "Real Estate"), ("AMT", "American Tower", "Real Estate"), ("EQIX", "Equinix", "Real Estate"), ("WELL", "Welltower", "Real Estate"),
    ("SPG", "Simon Property", "Real Estate"), ("PSA", "Public Storage", "Real Estate"), ("O", "Realty Income", "Real Estate"),
    ("LIN", "Linde", "Materials"), ("SHW", "Sherwin-Williams", "Materials"), ("APD", "Air Products", "Materials"), ("ECL", "Ecolab", "Materials"),
    ("FCX", "Freeport-McMoRan", "Materials"), ("NEM", "Newmont", "Materials"),
]


def parse_wikipedia(html: str) -> list[tuple[str, str, str]]:
    """(symbol, name, sector) rows from the 'constituents' table. Yahoo writes BRK.B as BRK-B."""
    df = pd.read_html(io.StringIO(html), attrs={"id": "constituents"})[0]
    col = lambda start: next(c for c in df.columns if str(c).lower().startswith(start))  # noqa: E731
    sym, name, sector = col("symbol"), col("security"), col("gics sector")
    return [(str(a).strip().replace(".", "-"), str(b).strip(), str(c).strip()) for a, b, c in zip(df[sym], df[name], df[sector])]


def _download() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (personal stock dashboard)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def _remember(value: dict, ttl: float) -> dict:
    _mem["value"], _mem["until"] = value, time.time() + ttl
    return value


def load_universe() -> dict:
    """{'source': ..., 'stocks': [(symbol, name, sector), ...]}"""
    now = time.time()
    if _mem["value"] and now < _mem["until"]:
        return _mem["value"]

    disk = None
    try:
        disk = json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    if disk and now - disk["at"] < _FRESH_SECONDS:
        return _remember({"source": "Wikipedia", "stocks": [tuple(x) for x in disk["stocks"]]}, 12 * 3600)

    try:
        stocks = parse_wikipedia(_download())
        if len(stocks) < 400:
            raise ValueError("list looks incomplete")
        _CACHE_FILE.write_text(json.dumps({"at": now, "stocks": stocks}))
        return _remember({"source": "Wikipedia", "stocks": stocks}, 12 * 3600)
    except Exception:
        if disk:  # an older copy beats the fallback
            return _remember({"source": "Wikipedia (older copy)", "stocks": [tuple(x) for x in disk["stocks"]]}, 600)
        return _remember({"source": "built-in list of the largest companies", "stocks": FALLBACK}, 600)
