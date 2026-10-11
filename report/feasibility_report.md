# Phase 1 — Feasibility Assessment and Source-to-Variable Mapping

*Prepared 2026-10-11. Every source below was actually queried. Status codes, row counts and vintages come from `data/raw/source_register_log.csv` and `data/processed/source_register.csv`.*

## 1. Research-design summary

The study links cross-border capital flows (IMF BPM6 balance of payments, 2015–2025, plus partial 2026) to dated national elections, institutional quality and global financial conditions, for a rule-based universe of advanced and emerging/developing economies.

* **Core design.** Two-way fixed-effects panels: a quarterly panel for election timing and an annual panel for governance and structural variables. Election-timing event studies are run on all elections and on constitutionally scheduled elections only; the scheduled-only version is the identifying sample.
* **Causal language.** Restricted to the scheduled-election design. Everything else is reported as conditional association.

## 2. Verified source inventory

| Source | Access verified | Retrieval route | Coverage obtained | Notes / limitations |
|---|---|---|---|---|
| IMF BOP (`IMF.STA:BOP` v21) | ✅ HTTP 200, data returned | SDMX 2.1 REST (CSV) | 198 economies annual, 158 quarterly; to 2026Q2 (61 sample economies) or 2026Q1 (34) | Bulk quarterly query takes ~8 min. Values are in USD units. Full BPM6 asset/liability split available. |
| IMF BOP sector detail (official OI liabilities) | ✅ | SDMX 2.1 | 98–152 economies per series | `O_FL1_S121/S13` is not published; instrument-level series (F2/F4/F81/F8AP × S121/S13) used instead |
| IMF WEO | ✅ (curl only; python-requests got 403) | DataMapper JSON | 229 entities, 1980–2031 | Vintage not stated by the API; 2026+ are projections. AE membership verified against the ADVEC aggregate. |
| IMF RSUI (social unrest) | ✅ | SDMX 2.1 | 133 countries, 2013-01 to 2026-05 | Media-based measure |
| World Bank WDI | ✅ | API v2 | Updated 2026-10-08 | External-debt series cover EMDE debtors only |
| World Bank WGI | ✅ after fixing codes | API v2, source 3 | 2026 release (updated 2026-09-25), data to 2025 | Codes changed to `GOV_WGI_*`. Historical series revised; **older vintage not available**, so the vintage-sensitivity test is infeasible. |
| V-Dem v16 | ✅ via V-Dem's GitHub package | raw `.RData` | 1789–2025 | The v-dem.net download needs a registration form (email + terms). It was **not submitted on the user's behalf**; the identical dataset from the V-Dem Institute's GitHub was used. |
| International IDEA Voter Turnout | ✅ | xlsx export | 3,934 national contests | **~half of post-2013 rows have year-only dates (YYYY-01-01)**, so IDEA cannot serve alone as the date source |
| Wikipedia national electoral calendars | ✅ (rate-limited; 6 s spacing) | MediaWiki API | 2010–2026 pages (2008–09 pages do not exist) | Used for exact dates only, triangulated with IDEA and V-Dem |
| Wikidata SPARQL (elections) | ⚠️ evaluated and **rejected** | SPARQL | — | 60 s timeouts; sub-national contests typed as "legislative election"; wrong dates on some items |
| World Uncertainty Index | ✅ | xlsx | 143 countries, to 2026Q2 | Not a baseline control (plausible mediator) |
| Geopolitical Risk (country) | ✅ | xls | 44 countries | Descriptive only |
| Chinn–Ito KAOPEN | ✅ | xls | to 2023 | — |
| BIS policy rates | ✅ | BIS SDMX v1 | 38 sample countries | Euro area reported as `XM`, not mapped to members |
| FRED (VIX, Fed funds, UST10y, USD index, Brent, HY OAS) | ✅ (curl) | fredgraph CSV | daily series to early 2026Q4 (partial quarter) | Only 2015Q1–2025Q4 used in estimation |
| UNCTAD WIR 2026 (greenfield, M&A) | ⏸ not ingested | — | — | Planned. FDI is measured from BOP only in v1.0. |
| BIS LBS / international debt securities | ⏸ not ingested | — | — | Planned. Bank flows are proxied by BOP other investment. |

## 3. Country-selection framework (applied, rule-based)

The inclusion rules are:

1. listed by the World Bank, or Taiwan Province of China (listed by the IMF);
2. population of at least 1 million in 2014;
3. gross FDI, portfolio and other-investment flows in both directions for at least 9 of the 11 years 2015–2025;
4. a 2014 WGI Rule of Law estimate.

