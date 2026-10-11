# Project status — 2026-10-11

## Deliverables

| Deliverable | Status | Where |
|---|---|---|
| A. Research protocol | **Completed**; frozen before estimation (git tag `protocol-v1.0`); post-hoc changes logged | `report/research_protocol.md`, `report/protocol_changelog.md` |
| Phase 1 feasibility report | **Completed** | `report/feasibility_report.md` |
| B. Literature review + verified bibliography + evidence matrix | **Completed** (57 entries; all scholarly DOIs Crossref-verified). 3 matrix rows are `metadata_only` and need full-text checks. | `report/final_report.md` §4, `literature/` |
| C. Data package | **Completed**: annual and quarterly panels, political and policy events, country metadata, variable dictionary, source register, data-quality report, cleaning scripts | `data/processed/`, `config/` |
| C. Policy-event database | **Partially completed**: data-derived events only (KAOPEN regime changes, ≥ 2pp policy-rate moves). Hand-coded legislative/regulatory events (codebook, double coding) **planned, not executed**. | `data/processed/policy_events.csv` |
| D. Econometric analysis | **Completed**: baseline, interactions, heterogeneity, TWFE and stacked event studies, robustness (34 specs, leave-one-out, placebo), multiple testing, post-hoc alignment | `results/tables/` |
| D. Quasi-experimental DiD for specific policy reforms | **Not executed**: no reform with a credible, pre-identified comparison group was found within scope (protocol §9) | — |
| E. Visualisation package (10 charts) | **Completed**: PDF/SVG/PNG plus source data | `results/figures/` |
| F. Final academic report | **Completed** (v1.0) | `report/final_report.md` |
| G. Executive presentation | **Completed**: 12-slide deck (private artifact) | https://claude.ai/artifact/BHZurUFgeXA6N2wQ9X4E3E ; source in `report/presentation/` |
| Phase 9 QA | **Completed**: full rerun from archived raw data reproduced all tables byte-for-byte; 21/21 tests pass | `results/logs/full_rerun.log` |
| Notebooks (`notebooks/01–06`) | **Not created**: the pipeline is script-based (`run_pipeline.sh`). Notebooks would duplicate it. | — |

## Policy tier (added 2026-10-11)

| Item | Status | Where |
|---|---|---|
| Flows at risk: 5th–95th percentiles of next-4-quarter gross inflows | **Completed**: lean quantile model blended with country history, tails calibrated in real time. Rolling 2019Q4–2024Q4: 5.2% of outcomes below the 5th percentile. | `src/forecast/risk.py`, `results/tables/far_*` |
| Sudden-stop probability | **Completed**: logit and base-rate blend. Rolling AUC 0.735, Brier 0.128 vs 0.141 for the base rate. | same |
| Vulnerability panel and buffer stress tests | **Completed**: 6 indicators with conventional thresholds; reserve cover of ST debt + CA deficit, of the flows-at-risk shortfall and of the worst year. IMF ARA metric not computed. | `src/forecast/vulnerability.py`, `results/tables/vulnerability_panel.csv` |
| Rolling ex-ante backtest 2020–2025 | **Completed**: EMDE gross inflows blend RMSE 9.24 vs 9.88 for the long-run average; for AE, nothing beats the average. | `results/tables/rolling_point_summary.csv` |
| Pre-registered 2026–27 election test | **Registered** (git tag `prereg-2026-elections`). Low power (22% at −2 pp), stated in the registration. | `report/preregistration_2026_elections.md` |

## Source versions used

IMF BOP v21.0.0 (data to 2026Q2); IMF WEO (DataMapper vintage at retrieval); WDI (2026-10-08); WGI 2026 release (2026-09-25); V-Dem v16 (2026-03-17); IDEA VTD; Wikipedia calendars 2010–2026 (revision IDs in raw JSON); WUI July 2026; GPR (to 2026-09); RSUI (to 2026-05); KAOPEN 2023; BIS WS_CBPOL; FRED. All retrieved 2026-10-11.

## Unresolved issues

1. The post-hoc EMDE election-quarter effect awaits its pre-registered out-of-sample test (2026Q3–2027Q4 elections). Power is low; a faster test would use market data around elections.
2. The WGI vintage-sensitivity test is infeasible, because only the revised 2026 vintage is accessible via the API.
3. Not ingested: UNCTAD greenfield and cross-border M&A data, and BIS LBS / international debt securities.
4. Not coded: election closeness or polarisation, government-formation delays, coalition changes.
5. The executive-relevance and early-election rules are approximations. A manual audit of the 71 early and 16 unclassified executive-relevant contests is recommended.
6. Three literature-matrix rows (Julio & Yook 2016; Forbes & Warnock 2012; Rey 2015) summarise designs without a retrieved abstract. Check them against the full text.

## Next exact actions

1. Run the pre-registered test when BOP data cover 2027Q4 election quarters (mid-2028). Do not regenerate the registration files.
2. Ingest UNCTAD WIR 2026 annex tables (greenfield announcements vs realised FDI) and BIS LBS cross-border claims. Re-estimate H3 with these.
3. Build the hand-coded policy-event codebook (investment screening, repatriation rules, capital-flow management measures) with two coders and κ reporting.
4. Audit the early-election classification against constitutional term lengths (e.g. Constitute Project) and re-run the scheduled-only design.
