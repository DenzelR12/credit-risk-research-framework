"""
Module 1: Automated Macro Credit Risk & Delinquency Monitor
--------------------------------------------------------------
Pulls public FRED CSV endpoints (no API key required) and computes:
  - Rolling Z-scores for High Yield credit spreads
  - True calendar-accurate YoY deltas for delinquency series
  - Yield curve inversion signal

Bug fixes vs. the original draft:
  1. The original script combined a DAILY series (HY_Spread) with QUARTERLY
     series (Auto_Delinq, CC_Delinq) via a single concat + ffill, then called
     `.diff(4)` on the whole frame. After ffill, diff(4) computed a 4-ROW
     delta (4 calendar days), not a 4-quarter / 1-year delta. This silently
     produced meaningless "YoY" numbers.
  2. This version reindexes every series onto a full daily calendar grid
     BEFORE forward-filling, so `.diff(365)` is a true year-over-year
     comparison regardless of each series' native reporting frequency.
  3. Added defensive handling for FRED's "." missing-value marker and
     network/HTTP failures per-series (one bad series no longer kills the
     whole run).
"""

from __future__ import annotations
import sys
import time
import pandas as pd
import numpy as np
import requests
from io import StringIO

INDICATORS = {
    "HY_Spread": "BAMLH0A0HYM2",       # ICE BofA High Yield Option-Adjusted Spread (daily)
    "Auto_Delinq": "DRALACBN",         # Auto Loan Delinquency Rate, Commercial Banks (quarterly)
    "CreditCard_Delinq": "DRCCLACBS",  # Credit Card Delinquency Rate, Commercial Banks (quarterly)
    "CRE_Loans": "CREACBW027SBOG",     # Commercial Real Estate Loans outstanding (weekly)
    "Yield_Curve_10Y2Y": "T10Y2Y",     # 10Y-2Y Treasury Yield Curve Spread (daily)
}

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def fetch_fred_series(series_id: str, timeout: int = 30, retries: int = 3) -> pd.Series:
    """Fetch a single FRED series as a clean pandas Series indexed by date."""
    url = FRED_CSV_URL.format(series_id=series_id)
    # NOTE: fred.stlouisfed.org can stall/read-timeout intermittently on rapid
    # back-to-back requests. Use the default requests UA (which is what works
    # reliably against this endpoint) and retry with backoff on timeout.
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    else:
        raise last_exc
    df = pd.read_csv(StringIO(resp.text))
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)
    series = pd.to_numeric(df[series_id], errors="coerce")
    series.name = series_id
    return series


def build_daily_panel(indicators: dict[str, str]) -> pd.DataFrame:
    """Fetch all indicators and align them onto one full daily calendar grid."""
    fetched = {}
    for label, series_id in indicators.items():
        try:
            fetched[label] = fetch_fred_series(series_id)
            print(f"  [ok] fetched {label} ({series_id}): {len(fetched[label])} rows")
        except Exception as exc:
            print(f"  [warn] failed to fetch {label} ({series_id}): {exc}", file=sys.stderr)
        time.sleep(1)  # space out requests to avoid FRED rate limiting

    if not fetched:
        raise RuntimeError("No FRED series could be fetched — check network access.")

    start = min(s.index.min() for s in fetched.values())
    end = max(s.index.max() for s in fetched.values())
    daily_index = pd.date_range(start=start, end=end, freq="D")

    panel = pd.DataFrame(index=daily_index)
    for label, series in fetched.items():
        panel[label] = series.reindex(daily_index).ffill()

    return panel


