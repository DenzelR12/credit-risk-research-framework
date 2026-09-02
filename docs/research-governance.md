# Research Governance

## Evidence standard

Every figure is a governed research artifact: stable identifier, definition and definition version, value and unit, source and snapshot, computation time, freshness SLA, and status.

## Freshness and fail-closed behavior

- `verified`: provenance complete and within SLA; may be stated as current.
- `stale`: labeled stale; may not be implied current.
- `unverifiable`: blocked from current claims.

Composite views disclose missing inputs explicitly; a degraded channel is shown as missing rather than silently interpolated.

## Term library and parameter governance

The forensic term library, calibration values, composite weights, and routing thresholds are versioned, reviewed, and private. Changes create new versions; historical results stay immutable under their original versions.

## Backtest claim gating

A historical performance claim requires a documented data window, universe construction, survivorship handling, cost and friction assumptions, and stated limitations. Absent any of these, it may not be cited.

## Ethical data acquisition

- Public or licensed data only; every source is used under its own terms.
- Rate limits and access controls are respected. When a public API blocked the crawler during development, the fix was lower concurrency and backoff — not evasion.
- Record-level surveillance-adjacent data was evaluated and deliberately rejected: it is not publicly accessible, and acting on it would raise material-nonpublic-information and compliance concerns. The compliant alternative is public, delayed, aggregate data only.

## Human review

Filing-forensics matches, low-confidence extractions, and scenario-routed configurations require human confirmation before publication. The system recommends; a person decides.

## Disclaimers

Educational research tooling. Not investment advice, not a solicitation, not a credit rating, and not a production risk model. Correlation is not causation; screening outputs are leads for human review, not confirmed events.
