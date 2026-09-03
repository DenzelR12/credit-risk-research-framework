"""
Market Regime Monitor — VIX level + term structure
---------------------------------------------------
A single global "what kind of tape is this?" classification used as a
dashboard banner. Two inputs, both free from Yahoo Finance:

  1. ^VIX spot level — bucketed:
        < 15      calm
        15–20     normal
        20–28     elevated
        >= 28     stressed
  2. Term structure: VIX / VIX3M (^VIX3M).
        ratio < 1.0  = contango (normal — near-term vol cheaper than 3-month)
        ratio >= 1.0 = backwardation (stress — market paying up for
                       near-term protection; historically associated with
                       drawdowns and violent short squeezes)

Why it's here: the engine's opportunity modules are mostly SHORT-side
setups. Shorts behave very differently in a stressed, backwardated tape —
rallies are sharper and squeezes more violent. The banner warns when
short setups are firing in a tape that punishes shorts.

Honest limitations:
  - The bucket thresholds (15/20/28) are conventional round numbers used
    by practitioners, not calibrated regime-detection statistics.
  - VIX measures S&P 500 implied volatility. Small-cap consumer-finance
    names can be in their own private storm while VIX is calm.
  - Yahoo's ^VIX quotes can lag the CBOE feed by minutes.
"""

from __future__ import annotations

from datetime import datetime, timezone

import yfinance as yf


def _last_price(symbol: str) -> tuple[float | None, float | None]:
    """Returns (last, previous_close)."""
    t = yf.Ticker(symbol)
    hist = t.history(period="5d", interval="1d")
    if hist.empty:
        return None, None
    closes = [float(c) for c in hist["Close"].tolist() if c == c]
    last = closes[-1] if closes else None
    prev = closes[-2] if len(closes) >= 2 else None
    try:
        fast = dict(t.fast_info)
        live = fast.get("lastPrice") or fast.get("last_price")
        if live:
            prev = last if len(closes) >= 1 else prev
            last = float(live)
    except Exception:
        pass
    return last, prev


def get_market_regime() -> dict:
    vix, vix_prev = _last_price("^VIX")
    vix3m, _ = _last_price("^VIX3M")

    if vix is None:
        raise RuntimeError("Could not fetch ^VIX from Yahoo Finance")

    if vix < 15:
        bucket, label = "calm", "Calm tape"
    elif vix < 20:
        bucket, label = "normal", "Normal tape"
    elif vix < 28:
        bucket, label = "elevated", "Elevated volatility"
    else:
        bucket, label = "stressed", "Stressed tape"

    ratio = None
    structure = None
    warning = None
    if vix3m and vix3m > 0:
        ratio = round(vix / vix3m, 3)
        if ratio >= 1.0:
            structure = "backwardation"
            warning = ("VIX term structure is inverted (backwardation) — the market is "
                       "paying up for near-term protection. Short setups face elevated "
                       "squeeze risk; size down and respect stops.")
        else:
            structure = "contango"

    if bucket == "stressed" and warning is None:
        warning = ("VIX above 28 — violent two-way moves are common. Mechanical levels "
                   "get overrun more often in this regime.")

    return {
        "vix": round(vix, 2),
        "vix_prev_close": round(vix_prev, 2) if vix_prev else None,
        "vix_change": round(vix - vix_prev, 2) if vix_prev else None,
        "vix3m": round(vix3m, 2) if vix3m else None,
        "term_ratio": ratio,
        "term_structure": structure,
        "regime": bucket,
        "regime_label": label,
        "short_setup_warning": warning,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_market_regime(), indent=2))
