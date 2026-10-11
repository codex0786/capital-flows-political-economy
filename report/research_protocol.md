# Research Protocol — Capital in Motion

**Political Policies, Institutional Stability and International Capital Flows Across Advanced and Emerging Economies, 2015–2026**

| | |
|---|---|
| Protocol version | 1.0 |
| Frozen on | 2026-10-11 |
| Status at freezing | Data acquired, harmonised and audited (`data/processed/data_quality_report.csv`). **No regression, event-study or other inferential estimate had been computed.** Only coverage, missingness and accounting-identity diagnostics had been inspected. |
| Change log | `report/protocol_changelog.md` (every later change is dated and marked as made before or after results were seen) |

---

## 1. Motivation

Capital-flow research in the IMF push–pull tradition explains cross-border flows by global factors (“push”) and domestic fundamentals (“pull”). Domestic political conditions are usually absent from that framework or enter only as slow-moving governance indices. Recent IMF work (*Elections Matter: Capital Flows and Political Cycles*, 2025) reports that gross private inflows to emerging markets weaken around elections. This study tests whether that pattern holds in a broader 2015–2025 sample of advanced and emerging/developing economies, and whether it varies by asset class, by institutional quality and between scheduled and early elections. It also tests whether institutions and external buffers change countries' exposure to global financial shocks.

## 2. Research questions and hypotheses

Hypotheses are stated as **two-sided** tests. Under the 2025 IMF result the expected sign is negative for H1a; the test does not assume it.

| ID | Hypothesis | Status |
|---|---|---|
| **H1a** | Gross private capital inflows (% GDP) differ in the pre-election window of executive-relevant national elections relative to other quarters, conditional on country and quarter fixed effects and predetermined fundamentals. | **Confirmatory (primary)** |
| **H1b** | Gross capital outflows by residents (% GDP) differ in the same window. | **Confirmatory (primary)** |
| H1c | Net flows and flow volatility differ in the same window. | Secondary |
| **H2** | The pre-election association in H1a varies with pre-determined institutional quality (WGI Rule of Law, 2014). | **Confirmatory** |
| H2-alt | The same moderation holds with regulatory quality, government effectiveness, voice and accountability, control of corruption, political stability (WGI 2014), and with V-Dem judicial and legislative constraints on the executive (2014). | Secondary (each reported; Holm-adjusted within family) |
| **H3** | The pre-election association differs across FDI, portfolio equity, portfolio debt and other-investment inflows. | **Confirmatory family of four** (Holm) plus equality test |
| H4 | Policy changes (large policy-rate moves, capital-account regime changes, fiscal balance) are associated with capital-flow changes. | **Exploratory only** — policy adoption is endogenous to flows and no credible quasi-experiment is pre-identified. |
| **H5** | The association between global risk (VIX, standardised) and gross inflows varies with pre-determined (2014) rule of law, reserve cover and short-term external debt/reserves. | **Confirmatory family of three** (Holm) |
| **H6** | The pre-election association (H1a) differs between AEs and EMDEs. | **Confirmatory** (difference tested directly) |
| R1 | Reverse direction: sudden stops of gross inflows in the previous four quarters predict chief-executive change, early elections or major social unrest. | Exploratory |

The primary family for the headline multiple-testing adjustment is {H1a, H1b, H2, H6} (Holm–Bonferroni, α = 0.05). H3 and H5 are adjusted within their own families.

## 3. Units, sample and timing

* **Country universe (rule-based, no discretionary exclusions):** an economy is included in the annual sample if it (i) is listed by the World Bank (or is Taiwan Province of China, which is listed by the IMF), (ii) had a population of at least 1 million in 2014 (IMF WEO), (iii) has gross FDI, portfolio and other-investment flows in both directions for at least 9 of the 11 years 2015–2025 (IMF BOP), and (iv) has a 2014 WGI Rule of Law estimate. The quarterly sample further requires at least 32 of the 44 quarters 2015Q1–2025Q4. **Result:** 121 annual, 108 quarterly economies (`data/processed/country_metadata.csv` gives the decision and reason for all 196 candidates).
* **Classification:** IMF WEO advanced economies (current DataMapper vintage; 43 economies, verified against the ADVEC aggregate) vs. all others (EMDE). Alternatives: (a) Croatia and Bulgaria as EMDE (pre-euro status), (b) World Bank high-income vs. others.
* **Financial centres** (LUX, IRL, NLD, MLT, CYP, HKG, SGP, CHE, BEL, PAN, MUS, BHR, BHS, BRB) are kept and excluded in a robustness test.
* **Period:** main estimation 2015Q1–2025Q4 (quarterly) and 2015–2025 (annual). Quarters of 2026 are published only for some countries. They are **excluded from all confirmatory estimates** and used only in descriptive extensions, labelled as partial.

