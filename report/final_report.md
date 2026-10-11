# Capital in Motion: Political Policies, Institutional Stability and International Capital Flows Across Advanced and Emerging Economies, 2015–2026

**Research report — version 1.0, 11 October 2026**

*Reproducible package: `run_pipeline.sh`. Pre-registered protocol: `report/research_protocol.md` (git tag `protocol-v1.0`, committed before any estimate was computed). Post-hoc changes: `report/protocol_changelog.md`.*

> **Evidence labels used throughout**
> **[Data]** what the data directly show · **[Descriptive]** patterns without a model · **[Confirmatory]** pre-registered tests (protocol v1.0) · **[Secondary]** pre-registered but outside the primary family · **[Exploratory / post-hoc]** specified after results were seen · **[Causal]** used only where the identifying assumption is stated.

---

## 1. Abstract

We study how national elections, institutional quality and global financial conditions relate to cross-border capital flows in 121 economies (annual) and 108 economies (quarterly) between 2015 and 2025. Flows come from IMF balance-of-payments data (BPM6 gross liabilities and assets). Election dates are triangulated across Wikipedia national electoral calendars, International IDEA and V-Dem v16.

Our **pre-registered** primary hypotheses are not supported. Gross inflows and gross outflows in a two-quarter pre-election window (the election quarter and the quarter before) are indistinguishable from other quarters:
* inflows: −0.14 pp of GDP annualised, 95% CI [−1.59, 1.30];
* outflows: +0.40, CI [−1.01, 1.81];
* Holm-adjusted p = 1.00 for both.

Pre-determined rule of law does not moderate the election-window association (p = 0.73), and the AE–EMDE difference is not significant (p = 0.39). Capital-flow components do not differ (joint test p = 0.43). Institutions and buffers do not significantly moderate exposure to VIX shocks after multiple-testing adjustment. Recent sudden stops do not predict unrest, early elections or executive turnover.

Two patterns emerge outside the confirmatory family:
* **[Secondary]** Gross inflows and outflows fall together by about 1.4 pp in the two quarters after elections (gross retrenchment, net flows unchanged). The sign is stable across all 34 robustness specifications but significance is fragile.
* **[Post-hoc]** After aligning the window with the closest prior study (the election quarter alone; Arakelyan & Evdokimova, 2025), emerging and developing economies show a sizeable election-quarter decline in gross inflows. It is −2.15 pp of GDP annualised, about one-third of mean EMDE inflows (wild-bootstrap p = 0.001; calendar-shift placebo p < 0.001; robust to country × season fixed effects).

That study's key moderation result, larger declines where political stability is low, does **not** replicate in 2015–2025. Because the window alignment was chosen after the pre-registered results were known, the EMDE election-quarter effect is a well-supported lead for out-of-sample confirmation, not a confirmed finding.

## 2. Introduction

Domestic politics is largely missing from the workhorse push–pull framework for capital flows (Koepke, 2019; Fratzscher, 2012). Elections are the most clearly dated political events. Finance research shows that investment and option prices react to them (Julio & Yook, 2012; Kelly, Pástor & Veronesi, 2016), and a recent IMF paper reports that gross private inflows to 38 emerging markets fall around elections between 1990 and 2020 (Arakelyan & Evdokimova, 2025). We ask whether such patterns hold in a broader, more recent sample (2015–2025, advanced and emerging economies). We also ask whether they differ by asset class and institutional quality, and whether institutions shape exposure to global shocks. Throughout, we separate what is pre-registered from what is not.

## 3. Motivation and contribution

* **Scope.** 121/108 economies, including advanced economies, over a post-2015 period dominated by quantitative easing and tightening, a pandemic and geopolitical fragmentation.
* **Measurement.** Gross inflows and outflows are tested separately under BPM6 definitions, with net flows and volatility as secondary outcomes. Election dates are triangulated across three sources, because the most common single source (IDEA) has year-only dates for about half of recent records.
* **Transparency.** A pre-registered protocol, multiple-testing adjustment, four inference methods, placebo calendars and leave-one-out checks.
* **Contribution, stated carefully.**
  1. A pre-registered null for a *run-up* (pre-election) effect across a broad sample.
  2. Out-of-period evidence consistent with an *election-quarter* decline in EMDEs. This partly replicates Arakelyan & Evdokimova (2025) in an independent period (2021–2025 is outside their sample) with a different election source.
  3. A failure to replicate their political-stability moderation.

  We do not claim novelty for the combination of variables alone.

## 4. Literature review

