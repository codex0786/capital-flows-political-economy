"""Export the data bundle for the interactive prototype (results/prototype/bundle.json).

Everything shown in the prototype is either taken from saved pipeline outputs or estimated
here with the same estimator (two-way within transformation + country-clustered SEs, the
estimator validated against linearmodels in tests/test_models.py). The model grid lets a
viewer switch outcome, sample, window scheme and fixed effects without running Python.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
from scipy import stats

from src.common import PROCESSED, RESULTS, TABLES
from src.econometrics.models import _cluster_t, twfe_demean
from src.econometrics.posthoc_alignment import event_windows, official_oi
from src.econometrics.run_analysis import CTRL, quarterly

OUT = RESULTS / "prototype"


def r(x, d=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), d)


def panel() -> pd.DataFrame:
    Q = quarterly().merge(official_oi(), on=["iso3", "quarter"], how="left")
    Q["private_inflows_gdp"] = 100 * 4 * (Q.gross_in_usd - Q.official_oi_usd) / Q.gdp_usd
    lo, hi = np.nanpercentile(Q.private_inflows_gdp.dropna(), [1, 99])
    Q["private_inflows_gdp_w"] = Q.private_inflows_gdp.clip(lo, hi)
    Q = event_windows(Q)
    meta = pd.read_csv(PROCESSED / "country_metadata.csv").set_index("iso3")
    Q["grp_alt"] = Q.iso3.map(meta.country_group_alt_pre_euro)
    Q["iso_season"] = Q.iso3 + "_" + Q.quarter.str[-1]
    return Q


OUTCOMES = {
    "gross_inflows_gdp_w": "Gross inflows",
    "gross_outflows_gdp_w": "Gross outflows",
    "net_flows_gdp_w": "Net flows",
    "private_inflows_gdp_w": "Private gross inflows",
    "fdi_in_gdp_w": "FDI inflows",
    "pe_in_gdp_w": "Portfolio equity inflows",
    "pd_in_gdp_w": "Portfolio debt inflows",
    "oi_in_gdp_w": "Other investment inflows",
}
SAMPLES = {
    "all": ("All economies", lambda q: q),
    "ae": ("Advanced economies", lambda q: q[q.grp_alt == "AE"]),
    "emde": ("Emerging & developing", lambda q: q[q.grp_alt == "EMDE"]),
    "nofc": ("Excluding financial centres", lambda q: q[q.financial_centre == 0]),
}
SCHEMES = {
    "prereg": ("Pre-registered windows", [("elec_exec_pre", "Election quarter + quarter before"),
                                          ("elec_exec_post", "Two quarters after")]),
    "imf": ("Election-quarter windows", [("eq_pre12", "1–2 quarters before"), ("eq_k0", "Election quarter"),
                                         ("eq_post12", "1–2 quarters after")]),
}
FES = {"cq": "Country + quarter", "csq": "Country × season + quarter"}


def estimate(df, y, terms, ent):
    d = df.dropna(subset=[y] + terms + CTRL).copy()
    d["_tid"] = d.quarter
    D = twfe_demean(d, [y] + terms + CTRL, ent=ent)
    X = D[terms + CTRL].to_numpy()
    g = d.iso3.astype("category").cat.codes.to_numpy()
    G = g.max() + 1
    out = []
    for k, t in enumerate(terms):
        b, se = _cluster_t(X, D[y].to_numpy(), g, k)
        crit = stats.t.ppf(0.975, G - 1)
        out.append({"term": t, "coef": r(b), "se": r(se), "lo": r(b - crit * se), "hi": r(b + crit * se),
                    "p": r(2 * stats.t.sf(abs(b / se), G - 1), 4)})
    within = (d[y] - d.groupby("iso3")[y].transform("mean")).std()
    return out, {"n": int(len(d)), "countries": int(d.iso3.nunique()), "within_sd": r(within, 2),
                 "mean": r(d[y].mean(), 2)}


def model_grid(Q):
    grid = []
    for y in OUTCOMES:
        for s, (_, f) in SAMPLES.items():
            for sch, (_, terms) in SCHEMES.items():
                for fe in FES:
                    est, info = estimate(f(Q), y, [t for t, _ in terms], "iso3" if fe == "cq" else "iso_season")
                    grid.append({"outcome": y, "sample": s, "scheme": sch, "fe": fe, "estimates": est, **info})
    return grid


def event_grid(Q):
    rows = []
    K, ref = 6, -4
    for y in ["gross_inflows_gdp_w", "gross_outflows_gdp_w", "private_inflows_gdp_w", "fdi_in_gdp_w", "oi_in_gdp_w"]:
        for s, (_, f) in SAMPLES.items():
            if s == "nofc":
                continue
            for et in ["event_time_exec", "event_time_exec_sched"]:
                d = f(Q).copy()
                names = []
                for k in range(-K, K + 1):
                    if k == ref:
                        continue
                    n = f"k{k}"
                    d[n] = (d[et] == k).astype(float)
                    names.append(n)
                est, info = estimate(d, y, names, "iso3")
                pts = [{"k": int(e["term"][1:]), "coef": e["coef"], "lo": e["lo"], "hi": e["hi"]} for e in est]
                pts.append({"k": ref, "coef": 0.0, "lo": 0.0, "hi": 0.0})
                rows.append({"outcome": y, "sample": s, "events": "scheduled" if et.endswith("sched") else "all",
                             "points": sorted(pts, key=lambda p: p["k"]), **info})
    return rows


def countries(Q):
    meta = pd.read_csv(PROCESSED / "country_metadata.csv")
    meta = meta[meta.in_quarterly_sample]
    A = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    el = pe[pe.event_type.str.startswith("election")]
    out = {}
    for m in meta.itertuples():
        q = A[(A.iso3 == m.iso3) & (A.year >= 2015)].sort_values("quarter")
        e = el[(el.iso3 == m.iso3) & (pd.to_datetime(el.event_date).dt.year >= 2015)].sort_values("event_date")
        out[m.iso3] = {
            "name": m.country_name, "group": m.country_group, "region": m.wb_region, "income": m.wb_income,
            "fc": int(m.financial_centre),
            "q": q.quarter.tolist(),
            "partial": q.partial_year.astype(int).tolist(),
            "in": [r(v, 2) for v in q.gross_inflows_gdp], "out": [r(v, 2) for v in q.gross_outflows_gdp],
            "net": [r(v, 2) for v in q.net_flows_gdp], "fdi": [r(v, 2) for v in q.fdi_in_gdp],
            "port": [r(v, 2) for v in q.port_in_gdp], "oi": [r(v, 2) for v in q.oi_in_gdp],
            "elections": [{"date": x.event_date, "type": x.event_type.replace("election_", ""),
                           "exec": None if pd.isna(x.exec_relevant) else int(x.exec_relevant),
                           "timing": x.scheduled_or_unexpected.replace("_rule_based", ""),
                           "verification": x.verification_status,
                           "turnover": None if pd.isna(x.exec_turnover_at_election) else int(x.exec_turnover_at_election)}
                          for x in e.itertuples()],
        }
    return out


def group_trends():
    A = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")
    A = A[A.year.between(2015, 2025)]
    rows = []
    for (g, y), d in A.groupby(["country_group", "year"]):
        row = {"group": g, "year": int(y)}
        for c, lab in (("fdi_in_usd", "fdi"), ("port_in_usd", "port"), ("oi_in_usd", "oi"),
                       ("gross_in_usd", "gross_in"), ("gross_out_usd", "gross_out")):
            dd = d.dropna(subset=[c])
            row[lab] = r(100 * dd[c].sum() / dd.gdp_usd.sum(), 2)
        rows.append(row)
    return rows


ANNUAL_VARS = {
    # key: (column, label, unit, kind)  kind: div = diverging around 0, seq = sequential
    "gross_in": ("gross_inflows_gdp", "Gross inflows", "% of GDP", "div"),
    "gross_out": ("gross_outflows_gdp", "Gross outflows", "% of GDP", "div"),
    "net": ("net_flows_gdp", "Net flows", "% of GDP", "div"),
    "fdi": ("fdi_in_gdp", "FDI inflows", "% of GDP", "div"),
    "port": ("port_in_gdp", "Portfolio inflows", "% of GDP", "div"),
    "oi": ("oi_in_gdp", "Other investment inflows", "% of GDP", "div"),
    "res": ("reserve_change_gdp", "Reserve accumulation", "% of GDP", "div"),
    "vol": ("q_vol", "Inflow volatility within year", "SD, pp of GDP", "seq"),
    "growth": ("gdp_growth", "Real GDP growth", "%", "div"),
    "infl": ("inflation", "Inflation", "%", "seq"),
    "debt": ("public_debt_gdp", "Public debt", "% of GDP", "seq"),
    "ca": ("ca_gdp", "Current account", "% of GDP", "div"),
    "rl": ("wgi_rl_est", "Rule of law (WGI)", "−2.5 to 2.5", "div"),
    "pv": ("wgi_pv_est", "Political stability (WGI)", "−2.5 to 2.5", "div"),
    "wui": ("wui", "World Uncertainty Index", "index", "seq"),
}


def annual_countries():
    """Country x year panel (annual sample, 2015-2025) for the heatmap and country profiles."""
    A = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")
    A = A[A.year.between(2015, 2025)].copy()
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")
    Q = Q[Q.year.between(2015, 2025)]
    qv = Q.groupby(["iso3", "year"]).agg(q_vol=("gross_inflows_gdp", "std"), stop_q=("sudden_stop", "sum"),
                                         stop_obs=("sudden_stop", "count")).reset_index()
    A = A.merge(qv, on=["iso3", "year"], how="left")
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    el = pe[pe.event_type.str.startswith("election") & pe.verification_status.isin(["wikipedia+idea+vdem", "two_sources"])].copy()
    el["year"] = pd.to_datetime(el.event_date).dt.year
    years = list(range(2015, 2026))
    out = {}
    for iso3, g in A.groupby("iso3"):
        g = g.set_index("year").reindex(years)
        e = el[el.iso3 == iso3]
        row = {"name": g.country_name.dropna().iloc[0], "group": g.country_group.dropna().iloc[0],
               "fc": int(g.financial_centre.dropna().iloc[0]), "v": {}}
        for k, (col, *_r) in ANNUAL_VARS.items():
            row["v"][k] = [r(x, 2) for x in g[col]]
        row["exec_el"] = [int(x) if pd.notna(x) else None for x in g.exec_election]
        row["early_el"] = [int(x) if pd.notna(x) else None for x in g.early_exec_election]
        row["exec_change"] = [int(x) if pd.notna(x) else None for x in g.exec_change]
        row["unrest"] = [int(x) if pd.notna(x) else None for x in g.rsui_event]
        row["stop_q"] = [int(x) if pd.notna(x) and pd.notna(o) and o > 0 else None for x, o in zip(g.stop_q, g.stop_obs)]
        row["elections"] = {int(y): "; ".join(f"{t.replace('election_', '')} {d}" for t, d in zip(ee.event_type, ee.event_date))
                            for y, ee in e.groupby("year") if 2015 <= y <= 2025}
        # descriptive election-year contrast for gross inflows (not causal; few years per country)
        gi = g.gross_inflows_gdp
        ey = g.exec_election == 1
        row["el_contrast"] = {"election_mean": r(gi[ey].mean(), 2), "other_mean": r(gi[~ey].mean(), 2),
                              "n_el_years": int(ey.sum()), "n_other": int((~ey & gi.notna()).sum())}
        out[iso3] = row
    return {"years": years, "vars": {k: {"label": v[1], "unit": v[2], "kind": v[3]} for k, v in ANNUAL_VARS.items()},
            "countries": out}


def saved_results():
    M = pd.read_csv(TABLES / "multiple_testing.csv")
    R = pd.read_csv(TABLES / "robustness_matrix.csv")
    lp = pd.read_csv(TABLES / "robustness_loo_placebo_summary.csv")
    pk = pd.read_csv(TABLES / "posthoc_placebo_k0.csv")
    me = pd.read_csv(TABLES / "h2_marginal_effects.csv")
    s = json.loads((TABLES / "sample_summary.json").read_text())
    clean = lambda df: json.loads(df.to_json(orient="records", double_precision=4))
    return {"multiple_testing": clean(M), "robustness": clean(R), "loo_placebo": clean(lp),
            "posthoc_placebo": clean(pk), "marginal_effects": clean(me), "sample": s}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    Q = panel()
    bundle = {
        "generated": "2026-10-11",
        "labels": {"outcomes": OUTCOMES, "samples": {k: v[0] for k, v in SAMPLES.items()},
                   "schemes": {k: {"label": v[0], "terms": dict(v[1])} for k, v in SCHEMES.items()}, "fe": FES},
        "models": model_grid(Q),
        "events": event_grid(Q),
        "countries": countries(Q),
        "trends": group_trends(),
        "annual": annual_countries(),
        "saved": saved_results(),
    }
    (OUT / "bundle.json").write_text(json.dumps(bundle, separators=(",", ":")))
    print("models", len(bundle["models"]), "events", len(bundle["events"]), "countries", len(bundle["countries"]),
          "size KB", round((OUT / "bundle.json").stat().st_size / 1024))


if __name__ == "__main__":
    main()
