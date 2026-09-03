"""
HTTP resilience layer — Retry-After-aware decorrelated-jitter backoff.
----------------------------------------------------------------------
Shared retry primitive for every module that talks to a rate-limited public
API (CFPB behind an Akamai-style WAF, FRED, Kalshi, Polymarket, Yahoo).

Design (AWS "Exponential Backoff and Jitter", Marc Brooker, 2015):

  Decorrelated jitter — the sleep for attempt n is drawn from a uniform
  distribution anchored to the PREVIOUS sleep, not reset to zero:

      t_n = min(t_max, U(t_base, t_prev * 3))

  vs. full jitter (U(0, min(t_max, t_base * 2^n))). Decorrelated jitter is
  used here because this process is a SINGLE polite client, not a fleet:
  the t_base floor prevents near-zero instant retries (which a WAF reads as
  hammering), while the recursive upper bound still grows the average wait
  exponentially and desynchronizes retry timing across the modules that
  share this helper.

Server-directed waits always win: if the response carries a Retry-After
header (integer seconds or an HTTP-date, both valid per RFC 9110), that
value is used verbatim (capped at retry_after_cap) instead of the jitter
draw — the server knows its own reset window better than any client-side
distribution does.

Retryable statuses: 429 (rate limit), 403 (edge-WAF concurrency block —
CFPB returns this instead of 429), 500/502/503/504 (transient upstream).
Anything else raises immediately — a 400/404 will never succeed on retry.
"""

from __future__ import annotations

import email.utils
import random
import time

import requests

RETRYABLE_STATUSES = {403, 429, 500, 502, 503, 504}


class RateLimitExhausted(RuntimeError):
    """All retry attempts were consumed while the endpoint kept rate-limiting."""

    def __init__(self, url: str, attempts: int, last_status: int | None):
        self.last_status = last_status
        super().__init__(
            f"Gave up after {attempts} attempts against {url} "
            f"(last status: {last_status}). Endpoint is rate-limiting or blocking; "
            f"serve the last-good snapshot instead of retrying harder."
        )


def _parse_retry_after(value: str | None) -> float | None:
    """Retry-After per RFC 9110: either delta-seconds or an HTTP-date."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(value)
        return max(0.0, dt.timestamp() - time.time())
    except (TypeError, ValueError):
        return None


def decorrelated_jitter_sleep(previous_sleep: float, base_delay: float, max_delay: float) -> float:
    """t_n = min(max_delay, U(base_delay, previous_sleep * 3))."""
    upper = max(base_delay, previous_sleep * 3.0)
    return min(max_delay, random.uniform(base_delay, upper))


def resilient_get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 45.0,
    retry_after_cap: float = 120.0,
    session: requests.Session | None = None,
) -> requests.Response:
    """GET with decorrelated-jitter backoff; honors Retry-After when present.

    Returns the successful Response. Raises RateLimitExhausted when every
    attempt hit a retryable status, or the underlying requests exception for
    repeated network-level failures. Non-retryable HTTP errors raise
    immediately via raise_for_status().
    """
    getter = session.get if session is not None else requests.get
    previous_sleep = base_delay
    last_status: int | None = None
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            resp = getter(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            # Network-level failure (timeout, reset) — retryable, jitter only.
            last_exc = exc
            if attempt < max_attempts - 1:
                previous_sleep = decorrelated_jitter_sleep(previous_sleep, base_delay, max_delay)
                time.sleep(previous_sleep)
            continue

        if resp.status_code not in RETRYABLE_STATUSES:
            resp.raise_for_status()
            return resp

        last_status = resp.status_code
        if attempt >= max_attempts - 1:
            break

        server_wait = _parse_retry_after(resp.headers.get("Retry-After"))
        if server_wait is not None:
            # Server told us its reset window — obey it (capped), and seed the
            # jitter state with it so a follow-up failure backs off from there.
            wait = min(server_wait, retry_after_cap)
            previous_sleep = max(wait, base_delay)
        else:
            previous_sleep = decorrelated_jitter_sleep(previous_sleep, base_delay, max_delay)
            wait = previous_sleep
        time.sleep(wait)

    if last_status is not None:
        raise RateLimitExhausted(url, max_attempts, last_status)
    raise last_exc  # type: ignore[misc]