**Push and pull determinants.** Global factors, especially risk appetite (the VIX), drive portfolio flows to emerging markets, while domestic “pull” factors matter more for bank and FDI flows (Koepke, 2019; Fratzscher, 2012; Cerutti, Claessens & Puy, 2019). A global financial cycle linked to US monetary policy transmits across borders (Rey, 2015; Miranda-Agrippino & Rey, 2020). Hence our quarter fixed effects and the VIX-interaction design (H5).

**Gross versus net flows and episodes.** Gross flows by residents and non-residents move differently and often offset each other (Broner et al., 2013; Forbes & Warnock, 2012). Sovereign flows frequently counter private flows (Avdjiev et al., 2022). This motivates separate gross outcomes and our post-hoc private-flow measure. Extreme episodes (surges, stops, retrenchment) are dominated by global risk (Forbes & Warnock, 2012; Ghosh et al., 2014). FDI is more stable than debt flows (Eichengreen, Gupta & Masetti, 2018).

**Political uncertainty and investment.** Firms cut investment in election years (Julio & Yook, 2012). US multinationals' FDI to foreign affiliates falls before host-country elections, with no comparable cycle in portfolio flows and smaller swings where institutions are stronger (Julio & Yook, 2016). Pre-election declines in private investment appear when elections imply large policy uncertainty: polarisation and competitiveness (Canes-Wrone & Park, 2012). Political uncertainty is priced in options around elections (Kelly, Pástor & Veronesi, 2016; Pástor & Veronesi, 2013). Continuous measures of uncertainty include EPU (Baker, Bloom & Davis, 2016), the WUI (Ahir, Bloom & Furceri, 2022), geopolitical risk (Caldara & Iacoviello, 2022) and social unrest (Barrett et al., 2022).

**Elections and capital flows.** The closest study is Arakelyan & Evdokimova (2025), whose full text we read only after the pre-registered estimation. Using DPI/NELDA election dates for 38 EMs (1990–2020) and gross *private* inflows scaled by trend GDP, they report:
* declines in the election quarter and up to two quarters after;
* *no* significant run-up decline;
* about a 28% fall in the election quarter for the bottom quartile of ICRG political stability, with no decline above average stability;
* mitigation by stronger institutions.

**Institutions and investment.** Low institutional quality explains much of the Lucas paradox (Alfaro, Kalemli-Ozcan & Volosovych, 2008). Political institutions shape FDI (Jensen, 2003; Li & Resnick, 2003; Busse & Hefeker, 2007; Papaioannou, 2009). Regime type, institutional quality and election uncertainty are distinct constructs. WGI estimates are composite, noisy and revised (Kaufmann, Kraay & Mastruzzi, 2011).

**Policy and capital controls.** Capital-flow management measures have mixed and context-specific effects (Forbes, Fratzscher & Straub, 2015; Fernández et al., 2016). De jure openness indices (Chinn & Ito, 2006) change rarely and endogenously.

**Methods.** We use:
* inference robust to cross-sectional dependence (Driscoll & Kraay, 1998);
* cluster bootstrap inference (Cameron, Gelbach & Miller, 2008; Roodman et al., 2019);
* event-study designs aware of heterogeneity bias in TWFE (Goodman-Bacon, 2021; de Chaisemartin & D'Haultfœuille, 2020; Sun & Abraham, 2021; Callaway & Sant'Anna, 2021), including a stacked clean-control design (Cengiz et al., 2019);
* Mundlak (1978) between/within decompositions.

**Gaps addressed.** Existing election–flow evidence is EM-only, ends in 2020 and is not pre-registered. AE–EM comparisons with common definitions are rare. A structured evidence matrix is in `literature/literature_matrix.csv`; all scholarly references have Crossref-verified DOIs (`literature/bibliography.csv`).

## 5. Theoretical framework

Elections bundle three mechanisms:
1. **Uncertainty about future policy.** Real-options logic says investors delay irreversible commitments until uncertainty resolves (Julio & Yook, 2012, 2016).
2. **Pre-electoral policy.** Political budget cycles (Brender & Drazen, 2005) may raise financing needs or yields, potentially attracting debt inflows.
3. **Post-electoral repricing** after the outcome is revealed.

Mechanisms 1 and 3 predict fewer inflows near and just after elections, larger for irreversible FDI than for liquid portfolio flows. Mechanism 2 can push debt inflows the other way. Institutions that constrain policy reversals should shrink uncertainty effects. Global push factors act on all countries but bite harder where buffers are thin. Reverse causation runs from sudden stops to political crises and early elections.

## 6. Research questions and hypotheses

