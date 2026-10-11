"""Generate the pre-registration for an out-of-sample test of the EMDE election-quarter effect.

Writes report/preregistration_2026_elections.md and report/preregistration_2026_spec.json.
Everything that defines the test (sample rule, qualifying elections, outcome construction with frozen
winsorisation bounds, specification, decision rule, timing) is fixed here before any balance-of-payments
data for the qualifying election quarters exist.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats

from src.common import PROCESSED, ROOT
from src.forecast.country_model import future_elections

FREEZE_DATE = "2026-10-11"


def main():
    meta = pd.read_csv(PROCESSED / "country_metadata.csv")
    emde = set(meta[meta.in_quarterly_sample & (meta.country_group_alt_pre_euro == "EMDE")].iso3)
    names = meta.set_index("iso3").country_name
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")
    latest_q = Q.dropna(subset=["gross_inflows_gdp"]).groupby("iso3").quarter.max()

    fut = future_elections()
    fut = fut[(fut.exec_relevant == 1) & fut.iso3.isin(emde)].copy()
    fut = fut[(fut.quarter >= "2026Q1") & (fut.quarter <= "2027Q4")].sort_values("date")
    fut["country"] = fut.iso3.map(names)
    fut["bop_latest_on_freeze_date"] = fut.iso3.map(latest_q)
    fut["data_status"] = np.where(fut.quarter > fut.bop_latest_on_freeze_date, "not yet published", "published (secondary set)")
    primary = fut[(fut.quarter >= "2026Q3") & (fut.data_status == "not yet published")]
    secondary = fut[fut.data_status != "not yet published"]

    # power: scale the historical EMDE election-quarter standard error by the number of elections
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    old = pe[pe.event_type.str.startswith("election") & (pe.exec_relevant == 1) & pe.iso3.isin(emde)
             & pe.verification_status.isin(["wikipedia+idea+vdem", "two_sources"])]
    old = old[pd.to_datetime(old.event_date).dt.year.between(2015, 2025)]
    al = pd.read_csv(ROOT / "results" / "tables" / "posthoc_imf_alignment.csv")
    se_old = float(al[(al.specification == "EMDE, gross inflows") & (al.term == "eq_k0")].se.iloc[0])
    b_old = float(al[(al.specification == "EMDE, gross inflows") & (al.term == "eq_k0")].coef.iloc[0])
    n_old, n_new = len(old), len(primary)
    se_new = se_old * np.sqrt(n_old / max(n_new, 1))
    power = {eff: float(stats.norm.cdf(abs(eff) / se_new - stats.norm.ppf(0.95))) for eff in (-1.0, -2.0, -3.0)}
    n80 = int(np.ceil(n_old * (se_old / (2.0 / (stats.norm.ppf(0.95) + stats.norm.ppf(0.80)))) ** 2))
    n_pool = n_new + len(secondary)
    se_pool = se_old * np.sqrt(n_old / max(n_pool, 1))
    power_pool = {eff: float(stats.norm.cdf(abs(eff) / se_pool - stats.norm.ppf(0.95))) for eff in (-1.0, -2.0, -3.0)}

    Qm = Q[Q.year.between(2015, 2025)]
    lo, hi = np.nanpercentile(Qm.gross_inflows_gdp.dropna(), [1, 99])

    spec = {
        "title": "Out-of-sample test of the election-quarter decline in EMDE gross capital inflows",
        "freeze_date": FREEZE_DATE,
        "hypothesis": "In emerging and developing economies, gross capital inflows (annualised % of GDP) are lower in the quarter of an executive-relevant national election than in other quarters.",
        "direction": "one-sided, coefficient < 0",
        "prior_estimate": {"coef": round(b_old, 3), "se": round(se_old, 3), "source": "post-hoc analysis on 2015Q1-2025Q4 (results/tables/posthoc_imf_alignment.csv)"},
        "sample_rule": "Economies in the quarterly sample classified EMDE under the pre-euro classification (country_metadata.country_group_alt_pre_euro).",
        "election_rule": "Executive-relevant national contests (presidential where V-Dem v2x_ex_direlect >= 0.5 in the latest V-Dem year, else lower-house) whose first round falls in 2026Q3-2027Q4 and whose BOP quarter was unpublished on the freeze date. Dates from the Wikipedia national electoral calendar; at analysis time each must be confirmed by a second source (International IDEA or the national election authority). Elections cancelled or postponed out of the window are dropped and reported. Elections moved into the window are not added.",
        "qualifying_elections_primary": [{"iso3": r.iso3, "country": r.country, "type": r.etype, "date": str(r.date.date()), "quarter": r.quarter} for r in primary.itertuples()],
        "qualifying_elections_secondary": [{"iso3": r.iso3, "country": r.country, "type": r.etype, "date": str(r.date.date()), "quarter": r.quarter} for r in secondary.itertuples()],
        "outcome": {"variable": "gross inflows = (D_F + P_F + O_F, L_NIL_T) * 4 / annual GDP (IMF WEO NGDPD) * 100",
                    "winsorisation_bounds_frozen": [round(float(lo), 4), round(float(hi), 4)],
                    "source": "IMF BOP (IMF.STA:BOP), retrieved fresh at analysis time; vintage recorded"},
        "primary_specification": "Panel 2015Q1-2027Q4, EMDE sample. y_it = country FE + quarter FE + b_old*E_old + b_new*E_new + pre12 + post12 + lagged-year controls (growth, inflation, CA, fiscal balance, public debt, log GDP per capita). E_old = election quarter for 2015-2025 elections; E_new = election quarter for the primary qualifying elections. Pre/post windows (1-2 quarters) for all elections. SEs clustered by country.",
        "primary_statistic": "b_new, one-sided p-value from the country-clustered t statistic (G-1 df)",
        "decision_rule": "Confirmed if b_new < 0 with one-sided p < 0.05. Otherwise reported as not confirmed, with the estimate and 90% CI. Either way the result is published.",
        "secondary_analyses": ["Wild cluster bootstrap p-value for b_new (999 Rademacher draws, seed 20261011)",
                               "Prediction-error test: mean residual in qualifying election quarters from the frozen 2015-2025 EMDE model (no re-estimation), one-sided t test",
                               "Private gross inflows (official OI liabilities and SDR removed)",
                               "Pooled test (pre-specified, reported alongside the primary): primary set plus the 2026Q1-Q2 secondary set, whose BOP data were published by the freeze date but were not analysed for this question. Same specification and decision rule; reported as secondary because the data existed at registration."],
        "power": {"n_elections_historical": n_old, "n_elections_primary": n_new, "expected_se": round(se_new, 3),
                  "power_one_sided_5pct": {str(k): round(v, 2) for k, v in power.items()},
                  "n_elections_pooled": n_pool, "expected_se_pooled": round(se_pool, 3),
                  "power_pooled_one_sided_5pct": {str(k): round(v, 2) for k, v in power_pool.items()},
                  "elections_needed_for_80pct_power_at_minus2": n80,
                  "note": "Approximation: historical SE scaled by sqrt(n_old/n_new). Low power means a null result would be weak evidence against the effect."},
        "timing": "Analysis runs once BOP data cover the 2027Q4 election quarter for at least 80% of qualifying economies (expected around mid-2028), and no later than 2028-09-30. An interim look at elections through 2027Q2 may be published but is labelled interim and does not change the decision rule.",
        "deviations": "Any deviation will be logged in report/protocol_changelog.md with date and reason, before the analysis is run.",
    }
    blob = json.dumps(spec, indent=1, ensure_ascii=False)
    (ROOT / "report" / "preregistration_2026_spec.json").write_text(blob)
    digest = hashlib.sha256(blob.encode()).hexdigest()

    rows = lambda df: "\n".join(f"| {r.country} | {r.etype} | {r.date.date()} | {r.quarter} | {r.bop_latest_on_freeze_date} |" for r in df.itertuples()) or "| — | | | | |"
    md = f"""# Pre-registration: out-of-sample test of the EMDE election-quarter effect

