"""Core logic for the earnings surprise screener.

Fetches index constituents and, for each member, the most recent reported
quarterly EPS vs. the consensus estimate (via Yahoo Finance / yfinance),
then ranks the biggest beats and misses and computes the average surprise
for the quarter.

This module is UI-agnostic: it is shared by the Streamlit app
(streamlit_app.py) and the ipywidgets notebook
(earnings_surprise_screener.ipynb).
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import io
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Index resolution
# ---------------------------------------------------------------------------

# Canonical index keys and the free-text aliases users may type in the textbox.
INDEX_ALIASES = {
    "SP500": {"sp500", "s&p500", "s&p 500", "sp 500", "spx", "^gspc", "gspc", "sandp500"},
    "NASDAQ100": {"nasdaq100", "nasdaq 100", "ndx", "^ndx", "qqq", "nasdaq-100"},
    "DOW30": {"dow", "dow30", "dow 30", "djia", "^dji", "dji", "dow jones"},
}

WIKIPEDIA_SOURCES = {
    "SP500": {
        "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "symbol_col": "Symbol",
        "name_col": "Security",
        "sector_col": "GICS Sector",
    },
    "NASDAQ100": {
        "url": "https://en.wikipedia.org/wiki/Nasdaq-100",
        "symbol_col": "Ticker",
        "name_col": "Company",
        "sector_col": "GICS Sector",
    },
    "DOW30": {
        "url": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
        "symbol_col": "Symbol",
        "name_col": "Company",
        "sector_col": "Industry",
    },
}

# Mirror for S&P 500 constituents when Wikipedia is unreachable.
SP500_FALLBACK_CSV = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "main/data/constituents.csv"
)


def resolve_index(text: str) -> Optional[str]:
    """Map free-form user input (e.g. 'S&P 500', '^GSPC') to a canonical key.

    Returns None when the text doesn't match a supported index, in which
    case the caller may treat it as a comma-separated ticker list.
    """
    cleaned = text.strip().lower()
    for key, aliases in INDEX_ALIASES.items():
        if cleaned == key.lower() or cleaned in aliases:
            return key
    return None


def parse_ticker_list(text: str) -> list[str]:
    """Parse 'AAPL, MSFT NVDA' style input into a list of Yahoo symbols."""
    raw = text.replace(",", " ").split()
    return [t.strip().upper() for t in raw if t.strip()]


def _yahooize(symbol: str) -> str:
    """Wikipedia uses BRK.B / BF.B; Yahoo Finance wants BRK-B / BF-B."""
    return symbol.strip().upper().replace(".", "-")


def get_index_members(index_key: str) -> pd.DataFrame:
    """Return DataFrame[symbol, name, sector] for a supported index.

    Tries Wikipedia first; for SP500 falls back to a GitHub-hosted mirror
    of the constituents list.
    """
    src = WIKIPEDIA_SOURCES[index_key]
    errors = []
    try:
        tables = pd.read_html(src["url"])
        for table in tables:
            if src["symbol_col"] in table.columns and src["name_col"] in table.columns:
                out = pd.DataFrame(
                    {
                        "symbol": table[src["symbol_col"]].map(_yahooize),
                        "name": table[src["name_col"]],
                        "sector": table.get(src["sector_col"], pd.Series(dtype=str)),
                    }
                )
                return out.dropna(subset=["symbol"]).drop_duplicates("symbol").reset_index(drop=True)
        errors.append(f"no matching table on {src['url']}")
    except Exception as exc:  # network blocked, layout change, ...
        errors.append(f"wikipedia: {exc}")

    if index_key == "SP500":
        try:
            import requests

            resp = requests.get(SP500_FALLBACK_CSV, timeout=30)
            resp.raise_for_status()
            table = pd.read_csv(io.StringIO(resp.text))
            return pd.DataFrame(
                {
                    "symbol": table["Symbol"].map(_yahooize),
                    "name": table["Security"],
                    "sector": table["GICS Sector"],
                }
            )
        except Exception as exc:
            errors.append(f"github fallback: {exc}")

    raise RuntimeError(
        f"Could not fetch constituents for {index_key}: " + "; ".join(errors)
    )


# ---------------------------------------------------------------------------
# Quarter handling
# ---------------------------------------------------------------------------


def current_quarter(today: Optional[dt.date] = None) -> tuple[int, int]:
    today = today or dt.date.today()
    return today.year, (today.month - 1) // 3 + 1


def quarter_bounds(year: int, quarter: int) -> tuple[dt.date, dt.date]:
    """[start, end) date bounds of a calendar quarter."""
    start = dt.date(year, 3 * (quarter - 1) + 1, 1)
    end = dt.date(year + 1, 1, 1) if quarter == 4 else dt.date(year, 3 * quarter + 1, 1)
    return start, end


def quarter_label(year: int, quarter: int) -> str:
    return f"{year}Q{quarter}"


def recent_quarters(n: int = 4, today: Optional[dt.date] = None) -> list[tuple[int, int]]:
    """Current quarter first, then the n-1 preceding ones."""
    year, quarter = current_quarter(today)
    out = []
    for _ in range(n):
        out.append((year, quarter))
        quarter -= 1
        if quarter == 0:
            year, quarter = year - 1, 4
    return out


# ---------------------------------------------------------------------------
# Earnings surprise fetching
# ---------------------------------------------------------------------------


def compute_surprise_pct(actual: float, estimate: float) -> Optional[float]:
    """Surprise % = (actual - estimate) / |estimate| * 100."""
    if pd.isna(actual) or pd.isna(estimate) or estimate == 0:
        return None
    return (actual - estimate) / abs(estimate) * 100.0


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def fetch_earnings_surprise(
    symbol: str,
    start: dt.date,
    end: dt.date,
    retries: int = 2,
) -> Optional[dict]:
    """Latest reported EPS vs. estimate for `symbol` announced in [start, end).

    Returns None when the company has not reported in the window or data
    is unavailable. Uses yfinance's earnings-dates feed, which includes
    'EPS Estimate', 'Reported EPS' and 'Surprise(%)'.
    """
    import yfinance as yf

    last_error = None
    for attempt in range(retries + 1):
        try:
            frame = yf.Ticker(symbol).get_earnings_dates(limit=12)
            break
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"{symbol}: {last_error}")

    if frame is None or frame.empty:
        return None

    frame = frame.reset_index()
    date_col = _pick_column(frame, ["Earnings Date", "index"])
    est_col = _pick_column(frame, ["EPS Estimate", "epsEstimate"])
    actual_col = _pick_column(frame, ["Reported EPS", "epsActual"])
    surprise_col = _pick_column(frame, ["Surprise(%)", "Surprise (%)", "surprisePercent"])
    if date_col is None or actual_col is None:
        return None

    dates = pd.to_datetime(frame[date_col]).dt.tz_localize(None).dt.date
    in_window = (dates >= start) & (dates < end) & frame[actual_col].notna()
    reported = frame[in_window]
    if reported.empty:
        return None

    row = reported.iloc[0]  # feed is newest-first; take latest report in window
    actual = float(row[actual_col])
    estimate = float(row[est_col]) if est_col and pd.notna(row[est_col]) else float("nan")
    surprise = None
    if surprise_col and pd.notna(row[surprise_col]):
        surprise = float(row[surprise_col])
    if surprise is None:
        surprise = compute_surprise_pct(actual, estimate)

    return {
        "symbol": symbol,
        "earnings_date": dates[reported.index[0]],
        "eps_estimate": None if pd.isna(estimate) else estimate,
        "reported_eps": actual,
        "surprise_pct": surprise,
    }


def screen_members(
    members: pd.DataFrame,
    year: int,
    quarter: int,
    max_workers: int = 8,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> "ScreenResult":
    """Fetch surprises for every index member that reported in the quarter.

    `progress(done, total, symbol)` is called after each ticker completes,
    letting both UIs render a progress bar.
    """
    start, end = quarter_bounds(year, quarter)
    symbols = list(members["symbol"])
    rows: list[dict] = []
    failures: list[str] = []
    done = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(fetch_earnings_surprise, sym, start, end): sym for sym in symbols
        }
        for future in concurrent.futures.as_completed(futures):
            sym = futures[future]
            try:
                result = future.result()
                if result is not None:
                    rows.append(result)
            except Exception:
                failures.append(sym)
            done += 1
            if progress:
                progress(done, len(symbols), sym)

    frame = pd.DataFrame(
        rows,
        columns=["symbol", "earnings_date", "eps_estimate", "reported_eps", "surprise_pct"],
    )
    if not frame.empty:
        frame = frame.merge(members, on="symbol", how="left")
        frame = frame.sort_values("surprise_pct", ascending=False).reset_index(drop=True)
    return ScreenResult(
        results=frame,
        year=year,
        quarter=quarter,
        total_members=len(symbols),
        failed_symbols=failures,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass
class ScreenResult:
    """Screen output plus the summary stats both UIs display."""

    results: pd.DataFrame
    year: int
    quarter: int
    total_members: int
    failed_symbols: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return quarter_label(self.year, self.quarter)

    @property
    def scored(self) -> pd.DataFrame:
        """Members that reported and have a computable surprise."""
        if self.results.empty:
            return self.results
        return self.results.dropna(subset=["surprise_pct"])

    @property
    def average_surprise(self) -> Optional[float]:
        scored = self.scored
        return None if scored.empty else float(scored["surprise_pct"].mean())

    @property
    def median_surprise(self) -> Optional[float]:
        scored = self.scored
        return None if scored.empty else float(scored["surprise_pct"].median())

    @property
    def beat_count(self) -> int:
        return int((self.scored["surprise_pct"] > 0).sum()) if not self.scored.empty else 0

    @property
    def miss_count(self) -> int:
        return int((self.scored["surprise_pct"] < 0).sum()) if not self.scored.empty else 0

    def top(self, n: int = 5) -> pd.DataFrame:
        return self.scored.nlargest(n, "surprise_pct").reset_index(drop=True)

    def bottom(self, n: int = 5) -> pd.DataFrame:
        return self.scored.nsmallest(n, "surprise_pct").reset_index(drop=True)


def run_screen(
    index_text: str,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    max_workers: int = 8,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> ScreenResult:
    """End-to-end screen from free-form index text (or a ticker list)."""
    if year is None or quarter is None:
        year, quarter = current_quarter()

    index_key = resolve_index(index_text)
    if index_key is not None:
        members = get_index_members(index_key)
    else:
        tickers = parse_ticker_list(index_text)
        if not tickers:
            raise ValueError(
                f"Unrecognised index {index_text!r}. Try SP500, NASDAQ100, DOW30 "
                "or a comma-separated ticker list."
            )
        members = pd.DataFrame({"symbol": tickers, "name": tickers, "sector": None})

    return screen_members(members, year, quarter, max_workers=max_workers, progress=progress)
