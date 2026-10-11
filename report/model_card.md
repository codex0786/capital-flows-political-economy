# Model card — Capital in Motion country tool

*Generated 2026-10-11 from the evaluation outputs. Commit `115f5b1`.*

## Intended use
Analytical support for economists monitoring capital-flow conditions in 108 economies: explaining past flows, giving a
four-quarter outlook with uncertainty, and flagging downside and sudden-stop risk. **Not** for automated decisions,
market trading, or public ranking of countries. Country-level risk numbers can be market-sensitive and should be
shared only with appropriate access controls.

## Models
| Component | Method | Data | Code |
|---|---|---|---|
| Driver attribution ("why") | Fixed-effects regression by country group; global push factors with country loadings shrunk to the group; previous-year fundamentals including terms of trade, real exchange rate and rate gap | 2015Q1–2025Q4, IMF BOP/WEO/CTOT/EER, FRED, World Bank | `src/forecast/country_model.py` |
| Point outlook | Backtest-weighted blend of driver model, last-4-quarter average and 2015–25 average (+ election effect where it helped) | as above | same |
| Flows at risk | Location-scale quantile regression blended with country history; tails recalibrated from earlier forecast errors | as above | `src/forecast/risk.py` |
| Sudden-stop probability | Logit (episode starts in next 4 quarters), blended with base rate; two definitions (gross, net) | as above | same |
| Early-warning score | Signals approach, thresholds minimising noise-to-signal on 2017–21 | as above | `src/forecast/early_warning.py` |
| Buffer tests | Reserves vs net financing gap at the 5th percentile of net inflows; plus Greenspan–Guidotti and gross-stress tests | WDI, WEO | `src/forecast/vulnerability.py` |

## Out-of-sample performance

### Point outlook, real-time rolling test (forecasts for 2020–2025; RMSE, pp of GDP annualised)
| Flow | Group | Blend | Driver model | Long-run average | Last 4 quarters |
|---|---|---|---|---|---|
| gross_in | EMDE | 9.21 | 9.73 | 9.88 | 9.53 |
| gross_in | AE | 19.54 | 20.18 | 19.63 | 20.66 |
| gross_out | EMDE | 9.87 | 11.04 | 11.20 | 9.84 |
| gross_out | AE | 20.15 | 21.18 | 19.93 | 21.49 |
| net | EMDE | 7.84 | 8.07 | 8.25 | 8.03 |
| net | AE | 7.59 | 8.15 | 7.68 | 7.91 |

### Flows at risk, held-out test (methods selected on 2019Q4–2022Q4 origins, tested on 2023Q1–2024Q4)
Share of outcomes below the 5th and 95th percentiles (nominal 5% and 95%), with 90% bootstrap interval.
| Target | Method | Below 5th pct [90% CI] | Below 95th pct | 5th-pct loss |
|---|---|---|---|---|
| gross_in | history | 9.2% [0.071, 0.114] | 92.7% | 0.574 |
| gross_in | blend | 7.6% [0.057, 0.092] | 94.1% | 0.545 |
| gross_in | blend_cal | 3.0% [0.02, 0.039] | 98.7% | 0.586 |
| net | history | 14.1% [0.113, 0.163] | 94.2% | 0.472 |
| net | blend | 12.0% [0.095, 0.143] | 95.3% | 0.425 |
| net | blend_cal | 1.2% [0.006, 0.019] | 98.7% | 0.480 |

Live method: gross inflows `blend_cal`, net flows `blend_cal`.

### Sudden-stop starts, held-out test
| Definition | Method | AUC | Brier | Episodes |
|---|---|---|---|---|
| fw_gross | base | 0.500 | 0.0700 | 61 |
| fw_gross | logit | 0.811 | 0.0647 | 61 |
| fw_gross | blend | 0.809 | 0.0637 | 61 |
| fw_gross | logit_contagion | 0.810 | 0.0650 | 61 |
| fw_net | base | 0.500 | 0.1092 | 103 |
| fw_net | logit | 0.682 | 0.1049 | 103 |
| fw_net | blend | 0.676 | 0.1037 | 103 |
| fw_net | logit_contagion | 0.677 | 0.1061 | 103 |

Live method: gross `blend_contagion`, net `blend`.

### Early-warning score (test 2022–24)
* Gross definition: AUC 0.619, vs 0.431 for a count of rule-of-thumb flags.
* Net definition: AUC 0.57, vs 0.536.

## Known limitations and failure cases
* **The driver model explains little.** Within-country R² is under 10%. For advanced-economy gross flows, nothing reliably beats the country's long-run average.
* **Tail calibration depends on the regime.**
  * Tuned on turbulent 2019–22, the tails were too wide in calm 2023–24 (gross 3.0%, net 1.2% of outcomes below the 5th percentile).
  * Without calibration, net-flow tails were too narrow.
  * Expect conservative ranges in calm periods.
* **Sudden-stop probabilities rank risk better than they measure it.** The gross-definition model ranked poorly in 2019–22 (AUC 0.63) but well in 2023–24 (0.81).
* **Regional contagion did not improve prediction** in the held-out test.
* **Rule-of-thumb thresholds did not predict sudden stops** in this sample (AUC below 0.55). The data-driven score is only moderately better.
* **Data gaps and freshness:**
  * The real-exchange-rate driver covers 57% of observations and the rate gap 49%; gaps are filled with each country's average.
  * Upcoming election dates are from Wikipedia calendars, not yet corroborated.
  * The forecast quarter in progress is not observed.
* **Not covered:** policy responses (FX intervention, capital-flow measures), crises/defaults/sanctions, market prices.

## Change control
Every live forecast is stored in `results/forecast_ledger/ledger.csv`. Method-selection changes are logged in `report/protocol_changelog.md`.