The quarterly sample additionally requires at least 32 of 44 quarters.

**Result:** 196 candidates, giving **121 annual** economies (33 AE, 88 EMDE) and **108 quarterly** economies (33 AE, 75 EMDE).

Exclusion reasons (a candidate can have several):

| Reason | Candidates |
|---|---|
| Population < 1m | 50 |
| Insufficient BOP years | 40 |
| No WGI 2014 | 10 |
| Not World Bank-listed | 5 |

**Classification** follows the IMF WEO advanced-economy group: 43 economies, including Bulgaria and Liechtenstein. Membership was verified because the sum of members' GDP equals the ADVEC aggregate to within USD 1m in 2015, 2019, 2024 and 2025. Alternatives used: pre-euro status for Croatia and Bulgaria, and World Bank high-income.

## 4. Variable-availability matrix (main sample 2015–2025)

See `data/processed/data_quality_report.csv` for every variable. Key items:

| Variable | Quarterly coverage (share non-missing) | Countries |
|---|---|---|
| Gross inflows / outflows (% GDP) | 99.7% / 99.7% | 108 |
| FDI / portfolio equity / portfolio debt / OI inflows | 100% / 97.0% / 96.0% / 100% | 108 / 106 / 105 / 108 |
| Lagged macro controls (WEO) | ≥ 99.7% | 108 |
| Reserves (months of imports), lagged | 99.1% | 108 |
| Executive-relevant election windows | 100% (coded for all) | 108 |
| WUI | 95.4% | 103 |
| RSUI | 90.8% | 98 |
| BIS policy rate | 34.7% | 38 |
| Country GPR | 39.1% | 42 |
| Private gross inflows (post-hoc) | 97.4% | 106 |

## 5. Main data-access risks (encountered and how they were handled)

1. **Year-only election dates in IDEA.** Resolved by triangulating with Wikipedia calendars and V-Dem; uncorroborated contests are excluded from the main models.
2. **WGI vintage.** Only the revised 2026 vintage is available. Mitigated by using 2014 levels as a predetermined moderator; the vintage test is reported as infeasible.
3. **V-Dem registration form.** Avoided by using the V-Dem Institute's own GitHub distribution.
4. **Bot filtering (IMF DataMapper, FRED).** Handled with a curl transport; the requests are identical.
5. **API error bodies returned with HTTP 200 (World Bank).** A response validator now rejects them before they are archived.
6. **Partial 2026.** Every 2026 value is flagged and excluded from confirmatory estimation; 2026 GDP denominators are WEO projections.
7. **Official vs private flows.** Total gross inflows include official-sector liabilities, which can offset private flows (Avdjiev et al. 2022). A private-inflow measure was added post hoc and labelled as such.

## 6. Baseline econometric specification

For country *i* and quarter *t*:

Y_it = α_i + λ_t + β₁·Pre_it + β₂·Post_it + γ′X_{i,y(t)−1} + ε_it

* Y = gross inflows or outflows, annualised % of GDP (winsorised 1/99).
* Pre = the quarter of, or the quarter before, an executive-relevant election.
* Post = the next two quarters.
* X = previous-year growth, inflation, current-account balance/GDP, fiscal balance/GDP, public debt/GDP and log GDP per capita.
* Standard errors are clustered by country. Driscoll–Kraay, two-way clustering and a wild cluster bootstrap are reported alongside.

## 7. Decisions resolved before full-scale analysis (provisional choices documented in protocol v1.0)

| Decision | Choice | Consequence |
|---|---|---|
| Gross vs private inflows | Total gross (all sectors) for confirmatory tests | May dilute election effects that operate through private investors. Addressed post hoc. |
| Election window | Pre = {t−1, t}, Post = {t+1, t+2} | Mixes the run-up quarter with the election quarter. Alternatives tested. |
| Event-study reference period | k = −4 | Avoids absorbing the run-up effect |
| Early-election rule | Interval more than 6 months shorter than the modal 1990–2014 term | Rule-based. Misses some dissolutions where de facto terms are short (e.g. Japan). |
| Institutional moderators | 2014 levels (predetermined) | Main effects absorbed by country fixed effects. Only interactions are identified. |
| Controls | Lagged one year | Avoids conditioning on within-window mediators |
| Classification | Current IMF AE list (time-invariant) | Croatia and Bulgaria re-tested as EMDE |

## 8. Implementation plan (as executed)

Phases 1–9 were executed in order on 2026-10-11. See `PROJECT_STATUS.md` for the status of each deliverable and the next actions.
