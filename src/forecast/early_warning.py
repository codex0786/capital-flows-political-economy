"""Data-driven early-warning thresholds (signals approach) and a composite score.

For each indicator the direction of risk is fixed in advance from economics, then the threshold is
chosen on a training window to minimise the noise-to-signal ratio (Kaminsky, Lizondo & Reinhart 1998):
    NSR = (false alarms / calm quarters) / (signals before episodes / episode quarters)
subject to catching at least 20% of episodes. Indicators with NSR < 1 enter a composite score weighted
by 1/NSR. The score is evaluated out of sample (AUC) against the conventional rule-of-thumb flag count.

Target: a sudden-stop episode starting within the next four quarters (both definitions in risk.py).
Training: quarters 2017Q1-2021Q4. Test: 2022Q1-2024Q4 (targets end by 2025Q4).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.common import PROCESSED, RESULTS, TABLES
from src.forecast.risk import STOPDEFS, auc, build

IND = {
    # name: (column, risk direction, label, unit)
    "res_months": ("res_months", "low", "Reserves, months of imports", "months"),
    "st_debt_res": ("st_debt_res", "high", "Short-term external debt / reserves", "%"),
    "ext_debt": ("ext_debt", "high", "External debt", "% of GDP"),
    "ca": ("L_ca_gdp", "low", "Current-account balance", "% of GDP"),
    "pub_debt": ("L_public_debt_gdp", "high", "Public debt", "% of GDP"),
    "infl": ("L_inflation", "high", "Inflation", "%"),
    "surge": ("surge", "high", "Recent inflow surge (last 4 quarters vs country norm)", "SD"),
    "usd": ("d4_usd_z", "high", "US dollar, 1-year appreciation", "SD"),
}
RULES_OF_THUMB = {"res_months": ("low", 3.0), "st_debt_res": ("high", 100.0), "ext_debt": ("high", 60.0),
                  "ca": ("low", -4.0), "pub_debt": ("high", 70.0), "infl": ("high", 10.0)}
TRAIN = ("2017Q1", "2021Q4")
TEST = ("2022Q1", "2024Q4")


def panel():
    Q = build()
    A = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")[["iso3", "year", "st_debt_reserves", "ext_debt_gdp"]]
    A["year"] += 1                       # previous year's value, known during the year
    Q = Q.merge(A.rename(columns={"st_debt_reserves": "st_debt_res", "ext_debt_gdp": "ext_debt"}), on=["iso3", "year"], how="left")
    st = Q[(Q.quarter >= "2015Q1") & (Q.quarter <= "2025Q4")].groupby("iso3").y_gross_in.agg(["mean", "std"])
    Q = Q.merge(st, left_on="iso3", right_index=True, how="left")
    Q["surge"] = (Q.back4_gross_in - Q["mean"]) / Q["std"].clip(lower=0.5)
    return Q


def signal(x, thr, direction):
    return (x < thr) if direction == "low" else (x > thr)


def best_threshold(x, y, direction):
    d = pd.DataFrame({"x": x, "y": y}).dropna()
    if d.y.sum() < 10:
        return None
    best = None
    for q in np.arange(0.05, 0.96, 0.025):
        thr = float(d.x.quantile(q))
        s = signal(d.x, thr, direction)
        hit = (s & (d.y == 1)).sum() / max((d.y == 1).sum(), 1)
        fa = (s & (d.y == 0)).sum() / max((d.y == 0).sum(), 1)
        if hit < 0.2 or hit == 0:
            continue
        nsr = fa / hit
        if best is None or nsr < best["nsr"]:
            best = {"threshold": thr, "nsr": float(nsr), "hit_rate": float(hit), "false_alarm_rate": float(fa)}
    return best


def run():
    Q = panel()
    tr = Q[(Q.quarter >= TRAIN[0]) & (Q.quarter <= TRAIN[1])]
    te = Q[(Q.quarter >= TEST[0]) & (Q.quarter <= TEST[1])]
    out = {"definitions": {}, "train": f"{TRAIN[0]}–{TRAIN[1]}", "test": f"{TEST[0]}–{TEST[1]}"}
    for d in STOPDEFS:
        y = f"fwd_{d}"
        rows, weights = [], {}
        for k, (col, direction, label, unit) in IND.items():
            b = best_threshold(tr[col], tr[y], direction)
            row = {"indicator": k, "label": label, "unit": unit, "direction": direction}
            if b:
                row.update({x: round(v, 3) for x, v in b.items()})
                tsub = te[[col, y]].dropna()
                s = signal(tsub[col], b["threshold"], direction)
                row["test_hit_rate"] = round(float((s & (tsub[y] == 1)).sum() / max((tsub[y] == 1).sum(), 1)), 3)
                row["test_false_alarm_rate"] = round(float((s & (tsub[y] == 0)).sum() / max((tsub[y] == 0).sum(), 1)), 3)
                if b["nsr"] < 1:
                    weights[k] = 1 / b["nsr"]
            rt = RULES_OF_THUMB.get(k)
            row["rule_of_thumb"] = rt[1] if rt else None
            rows.append(row)
        thr = {r["indicator"]: r.get("threshold") for r in rows}

        def score(df):
            num = sum(w * signal(df[IND[k][0]], thr[k], IND[k][1]).astype(float).where(df[IND[k][0]].notna()) .fillna(0) for k, w in weights.items())
            den = sum(w * df[IND[k][0]].notna().astype(float) for k, w in weights.items())
            return num / den.replace(0, np.nan)

        def rot(df):
            return sum(signal(df[IND[k][0]], v, dirn).astype(float).where(df[IND[k][0]].notna()).fillna(0)
                       for k, (dirn, v) in RULES_OF_THUMB.items())
        tt = te.dropna(subset=[y]).copy()
        tt["ews"], tt["rot"] = score(tt), rot(tt)
        tt = tt.dropna(subset=["ews"])
        ev = {"test_quarters": int(len(tt)), "test_episodes": int(tt[y].sum()),
              "auc_score": round(float(auc(tt[y], tt.ews)), 3), "auc_rule_of_thumb_count": round(float(auc(tt[y], tt["rot"])), 3)}
        last = Q.dropna(subset=["vix_z"]).sort_values("qo").groupby("iso3").tail(1).copy()
        last["ews"] = score(last)
        countries = {}
        for _, r in last.iterrows():
            sig = {k: (None if pd.isna(r[IND[k][0]]) else bool(signal(pd.Series([r[IND[k][0]]]), thr[k], IND[k][1]).iloc[0]))
                   for k in IND if thr.get(k) is not None}
            countries[r.iso3] = {"score": None if pd.isna(r.ews) else round(float(r.ews), 3), "as_of": r.quarter,
                                 "signals": sig, "values": {k: (None if pd.isna(r[IND[k][0]]) else round(float(r[IND[k][0]]), 2)) for k in IND}}
        dist = pd.Series([c["score"] for c in countries.values() if c["score"] is not None])
        for c in countries.values():
            c["pctile"] = None if c["score"] is None else round(float((dist <= c["score"]).mean()), 3)
        out["definitions"][d] = {"indicators": rows, "weights": {k: round(v, 3) for k, v in weights.items()}, "evaluation": ev,
                                 "countries": countries}
        pd.DataFrame(rows).assign(definition=d).to_csv(TABLES / f"early_warning_thresholds_{d}.csv", index=False)
    (RESULTS / "prototype" / "early_warning.json").write_text(json.dumps(out, separators=(",", ":")))
    return out


if __name__ == "__main__":
    o = run()
    for d, v in o["definitions"].items():
        print("==", d, v["evaluation"], v["weights"])
        print(pd.DataFrame(v["indicators"])[["label", "direction", "threshold", "nsr", "hit_rate", "false_alarm_rate", "test_hit_rate", "test_false_alarm_rate", "rule_of_thumb"]].to_string(index=False))
