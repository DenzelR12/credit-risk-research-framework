"""
Crypto Cross-Exchange Arbitrage Scanner
----------------------------------------------------------------
Compares live spot prices for the same asset across independent exchanges
(Coinbase, Kraken, Bitstamp — all free, no-key public REST endpoints) and
flags spreads. Binance's public API is geo-restricted from this server's
network location and is excluded rather than silently faked.

Honest limitations (read before wiring alerts to real money):
  1. These are top-of-book/last-trade prices, not executable depth — the
     size you can actually move at the quoted price may be thin.
  2. Round-trip cost is NOT just the price gap. You pay a taker fee on
     both legs (~0.10-0.60% each, exchange-dependent) plus, if you must
     move the asset itself between exchanges, a network/withdrawal fee
     and a settlement delay (minutes for most coins, up to ~60 min for
     BTC waiting on confirmations) during which the spread can vanish.
  3. A spread only clears ACTIONABLE_SPREAD_PCT_THRESHOLD below because
     that is roughly the combined fee floor — anything under that is
     very unlikely to be net-profitable for a manual retail trade, even
     if it's real. Spreads this small are mostly captured by bots in
     milliseconds; a human clicking through browsers will usually miss it.
  4. This module cannot execute anything — it's read-only detection.
"""

from __future__ import annotations
import requests

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Rough combined taker-fee floor (both legs) below which a spread is very
# unlikely to survive fees + slippage for a manual retail trade.
ACTIONABLE_SPREAD_PCT_THRESHOLD = 0.5

ASSETS = {
    "BTC": {
        "coinbase": "BTC-USD",
        "kraken": "XBTUSD",
        "bitstamp": "btcusd",
    },
    "ETH": {
        "coinbase": "ETH-USD",
        "kraken": "ETHUSD",
        "bitstamp": "ethusd",
    },
    "SOL": {
        "coinbase": "SOL-USD",
        "kraken": "SOLUSD",
        "bitstamp": "solusd",
    },
    "XRP": {
        "coinbase": "XRP-USD",
        "kraken": "XRPUSD",
        "bitstamp": "xrpusd",
    },
}


def _fetch_coinbase(product: str) -> float | None:
    try:
        resp = requests.get(
            f"https://api.exchange.coinbase.com/products/{product}/ticker",
            headers=BROWSER_HEADERS, timeout=10,
        )
        resp.raise_for_status()
        return float(resp.json()["price"])
    except Exception:
        return None


def _fetch_kraken(pair: str) -> float | None:
    try:
        resp = requests.get(
            "https://api.kraken.com/0/public/Ticker",
            params={"pair": pair}, headers=BROWSER_HEADERS, timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            return None
        result = data["result"]
        key = next(iter(result))
        return float(result[key]["c"][0])  # last trade closed price
    except Exception:
        return None


def _fetch_bitstamp(pair: str) -> float | None:
    try:
        # Bitstamp's edge appears to challenge/redirect requests carrying a
        # generic browser User-Agent header; the bare default requests UA
        # (no custom headers) passes through cleanly.
        resp = requests.get(
            f"https://www.bitstamp.net/api/v2/ticker/{pair}/",
            timeout=10,
        )
        resp.raise_for_status()
        return float(resp.json()["last"])
    except Exception:
        return None


def scan_asset(symbol: str, ids: dict) -> dict:
    prices = {
        "coinbase": _fetch_coinbase(ids["coinbase"]),
        "kraken": _fetch_kraken(ids["kraken"]),
        "bitstamp": _fetch_bitstamp(ids["bitstamp"]),
    }
    valid = {k: v for k, v in prices.items() if v is not None}

    if len(valid) < 2:
        return {
            "asset": symbol,
            "prices": prices,
            "error": "Fewer than 2 exchanges returned a price — cannot compute a spread.",
        }

    low_exchange = min(valid, key=valid.get)
    high_exchange = max(valid, key=valid.get)
    low_price = valid[low_exchange]
    high_price = valid[high_exchange]
    spread_abs = high_price - low_price
    spread_pct = (spread_abs / low_price) * 100 if low_price else 0.0

    return {
        "asset": symbol,
        "prices": prices,
        "buy_at": low_exchange,
        "buy_price": low_price,
        "sell_at": high_exchange,
        "sell_price": high_price,
        "spread_abs": round(spread_abs, 6),
        "spread_pct": round(spread_pct, 4),
        "actionable": spread_pct >= ACTIONABLE_SPREAD_PCT_THRESHOLD,
    }


def scan_all() -> dict:
    results = [scan_asset(symbol, ids) for symbol, ids in ASSETS.items()]
    actionable = [r for r in results if r.get("actionable")]
    return {
        "assets": results,
        "actionable_count": len(actionable),
        "actionable_spreads": actionable,
        "fee_floor_note": (
            f"Spreads below {ACTIONABLE_SPREAD_PCT_THRESHOLD}% are flagged not-actionable — "
            "that's roughly the combined taker-fee floor for a manual two-exchange round trip. "
            "Binance is excluded (its public API is geo-restricted from this server)."
        ),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(scan_all(), indent=2))