| | |
|---|---|
| Frozen on | {FREEZE_DATE} |
| Machine-readable spec | `report/preregistration_2026_spec.json` (SHA-256 `{digest}`) |
| Git tag | `prereg-2026-elections` |
| Status | Registered. No balance-of-payments data for any primary election quarter existed on the freeze date. |

## Why

The study's post-hoc analysis found that gross capital inflows to emerging and developing economies were {abs(b_old):.2f} pp of GDP (annualised) lower in the quarter of an executive-relevant election, 2015–2025 (SE {se_old:.2f}). Because that window was chosen after the pre-registered results were seen, it must be tested on new elections before policymakers rely on it.

## Hypothesis

{spec['hypothesis']} Test: {spec['direction']}.

## Qualifying elections (primary set: 2026Q3–2027Q4, data not yet published on {FREEZE_DATE})

| Economy | Contest | Date | Quarter | Latest BOP quarter on freeze date |
|---|---|---|---|---|
{rows(primary)}

**{n_new} primary elections.** Dates from the Wikipedia calendar; each must be confirmed by a second source when the analysis runs.

### Secondary set (2026Q1–Q2, data already published but not analysed for this question)

| Economy | Contest | Date | Quarter | Latest BOP quarter on freeze date |
|---|---|---|---|---|
{rows(secondary)}

## Outcome and specification

* **Outcome:** {spec['outcome']['variable']}. Winsorisation bounds are frozen at [{lo:.2f}, {hi:.2f}].
* **Specification:** {spec['primary_specification']}
* **Primary statistic:** {spec['primary_statistic']}.
* **Decision rule:** {spec['decision_rule']}

## Secondary analyses

""" + "\n".join(f"* {x}" for x in spec["secondary_analyses"]) + f"""

## Power

* Historical estimate: {n_old} EMDE executive-relevant elections, SE {se_old:.2f}.
* **Primary set:** {n_new} elections, expected SE about {se_new:.2f}. One-sided 5% power is {power[-1.0]:.0%}, {power[-2.0]:.0%} and {power[-3.0]:.0%} for true effects of −1, −2 and −3 pp.
* **Pooled set:** {n_pool} elections, expected SE about {se_pool:.2f}. Power is {power_pool[-1.0]:.0%}, {power_pool[-2.0]:.0%} and {power_pool[-3.0]:.0%}.
* {spec['power']['note']} A test of this size can confirm a large effect but cannot rule out a moderate one.
* About **{n80} elections** would be needed for 80% power against a true −2 pp effect, roughly six to seven years of EMDE elections. A faster and more powerful confirmation would use market data around election dates (weekly portfolio flows, sovereign spreads, exchange rates); that is outside this registration.

## Interpretation commitments

* A confirmed result supports using the election-quarter adjustment in EMDE outlooks.
* A non-confirmed result is reported as *inconclusive*, not as evidence of no effect, unless the 90% interval excludes −1 pp.
* An estimate with the opposite sign and one-sided p < 0.05 for a positive effect is reported as contradicting the post-hoc finding.

## Timing and deviations

{spec['timing']} {spec['deviations']}
"""
    (ROOT / "report" / "preregistration_2026_elections.md").write_text(md)
    print(md[:3000])
    print("primary", n_new, "secondary", len(secondary), "power", power, "sha", digest)


if __name__ == "__main__":
    main()