See protocol §2. The confirmatory family is {H1a gross inflows, H1b gross outflows, H2 rule-of-law moderation, H6 AE/EMDE difference}, Holm-adjusted. H3 (components) and H5 (global-shock moderation) are separately adjusted families. H4 (policy) and R1 (reverse direction) are exploratory.

## 7. Data sources and sample construction

**[Data]** All series were retrieved on 2026-10-11 (`data/processed/source_register.csv`; SHA-256 hashes in `data/raw/source_register_log.csv`).

* **Flows.** IMF BOP (IMF.STA:BOP v21), BPM6 financial account by functional category and accounting entry, annual and quarterly, 2014–2026Q2.
* **GDP.** IMF WEO (WDI as fallback).
* **Institutions.** WGI 2026 release; V-Dem v16.
* **Elections.** Wikipedia national electoral calendars (exact dates), International IDEA and V-Dem.
* **Uncertainty.** WUI, GPR, IMF RSUI.
* **Global.** FRED (VIX, Fed funds, US 10-year yield, broad dollar, Brent, US HY OAS).
* **Policy.** BIS policy rates; Chinn–Ito KAOPEN.

**Sample.** A documented rule (protocol §3) applied to 196 candidates gives 121 annual (33 AE, 88 EMDE) and 108 quarterly (33 AE, 75 EMDE) economies. Exclusions are listed with reasons in `country_metadata.csv`:

| Reason | Candidates |
|---|---|
| Population < 1m | 50 |
| < 9 years of complete BOP | 40 |
| No WGI 2014 | 10 |
| Not World Bank-listed | 5 |

Advanced-economy membership follows the current IMF WEO group (43 economies). It was verified exactly against the published ADVEC GDP aggregate (`results/diagnostics/ae_membership_check.csv`).

**2026.** Quarterly data for 2026 exist for 95 sample economies (61 to Q2, 34 to Q1). They are flagged as partial and **excluded from all estimates**.

**Elections.** 431 corroborated national contests fall in 2015–2025 in the quarterly sample. Of these, 282 are executive-relevant: 195 scheduled, 71 early under the rule-based classification, and 16 unclassified because they are the first contest in the series. 37.7% of executive-relevant elections produced a change of chief executive (V-Dem).

| Election verification | Count |
|---|---|
| All three sources agree | 642 |
| Two sources | 110 |
| Wikipedia only (excluded) | 137 |
| Date conflicts with IDEA > 7 days (Wikipedia date kept, both recorded) | 7 |

**Validation.** Panel keys are unique. The BPM6 identity (financial-account balance = gross outflows − gross inflows + derivatives + reserves) holds within 0.5% of GDP in 100% of country-periods. Core flow variables are ≥ 99.6% complete. 21 unit tests pass.

## 8. Variable definitions

Full dictionary: `config/variable_dictionary.csv`.

* **Gross inflows.** Net incurrence of liabilities (FDI + portfolio + other investment); positive = new non-resident claims.
* **Gross outflows.** Net acquisition of assets by residents in the same categories, excluding reserves.
* **Net flows** = gross inflows − gross outflows.
* **Scaling.** Quarterly flows are expressed as 100 × 4 × flow / annual GDP (annualised % of GDP) and winsorised at the pooled 1st/99th percentiles.
* **Election windows.** Pre = the quarter of, or before, an executive-relevant corroborated election. Post = the two following quarters.
* **Moderators.** Fixed at 2014 values.
* **Controls.** Previous-year macro fundamentals.

## 9. Empirical methodology

For country *i* and quarter *t*:

Y_it = α_i + λ_t + β₁·Pre_it + β₂·Post_it + γ′X_{i,y(t)−1} + ε_it

* Country and quarter fixed effects; standard errors clustered by country (108 clusters).
* Driscoll–Kraay (bandwidth 4) and two-way clustered standard errors reported.
* Restricted wild cluster bootstrap p-values (999 Rademacher draws).
* Moderation models interact Pre and Post with centred 2014 moderators.
* Event studies use k = −6…+6 with reference k = −4, in TWFE and stacked clean-control variants.

Estimation code: `src/econometrics/`. Every specification is logged in `results/logs/model_specs.json`.

## 10. Identification assumptions

Fixed-effects estimates are conditional associations. A causal reading of the election-period coefficient requires that, conditional on fixed effects and predetermined controls, *scheduled* election timing is unrelated to other country-specific shocks to capital flows. This is plausible because constitutional calendars are set years ahead. The estimand is the effect of the election period as a bundle, not of uncertainty per se.

Early elections, governance changes and policy changes are endogenous and are interpreted only associationally. No instrumental-variable design was used.

