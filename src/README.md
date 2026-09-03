# Public Engineering Subset

Selected standalone components from the private implementation behind the Credit Risk Research Framework. These files are published verbatim from the working engine — they run as-is against free public endpoints.

## What is public

- `http_resilience.py` — Shared retry primitive for rate-limited public APIs: decorrelated-jitter backoff (AWS pattern) with server-sent `Retry-After` taking precedence, retryable-status allowlist, and fail-fast behavior for permanent errors.
- `macro_credit_monitor.py` — FRED public-CSV ingestion with frequency-aware alignment: every series is reindexed onto a daily calendar grid before forward-fill, so 365-day differences are true year-over-year deltas rather than row-count artifacts. Includes rolling z-scores and per-series fault isolation.
- `world_credit_risk_monitor.py` — Sovereign stress screen: IMF DataMapper indicators (debt/GDP, fiscal balance, current account, real GDP growth) plus FRED 10Y yields, combined into a transparent percentile-rank composite. A relative-stress screen, not an agency-grade rating model.
- `market_regime.py` — VIX level + VIX/VIX3M term-structure regime classifier with disclosed round-number buckets. Exists to flag when a stressed tape argues against fresh short-side setups, not to time volatility itself.
- `crypto_arbitrage_scanner.py` — Read-only top-of-book comparison across Coinbase, Kraken, and Bitstamp with a disclosed fee-floor threshold. Detection only; it cannot execute anything.

## What is intentionally absent

This is not the full engine. It excludes calibrated composite weights, cross-market lead-lag ordering, security-specific watchlists, discretionary entry/stop/target levels, account-sizing defaults, forensic term libraries, and all execution or routing logic.

The code is shared for engineering review and education. It is not investment advice, a trading system, or an agency credit rating, and it comes with no guarantee of data availability or correctness.

## Install and run

```bash
pip install pandas numpy requests yfinance
python src/macro_credit_monitor.py   # example: prints the current macro credit panel
```

Each module is self-contained. Public endpoints may rate-limit, delay, or change schemas — preserve source timestamps and validate outputs before relying on them.
