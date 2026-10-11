# Protocol change log

| Date | Version | Change | Before/after seeing results | Reason |
|---|---|---|---|---|
| 2026-10-11 | 1.0 | Protocol frozen | n/a (no estimates computed) | Initial version |
| 2026-10-11 | 1.0-posthoc-a | Added `src/econometrics/posthoc_alignment.py`: (i) gross **private** inflows (official-sector OI liabilities + SDR allocations removed) using a new IMF BOP query by sector and instrument; (ii) IMF-style windows (election quarter k=0; 1–2 quarters before; 1–2 after); (iii) EMDE subsample; (iv) bottom-quartile WGI political stability interaction; (v) 1,000-draw calendar-shift placebo for k=0. | **AFTER** the v1.0 confirmatory results were seen | To reconcile our null pre-registered result with Arakelyan & Evdokimova (2025, IMF WP/25/243), whose full text was read only after estimation. They define the event as the election quarter itself and study private inflows to EMs. All results labelled POST-HOC / EXPLORATORY; confirmatory conclusions remain those of v1.0. |
| 2026-10-11 | 1.0 (note) | The first official-sector query (`O_FL1_S121/S13`) returned only SDR series; replaced by an instrument-level query. Both raw files retained. | after | Data-availability correction |
| 2026-10-11 | 1.0-posthoc-b | Added `seasonality_check()`: country × quarter-of-year fixed effects for the post-hoc election-quarter coefficient | AFTER results seen | Fixed election calendars could coincide with country-specific seasonal flow patterns not absorbed by common quarter FE |
