"""Descriptive tables and report-ready summaries (Markdown + CSV) from saved outputs.

Everything quoted in report/final_report.md is generated here or read from results/tables,
so numbers in the text can be regenerated from the pipeline.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.common import PROCESSED, TABLES


def fmt(x, d=2):
    return "" if pd.isna(x) else f"{x:.{d}f}"


def table1_descriptives():
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")
    Q = Q[Q.year.between(2015, 2025)]
    vars_ = {"gross_inflows_gdp_w": "Gross inflows (% GDP, ann.)", "gross_outflows_gdp_w": "Gross outflows (% GDP, ann.)",
             "net_flows_gdp_w": "Net flows (% GDP, ann.)", "fdi_in_gdp_w": "FDI inflows", "pe_in_gdp_w": "Portfolio equity inflows",
             "pd_in_gdp_w": "Portfolio debt inflows", "oi_in_gdp_w": "Other investment inflows",
             "gross_inflows_vol8": "Inflow volatility (8-qtr SD)", "elec_exec_pre": "Pre-election window (0/1)",
             "elec_exec_post": "Post-election window (0/1)", "wui": "World Uncertainty Index", "vix": "VIX (quarterly mean)"}
    rows = []
    for v, lab in vars_.items():
        for g in ["AE", "EMDE", "All"]:
            s = Q[v] if g == "All" else Q.loc[Q.country_group == g, v]
            within = (Q[v] - Q.groupby("iso3")[v].transform("mean")) if g == "All" else \
                (Q.loc[Q.country_group == g, v] - Q[Q.country_group == g].groupby("iso3")[v].transform("mean"))
            rows.append({"variable": lab, "group": g, "N": int(s.notna().sum()), "mean": s.mean(), "median": s.median(),
                         "sd": s.std(), "within_sd": within.std(), "p10": s.quantile(.1), "p90": s.quantile(.9)})
    t = pd.DataFrame(rows)
    t.to_csv(TABLES / "table1_descriptives.csv", index=False)
    return t


def sample_summary():
    meta = pd.read_csv(PROCESSED / "country_metadata.csv")
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    el = pe[pe.event_type.str.startswith("election")].copy()
    el["year"] = pd.to_datetime(el.event_date).dt.year
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")
    qs = set(Q.iso3)
    e = el[el.iso3.isin(qs) & el.year.between(2015, 2025) & el.verification_status.isin(["wikipedia+idea+vdem", "two_sources"])]
    q26 = Q[Q.year == 2026].groupby("iso3").quarter.max()
    s = {
        "candidates": len(meta), "annual_sample": int(meta.in_annual_sample.sum()), "quarterly_sample": int(meta.in_quarterly_sample.sum()),
        "annual_AE": int(((meta.in_annual_sample) & (meta.country_group == "AE")).sum()),
        "annual_EMDE": int(((meta.in_annual_sample) & (meta.country_group == "EMDE")).sum()),
        "quarterly_AE": int(((meta.in_quarterly_sample) & (meta.country_group == "AE")).sum()),
        "quarterly_EMDE": int(((meta.in_quarterly_sample) & (meta.country_group == "EMDE")).sum()),
        "exclusion_reasons": meta.loc[~meta.in_annual_sample, "exclusion_reason"].str.split("; ").explode()
            .str.replace(r"\d+/11", "n/11", regex=True).value_counts().to_dict(),
        "elections_2015_2025_quarterly_sample_corroborated": len(e),
        "exec_relevant": int((e.exec_relevant == 1).sum()),
        "exec_relevant_scheduled": int(((e.exec_relevant == 1) & (e.scheduled_or_unexpected == "scheduled_rule_based")).sum()),
        "exec_relevant_early": int(((e.exec_relevant == 1) & (e.scheduled_or_unexpected == "early_rule_based")).sum()),
        "exec_turnover_share": float(e.loc[e.exec_relevant == 1, "exec_turnover_at_election"].mean()),
        "countries_with_2026_data": int(q26.shape[0]), "latest_2026_quarter_counts": q26.value_counts().to_dict(),
    }
    (TABLES / "sample_summary.json").write_text(json.dumps(s, indent=1, default=str))
    return s


def main_results_markdown():
    R = pd.read_csv(TABLES / "all_estimates.csv")
    M = pd.read_csv(TABLES / "multiple_testing.csv")
    lines = ["| Hypothesis | Outcome | Term | Coef. | SE (country) | 95% CI | p | WCB p | Holm p | N | Countries |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in M.itertuples():
        lines.append(f"| {r.hypothesis} | {r.outcome} | {r.term} ({r.spec}) | {fmt(r.coef)} | {fmt(r.se)} | [{fmt(r.ci_low)}, {fmt(r.ci_high)}] | "
                     f"{fmt(r.p, 3)} | {fmt(r.wcb_p, 3)} | {fmt(r.p_holm, 3)} | {r.nobs} | {r.n_countries} |")
    (TABLES / "table2_confirmatory.md").write_text("\n".join(lines))
    b = R[(R.spec == "baseline") & R.hypothesis.isin(["H1a", "H1b"])]
    lines = ["| Outcome | Term | Covariance | Coef. | SE | p |", "|---|---|---|---|---|---|"]
    for _, r in b.iterrows():
        lines.append(f"| {r['outcome']} | {r['term']} | {r['cov']} | {fmt(r['coef'])} | {fmt(r['se'])} | {fmt(r['p'], 3)} |")
    (TABLES / "table3_inference_comparison.md").write_text("\n".join(lines))


if __name__ == "__main__":
    t = table1_descriptives()
    print(t[t.group != "All"].round(2).to_string(index=False))
    print(json.dumps(sample_summary(), indent=1, default=str))
    main_results_markdown()
