# Architecture

## Objective

Treat early-warning credit research as an explicit system: ingestion, validation, evidence assembly, deterministic quality gates, and publication are separate concerns rather than implicit script behavior.

## Control plane and data plane

The data plane ingests public source documents and time series, maintains the document store and feature registry, and runs the research modules. The control plane owns source contracts, freshness SLAs, term-library versions, cache policy, snapshot retention, and audit events. The separation lets a source, model, or venue change without redefining what constitutes a valid signal.

```text
Public sources -> adapters -> contract validation -> snapshots
                                              |
Research modules -> evidence assembly -> quality gates -> alerts / dashboard
                                              |
                              control plane: freshness SLAs, term-library
                              versions, cache TTLs, audit events
```

## Non-negotiable invariants

1. No alert without evidence references, source snapshot identity, definition version, and computation time.
2. Stale or unverifiable input fails closed; it is labeled, never implied current.
3. Definition changes create new versions; historical research records remain immutable.
4. LLM-assisted extraction is untrusted input and can never override a deterministic check; a rule-based fallback must always exist.
5. A served snapshot must be labeled with its age and discarded past its per-source maximum.
6. Rate-limit and WAF responses are respected; circumvention, including rotating egress or spoofing headers to evade blocks, is out of bounds by policy.

## Layered design

- Source adapters: one per public source, each with contract validation and courteous-fetch behavior.
- Research modules: independent and individually runnable, with per-module failure isolation so one blocked or failing source degrades gracefully instead of crashing the report.
- Backend: FastAPI service with per-module TTL caches, background refresh, atomic last-good disk mirrors, and a persisted status-transition log.
- Frontend: static dashboard rendering only what the backend serves, with freshness labeling on every panel.

## Alert contract

Every published alert carries: subject, claim, evidence references, source snapshot, definition version, computation time, freshness status, and route — publish or human review.
