"""Analyses using the crisis/event database, policy levers and market prices (v3, EXPLORATORY).

1. event_attribution   Do named crises and events account for the driver model's large "unexplained" years?
2. policy_levers       Associations of capital-flow restrictions, FX intervention and policy-rate moves with flows
                       (policy responds to flows, so these are not causal effects).
3. market_elections    Exchange-rate and bond-yield behaviour around elections: monthly (all economies, TWFE event
                       study) and daily (12 currencies, cumulative abnormal depreciation vs the broad dollar).
None of these was pre-registered; they are reported as exploratory.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from src.common import PROCESSED, RAW, RESULTS, TABLES, get_logger
from src.econometrics.models import _cluster_t, twfe_demean
from src.econometrics.run_analysis import CTRL

log = get_logger("events_analysis")
EVENT_TYPES = ["banking_crisis", "sovereign_default_private", "currency_crisis", "imf_financing", "high_inflation",
               "capital_control_tightening", "capital_control_easing", "official_arrears", "other_private_arrears",
               "local_currency_default"]
LABEL = {"banking_crisis": "Systemic banking crisis", "sovereign_default_private": "Default to private creditors",
         "currency_crisis": "Currency crisis", "imf_financing": "Large IMF financing", "high_inflation": "Inflation above 40%",
         "capital_control_tightening": "Capital-flow restrictions tightened", "capital_control_easing": "Capital-flow restrictions eased",
         "official_arrears": "Arrears to official creditors", "other_private_arrears": "Arrears to other private creditors",
         "local_currency_default": "Local-currency debt default"}


def events():
    E = pd.read_csv(PROCESSED / "crisis_events.csv")
    return E


def country_year_events(E):
    rows = []
    for r in E.itertuples():
        for y in range(int(max(r.start_year, 2012)), int(r.end_year) + 1):
            rows.append({"iso3": r.iso3, "year": y, "event_type": r.event_type, "detail": r.detail,
                         "new": int(y == r.start_year)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------- 1
def event_attribution():
    ca = json.loads((RESULTS / "prototype" / "country_analysis.json").read_text())
    rows = []
    for iso, c in ca["countries"].items():
        for a in c["gross_in"]["annual"]:
            rows.append({"iso3": iso, "group": c["group"], "year": a["year"], "unexplained": a["Unexplained"],
                         "dev": a["actual"] - c["gross_in"]["mean"], "sigma": c["gross_in"]["sigma"]})
    U = pd.DataFrame(rows)
    # standardise by the country's own residual volatility, so noisy financial centres do not dominate
    U["unexplained"] = U.unexplained / U.sigma.clip(lower=0.5)
    CY = country_year_events(events())
    crisis_types = ["banking_crisis", "sovereign_default_private", "currency_crisis", "imf_financing", "high_inflation"]
    flags = CY[CY.event_type.isin(crisis_types)].groupby(["iso3", "year"]).event_type.apply(lambda s: sorted(set(s))).rename("events")
    U = U.merge(flags.reset_index(), on=["iso3", "year"], how="left")
    U["any_event"] = U.events.notna()
    out = []
    thr = U.unexplained.abs().quantile(0.9)
    big = U[U.unexplained.abs() >= thr]
    out.append({"group": "All country-years", "n": len(U), "mean_abs_unexplained": U.unexplained.abs().mean(),
                "mean_unexplained": U.unexplained.mean(), "share_largest_decile": 0.1})
    for t in crisis_types:
        m = U.events.apply(lambda e: isinstance(e, list) and t in e)
        if m.sum():
            out.append({"group": LABEL[t], "n": int(m.sum()), "mean_abs_unexplained": U[m].unexplained.abs().mean(),
                        "mean_unexplained": U[m].unexplained.mean(), "share_largest_decile": (U[m].unexplained.abs() >= thr).mean()})
    out.append({"group": "No crisis event", "n": int((~U.any_event).sum()), "mean_abs_unexplained": U[~U.any_event].unexplained.abs().mean(),
                "mean_unexplained": U[~U.any_event].unexplained.mean(), "share_largest_decile": (U[~U.any_event].unexplained.abs() >= thr).mean()})
    T = pd.DataFrame(out).round(3)
    T.attrs["scale"] = "unexplained remainder divided by the country's residual SD"
    # how many of the largest-residual years carry a named crisis event?
    T.attrs["largest_decile_with_event"] = float(big.any_event.mean())
    T.attrs["base_rate_event_years"] = float(U.any_event.mean())
    # difference test: |unexplained| in crisis years vs others, with country fixed effects
    U["absu"] = U.unexplained.abs()
    d = U.copy()
    d["_tid"] = d.year
    d["ev"] = d.any_event.astype(float)
    for lab, sub in (("all", d), ("EMDE", d[d.group == "EMDE"])):
        sub = sub.copy()
        D = twfe_demean(sub, ["absu", "unexplained", "ev"])
        g = sub.iso3.astype("category").cat.codes.to_numpy()
        b, se = _cluster_t(D[["ev"]].to_numpy(), D.absu.to_numpy(), g, 0)
        b2, se2 = _cluster_t(D[["ev"]].to_numpy(), D.unexplained.to_numpy(), g, 0)
        T.attrs[f"fe_abs_{lab}"] = {"coef": round(b, 3), "se": round(se, 3), "p": round(float(2 * stats.t.sf(abs(b / se), g.max())), 4)}
        T.attrs[f"fe_signed_{lab}"] = {"coef": round(b2, 3), "se": round(se2, 3), "p": round(float(2 * stats.t.sf(abs(b2 / se2), g.max())), 4)}
    T.to_csv(TABLES / "event_attribution.csv", index=False)
    json.dump(T.attrs, open(TABLES / "event_attribution_summary.json", "w"), indent=1)
    return T


# ------------------------------------------------------------------------------------- 2
def policy_levers():
    from src.econometrics.run_analysis import quarterly
    Q = quarterly()
    P = pd.read_parquet(PROCESSED / "policy_quarterly.parquet").sort_values(["iso3", "quarter"])
    for c in ["d_ccr_in", "d_ccr_out", "fxi_gdp", "d_policy_rate"]:
        P[f"L_{c}"] = P.groupby("iso3")[c].shift(1)
    Q = Q.merge(P[["iso3", "quarter", "L_d_ccr_in", "L_d_ccr_out", "L_fxi_gdp", "L_d_policy_rate"]], on=["iso3", "quarter"], how="left")
    rows = []
    specs = {"Capital-flow restrictions (inflows, change, t−1)": ["L_d_ccr_in", "L_d_ccr_out"],
             "FX intervention (% of GDP, t−1)": ["L_fxi_gdp"],
             "Policy-rate change (pp, t−1)": ["L_d_policy_rate"]}
    for y, ylab in (("gross_inflows_gdp_w", "Gross inflows"), ("gross_outflows_gdp_w", "Gross outflows"), ("net_flows_gdp_w", "Net flows")):
        for sname, terms in specs.items():
            d = Q.dropna(subset=[y] + terms + CTRL).copy()
            if d.iso3.nunique() < 10:
                continue
            d["_tid"] = d.quarter
            D = twfe_demean(d, [y] + terms + CTRL)
            g = d.iso3.astype("category").cat.codes.to_numpy()
            X = D[terms + CTRL].to_numpy()
            for j, t in enumerate(terms):
                b, se = _cluster_t(X, D[y].to_numpy(), g, j)
                rows.append({"outcome": ylab, "lever": {"L_d_ccr_in": "Inflow restrictions tightened (measures, t−1)",
                                                        "L_d_ccr_out": "Outflow restrictions tightened (measures, t−1)",
                                                        "L_fxi_gdp": "FX intervention, purchases + (% of GDP, t−1)",
                                                        "L_d_policy_rate": "Policy-rate change (pp, t−1)"}[t],
                             "coef": round(b, 3), "se": round(se, 3), "p": round(float(2 * stats.t.sf(abs(b / se), g.max())), 4),
                             "nobs": len(d), "countries": int(d.iso3.nunique()), "status": "EXPLORATORY: policy is endogenous to flows"})
    T = pd.DataFrame(rows)
    T.to_csv(TABLES / "policy_lever_associations.csv", index=False)
    return T


# ------------------------------------------------------------------------------------- 3
def exec_elections():
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    el = pe[pe.event_type.str.startswith("election") & (pe.exec_relevant == 1)
            & pe.verification_status.isin(["wikipedia+idea+vdem", "two_sources"])].copy()
    el["date"] = pd.to_datetime(el.event_date)
    el = el[el.date.dt.year.between(2015, 2025)]
    meta = pd.read_csv(PROCESSED / "country_metadata.csv").set_index("iso3")
    el["group"] = el.iso3.map(meta.country_group_alt_pre_euro)
    return el[["iso3", "date", "group", "scheduled_or_unexpected", "exec_turnover_at_election"]]


def market_elections_monthly(K=6, ref=-4):
    M = pd.read_parquet(PROCESSED / "market_monthly.parquet").sort_values(["iso3", "month"])
    M["d_yld"] = M.groupby("iso3").yld.diff()
    M = M[M.month.between("2014-07", "2026-06")]
    M["dep_m"] = M.dep_m.clip(-20, 40)
    M["d_yld"] = M.d_yld.clip(-5, 5)
    el = exec_elections()
    el["month"] = el.date.dt.strftime("%Y-%m")
    mo = lambda s: pd.PeriodIndex(s, freq="M").map(lambda p: p.ordinal)
    M["mo"] = mo(M.month)
    ev = el.assign(eo=mo(el.month))[["iso3", "eo"]]
    m = M[["iso3", "mo"]].merge(ev, on="iso3", how="left")
    m["rel"] = m.mo - m.eo
    m["absrel"] = m.rel.abs()
    near = m.dropna(subset=["rel"]).sort_values("absrel").drop_duplicates(["iso3", "mo"])[["iso3", "mo", "rel"]]
    M = M.merge(near, on=["iso3", "mo"], how="left")
    meta = pd.read_csv(PROCESSED / "country_metadata.csv").set_index("iso3")
    M["group"] = M.iso3.map(meta.country_group_alt_pre_euro)
    M = M[M.group.notna()]
    names = []
    for k in range(-K, K + 1):
        if k == ref:
            continue
        n = f"k{k}"
        M[n] = (M.rel == k).astype(float)
        names.append(n)
    rows = []
    for y, ylab in (("dep_m", "Currency depreciation vs USD (% in month)"), ("d_yld", "Change in government yield (pp in month)")):
        for grp in ("EMDE", "AE"):
            d = M[(M.group == grp)].dropna(subset=[y]).copy()
            if d.iso3.nunique() < 8:
                continue
            d["_tid"] = d.month
            D = twfe_demean(d, [y] + names)
            g = d.iso3.astype("category").cat.codes.to_numpy()
            X = D[names].to_numpy()
            pts = []
            for j, n in enumerate(names):
                b, se = _cluster_t(X, D[y].to_numpy(), g, j)
                pts.append({"k": int(n[1:]), "coef": round(b, 3), "lo": round(b - 1.96 * se, 3), "hi": round(b + 1.96 * se, 3)})
            pts.append({"k": ref, "coef": 0.0, "lo": 0.0, "hi": 0.0})
            # cumulative effect over the election month and the next two (k = 0..2)
            idx = [names.index(f"k{k}") for k in (0, 1, 2)]
            w = np.zeros(len(names)); w[idx] = 1
            Xw = X.copy()
            # reparametrise to get the sum's SE: regress on X with the sum as one column
            Xs = np.column_stack([X[:, idx].sum(axis=1) / 3] + [X[:, j] for j in range(len(names)) if j not in idx])
            bs, ses = _cluster_t(Xs, D[y].to_numpy(), g, 0)
            rows.append({"outcome": ylab, "group": grp, "points": sorted(pts, key=lambda p: p["k"]),
                         "avg_k0_2": round(bs, 3), "avg_k0_2_se": round(ses, 3),
                         "avg_k0_2_p": round(float(2 * stats.t.sf(abs(bs / ses), g.max())), 4),
                         "countries": int(d.iso3.nunique()), "nobs": len(d)})
    json.dump(rows, open(TABLES / "market_elections_monthly.json", "w"), indent=1)
    return rows


def market_elections_daily(W=20, reps=1000, seed=20261011):
    D = pd.read_parquet(PROCESSED / "market_daily.parquet")
    usd = pd.read_csv(RAW / "fred" / "DTWEXBGS.csv")
    usd.columns = ["date", "usd"]
    usd["usd"] = pd.to_numeric(usd.usd, errors="coerce")
    usd["date"] = pd.to_datetime(usd.date)
    usd = usd.dropna().sort_values("date")
    usd["usd_d"] = 100 * (usd.usd / usd.usd.shift() - 1)
    D = D.merge(usd[["date", "usd_d"]], on="date", how="left")
    D["abn"] = D.dep_d - D.usd_d.fillna(0)          # depreciation beyond the broad dollar move
    el = exec_elections()
    el = el[el.iso3.isin(D.iso3.unique())]
    paths = []
    for r in el.itertuples():
        d = D[D.iso3 == r.iso3].reset_index(drop=True)
        pos = d.index[d.date >= r.date]
        if len(pos) == 0:
            continue
        p0 = pos[0]
        if p0 - W < 1 or p0 + W >= len(d):
            continue
        seg = d.loc[p0 - W:p0 + W, "abn"].to_numpy()
        car = np.cumsum(seg) - seg[0]
        paths.append({"iso3": r.iso3, "date": str(r.date.date()), "car": car})
    A = np.array([p["car"] for p in paths])
    rng = np.random.default_rng(seed)
    boot = np.array([A[rng.integers(0, len(A), len(A))].mean(axis=0) for _ in range(reps)])
    days = list(range(-W, W + 1))
    res = {"elections": [{"iso3": p["iso3"], "date": p["date"]} for p in paths], "n": len(paths),
           "days": days, "mean": A.mean(axis=0).round(3).tolist(),
           "lo": np.quantile(boot, 0.025, axis=0).round(3).tolist(), "hi": np.quantile(boot, 0.975, axis=0).round(3).tolist()}
    # placebo: random dates in the same currencies
    pl = []
    for _ in range(300):
        cars = []
        for p in paths:
            d = D[D.iso3 == p["iso3"]].reset_index(drop=True)
            p0 = rng.integers(W + 1, len(d) - W - 1)
            seg = d.loc[p0 - W:p0 + W, "abn"].to_numpy()
            cars.append(np.cumsum(seg)[-1] - seg[0])
        pl.append(np.mean(cars))
    res["placebo_p_two_sided"] = float((np.abs(pl) >= abs(res["mean"][-1])).mean())
    json.dump(res, open(TABLES / "market_elections_daily.json", "w"), indent=1)
    return res


if __name__ == "__main__":
    T = event_attribution()
    print(T.to_string(index=False)); print(T.attrs)
    print(policy_levers().to_string(index=False))
    for r in market_elections_monthly():
        print(r["outcome"], r["group"], "avg k0-2:", r["avg_k0_2"], "p", r["avg_k0_2_p"], "countries", r["countries"])
    d = market_elections_daily()
    print("daily n", d["n"], "CAR(+20)", d["mean"][-1], "CI", d["lo"][-1], d["hi"][-1], "CAR(0)", d["mean"][20], "placebo p", d["placebo_p_two_sided"])