## 4. Outcomes

Defined in BPM6 terms (IMF BOP, `IMF.STA:BOP` v21):

| Variable | Definition |
|---|---|
| `gross_inflows_gdp` (**primary**) | Net incurrence of liabilities to non-residents: direct investment + portfolio investment + other investment. Quarterly: 100 × 4 × flow / annual GDP (annualised % of GDP). |
| `gross_outflows_gdp` (**primary**) | Net acquisition of external financial assets by residents in the same three categories (reserves excluded). |
| `net_flows_gdp` | gross inflows − gross outflows (positive = net inflow). |
| `fdi_in_gdp`, `pe_in_gdp`, `pd_in_gdp`, `oi_in_gdp` | Liability-side components (H3). |
| `*_vol8` | 8-quarter rolling SD of the outcome (secondary; 4-quarter version descriptive only). |

Ratio outcomes are winsorised at the 1st/99th pooled percentiles within the main sample (suffix `_w`). Robustness: no winsorisation; 2.5/97.5. Aggregates are computed only when all components are present; missing values are never zero-filled.

## 5. Explanatory variables

* **Election timing (H1, H2, H3, H6).** Elections come from Wikipedia national electoral calendars, which give the event list and exact dates, and are triangulated with International IDEA and V-Dem v16. Only contests **corroborated by at least two sources** are used. *Executive-relevant* = the presidential contest where V-Dem codes the chief executive as directly elected (`v2x_ex_direlect ≥ 0.5`), otherwise the lower-house contest.
  * `elec_exec_pre` = 1 in the quarter of an executive-relevant election and in the quarter before it.
  * `elec_exec_post` = 1 in the two quarters after it.

  Both enter every election regression, so the reference is “quarters outside these windows”.
* **Early vs scheduled.** An election is early if the interval since the previous contest is more than 6 months shorter than the country's modal 1990–2014 term (V-Dem election years). This is a rule-based classification and not a legal judgement.
* **Institutional moderators.** WGI 2014 estimates (2026 WGI release) and V-Dem 2014 constraints. They are **predetermined and time-invariant** in the quarterly models, so their main effects are absorbed by country fixed effects and only the interactions are identified. They are mean-centred within the estimation sample.
* **Global risk (H5).** VIX quarterly mean, standardised over 2015–2025; it enters only through interactions because quarter fixed effects absorb its main effect.

## 6. Baseline controls and the bad-control problem

Baseline controls are the **previous calendar year's** real GDP growth, CPI inflation, current-account balance/GDP, general-government balance/GDP, gross public debt/GDP and log GDP per capita (IMF WEO). Lagging them keeps them predetermined relative to the quarter's flows and reduces the risk of controlling for channels through which elections act on flows, such as exchange-rate moves or policy-rate changes within the election window. Contemporaneous exchange rates, policy rates and WUI are **not** baseline controls because they are plausible mediators. A specification without any controls is reported for every primary result.

## 7. Estimators

1. **Baseline (H1).** For country *i* and quarter *t*, Y_it = α_i + λ_t + β₁·Pre_it + β₂·Post_it + γ′X_{i,y(t)−1} + ε_it, estimated by within-transformation OLS (`linearmodels.PanelOLS`) with country and quarter fixed effects.
2. **Moderation (H2).** The baseline plus Pre_it × (I_i − Ī) and Post_it × (I_i − Ī). Marginal effects of Pre are reported at the 10th, 50th and 90th percentiles of I with 95% confidence intervals.
3. **Group difference (H6).** The baseline plus Pre × EMDE and Post × EMDE. The test is on the interaction coefficient, with group-specific regressions reported alongside.
4. **Global shocks (H5).** Y_it = α_i + λ_t + δ·(VIX_t × M_i) + γ′X + ε, with each moderator M entered separately and then jointly.
5. **Event study (dynamics, pre-trends).** Indicators for k = −6…+6 quarters relative to an executive-relevant election, omitting k = −4. Quarters farther than 6 from any election are also part of the reference category. **Reference period: k = −4**, not −1, because the hypothesis concerns the pre-election run-up itself. Two versions are estimated:
   * all corroborated executive-relevant elections;
   * **scheduled elections only**, the identifying sample (see §8).

   As a robustness check, a **stacked event study** uses clean controls: countries with no executive-relevant election within ±6 quarters of the treated event, with event-by-country and event-by-quarter fixed effects. This guards against the contamination of two-way fixed-effects (TWFE) event studies under heterogeneous effects.
