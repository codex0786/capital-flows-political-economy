"""Forecast ledger and model card.

Ledger: every live forecast is appended to results/forecast_ledger/ledger.csv with the date it was made,
the data it used, the git commit and the method chosen, so it can be scored against outcomes later
without hindsight. Appending is idempotent per (made_on, commit): re-running the same build does not
duplicate rows; a new build after code or data changes adds a new vintage. Never edit past rows.

Model card: report/model_card.md, generated from the evaluation outputs.
"""
from __future__ import annotations

import json
import subprocess
from datetime import date

import pandas as pd

from src.common import RESULTS, ROOT, TABLES

MADE_ON = "2026-10-11"   # data retrieval date for this build
LEDGER = RESULTS / "forecast_ledger" / "ledger.csv"


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def ledger():
    P = RESULTS / "prototype"
    ca = json.loads((P / "country_analysis.json").read_text())
    risk = json.loads((P / "risk.json").read_text())
    vul = json.loads((P / "vulnerability.json").read_text())
    sha = commit()
    rows = []
    for iso, c in ca["countries"].items():
        for k in ("gross_in", "gross_out", "net"):
            d = c.get(k)
            if not d:
                continue
            last = [q for q, v in zip(d["quarters"], d["actual"]) if v is not None][-1]
            for f in d["forecast"]:
                rows.append({"made_on": MADE_ON, "commit": sha, "iso3": iso, "kind": "point", "target": k,
                             "data_through": last, "period": f["quarter"], "value": f["mean"], "lo80": f["lo80"], "hi80": f["hi80"],
                             "method": f"blend model={d['weights']['model']} last4={d['weights']['last4']} mean={d['weights']['mean']}"
                                       f" elec={d['weights'].get('election_overlay', 0)}"})
    for iso, r in risk["countries"].items():
        for k in ("gross_in", "net"):
            if k in r:
                for q, v in r[k]["quantiles"].items():
                    rows.append({"made_on": MADE_ON, "commit": sha, "iso3": iso, "kind": f"far_{q}", "target": f"{k}_avg_next4",
                                 "data_through": r["origin"], "period": r["horizon"], "value": v, "lo80": None, "hi80": None,
                                 "method": risk["selection"]["far_live"][k]})
        for d_, p in r.get("p_stop", {}).items():
            rows.append({"made_on": MADE_ON, "commit": sha, "iso3": iso, "kind": "p_stop_start", "target": d_,
                         "data_through": r.get("origin"), "period": r.get("horizon"), "value": p, "lo80": None, "hi80": None,
                         "method": risk["selection"]["stop_live"][d_]})
    for iso, v in vul["countries"].items():
        if v.get("early_warning") and v["early_warning"]["score"] is not None:
            rows.append({"made_on": MADE_ON, "commit": sha, "iso3": iso, "kind": "early_warning_score", "target": "fw_net",
                         "data_through": v["early_warning"]["as_of"], "period": "next 4 quarters", "value": v["early_warning"]["score"],
                         "lo80": None, "hi80": None, "method": "signals approach, 1/NSR weights"})
    new = pd.DataFrame(rows)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if LEDGER.exists():
        old = pd.read_csv(LEDGER, dtype=str)
        if ((old.made_on == MADE_ON) & (old.commit == sha)).any():
            return old, 0
        out = pd.concat([old, new.astype(str)], ignore_index=True)
    else:
        out = new
    out.to_csv(LEDGER, index=False)
    return out, len(new)


