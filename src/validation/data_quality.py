"""Pre-estimation data audit. Writes data/processed/data_quality_report.csv and diagnostics.

Checks
------
1. Panel-key uniqueness and date coverage.
2. BPM6 accounting identity: FA balance (net lending) =
       (gross outflows - gross inflows) + financial derivatives (net) + reserve assets.
   Residuals are reported as % of GDP; large residuals indicate component gaps or revisions.
3. Variable-level coverage and missingness (main sample 2015-2025), by country group.
4. Outlier flags: |robust z| > 5 using median/MAD within variable (pooled), reported not removed.
5. Election-source triangulation summary.
6. Advanced-economy membership check against the WEO ADVEC aggregate.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.common import DIAGNOSTICS, INTERIM, PROCESSED, RAW, get_logger, load_config
from src.features.build_panels import ADVANCED_IMF_CURRENT

log = get_logger("validation")
CFG = load_config()


def identity_check(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    d = df.copy()
    implied = (d.gross_out_usd - d.gross_in_usd) + d.deriv_net_usd.fillna(0) + d.reserves_flow_usd
    d["identity_resid_usd"] = d.fa_balance_usd - implied
    scale = d.gdp_usd / (4 if freq == "Q" else 1)
    d["identity_resid_pct_gdp"] = 100 * d.identity_resid_usd / scale
    return d


def robust_outliers(s: pd.Series, z: float = 5.0) -> pd.Series:
    med = s.median()
    mad = (s - med).abs().median() * 1.4826
    return ((s - med).abs() / mad > z) if mad and mad > 0 else pd.Series(False, index=s.index)


def run() -> pd.DataFrame:
    DIAGNOSTICS.mkdir(parents=True, exist_ok=True)
    s = CFG["sample"]
    A = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")
    rows = []

    for name, df, key in (("annual", A, "year"), ("quarterly", Q, "quarter")):
        rows.append({"check": "unique_keys", "dataset": name, "variable": f"iso3+{key}",
                     "value": int(not df.duplicated(["iso3", key]).any()), "detail": f"n={len(df)}"})
        main = df[df.year.between(s["main_start_year"], s["main_end_year"])]
        rows.append({"check": "coverage", "dataset": name, "variable": key,
                     "value": main.iso3.nunique(), "detail": f"{df[key].min()} to {df[key].max()}"})
        idc = identity_check(main, "Q" if name == "quarterly" else "A")
        r = idc.identity_resid_pct_gdp.dropna()
        rows.append({"check": "bpm6_identity_resid_abs_median_pct_gdp", "dataset": name, "variable": "fa_balance",
                     "value": round(float(r.abs().median()), 4),
                     "detail": f"share |resid|<0.5% GDP: {(r.abs() < 0.5).mean():.3f}; n={len(r)}"})
        idc[["iso3", key, "identity_resid_pct_gdp"]].to_csv(DIAGNOSTICS / f"bpm6_identity_{name}.csv", index=False)

        vars_ = [c for c in df.columns if c.endswith("_gdp") or c.startswith(("L_", "wgi_", "elec_", "wui", "rsui", "policy_rate", "gpr"))]
        for v in vars_:
            x = main[v]
            byg = main.groupby("country_group")[v].apply(lambda z: z.notna().mean()).round(3).to_dict()
            out = robust_outliers(x.dropna()) if x.notna().sum() > 10 and x.dtype.kind == "f" else pd.Series(dtype=bool)
            rows.append({"check": "missingness_share", "dataset": name, "variable": v,
                         "value": round(float(x.isna().mean()), 4),
                         "detail": f"nonmissing by group {byg}; countries with any data {main.loc[x.notna(), 'iso3'].nunique()}"})
            if len(out):
                sel = main.loc[out[out].index]
                flagged = (sel.iso3 + ":" + sel[key].astype(str)).tolist()
                rows.append({"check": "outliers_robust_z_gt5", "dataset": name, "variable": v,
                             "value": int(out.sum()), "detail": ", ".join(flagged[:15]) + (" ..." if len(flagged) > 15 else "")})

    pe = pd.read_csv(PROCESSED / "political_events.csv")
    el = pe[pe.event_type.str.startswith("election")]
    el = el[pd.to_datetime(el.event_date).dt.year.between(2015, 2026)]
    for k, v in el.verification_status.value_counts().items():
        rows.append({"check": "election_verification", "dataset": "political_events", "variable": k,
                     "value": int(v), "detail": "2015-2026 national contests"})
    conflicts = el.coding_notes.str.contains("DATE CONFLICT").sum()
    rows.append({"check": "election_date_conflicts_gt7d", "dataset": "political_events", "variable": "event_date",
                 "value": int(conflicts), "detail": "Wikipedia date kept; IDEA date preserved in coding_notes"})

    # AE membership check
    v = json.loads((RAW / "imf_weo" / "weo_NGDPD.json").read_text())["values"]["NGDPD"]
    chk = []
    for y in ["2015", "2019", "2024", "2025"]:
        tot = sum(v[a][y] for a in ADVANCED_IMF_CURRENT if y in v.get(a, {}))
        chk.append({"year": y, "sum_members_bn": round(tot, 3), "ADVEC_aggregate_bn": v["ADVEC"][y],
                    "difference_bn": round(v["ADVEC"][y] - tot, 3)})
    pd.DataFrame(chk).to_csv(DIAGNOSTICS / "ae_membership_check.csv", index=False)
    rows.append({"check": "ae_membership_matches_ADVEC", "dataset": "country_metadata", "variable": "country_group",
                 "value": int(all(abs(c["difference_bn"]) < 0.01 for c in chk)), "detail": str(chk)})

    rep = pd.DataFrame(rows)
    rep.to_csv(PROCESSED / "data_quality_report.csv", index=False)
    log.info("data quality report: %d rows", len(rep))
    return rep


if __name__ == "__main__":
    r = run()
    print(r[r.check.isin(["unique_keys", "coverage", "bpm6_identity_resid_abs_median_pct_gdp",
                          "election_verification", "election_date_conflicts_gt7d", "ae_membership_matches_ADVEC"])].to_string())