## 11. Descriptive results

**[Descriptive]**
* **Figure 1.** In advanced economies, aggregate gross inflows swing widely and portfolio inflows rose to about 6% of group GDP in 2025. In EMDEs, FDI was the largest component until 2021 but fell from about 2.3% to about 1% of GDP by 2023–25.
* **Table 1** (`results/tables/table1_descriptives.csv`). Mean quarterly annualised gross inflows are 11.3% of GDP (AE) and 6.6% (EMDE). Within-country standard deviations are large (20.1 and 9.7 pp). Quarterly flows are very noisy relative to any plausible election effect.
* **Figure 5.** The cross-section shows no clear relationship between 2014 rule of law and average inflows once financial centres are set aside.
* **Figure 8.** Inflow volatility is higher in AEs and financial centres.

## 12. Main econometric results

**[Confirmatory]** (`results/tables/table2_confirmatory.md`, `multiple_testing.csv`)

| Hypothesis | Estimate (pp GDP, ann.) | 95% CI | WCB p | Holm p |
|---|---|---|---|---|
| H1a pre-election window → gross inflows | −0.14 | [−1.59, 1.30] | 0.851 | 1.000 |
| H1b pre-election window → gross outflows | +0.40 | [−1.01, 1.81] | 0.591 | 1.000 |
| H2 pre-window × rule of law (2014, per unit) | +0.34 | [−1.64, 2.32] | 0.727 | 1.000 |
| H6 pre-window × EMDE | −1.58 | [−5.25, 2.10] | 0.389 | 1.000 |

The H1a confidence interval rules out pre-window effects larger than about 1.6 pp of GDP in either direction. That is about 0.12 within-country standard deviations of gross inflows.

Inference is consistent across methods for H1a: country-clustered SE 0.73, Driscoll–Kraay 0.45, two-way clustered 0.68, all with p > 0.7.

**[Secondary]**
* **Post-election window:** gross inflows −1.36 (p = 0.04) and gross outflows −1.39 (p = 0.05). Net flows: pre −0.36 (p = 0.32), post +0.11 (p = 0.75). Flow volatility does not change.
* **Scheduled vs early:** for scheduled elections the post-window coefficients are −1.94 (inflows, p = 0.018) and −2.08 (outflows, p = 0.013); pre-window coefficients are near zero. Early elections show no detectable pattern, but they are few (71) and the estimates are imprecise.
* **Annual panel:** the election-year coefficient is −0.43 for gross inflows (p = 0.25) and −0.44 for FDI inflows (p = 0.06).

## 13. Heterogeneity analysis

* **H2 (institutions).** None of the eight institutional moderators significantly changes the pre-window association (Holm p = 1.00 for all; Figure 6). Marginal effects at the 10th, 50th and 90th percentiles of each moderator all include zero.
* **H6 (AE vs EMDE).**
  * Group-specific pre-window estimates are −0.90 for EMDEs (p = 0.08) and +0.77 for AEs (p = 0.69).
  * The difference is not significant (−1.58, p = 0.39).
  * Point estimates suggest EMDE inflows soften around elections, consistent in sign with the IMF evidence, but the pre-registered test cannot distinguish groups.
* **H3 (components).**
  * Pre-window estimates: FDI −0.24, portfolio equity −0.14, portfolio debt +0.25, other investment +0.10 (Holm p ≥ 0.67).
  * The joint equality test does not reject (χ²(3) = 2.77, p = 0.43).
  * The post-window decline is concentrated in other investment: inflows −1.03 (p = 0.04) and outflows −0.98 (p = 0.04). This is consistent with the gross co-movement of bank-intermediated flows (Avdjiev et al., 2022).
* **H5 (global shocks).** A one-SD higher VIX lowers gross inflows more in countries with higher 2014 reserve cover: −0.50 pp per SD of reserves (WCB p = 0.086, Holm p = 0.26). This sign is counter-intuitive under a buffer story; it may reflect deeper financial integration of high-reserve economies. Rule of law (+0.29, p = 0.38) and short-term debt/reserves (−0.35, p = 0.19; 61 economies) are not significant. **No H5 hypothesis survives adjustment.**
* **H4 (policy, exploratory).**
  * Large policy-rate changes (38 BIS economies): +0.12 pp per percentage point, p = 0.17.
  * KAOPEN changes: +2.05, p = 0.51.
  * Contemporaneous fiscal balance: −0.11, p = 0.43.
  * No association is detectable. Figure 9 shows descriptive paths around capital-account regime changes with wide uncertainty.