def model_card():
    rp = pd.read_csv(TABLES / "rolling_point_summary.csv")
    far = pd.read_csv(TABLES / "far_rolling_summary.csv")
    st = pd.read_csv(TABLES / "stop_rolling_summary.csv")
    risk = json.loads((RESULTS / "prototype" / "risk.json").read_text())
    ew = json.loads((RESULTS / "prototype" / "early_warning.json").read_text())
    def rp_row(o, g):
        r = rp[(rp.outcome == o) & (rp.group == g) & (rp.origin == "all")].iloc[0]
        return f"| {o} | {g} | {r.rmse_blend_rt:.2f} | {r.rmse_model:.2f} | {r.rmse_mean:.2f} | {r.rmse_last4:.2f} |"
    def far_row(k, m):
        r = far[(far.target == k) & (far.method == m) & (far.window == "test") & (far.group == "all")].iloc[0]
        return f"| {k} | {m} | {r.cover_q05:.1%} {r.cover_q05_ci90} | {r.cover_q95:.1%} | {r.pinball_q05:.3f} |"
    def st_row(d, m):
        r = st[(st["def"] == d) & (st.method == m) & (st.window == "test")].iloc[0]
        return f"| {d} | {m} | {r.auc:.3f} | {r.brier:.4f} | {int(r.events)} |"
    sel = risk["selection"]
    md = f"""# Model card — Capital in Motion country tool

*Generated {MADE_ON} from the evaluation outputs. Commit `{commit()}`.*

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
{chr(10).join(rp_row(o, g) for o in ("gross_in", "gross_out", "net") for g in ("EMDE", "AE"))}

### Flows at risk, held-out test (methods selected on 2019Q4–2022Q4 origins, tested on 2023Q1–2024Q4)
Share of outcomes below the 5th and 95th percentiles (nominal 5% and 95%), with 90% bootstrap interval.
| Target | Method | Below 5th pct [90% CI] | Below 95th pct | 5th-pct loss |
|---|---|---|---|---|
{chr(10).join(far_row(k, m) for k in ("gross_in", "net") for m in ("history", "blend", "blend_cal", "blend_market", "blend_market_cal"))}

Live method: gross inflows `{sel['far_live']['gross_in']}`, net flows `{sel['far_live']['net']}`.

### Sudden-stop starts, held-out test
| Definition | Method | AUC | Brier | Episodes |
|---|---|---|---|---|
{chr(10).join(st_row(d, m) for d in ("fw_gross", "fw_net") for m in ("base", "logit", "blend", "logit_contagion", "logit_market"))}

Live method: gross `{sel['stop_live']['fw_gross']}`, net `{sel['stop_live']['fw_net']}`.

### Early-warning score (test 2022–24)
* Gross definition: AUC {ew['definitions']['fw_gross']['evaluation']['auc_score']}, vs {ew['definitions']['fw_gross']['evaluation']['auc_rule_of_thumb_count']} for a count of rule-of-thumb flags.
* Net definition: AUC {ew['definitions']['fw_net']['evaluation']['auc_score']}, vs {ew['definitions']['fw_net']['evaluation']['auc_rule_of_thumb_count']}.

## Known limitations and failure cases
* **The driver model explains little.** Within-country R² is under 10%. For advanced-economy gross flows, nothing reliably beats the country's long-run average.
* **Tail calibration depends on the regime.**
  * Tuned on turbulent 2019–22, the tails were too wide in calm 2023–24 (gross 3.0%, net 1.2% of outcomes below the 5th percentile).
  * Without calibration, net-flow tails were too narrow.
  * Expect conservative ranges in calm periods.
* **Sudden-stop probabilities rank risk better than they measure it.** The gross-definition model ranked poorly in 2019–22 (AUC 0.63) but well in 2023–24 (0.81).
* **Regional contagion and market signals did not improve prediction** in the held-out test. Market signals are 3-month currency depreciation and yield change; yields exist for only 39% of country-months.
* **Rule-of-thumb thresholds did not predict sudden stops** in this sample (AUC below 0.55). The data-driven score is only moderately better.
* **Data gaps and freshness:**
  * The real-exchange-rate driver covers 57% of observations and the rate gap 49%; gaps are filled with each country's average.
  * Upcoming election dates are from Wikipedia calendars, not yet corroborated.
  * The forecast quarter in progress is not observed.
* **Crises, policy and markets (added v3) are context, not model inputs** (apart from the market-signal variants above).
  * Named crises do not explain most model surprises (21% of the largest 10% of surprises fall in crisis years vs 23% of all years).
  * Policy-lever associations reflect policy reacting to flows (reverse causality); they are not policy effects.
  * Bond spreads are local-currency yields minus US Treasuries, not EMBI credit spreads; daily FX covers 12 currencies.
* **Not covered:** macroprudential measures (iMaPP), IMF programme conditionality (MONA), sanctions, credit ratings and EMBI spreads. IMF financing is a proxy from IMF credit outstanding.

## Change control
Every live forecast is stored in `results/forecast_ledger/ledger.csv`. Method-selection changes are logged in `report/protocol_changelog.md`.
"""
    (ROOT / "report" / "model_card.md").write_text(md)


if __name__ == "__main__":
    out, n = ledger()
    model_card()
    print("ledger rows added:", n, "total:", len(out))
