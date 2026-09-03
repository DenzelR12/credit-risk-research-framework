"""
World Credit Risk Monitor — Sovereign Stress Across Major Economies
------------------------------------------------------------------------
Extends the engine from single-company/US-only coverage to a global
sovereign credit risk view, using two genuinely free, no-key data sources:

  - IMF DataMapper API (https://www.imf.org/external/datamapper/api/v1/)
    General government gross debt (% GDP), fiscal balance (% GDP),
    current account balance (% GDP), real GDP growth.
  - FRED long-term government bond yield series (10Y) for major economies,
    used as a market-based cost-of-borrowing signal per country.

Composite score: for each country, combines high debt/GDP, wide fiscal
deficit, negative current account, and elevated long-term yields into a
0-100 Sovereign Stress Score. This is a simple, transparent weighted-rank
model — not a replacement for CDS pricing or agency ratings, but a genuine
free/live cross-country early-warning signal.

Honest limitation, verified live: World Bank's indicator API
(api.worldbank.org) consistently timed out during testing despite the base
country-lookup endpoint responding fine — so this module uses IMF's
DataMapper API instead, which returned fast, complete responses for every
indicator tested. If World Bank access recovers, it can be added as a
secondary/cross-check source.
"""

from __future__ import annotations
import requests
import pandas as pd

IMF_BASE = "https://www.imf.org/external/datamapper/api/v1"

IMF_INDICATORS = {
    "debt_to_gdp": "GGXWDG_NGDP",     # General government gross debt, % of GDP
    "fiscal_balance": "GGXCNL_NGDP",  # General government net lending/borrowing, % of GDP
    "current_account": "BCA_NGDPD",   # Current account balance, % of GDP
    "real_gdp_growth": "NGDP_RPCH",   # Real GDP growth, % change
}

# FRED 10Y government bond yield series (OECD "IRLTLT01" family) for major economies
FRED_10Y_YIELDS = {
    "USA": "IRLTLT01USM156N",
    "JPN": "IRLTLT01JPM156N",
    "DEU": "IRLTLT01DEM156N",
    "GBR": "IRLTLT01GBM156N",
    "FRA": "IRLTLT01FRM156N",
    "ITA": "IRLTLT01ITM156N",
    "BRA": "IRLTLT01BRM156N",
    "KOR": "IRLTLT01KRM156N",
    "GRC": "IRLTLT01GRM156N",
    "IND": "INDIRLTLT01STM",  # different naming convention on FRED for India
}

WATCHED_COUNTRIES = ["USA", "CHN", "JPN", "DEU", "GBR", "FRA", "ITA", "BRA", "IND", "ARG", "GRC", "PAK"]

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def fetch_imf_indicator(indicator_code: str, countries: list[str]) -> dict[str, float]:
    """Fetches the latest available value (<=current year) for an IMF indicator across countries."""
    url = f"{IMF_BASE}/{indicator_code}/" + "/".join(countries)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    values = resp.json().get("values", {}).get(indicator_code, {})

    result = {}
    for country in countries:
        country_vals = values.get(country, {})
        numeric_years = [y for y in country_vals if y.isdigit()]
        if not numeric_years:
            continue
        # Prefer the latest year that is <= 2026 (avoid IMF's forward-looking forecast years
        # if a more recent actual/estimate exists; fall back to latest available otherwise)
        past_years = [y for y in numeric_years if int(y) <= 2026]
        latest_year = max(past_years) if past_years else max(numeric_years)
        result[country] = country_vals[latest_year]
    return result


def fetch_fred_yield(series_id: str) -> float | None:
    try:
        resp = requests.get(FRED_CSV_URL.format(series_id=series_id), timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(pd.io.common.StringIO(resp.text))
        col = df.columns[1]
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        return float(series.iloc[-1]) if len(series) else None
    except Exception:
        return None


def build_world_credit_risk_table(countries: list[str] | None = None) -> pd.DataFrame:
    countries = countries or WATCHED_COUNTRIES

    print("Fetching IMF sovereign indicators...")
    debt_to_gdp = fetch_imf_indicator(IMF_INDICATORS["debt_to_gdp"], countries)
    fiscal_balance = fetch_imf_indicator(IMF_INDICATORS["fiscal_balance"], countries)
    current_account = fetch_imf_indicator(IMF_INDICATORS["current_account"], countries)
    real_gdp_growth = fetch_imf_indicator(IMF_INDICATORS["real_gdp_growth"], countries)

    print("Fetching FRED 10Y sovereign bond yields (where available)...")
    yields = {c: fetch_fred_yield(sid) for c, sid in FRED_10Y_YIELDS.items() if c in countries}

    rows = []
    for c in countries:
        rows.append(
            {
                "country": c,
                "debt_to_gdp_pct": debt_to_gdp.get(c),
                "fiscal_balance_pct_gdp": fiscal_balance.get(c),
                "current_account_pct_gdp": current_account.get(c),
                "real_gdp_growth_pct": real_gdp_growth.get(c),
                "gov_10y_yield_pct": yields.get(c),
            }
        )
    df = pd.DataFrame(rows).set_index("country")
    return df


def compute_stress_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simple transparent 0-100 composite: rank each country on four risk
    dimensions (higher debt/GDP worse, wider deficit worse, more negative
    current account worse, higher bond yield worse) and average the
    percentile ranks. Missing values are excluded from that country's
    average rather than imputed.
    """
    df = df.copy()
    rank_components = []

    if df["debt_to_gdp_pct"].notna().any():
        df["_r_debt"] = df["debt_to_gdp_pct"].rank(pct=True) * 100
        rank_components.append("_r_debt")
    if df["fiscal_balance_pct_gdp"].notna().any():
        df["_r_fiscal"] = (-df["fiscal_balance_pct_gdp"]).rank(pct=True) * 100  # more negative = worse = higher rank
        rank_components.append("_r_fiscal")
    if df["current_account_pct_gdp"].notna().any():
        df["_r_ca"] = (-df["current_account_pct_gdp"]).rank(pct=True) * 100
        rank_components.append("_r_ca")
    if df["gov_10y_yield_pct"].notna().any():
        df["_r_yield"] = df["gov_10y_yield_pct"].rank(pct=True) * 100
        rank_components.append("_r_yield")

    df["Sovereign_Stress_Score"] = df[rank_components].mean(axis=1).round(1)
    df = df.drop(columns=rank_components)
    return df.sort_values("Sovereign_Stress_Score", ascending=False)


def generate_world_credit_risk_report(countries: list[str] | None = None) -> dict:
    df = build_world_credit_risk_table(countries)
    scored = compute_stress_scores(df)

    print("\n=== WORLD SOVEREIGN CREDIT STRESS REPORT ===")
    print(scored.to_string())

    high_risk = scored[scored["Sovereign_Stress_Score"] > 75]
    alerts = [f"[!] {c}: Sovereign Stress Score {row['Sovereign_Stress_Score']}" for c, row in high_risk.iterrows()]

    if alerts:
        print("\nHIGH-STRESS SOVEREIGNS:")
        for a in alerts:
            print(f" {a}")

    table_records = scored.reset_index().to_dict(orient="records")
    for row in table_records:
        for k, v in row.items():
            if isinstance(v, float) and (v != v):
                row[k] = None
    return {"table": table_records, "alerts": alerts}


if __name__ == "__main__":
    generate_world_credit_risk_report()
