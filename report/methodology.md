# Methodology (technical companion)

This note documents implementation details that are not in the protocol (`research_protocol.md`) or the report.

## Data engineering

* **Raw archive** (`data/raw/`): files are written once by `src/common.fetch_raw` and never modified. Each download is logged with URL, UTC timestamp, size and SHA-256 in `data/raw/source_register_log.csv`. The log is append-only, so failed or replaced attempts remain visible, for example the first WGI query with superseded codes and the rate-limited Wikipedia calls.
* **Interim** (`data/interim/`): tidy parquet tables built by `src/cleaning/parse_sources.py`, one process per source.
* **Processed** (`data/processed/`): analytical panels and event files built by `src/features/build_panels.py`. Documentation (variable dictionary, source register) comes from `src/features/documentation.py`.
* **Validation:** `src/validation/data_quality.py` and `tests/` (21 tests).

## BPM6 conventions

* `L_NIL_T` (net incurrence of liabilities) is the gross inflow; `A_NFA_T` (net acquisition of financial assets) is the gross outflow; `NNAFANIL_T` = assets − liabilities is the BPM6 net-lending sign.
* Our `net_flows` = inflows − outflows, which is the negative of the BPM6 sign, so that positive means a net inflow.
* Reserves (`R_F`, `A_T`) and financial derivatives (`F_F7`) are excluded from gross flows.
* The identity FA = (outflows − inflows) + derivatives + reserves holds in 100% of country-periods within 0.5% of GDP.

## Election coding pipeline

1. Parse Wikipedia calendars (2010–2026):
   * italicised (non-sovereign) entries dropped;
   * vice-presidential, referendum, primary and upper-chamber-only items excluded;
   * rounds or phases within 90 days collapsed to the first-round date.
2. Map names to ISO3 using World Bank and IDEA names plus 23 manual aliases. Non-sovereign entities (Abkhazia, Northern Cyprus, etc.) are dropped.
3. Corroborate:
   * IDEA: same country, type and year;
   * V-Dem v16: `v2eltype_0/1` for lower chamber, `v2eltype_6/7` for presidential.
   * Contests with at least two sources form the analysis set.
4. **Executive relevance:** presidential contest if `v2x_ex_direlect ≥ 0.5`, otherwise lower-house contest.
5. **Early elections:** the interval since the previous same-type contest is more than 6 months shorter than the modal gap between election years in V-Dem for 1990–2014 (fallback 1960–2014).

## Estimation

* **TWFE.** `linearmodels.PanelOLS` with entity and time effects; `drop_absorbed=True`.
* **p-values.** For clustered standard errors, p-values use a t distribution with G − 1 degrees of freedom.
* **Wild cluster bootstrap.** Restricted model (null imposed), Rademacher weights at country level, 999 replications, seed 20261011. Fixed effects are removed once by alternating-projection demeaning; the coefficient matches linearmodels to 1e-6 (unit test).
* **Stacked event study.** One stack per scheduled executive-relevant election (2016Q3–2024Q2, so the full ±6 window is observed). Controls are countries with no executive-relevant election within ±12 quarters of the event. Fixed effects are unit-by-stack and stack-by-quarter; standard errors are clustered by country.
* **Placebo calendars.** Each country's entire election calendar is shifted by ±8–12 quarters and wrapped within the sample. The shift is drawn per country per draw, preserving the number and spacing of elections.

## Known implementation choices that affect results

* Quarterly ratios use annual GDP. Robustness uses previous-year GDP.
* Winsorisation is pooled across countries over 2015–2025.
* `event_time_*` uses the nearest election within ±6 quarters. With recurrent elections this assigns each quarter to one event.