6. **Annual panel.** The same H1, H2 and H6 designs using an annual election indicator (`exec_election`), plus within-country relationships of time-varying WGI and V-Dem measures with flows. These are associations, not causal effects. A correlated-random-effects (Mundlak) specification reports between-country governance associations.
7. **Reverse direction (R1, exploratory).** Linear probability models of chief-executive change (annual), early election in the year, or a major unrest quarter on sudden-stop indicators in t−1…t−4, with country and time fixed effects.

## 8. Identification

* Fixed-effects estimates are conditional within-country associations. **Causal language is reserved for the scheduled-election design.** The timing of constitutionally scheduled elections is fixed years in advance, so the election quarter is plausibly unrelated to contemporaneous country-specific capital-flow shocks. The estimand is the effect of the *election period* as a bundle (uncertainty, campaign-period policy, pre-electoral fiscal behaviour), not of “uncertainty” alone.
* Early elections are plausibly endogenous to economic conditions, including capital-flow stress (reverse causality), so they are analysed separately and treated as associational.
* The pre-trend test uses the joint significance of the k = −6 and k = −5 leads. Failing to reject is not proof of parallel trends; the stacked design and placebo dates are complementary checks.
* No instrumental-variable design is used. No candidate instrument with a defensible exclusion restriction was identified. Lagged political variables are not valid instruments.

## 9. Policy events (H4)

`policy_events.csv` v1.0 contains only events derived mechanically from data:
* |Δ Chinn–Ito ka_open| ≥ 0.10 in a year;
* |quarterly Δ BIS policy rate| ≥ 2 percentage points.

Hand-coded legislative and regulatory events (investment screening, ownership limits, repatriation rules, sanctions) require a codebook, primary legal sources and double coding. They are **planned but not executed** in v1.0. All policy analyses are exploratory.

## 10. Inference

* **Primary:** standard errors clustered by country (108 quarterly / 121 annual clusters).
* **Reported alongside every primary coefficient:**
  * Driscoll–Kraay standard errors (bandwidth 4 quarters), robust to cross-sectional dependence from common shocks;
  * two-way clustering by country and quarter;
  * a wild cluster bootstrap p-value (Rademacher weights, 999 replications, seed 20261011, null imposed).

  The inference method was chosen in advance and is not selected by p-value.
* Effect sizes are reported in percentage points of GDP and relative to the outcome's within-country standard deviation.

## 11. Robustness programme (pre-specified)

| Test | Threat addressed |
|---|---|
| No controls / contemporaneous controls | Bad controls; omitted fundamentals |
| Unwinsorised; 2.5/97.5 winsorisation | Outlier influence |
| Exclude financial centres | SPE pass-through flows unrelated to domestic politics |
| Exclude 2020 | Pandemic shock coinciding with elections |
| Leave-one-country-out (distribution of β) | Single-country influence |
| Alternative windows: pre = election quarter only; pre = 3 quarters | Arbitrary window choice |
| Any national election instead of executive-relevant | Executive-relevance coding error |
| Wikipedia+IDEA+V-Dem (3-source) elections only | Event-coding error |
| Balanced quarterly panel only | Composition changes |
| Scale by previous-year GDP | Denominator endogeneity (elections affecting GDP) |
| Alternative AE/EMDE classifications | Classification sensitivity |
| Placebo election dates (each country's elections shifted by a random 8–12 quarters, 500 draws) | Spurious timing correlation |
| Driscoll–Kraay, two-way clustering, wild bootstrap | Cross-sectional dependence; few clusters within subgroups |

## 12. Known limitations at freezing

* The WGI 2026 release revises historical estimates; only this vintage is accessible through the API, so a vintage-sensitivity test is **not feasible** in v1.0. Using 2014 levels limits the issue to measurement and does not touch timing.
* UNCTAD greenfield and M&A data and BIS banking statistics (beyond policy rates) are **not ingested in v1.0**. FDI is measured from BOP only.
* Election closeness, government-formation delays and coalition changes are not coded.
* Quarterly ratios use annual GDP as the denominator, with WEO projections for 2026.
* The V-Dem leader-change measure uses end-of-year snapshots and misses short-lived intra-year changes.