* **Governance, within-country (annual, exploratory).** Year-to-year improvements in WGI political stability (+3.24 pp per unit, p = 0.046) and regulatory quality (+5.05, p = 0.049) are associated with higher gross inflows. Mundlak between-country coefficients are near zero. These are unadjusted, associational results on slow-moving, revised indices.

## 14. Event-study and causal analysis

**TWFE event studies** (Figure 7, `event_study_coefficients.csv`):
* No coefficient in k = −3…0 is individually significant for inflows.
* The post-election dip at k = +1, +2 (scheduled: −2.32 and −1.98) is followed by a rebound at k = +3 (+1.71). That pattern looks more like a timing shift in flows than a persistent level change.
* Pre-trend tests (k = −6, −5 jointly):
  * inflows: p = 0.16 (all elections), 0.41 (scheduled);
  * outflows: p = 0.047 (all elections, a warning) and 0.34 (scheduled).

**Stacked clean-control design** (92 scheduled elections; controls with no executive-relevant election within ±12 quarters):
* Point estimates after elections are mostly negative.
* Standard errors are 3–5 pp, so the design cannot confirm or reject effects of the size suggested by TWFE.
* The pre-window joint test gives p = 0.42.

**Causal reading [Causal, scheduled-election design].** Under the identifying assumption in §10, the effect of the two-quarter pre-election period on gross inflows is close to zero with moderate precision (scheduled pre −0.23, CI [−1.91, 1.46]). The post-election effect is negative (about −1.9 pp) but not robust across designs. Neither is established as a causal effect at conventional confidence once design sensitivity is considered.

**Reverse direction, R1 (exploratory).** Sudden stops in the previous four quarters do not predict:
* major social unrest (coefficient 0.000, p = 0.99);
* early elections (+0.002, p = 0.74);
* chief-executive change in the following year (−0.012, p = 0.81).

Sudden stops are not rare: 247 episode-quarters across 69 economies, 8.1% of quarters. The political outcomes are rarer (71 early executive-relevant elections in about 4,700 country-quarters), which limits power for that outcome.

## 15. Robustness checks

All 34 pre-specified tests are in `robustness_matrix.csv` and Figure 10.

* **Pre-window coefficient for inflows.**
  * Ranges from −0.94 to +0.27 and is never significant at 5%.
  * The closest is the EMDE-only sample (−0.94, p = 0.06).
  * Leave-one-country-out range: [−0.47, +0.19].
  * Placebo calendars (500 draws, shifted 8–12 quarters): p = 0.84.
* **Post-window coefficient.**
  * Negative in every specification (−0.86 to −3.00).
  * p ranges from 0.014 to 0.27. It loses significance when financial centres are excluded (p = 0.14), when 2020 is excluded (0.10), with 2.5/97.5 winsorisation (0.06) and in the balanced panel (0.06).
  * Placebo p = 0.050 (inflows) and 0.11 (outflows).
  * Leave-one-out range: [−1.49, −0.97].
* **Interpretation.** The pre-registered null is robust. The post-election retrenchment is directionally stable but statistically fragile.

## 16. Discussion — post-hoc alignment with the closest prior study

**[Exploratory / post-hoc — specified after the confirmatory results were known; see changelog entries 1.0-posthoc-a and 1.0-posthoc-b.]**

After estimation we read Arakelyan & Evdokimova (2025) in full. Their design differs from our protocol in three ways:
1. the event is the election quarter itself;
2. the outcome removes official-sector other-investment liabilities;
3. the sample is emerging markets only.

Re-estimating with their window and outcome definitions (`posthoc_imf_alignment.csv`):

| Sample / outcome | Election-quarter (k=0) coefficient | WCB p | Placebo p (1,000 calendars) | With country × season FE |
|---|---|---|---|---|
| EMDE, gross inflows | −2.15 (SE 0.65) | 0.001 | < 0.001 | −1.93 (p = 0.006) |
| EMDE, private gross inflows | −1.83 (SE 0.63) | 0.005 | 0.002 | −1.71 (p = 0.010) |
| All economies, private gross inflows | −1.47 (SE 0.69) | 0.032 | — | −1.39 (p = 0.035) |
| All economies, gross inflows | −0.95 (SE 0.68) | 0.152 | — | −0.59 (p = 0.37) |

The EMDE election-quarter decline is about −2 pp of GDP annualised. That is roughly 0.2 within-country standard deviations, or about one-third of mean EMDE gross inflows. It is similar in relative magnitude to the ~28% decline that Arakelyan & Evdokimova report for low-stability EMs.

