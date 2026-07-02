"""Offline unit tests for the screener core (Yahoo Finance calls are mocked).

Run with:  python -m pytest earnings_screener/test_core.py -q
"""

from __future__ import annotations

import datetime as dt
from unittest import mock

import pandas as pd
import pytest

import core


# ---------------------------------------------------------------------------
# Index resolution / input parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("SP500", "SP500"),
        ("s&p 500", "SP500"),
        ("^GSPC", "SP500"),
        (" spx ", "SP500"),
        ("Nasdaq 100", "NASDAQ100"),
        ("QQQ", "NASDAQ100"),
        ("dow jones", "DOW30"),
        ("AAPL, MSFT", None),
        ("", None),
    ],
)
def test_resolve_index(text, expected):
    assert core.resolve_index(text) == expected


def test_parse_ticker_list():
    assert core.parse_ticker_list("aapl, msft nvda,") == ["AAPL", "MSFT", "NVDA"]
    assert core.parse_ticker_list("  ") == []


def test_yahooize_dots():
    assert core._yahooize("brk.b") == "BRK-B"


# ---------------------------------------------------------------------------
# Quarter helpers
# ---------------------------------------------------------------------------


def test_quarter_bounds():
    assert core.quarter_bounds(2026, 2) == (dt.date(2026, 4, 1), dt.date(2026, 7, 1))
    assert core.quarter_bounds(2026, 4) == (dt.date(2026, 10, 1), dt.date(2027, 1, 1))


def test_current_quarter_and_recent():
    assert core.current_quarter(dt.date(2026, 7, 2)) == (2026, 3)
    assert core.recent_quarters(3, dt.date(2026, 1, 15)) == [
        (2026, 1),
        (2025, 4),
        (2025, 3),
    ]


def test_compute_surprise_pct():
    assert core.compute_surprise_pct(1.10, 1.00) == pytest.approx(10.0)
    assert core.compute_surprise_pct(-0.50, -1.00) == pytest.approx(50.0)  # smaller loss = beat
    assert core.compute_surprise_pct(1.0, 0.0) is None
    assert core.compute_surprise_pct(float("nan"), 1.0) is None


# ---------------------------------------------------------------------------
# Earnings fetch (mocked yfinance)
# ---------------------------------------------------------------------------


def _fake_earnings_frame(rows):
    """rows: list of (date, estimate, actual, surprise_pct_or_None)."""
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d, *_ in rows], name="Earnings Date")
    return pd.DataFrame(
        {
            "EPS Estimate": [r[1] for r in rows],
            "Reported EPS": [r[2] for r in rows],
            "Surprise(%)": [r[3] for r in rows],
        },
        index=idx,
    )


def _mock_yf(frames_by_symbol):
    ticker = mock.MagicMock()

    def factory(symbol):
        t = mock.MagicMock()
        frame = frames_by_symbol.get(symbol)
        if isinstance(frame, Exception):
            t.get_earnings_dates.side_effect = frame
        else:
            t.get_earnings_dates.return_value = frame
        return t

    ticker.side_effect = factory
    return mock.patch.dict("sys.modules", {"yfinance": mock.MagicMock(Ticker=ticker)})


def test_fetch_earnings_surprise_picks_latest_report_in_window():
    frame = _fake_earnings_frame(
        [
            ("2026-10-25", 2.00, None, None),        # future, not yet reported
            ("2026-06-15", 1.00, 1.20, 20.0),        # in window (latest)
            ("2026-04-10", 0.90, 0.80, None),        # in window (older)
            ("2026-01-20", 0.85, 0.90, 5.9),         # previous quarter
        ]
    )
    with _mock_yf({"TEST": frame}):
        row = core.fetch_earnings_surprise("TEST", dt.date(2026, 4, 1), dt.date(2026, 7, 1))
    assert row["earnings_date"] == dt.date(2026, 6, 15)
    assert row["reported_eps"] == 1.20
    assert row["surprise_pct"] == pytest.approx(20.0)


def test_fetch_earnings_surprise_recomputes_missing_surprise():
    frame = _fake_earnings_frame([("2026-05-01", 2.00, 1.50, None)])
    with _mock_yf({"TEST": frame}):
        row = core.fetch_earnings_surprise("TEST", dt.date(2026, 4, 1), dt.date(2026, 7, 1))
    assert row["surprise_pct"] == pytest.approx(-25.0)


def test_fetch_earnings_surprise_none_when_not_reported():
    frame = _fake_earnings_frame([("2026-01-20", 0.85, 0.90, 5.9)])
    with _mock_yf({"TEST": frame}):
        assert core.fetch_earnings_surprise("TEST", dt.date(2026, 4, 1), dt.date(2026, 7, 1)) is None
    with _mock_yf({"TEST": None}):
        assert core.fetch_earnings_surprise("TEST", dt.date(2026, 4, 1), dt.date(2026, 7, 1)) is None


# ---------------------------------------------------------------------------
# Screening + aggregation
# ---------------------------------------------------------------------------


def test_screen_members_ranking_and_summary():
    members = pd.DataFrame(
        {
            "symbol": ["BIGBEAT", "SMALLBEAT", "MISS", "NOREPORT", "BROKEN"],
            "name": ["Big Beat Co", "Small Beat Co", "Miss Co", "No Report Co", "Broken Co"],
            "sector": ["Tech", "Tech", "Energy", "Utilities", "Tech"],
        }
    )
    frames = {
        "BIGBEAT": _fake_earnings_frame([("2026-05-05", 1.00, 1.50, 50.0)]),
        "SMALLBEAT": _fake_earnings_frame([("2026-05-06", 1.00, 1.05, 5.0)]),
        "MISS": _fake_earnings_frame([("2026-05-07", 1.00, 0.60, -40.0)]),
        "NOREPORT": _fake_earnings_frame([("2026-08-01", 1.00, None, None)]),
        "BROKEN": RuntimeError("boom"),
    }
    with _mock_yf(frames):
        result = core.screen_members(members, 2026, 2, max_workers=2)

    assert result.label == "2026Q2"
    assert result.total_members == 5
    assert result.failed_symbols == ["BROKEN"]
    assert len(result.scored) == 3
    assert list(result.results["symbol"]) == ["BIGBEAT", "SMALLBEAT", "MISS"]  # sorted desc
    assert result.beat_count == 2 and result.miss_count == 1
    assert result.average_surprise == pytest.approx((50 + 5 - 40) / 3)
    assert result.top(2)["symbol"].tolist() == ["BIGBEAT", "SMALLBEAT"]
    assert result.bottom(1)["symbol"].tolist() == ["MISS"]
    # sector merged in from the members frame
    assert result.results.loc[0, "name"] == "Big Beat Co"


def test_run_screen_rejects_garbage_index():
    with pytest.raises(ValueError):
        core.run_screen("", 2026, 2)
