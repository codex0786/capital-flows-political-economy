"""Assemble results/prototype/index.html from the template and bundle.json."""
from src.common import RESULTS, ROOT


def main():
    tpl = (ROOT / "src" / "prototype" / "app_template.html").read_text()
    bundle = (RESULTS / "prototype" / "bundle.json").read_text().replace("</", "<\\/")
    out = RESULTS / "prototype" / "index.html"
    ca = (RESULTS / "prototype" / "country_analysis.json").read_text().replace("</", "<\\/")
    import json
    import pandas as pd
    P = RESULTS / "prototype"
    risk = json.loads((P / "risk.json").read_text())
    vul = json.loads((P / "vulnerability.json").read_text())
    rp = pd.read_csv(RESULTS / "tables" / "rolling_point_summary.csv")
    spec = json.loads((ROOT / "report" / "preregistration_2026_spec.json").read_text())
    eh = pd.read_csv(RESULTS / "tables" / "election_heterogeneity.csv")
    rb = {"risk": risk, "vul": vul, "rolling_point": json.loads(rp.to_json(orient="records")), "prereg": spec,
          "election_het": json.loads(eh.to_json(orient="records"))}
    rbs = json.dumps(rb, separators=(",", ":")).replace("</", "<\\/")
    # v3: crises/events, policy levers and market prices
    import numpy as np
    meta = pd.read_csv(ROOT / "data" / "processed" / "country_metadata.csv")
    sample = set(meta[meta.in_quarterly_sample].iso3)
    E = pd.read_csv(ROOT / "data" / "processed" / "crisis_events.csv")
    E = E[E.iso3.isin(sample)]
    ev = {iso: json.loads(g[["event_type", "start", "end", "start_year", "end_year", "detail", "source", "rule", "verification", "notes"]]
                          .fillna("").to_json(orient="records")) for iso, g in E.groupby("iso3")}
    P = pd.read_parquet(ROOT / "data" / "processed" / "policy_quarterly.parquet")
    P = P[P.iso3.isin(sample) & (P.quarter >= "2014Q1")].sort_values(["iso3", "quarter"])
    rnd = lambda v: None if pd.isna(v) else round(float(v), 3)
    pol = {iso: {"q": g.quarter.tolist(), "ccr_in": [rnd(v) for v in g.ccr_in], "ccr_out": [rnd(v) for v in g.ccr_out],
                 "fxi": [rnd(v) for v in g.fxi_gdp], "rate": [rnd(v) for v in g.policy_rate],
                 "rate_src": g.policy_rate_source.dropna().iloc[-1] if g.policy_rate_source.notna().any() else None}
           for iso, g in P.groupby("iso3")}
    M = pd.read_parquet(ROOT / "data" / "processed" / "market_monthly.parquet")
    M = M[M.iso3.isin(sample) & (M.month >= "2014-01")].sort_values(["iso3", "month"])
    mk = {}
    for iso, g in M.groupby("iso3"):
        base = g.fx.dropna()
        b0 = base.iloc[0] if len(base) else None
        mk[iso] = {"m": g.month.tolist(), "fx_idx": [None if (pd.isna(v) or not b0) else round(100 * v / b0, 2) for v in g.fx],
                   "fx": [rnd(v) for v in g.fx], "yld": [rnd(v) for v in g.yld], "spread": [rnd(v) for v in g.spread_us],
                   "yld_src": g.yld_source.dropna().iloc[-1] if g.yld_source.notna().any() else None,
                   "dep3m": rnd(100 * (g.fx.dropna().iloc[-1] / g.fx.dropna().iloc[-4] - 1)) if g.fx.notna().sum() > 4 else None,
                   "dyld3m": rnd(g.yld.dropna().iloc[-1] - g.yld.dropna().iloc[-4]) if g.yld.notna().sum() > 4 else None,
                   "last": g.dropna(subset=["fx"]).month.iloc[-1] if g.fx.notna().any() else None}
    T = RESULTS / "tables"
    att = pd.read_csv(T / "event_attribution.csv")
    evb = {"events": ev, "policy": pol, "markets": mk,
           "attribution": json.loads(att.to_json(orient="records")), "attribution_summary": json.loads((T / "event_attribution_summary.json").read_text()),
           "policy_assoc": json.loads(pd.read_csv(T / "policy_lever_associations.csv").to_json(orient="records")),
           "mkt_monthly": json.loads((T / "market_elections_monthly.json").read_text()),
           "mkt_daily": json.loads((T / "market_elections_daily.json").read_text())}
    evs = json.dumps(evb, separators=(",", ":"), default=lambda o: None).replace("</", "<\\/")
    out.write_text(tpl.replace("__BUNDLE__", bundle).replace("__CABUNDLE__", ca).replace("__RISKBUNDLE__", rbs).replace("__EVBUNDLE__", evs))
    print(out, round(out.stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