Our pre-registered window combined the election quarter with the quarter before. The quarter before shows small positive coefficients (k = −1: +0.46 to +0.79), so the combined window diluted the effect. In other words, the null for the run-up and the post-hoc election-quarter effect are mutually consistent. Both agree with Arakelyan & Evdokimova's own finding of no run-up decline.

**What does not replicate.** Their headline moderation does not hold here. Interacting the election quarter with bottom-quartile 2014 WGI political stability gives +0.08 (p = 0.95) in EMDEs. Using WGI rather than ICRG, a different period and different election coding may all contribute.

**Status.** Six post-hoc specifications were estimated. The EMDE k = 0 result survives a Bonferroni factor of 6 (p = 0.006 for gross inflows), the placebo, seasonality fixed effects and the private-flow definition. It remains post-hoc. Confirming it requires an out-of-sample test with the window fixed in advance; 2026 elections are a natural candidate once data are published.

## 16b. Crises, policy levers and market prices (exploratory, added in v3)

**Data.** We built a country-level event database of 1,265 events. It covers:
* systemic banking crises (IMF WP/26/94);
* sovereign defaults by creditor type (BoC–BoE 2026);
* currency crises (Laeven–Valencia rule on annual-average USD rates);
* large IMF financing (credit outstanding up at least 25% of quota within four quarters; a proxy for disbursing programmes);
* inflation above 40%;
* quarters with two or more capital-flow restriction changes (Bergant, Fernández, Teoh & Uribe 2025).

Policy-lever panels add capital-flow restrictions, FX intervention (IMF) and policy rates. Market panels add exchange rates, government yields and spreads over US Treasuries (monthly), plus daily FX for 12 currencies.

**Do named crises explain the model's surprises?** Largely no. Unexplained flow movements, scaled by country volatility, are not significantly larger in crisis years once country fixed effects are included (+0.04 SD, p = 0.11). Of the largest 10% of surprises, 21% fall in crisis years, against a 23% base rate. Currency-crisis years are the exception: they are twice as likely to be among the largest surprises (20% vs 10%).

**Policy levers.** Next-quarter flows rise after inflow-restriction tightening (+0.38 pp, p = 0.03), FX purchases (net flows +0.44 pp, p = 0.001) and rate hikes (gross inflows +0.25 pp, p = 0.003). These signs are what reverse causality predicts: policy responds to surges. They are not estimates of policy effectiveness.

**Markets around elections.** Monthly, EMDE currencies move +0.27% per month against the USD in the election month and the following two months (p = 0.45). EMDE yields move +0.11 pp (p = 0.44). Daily, across 21 elections, the cumulative move 20 trading days after the vote is −0.95% (95% CI −2.42 to 0.42; placebo p = 0.21). Markets show no detectable election reaction, consistent with the null pre-registered flow results.

**Market signals in risk models.** Adding 3-month currency and yield moves did not improve held-out flows-at-risk or sudden-stop prediction (see the model card).

## 17. Limitations

1. **Power.** Quarterly gross flows are extremely noisy (within-SD ≈ 10–20 pp of GDP annualised), and windows are short. Moderately sized effects, below about 0.1 within-SD, cannot be ruled out.
2. **Election coding.** The executive-relevance rule (V-Dem `v2x_ex_direlect`) and the early-election rule are approximations. The first contest after 2010 in each series cannot be classified. Wikipedia is crowd-sourced; we require corroboration by at least two sources.
3. **Measures not coded:** closeness, polarisation, government-formation delays, coalition changes.
4. **Official vs private flows.** The confirmatory outcome includes official-sector liabilities. The private measure treats unpublished official instruments as not reported.
5. **Data vintages.** Only the revised WGI 2026 vintage is available. WEO 2025 values are partly estimates, and 2026 GDP denominators are projections (used only in descriptive 2026 figures).
6. **Not ingested:** UNCTAD greenfield/M&A data (FDI measured via BOP only), BIS banking and international debt-securities statistics, the iMaPP macroprudential database, IMF MONA programme data, sanctions, credit ratings and EMBI spreads. IMF financing is proxied from Fund Accounts; spreads are local-currency yields minus US Treasuries, not credit spreads.
7. **Policy events.** These are data-derived only. Hand-coded legislative and regulatory events, with a codebook and double coding, were not produced.
8. **Event studies.** Elections recur, so event windows overlap and the TWFE reference category mixes k = −4 with out-of-window quarters. The stacked design addresses contamination at a heavy cost in precision.
9. **Leader change** comes from V-Dem end-of-year snapshots and misses short-lived intra-year changes.
10. **External validity.** Results are for 2015–2025; the period-specific global financial cycle may matter.

