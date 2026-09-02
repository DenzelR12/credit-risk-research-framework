# Credit Risk Research Framework

> A transparent reference architecture for quality-gated, explainable financial-risk research alerts. Educational only; not investment advice or a production risk model.

## Overview

An early-warning credit-risk research engine: eighteen research areas behind a FastAPI backend and a live dashboard, built and tested against real public endpoints. This repository documents the architecture, data contracts, and governance standard. The implementation, calibrated parameters, and research library remain private.

## Problem

Credit deterioration surfaces in public data — macro credit conditions, regulatory filings, footnote disclosures, consumer complaints, rating actions — before it shows in prices. The hard part is not finding information; it is separating durable signal from narrative noise under provenance discipline strict enough that every conclusion can be audited, reproduced, and challenged.

## Architecture

```text
Public sources -> source contracts -> validation -> versioned snapshots
      |                                        |
 document store                         feature registry
      |                                        |
      +----------> evidence assembly ----------+
                          |
              deterministic quality gates
                          |
        explainable alerts / dashboard / human review
```

The control plane owns source contracts, freshness SLAs, term-library versions, cache policy, and audit events. Research modules retrieve, assess, and recommend; nothing publishes without evidence and freshness checks.

## Research coverage

US credit and macro:

- Macro credit stress: high-yield spreads, consumer delinquencies, commercial real estate credit, and the yield curve from public macro series, with rolling z-scores and calendar-accurate year-over-year deltas.
- Market regime filter: volatility level buckets and term-structure state that can veto initiating new risk setups in stressed tapes.
- Rates and credit: the full Treasury curve with inversion flags, high-yield and investment-grade spread z-scores, and rates-volatility regime.
- Oil transmission belt: crude futures and official spot cross-checks, shock classification, oil volatility regime, and a scored map of where an oil move transmits next.

Company and filing forensics:

- Filing distress scan: full-text screening of recent SEC filings for financing-stress disclosure patterns using a governed, versioned term library (the library itself is not published).
- Footnote extraction: covenant waivers and earnings add-backs extracted from filing footnotes with an LLM-assisted path and a deterministic regex fallback, with per-document provenance.
- Earnings-quality normalization: reported coverage and yield measures adjusted for non-cash and discretionary accounting effects before comparison (definitions private).
- Alternative distress monitoring: lien and docket acceleration from records supplied by the user's own PACER or vendor account.

Consumer, ratings, and sovereign:

- Consumer complaint spikes: weekly product-level complaint volumes from the CFPB public API with rolling-mean z-score detection and per-product failure isolation.
- Ratings-action monitor: live upgrade, downgrade, and outlook parsing from public rating-agency research feeds.
- World sovereign stress: a composite relative-stress ranking across tracked countries from IMF and FRED public series — a screening tool, not a substitute for agency ratings.
- Sovereign scenario routing: routes sovereign stress configurations between bailout-style and default-style scenario frameworks from public aggregates (routing thresholds private).

Market structure and synthesis:

- Prediction-market radar: top macro markets and 24h probability movers from public, delayed Polymarket and Kalshi data — attention speed, not information edge.
- Crypto cross-exchange spreads: read-only top-of-book comparison across three venues with a configurable fee floor; honest that quoted spreads are not executable depth.
- Opportunity monitors: status tracking for rule-based reference setups — informational triggers worth a manual look, never order placement.
- CFPB-to-ticker exposure mapping: maps spiking complaint categories to curated lists of exposed public companies, then enriches only flagged categories with live prices, mechanical range-based reference levels, short-interest snapshots with as-of dates, earnings proximity, volume confirmation, relative strength, and ratings-downgrade corroboration.
- Global risk synthesis: every module becomes a scored channel; channels combine into a single composite with a disclosed-weight methodology, plus an all-pairs cross-market divergence matrix annotated with historical analogues. Heuristic by design; weights are disclosed in the methodology, not fitted to crisis history.

## Platform engineering

- FastAPI backend with per-module cache TTLs matched to each source's natural cadence; refreshes run in a background thread so requests never block on a live fetch.
- Graceful degradation: every successful refresh is mirrored to disk atomically; when an upstream blocks or fails, the API serves the last-good snapshot labeled "mirror saved Xh ago" rather than pretending it is live, and snapshots older than a per-source maximum are discarded rather than shown.
- Shared HTTP resilience layer: Retry-After-aware decorrelated-jitter backoff with fail-fast on non-retryable statuses. Rotating IPs or user agents to evade rate limits was considered and rejected as circumvention.
- Two-layer NaN/Infinity sanitization so partial sovereign or macro data can never crash the API serializer.
- A persisted status-transition log: every time a tracked setup, mapped ticker, or market regime changes state, an event is appended server-side and survives restarts; first sightings are stored silently to avoid restart noise.
- Mobile-first dashboard with per-panel manual refresh and separate fast and slow polling lanes so expensive upstream calls are never hammered.

## Data sources

All public and subject to source terms: FRED, SEC EDGAR, the CFPB Consumer Complaint Database, Moody's and Fitch public research feeds, IMF DataMapper, Yahoo Finance public endpoints, Coinbase, Kraken, and Bitstamp public tickers, and Polymarket and Kalshi public APIs. This repository redistributes no source data.

## Honest limitations

- Official macro and credit-spread series publish with lags; readings are yesterday's close, not intraday.
- Unofficial market endpoints can go stale or rate-limit without notice.
- Composite scores and regime buckets are disclosed heuristics chosen for interpretability, not fitted or backtested models.
- Lead-lag interpretation across channels is a documented judgment call; channels have swapped order across historical cycles.
- Prediction-market prices are downstream public consensus, not non-public information.
- Curated category-to-company mappings are judgment calls, and a complaint spike is correlation, not confirmed distress.
- Mechanical reference levels know nothing about event calendars, supply, or roll costs.
- No module places or manages orders; nothing here executes.

## Deliberately not published

- The implementation: research modules, backend, and dashboard code.
- Signal definitions, calibrated thresholds, scoring weights, and the forensic term library.
- The cross-channel lead-lag ordering and scenario-routing thresholds.
- Specific tracked instruments, reference levels, and any execution or sizing logic.
- Any non-public data. Only public or synthetic data is ever used.

The transferable artifact is the architecture and its governance standard. The calibrated research stays private.

## Status model

| Status | Meaning |
|---|---|
| `verified` | Source snapshot, definition, and recomputation checks pass within the freshness SLA |
| `stale` | A prior result exceeds its freshness SLA; labeled, never implied current |
| `unverifiable` | Source, schema, or recomputation cannot be validated; blocked from current claims |

## Claim gating

A capability may be described as implemented only when reproducible evidence supports the claim. Backtests are claims: they require documented data windows, universe construction, survivorship handling, cost assumptions, and stated limitations before they may be cited.

## Disclaimers

Educational and architectural reference only. Not investment advice, not a solicitation, not a credit rating, and not a production risk model. No employer, client, brokerage, or account data is used or referenced. Public sources are subject to their own terms.

## License

MIT