def generate_credit_stress_report(save_csv: str | None = None) -> dict:
    print("Fetching FRED series...")
    data = build_daily_panel(INDICATORS)

    # Rolling Z-score on the daily-ffilled HY spread (calendar days -> 3yr ~ 365*3)
    rolling_window = 365 * 3
    if "HY_Spread" in data:
        roll_mean = data["HY_Spread"].rolling(rolling_window, min_periods=250).mean()
        roll_std = data["HY_Spread"].rolling(rolling_window, min_periods=250).std()
        data["HY_Spread_ZScore"] = (data["HY_Spread"] - roll_mean) / roll_std

    # True calendar-year-over-year deltas (365 calendar days, not 4 rows)
    if "Auto_Delinq" in data:
        data["Auto_Delinq_YoY"] = data["Auto_Delinq"].diff(365)
    if "CreditCard_Delinq" in data:
        data["CC_Delinq_YoY"] = data["CreditCard_Delinq"].diff(365)

    valid = data.dropna(subset=[c for c in ["HY_Spread", "HY_Spread_ZScore"] if c in data.columns])
    if valid.empty:
        raise RuntimeError("Insufficient data to compute latest report row.")
    latest_date = valid.index[-1]
    latest = data.loc[latest_date]

    alerts = []
    if "HY_Spread_ZScore" in latest and pd.notna(latest["HY_Spread_ZScore"]) and latest["HY_Spread_ZScore"] > 2.0:
        alerts.append(f"CRITICAL: High Yield Spreads expanded rapidly (Z-Score: {latest['HY_Spread_ZScore']:.2f}).")
    if "Auto_Delinq_YoY" in latest and pd.notna(latest["Auto_Delinq_YoY"]) and latest["Auto_Delinq_YoY"] > 0.5:
        alerts.append(f"WARNING: Auto loan delinquencies spiking (+{latest['Auto_Delinq_YoY']:.2f}pp YoY).")
    if "CC_Delinq_YoY" in latest and pd.notna(latest["CC_Delinq_YoY"]) and latest["CC_Delinq_YoY"] > 0.75:
        alerts.append(f"WARNING: Consumer credit card delinquencies accelerating (+{latest['CC_Delinq_YoY']:.2f}pp YoY).")
    if "Yield_Curve_10Y2Y" in latest and pd.notna(latest["Yield_Curve_10Y2Y"]) and latest["Yield_Curve_10Y2Y"] < 0:
        alerts.append("SIGNAL: Yield curve inverted (historically precedes recessions by 12-18 months).")

    print(f"\n=== CREDIT RISK MONITOR REPORT ({latest_date.strftime('%Y-%m-%d')}) ===")
    for label in INDICATORS:
        if label in latest and pd.notna(latest[label]):
            print(f"• {label}: {latest[label]:.3f}")
    if "HY_Spread_ZScore" in latest and pd.notna(latest["HY_Spread_ZScore"]):
        print(f"• HY_Spread Z-Score (3yr): {latest['HY_Spread_ZScore']:.2f}")
    print("-" * 60)

    if alerts:
        print("ACTIVE RISK ALERTS:")
        for a in alerts:
            print(f" [!] {a}")
    else:
        print("No threshold breaches detected. Credit conditions within normal historical ranges.")

    if save_csv:
        data.to_csv(save_csv)
        print(f"\nFull panel saved to {save_csv}")

    trailing = data.tail(730).reset_index().rename(columns={"index": "date"})
    trailing_series = []
    for _, row in trailing.iterrows():
        entry = {"date": row["date"].strftime("%Y-%m-%d")}
        for col in ["HY_Spread", "HY_Spread_ZScore", "Yield_Curve_10Y2Y", "Auto_Delinq_YoY", "CC_Delinq_YoY"]:
            if col in trailing.columns:
                val = row[col]
                entry[col] = None if pd.isna(val) else float(val)
        trailing_series.append(entry)

    return {
        "latest_date": str(latest_date.date()),
        "latest": {k: (None if pd.isna(v) else float(v)) for k, v in latest.to_dict().items()},
        "alerts": alerts,
        "trailing_series": trailing_series,
    }


if __name__ == "__main__":
    generate_credit_stress_report(save_csv="macro_credit_panel.csv")
