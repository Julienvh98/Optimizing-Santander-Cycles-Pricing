"""Streamlit earnings surprise screener.

Run with:
    streamlit run earnings_screener/streamlit_app.py

Type an index (SP500, NASDAQ100, DOW30 — or a comma-separated ticker list),
pick the quarter, and the app screens every member's latest reported EPS
against the consensus estimate: top 5 beats, bottom 5 misses, and the
average surprise across all members that reported.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

try:
    from core import (
        ScreenResult,
        get_index_members,
        parse_ticker_list,
        quarter_label,
        recent_quarters,
        resolve_index,
        screen_members,
    )
except ImportError:  # run from repo root: streamlit run earnings_screener/streamlit_app.py
    from earnings_screener.core import (
        ScreenResult,
        get_index_members,
        parse_ticker_list,
        quarter_label,
        recent_quarters,
        resolve_index,
        screen_members,
    )

# Diverging pair (blue = beat, red = miss) + muted ink, from the reference palette.
BEAT_COLOR = "#2a78d6"
MISS_COLOR = "#e34948"
LABEL_COLOR = "#898781"  # muted ink, legible on light and dark surfaces

st.set_page_config(page_title="Earnings Surprise Screener", page_icon="📈", layout="wide")

st.title("Earnings Surprise Screener")
st.caption(
    "Actual EPS vs. consensus estimate for every index member that reported "
    "in the selected quarter — data from Yahoo Finance via `yfinance`."
)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def cached_members(index_key: str) -> pd.DataFrame:
    return get_index_members(index_key)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_screen(index_text: str, year: int, quarter: int) -> ScreenResult:
    index_key = resolve_index(index_text)
    if index_key is not None:
        members = cached_members(index_key)
    else:
        tickers = parse_ticker_list(index_text)
        if not tickers:
            raise ValueError(
                f"Unrecognised index {index_text!r}. Try SP500, NASDAQ100, DOW30 "
                "or a comma-separated ticker list."
            )
        members = pd.DataFrame({"symbol": tickers, "name": tickers, "sector": None})

    bar = st.progress(0.0, text="Fetching earnings dates…")

    def on_progress(done: int, total: int, symbol: str) -> None:
        bar.progress(done / total, text=f"Fetching earnings… {done}/{total} ({symbol})")

    result = screen_members(members, year, quarter, progress=on_progress)
    bar.empty()
    return result


with st.form("screen_form"):
    col_index, col_quarter = st.columns([3, 1])
    index_text = col_index.text_input(
        "Index to analyse",
        value="SP500",
        help="SP500, NASDAQ100, DOW30 — or paste a comma-separated ticker list (e.g. AAPL, MSFT, NVDA).",
    )
    quarters = recent_quarters(6)
    quarter_choice = col_quarter.selectbox(
        "Reporting quarter",
        quarters,
        format_func=lambda yq: quarter_label(*yq),
        help="Calendar quarter in which the earnings were announced.",
    )
    submitted = st.form_submit_button("Run screen", type="primary")

if submitted:
    year, quarter = quarter_choice
    try:
        result = cached_screen(index_text, year, quarter)
    except Exception as exc:
        st.error(f"Screen failed: {exc}")
        st.stop()

    scored = result.scored
    if scored.empty:
        st.warning(
            f"No members of {index_text!r} have reported earnings in {result.label} yet "
            "(or Yahoo Finance returned no data). Try the previous quarter."
        )
        st.stop()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Average surprise — {result.label}", f"{result.average_surprise:+.2f}%")
    m2.metric("Median surprise", f"{result.median_surprise:+.2f}%")
    m3.metric("Beats / misses", f"{result.beat_count} / {result.miss_count}")
    m4.metric("Reported", f"{len(scored)} of {result.total_members}")

    top5, bottom5 = result.top(5), result.bottom(5)

    def fmt_table(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame[["symbol", "name", "sector", "earnings_date", "eps_estimate", "reported_eps", "surprise_pct"]]
        return out.rename(
            columns={
                "symbol": "Ticker",
                "name": "Company",
                "sector": "Sector",
                "earnings_date": "Reported on",
                "eps_estimate": "EPS estimate",
                "reported_eps": "Actual EPS",
                "surprise_pct": "Surprise %",
            }
        )

    col_top, col_bottom = st.columns(2)
    col_top.subheader("Top 5 beats")
    col_top.dataframe(
        fmt_table(top5).style.format({"EPS estimate": "{:.2f}", "Actual EPS": "{:.2f}", "Surprise %": "{:+.1f}%"}),
        hide_index=True,
        use_container_width=True,
    )
    col_bottom.subheader("Bottom 5 misses")
    col_bottom.dataframe(
        fmt_table(bottom5).style.format({"EPS estimate": "{:.2f}", "Actual EPS": "{:.2f}", "Surprise %": "{:+.1f}%"}),
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Biggest surprises")
    extremes = pd.concat([top5, bottom5]).drop_duplicates("symbol")
    extremes["direction"] = extremes["surprise_pct"].map(lambda v: "Beat" if v >= 0 else "Miss")
    sort_order = alt.EncodingSortField(field="surprise_pct", op="max", order="descending")
    base = alt.Chart(extremes).encode(
        y=alt.Y("symbol:N", sort=sort_order, title=None),
        x=alt.X("surprise_pct:Q", title="EPS surprise vs. estimate (%)"),
        tooltip=[
            alt.Tooltip("symbol", title="Ticker"),
            alt.Tooltip("name", title="Company"),
            alt.Tooltip("eps_estimate", title="EPS estimate", format=".2f"),
            alt.Tooltip("reported_eps", title="Actual EPS", format=".2f"),
            alt.Tooltip("surprise_pct", title="Surprise %", format="+.1f"),
        ],
    )
    bars = base.mark_bar(size=14, cornerRadiusEnd=4).encode(
        color=alt.Color(
            "direction:N",
            scale=alt.Scale(domain=["Beat", "Miss"], range=[BEAT_COLOR, MISS_COLOR]),
            legend=alt.Legend(title=None, orient="top"),
        )
    )
    label_text = alt.Text("surprise_pct:Q", format="+.1f")
    beat_labels = (
        base.transform_filter(alt.datum.surprise_pct >= 0)
        .mark_text(align="left", dx=4, color=LABEL_COLOR)
        .encode(text=label_text)
    )
    miss_labels = (
        base.transform_filter(alt.datum.surprise_pct < 0)
        .mark_text(align="right", dx=-4, color=LABEL_COLOR)
        .encode(text=label_text)
    )
    st.altair_chart(
        (bars + beat_labels + miss_labels).properties(height=360), use_container_width=True
    )

    with st.expander(f"All {len(scored)} reported members"):
        st.dataframe(
            fmt_table(scored).style.format(
                {"EPS estimate": "{:.2f}", "Actual EPS": "{:.2f}", "Surprise %": "{:+.1f}%"}
            ),
            hide_index=True,
            use_container_width=True,
        )
        st.download_button(
            "Download results as CSV",
            scored.to_csv(index=False).encode(),
            file_name=f"earnings_surprises_{index_text.strip().replace(' ', '_')}_{result.label}.csv",
            mime="text/csv",
        )

    if result.failed_symbols:
        st.caption(
            f"⚠️ Could not fetch data for {len(result.failed_symbols)} symbols: "
            + ", ".join(sorted(result.failed_symbols)[:20])
            + ("…" if len(result.failed_symbols) > 20 else "")
        )
else:
    st.info("Enter an index (try **SP500**) and press **Run screen**.")