## 18. Conclusion

In 2015–2025 the pre-registered tests find no evidence that the two-quarter pre-election window changes gross capital inflows or outflows across 108 economies. They also find no evidence that institutions, development level or asset class reliably condition that association. Election periods in this sample are better described by:
* **[Secondary]** a modest, directionally stable but fragile retrenchment of both gross inflows and outflows in the two quarters after elections, mainly in other investment;
* **[Post-hoc]** a sizeable, placebo-robust decline of gross inflows *in the election quarter itself* in emerging and developing economies, broadly in line with prior IMF evidence. That evidence's political-stability moderation does not replicate.

Elections matter for EMDE capital flows at the moment of the vote more than in the run-up. The institutional story behind that pattern remains unresolved. These are statements about association, and about scheduled election timing under stated assumptions. They do not rank countries or political systems.

## 19. References

All entries, with DOIs verified against Crossref on 2026-10-11, are in `literature/bibliography.csv`. Key references:

* Ahir, H., Bloom, N. & Furceri, D. (2022). The World Uncertainty Index. NBER WP 29763. https://doi.org/10.3386/w29763
* Alfaro, L., Kalemli-Ozcan, S. & Volosovych, V. (2008). Why doesn't capital flow from rich to poor countries? An empirical investigation. *Review of Economics and Statistics* 90(2). https://doi.org/10.1162/rest.90.2.347
* Arakelyan, M. & Evdokimova, T. (2025). Elections Matter: Capital Flows and Political Cycles. IMF WP/25/243.
* Avdjiev, S., Hardy, B., Kalemli-Özcan, Ş. & Servén, L. (2022). Gross capital flows by banks, corporates, and sovereigns. *JEEA*. https://doi.org/10.1093/jeea/jvac038
* Baker, S., Bloom, N. & Davis, S. (2016). Measuring economic policy uncertainty. *QJE*. https://doi.org/10.1093/qje/qjw024
* Barrett, P. et al. (2022). Measuring social unrest using media reports. *JDE* 158. https://doi.org/10.1016/j.jdeveco.2022.102924
* Brender, A. & Drazen, A. (2005). Political budget cycles in new versus established democracies. *JME*. https://doi.org/10.1016/j.jmoneco.2005.04.004
* Broner, F., Didier, T., Erce, A. & Schmukler, S. (2013). Gross capital flows: Dynamics and crises. *JME*. https://doi.org/10.1016/j.jmoneco.2012.12.004
* Busse, M. & Hefeker, C. (2007). Political risk, institutions and foreign direct investment. *EJPE*. https://doi.org/10.1016/j.ejpoleco.2006.02.003
* Caldara, D. & Iacoviello, M. (2022). Measuring geopolitical risk. *AER* 112(4). https://doi.org/10.1257/aer.20191823
* Callaway, B. & Sant'Anna, P. (2021). Difference-in-differences with multiple time periods. *J. Econometrics*. https://doi.org/10.1016/j.jeconom.2020.12.001
* Cameron, A.C., Gelbach, J. & Miller, D. (2008). Bootstrap-based improvements for inference with clustered errors. *REStat*. https://doi.org/10.1162/rest.90.3.414
* Canes-Wrone, B. & Park, J.-K. (2012). Electoral business cycles in OECD countries. *APSR*. https://doi.org/10.1017/s0003055411000529
* Cengiz, D., Dube, A., Lindner, A. & Zipperer, B. (2019). The effect of minimum wages on low-wage jobs. *QJE*. https://doi.org/10.1093/qje/qjz014
* Cerutti, E., Claessens, S. & Puy, D. (2019). Push factors and capital flows to emerging markets. *JIE*. https://doi.org/10.1016/j.jinteco.2019.04.006
* Chinn, M. & Ito, H. (2006). What matters for financial development? *JDE*. https://doi.org/10.1016/j.jdeveco.2005.05.010
* de Chaisemartin, C. & D'Haultfœuille, X. (2020). Two-way fixed effects estimators with heterogeneous treatment effects. *AER*. https://doi.org/10.1257/aer.20181169
* Driscoll, J. & Kraay, A. (1998). Consistent covariance matrix estimation with spatially dependent panel data. *REStat*. https://doi.org/10.1162/003465398557825
* Eichengreen, B., Gupta, P. & Masetti, O. (2018). Are capital flows fickle? *Asian Economic Papers*. https://doi.org/10.1162/asep_a_00583
* Fernández, A. et al. (2016). Capital control measures: A new dataset. *IMF Economic Review*. https://doi.org/10.1057/imfer.2016.11
* Forbes, K., Fratzscher, M. & Straub, R. (2015). Capital-flow management measures: What are they good for? *JIE*. https://doi.org/10.1016/j.jinteco.2014.11.004
* Forbes, K. & Warnock, F. (2012). Capital flow waves. *JIE*. https://doi.org/10.1016/j.jinteco.2012.03.006
* Fratzscher, M. (2012). Capital flows, push versus pull factors and the global financial crisis. *JIE* 88. https://doi.org/10.1016/j.jinteco.2012.05.003
* Ghosh, A., Qureshi, M., Kim, J. & Zalduendo, J. (2014). Surges. *JIE*. https://doi.org/10.1016/j.jinteco.2013.12.007
* Goodman-Bacon, A. (2021). Difference-in-differences with variation in treatment timing. *J. Econometrics*. https://doi.org/10.1016/j.jeconom.2021.03.014
* Jensen, N. (2003). Democratic governance and multinational corporations. *International Organization*. https://doi.org/10.1017/s0020818303573040
* Julio, B. & Yook, Y. (2012). Political uncertainty and corporate investment cycles. *Journal of Finance* 67(1). https://doi.org/10.1111/j.1540-6261.2011.01707.x
* Julio, B. & Yook, Y. (2016). Policy uncertainty, irreversibility, and cross-border flows of capital. *JIE* 103. https://doi.org/10.1016/j.jinteco.2016.08.004
* Kaufmann, D., Kraay, A. & Mastruzzi, M. (2011). The Worldwide Governance Indicators: Methodology and analytical issues. *Hague J. Rule of Law*. https://doi.org/10.1017/s1876404511200046
* Kelly, B., Pástor, Ľ. & Veronesi, P. (2016). The price of political uncertainty. *Journal of Finance*. https://doi.org/10.1111/jofi.12406
* Koepke, R. (2019). What drives capital flows to emerging markets? *J. Economic Surveys*. https://doi.org/10.1111/joes.12273
* Koepke, R. & Paetzold, S. (2024). Capital flow data — A guide for empirical analysis and real-time tracking. *IJFE* 29(1). https://doi.org/10.1002/ijfe.2687
* Li, Q. & Resnick, A. (2003). Reversal of fortunes. *International Organization*. https://doi.org/10.1017/s0020818303571077
* Miranda-Agrippino, S. & Rey, H. (2020). U.S. monetary policy and the global financial cycle. *REStud*. https://doi.org/10.1093/restud/rdaa019
* Mundlak, Y. (1978). On the pooling of time series and cross section data. *Econometrica*. https://doi.org/10.2307/1913646
* Papaioannou, E. (2009). What drives international financial flows? *JDE*. https://doi.org/10.1016/j.jdeveco.2008.04.001
* Pástor, Ľ. & Veronesi, P. (2013). Political uncertainty and risk premia. *JFE*. https://doi.org/10.1016/j.jfineco.2013.08.007
* Rey, H. (2015). Dilemma not trilemma. NBER WP 21162 (Jackson Hole, 2013). https://doi.org/10.3386/w21162
* Roodman, D. et al. (2019). Fast and wild: Bootstrap inference in Stata using boottest. *Stata Journal*. https://doi.org/10.1177/1536867x19830877
* Sun, L. & Abraham, S. (2021). Estimating dynamic treatment effects in event studies with heterogeneous treatment effects. *J. Econometrics*. https://doi.org/10.1016/j.jeconom.2020.09.006

Datasets: IMF BOP; IMF WEO; World Bank WDI and WGI (2026 release); V-Dem v16; International IDEA Voter Turnout Database; Wikipedia national electoral calendars (CC BY-SA); WUI; GPR; IMF RSUI; Chinn–Ito KAOPEN; BIS policy rates; FRED. Full details in `data/processed/source_register.csv`.

## 20. Appendix

* **A. Data definitions:** `config/variable_dictionary.csv`; `data/processed/data_quality_report.csv`; `country_metadata.csv`; `political_events.csv`; `policy_events.csv`.
* **B. Model specifications:** `results/logs/model_specs.json`; protocol §7.
* **C. All estimates:** `results/tables/all_estimates.csv` (166 rows, every coefficient with SE, CI, N, countries, covariance type).
* **D. Diagnostics:** `results/diagnostics/` (BPM6 identity residuals, AE membership check); `robustness_loo_placebo.csv`; `posthoc_placebo_k0.csv`; `posthoc_seasonality_check.csv`.
* **E. Figures 1–10:** `results/figures/` (PDF, SVG and PNG, with source data in `results/figures/data/`).
