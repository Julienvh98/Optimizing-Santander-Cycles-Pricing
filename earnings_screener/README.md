# Earnings Surprise Screener

Screen an equity index for the **top EPS beats and misses** — actual reported EPS vs. the
market (consensus) estimate — with data pulled live from **Yahoo Finance** via `yfinance`.

For each index member that reported in the selected calendar quarter, the screener computes

```
surprise % = (actual EPS − consensus estimate) / |consensus estimate| × 100
```

and shows the **top 5 beats**, the **bottom 5 misses**, and the **average surprise across
all reported members** of the index for that quarter.

## Contents

| File | What it is |
|---|---|
| `core.py` | Shared logic: index constituents, per-ticker earnings surprise, quarter aggregation |
| `streamlit_app.py` | Streamlit web app (textbox for index selection, quarter picker, charts, CSV export) |
| `earnings_surprise_screener.ipynb` | Jupyter notebook with **ipywidgets** controls (textbox + dropdown + button) |
| `test_core.py` | Offline unit tests for the core logic (mocked Yahoo data) |

## Setup

```bash
pip install -r earnings_screener/requirements.txt
```

## Streamlit app

```bash
streamlit run earnings_screener/streamlit_app.py
```

Type the index in the textbox — `SP500` (default), `NASDAQ100`, `DOW30`, common aliases
(`S&P 500`, `^GSPC`, `SPX`, …), or any comma-separated ticker list (`AAPL, MSFT, NVDA`) —
pick the reporting quarter, and press **Run screen**.

## Notebook (ipywidgets)

Open `earnings_surprise_screener.ipynb` in Jupyter and run all cells. The widget panel has a
**textbox for index selection**, a quarter dropdown, a progress bar, and a Run button. The
final cell answers "top and bottom 5 EPS surprises for the S&P 500 this quarter" as a script.

## Notes

- **Constituents**: fetched from Wikipedia (S&P 500 additionally falls back to the
  [`datasets/s-and-p-500-companies`](https://github.com/datasets/s-and-p-500-companies)
  mirror on GitHub if Wikipedia is unreachable).
- **Earnings data**: `yfinance`'s earnings-dates feed (`EPS Estimate`, `Reported EPS`,
  `Surprise(%)`). Where Yahoo's own surprise figure is missing it is recomputed from
  actual vs. estimate.
- **"This quarter"** means the calendar quarter in which the earnings were *announced*
  (announcements typically cover the previous fiscal quarter's results).
- A full S&P 500 screen makes ~500 Yahoo Finance requests (threaded, ~2–5 minutes).
  Results are cached for an hour in the Streamlit app.
- Requires unrestricted internet access to `*.finance.yahoo.com` and `en.wikipedia.org`.
