# Pre-registration: out-of-sample test of the EMDE election-quarter effect

| | |
|---|---|
| Frozen on | 2026-10-11 |
| Machine-readable spec | `report/preregistration_2026_spec.json` (SHA-256 `0dffd335df458107a5e9170ca73f575e04301a93b0477434eea82851776f8b81`) |
| Git tag | `prereg-2026-elections` |
| Status | Registered. No balance-of-payments data for any primary election quarter existed on the freeze date. |

## Why

The study's post-hoc analysis found that gross capital inflows to emerging and developing economies were 2.15 pp of GDP (annualised) lower in the quarter of an executive-relevant election, 2015–2025 (SE 0.65). Because that window was chosen after the pre-registered results were seen, it must be tested on new elections before policymakers rely on it.

## Hypothesis

In emerging and developing economies, gross capital inflows (annualised % of GDP) are lower in the quarter of an executive-relevant national election than in other quarters. Test: one-sided, coefficient < 0.

## Qualifying elections (primary set: 2026Q3–2027Q4, data not yet published on 2026-10-11)

| Economy | Contest | Date | Quarter | Latest BOP quarter on freeze date |
|---|---|---|---|---|
| Zambia | presidential | 2026-08-13 | 2026Q3 | 2026Q1 |
| Morocco | parliamentary | 2026-09-23 | 2026Q3 | 2026Q2 |
| Brazil | presidential | 2026-10-04 | 2026Q4 | 2026Q2 |
| Bosnia and Herzegovina | parliamentary | 2026-10-04 | 2026Q4 | 2026Q1 |
| Serbia | parliamentary | 2026-10-25 | 2026Q4 | 2026Q1 |
| Nigeria | presidential | 2027-01-16 | 2027Q1 | 2026Q1 |
| Kyrgyz Republic | presidential | 2027-01-27 | 2027Q1 | 2024Q4 |
| El Salvador | presidential | 2027-02-28 | 2027Q1 | 2026Q1 |
| Burundi | presidential | 2027-05-03 | 2027Q2 | 2026Q2 |
| Guatemala | presidential | 2027-06-27 | 2027Q2 | 2026Q1 |
| Angola | parliamentary | 2027-08-24 | 2027Q3 | 2026Q2 |
| Papua New Guinea | parliamentary | 2027-10-24 | 2027Q4 | 2025Q1 |
| Poland | parliamentary | 2027-10-24 | 2027Q4 | 2026Q2 |
| Tajikistan | presidential | 2027-10-24 | 2027Q4 | 2026Q1 |
| Argentina | presidential | 2027-10-24 | 2027Q4 | 2026Q2 |

**15 primary elections.** Dates from the Wikipedia calendar; each must be confirmed by a second source when the analysis runs.

### Secondary set (2026Q1–Q2, data already published but not analysed for this question)

| Economy | Contest | Date | Quarter | Latest BOP quarter on freeze date |
|---|---|---|---|---|
| Uganda | presidential | 2026-01-15 | 2026Q1 | 2026Q1 |
| Costa Rica | presidential | 2026-02-01 | 2026Q1 | 2026Q1 |
| Thailand | parliamentary | 2026-02-08 | 2026Q1 | 2026Q2 |
| Bangladesh | parliamentary | 2026-02-12 | 2026Q1 | 2026Q2 |
| Lao PDR | parliamentary | 2026-02-22 | 2026Q1 | 2026Q2 |
| Nepal | parliamentary | 2026-03-05 | 2026Q1 | 2026Q2 |
| Viet Nam | parliamentary | 2026-03-15 | 2026Q1 | 2026Q1 |
| Hungary | parliamentary | 2026-04-12 | 2026Q2 | 2026Q2 |
| Bulgaria | parliamentary | 2026-04-19 | 2026Q2 | 2026Q2 |
| Colombia | presidential | 2026-05-31 | 2026Q2 | 2026Q2 |

## Outcome and specification

* **Outcome:** gross inflows = (D_F + P_F + O_F, L_NIL_T) * 4 / annual GDP (IMF WEO NGDPD) * 100. Winsorisation bounds are frozen at [-34.17, 105.04].
* **Specification:** Panel 2015Q1-2027Q4, EMDE sample. y_it = country FE + quarter FE + b_old*E_old + b_new*E_new + pre12 + post12 + lagged-year controls (growth, inflation, CA, fiscal balance, public debt, log GDP per capita). E_old = election quarter for 2015-2025 elections; E_new = election quarter for the primary qualifying elections. Pre/post windows (1-2 quarters) for all elections. SEs clustered by country.
* **Primary statistic:** b_new, one-sided p-value from the country-clustered t statistic (G-1 df).
* **Decision rule:** Confirmed if b_new < 0 with one-sided p < 0.05. Otherwise reported as not confirmed, with the estimate and 90% CI. Either way the result is published.

## Secondary analyses

* Wild cluster bootstrap p-value for b_new (999 Rademacher draws, seed 20261011)
* Prediction-error test: mean residual in qualifying election quarters from the frozen 2015-2025 EMDE model (no re-estimation), one-sided t test
* Private gross inflows (official OI liabilities and SDR removed)
* Pooled test (pre-specified, reported alongside the primary): primary set plus the 2026Q1-Q2 secondary set, whose BOP data were published by the freeze date but were not analysed for this question. Same specification and decision rule; reported as secondary because the data existed at registration.

## Power

* Historical estimate: 188 EMDE executive-relevant elections, SE 0.65.
* **Primary set:** 15 elections, expected SE about 2.30. One-sided 5% power is 11%, 22% and 37% for true effects of −1, −2 and −3 pp.
* **Pooled set:** 25 elections, expected SE about 1.78. Power is 14%, 30% and 52%.
* Approximation: historical SE scaled by sqrt(n_old/n_new). Low power means a null result would be weak evidence against the effect. A test of this size can confirm a large effect but cannot rule out a moderate one.
* About **123 elections** would be needed for 80% power against a true −2 pp effect, roughly six to seven years of EMDE elections. A faster and more powerful confirmation would use market data around election dates (weekly portfolio flows, sovereign spreads, exchange rates); that is outside this registration.

## Interpretation commitments

* A confirmed result supports using the election-quarter adjustment in EMDE outlooks.
* A non-confirmed result is reported as *inconclusive*, not as evidence of no effect, unless the 90% interval excludes −1 pp.
* An estimate with the opposite sign and one-sided p < 0.05 for a positive effect is reported as contradicting the post-hoc finding.

## Timing and deviations

Analysis runs once BOP data cover the 2027Q4 election quarter for at least 80% of qualifying economies (expected around mid-2028), and no later than 2028-09-30. An interim look at elections through 2027Q2 may be published but is labelled interim and does not change the decision rule. Any deviation will be logged in report/protocol_changelog.md with date and reason, before the analysis is run.
