"""Estimate the pre-specified models in report/research_protocol.md (v1.0).

Writes results/tables/*.csv and results/logs/model_specs.json. Run after build_panels and
data_quality. Section numbers refer to the protocol.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.common import LOGS, PROCESSED, TABLES, get_logger, load_config
from src.econometrics.models import (event_dummies, extract, fit, holm, k_of, marginal_effect,
                                     wild_cluster_bootstrap)

log = get_logger("analysis")
CFG = load_config()
S = CFG["sample"]
CTRL = ["L_gdp_growth", "L_inflation", "L_ca_gdp", "L_fiscal_balance_gdp", "L_public_debt_gdp", "L_log_gdp_pc"]
COVS = ["cluster_country", "driscoll_kraay", "twoway_cluster"]
PRE, POST = "elec_exec_pre", "elec_exec_post"
RESULTS: list[dict] = []
SPECS: list[dict] = []


def quarterly() -> pd.DataFrame:
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")
    Q = Q[Q.year.between(S["main_start_year"], S["main_end_year"])].copy()
    Q["emde"] = (Q.country_group == "EMDE").astype(float)
    v = Q.drop_duplicates("quarter").set_index("quarter").vix
    Q["vix_std"] = Q.quarter.map((v - v.mean()) / v.std())
    return Q


def annual() -> pd.DataFrame:
    A = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")
    A = A[A.year.between(S["main_start_year"], S["main_end_year"])].copy()
    A["emde"] = (A.country_group == "EMDE").astype(float)
    return A


def center(df, col):
    """Centre a country-level moderator on its mean across countries in the estimation sample."""
    c = df.drop_duplicates("iso3").set_index("iso3")[col]
    return df.iso3.map(c - c.mean()), c - c.mean()


def record(res, d, y, term, cov, spec, sample, controls, family="", hyp="", time_col="quarter", **extra):
    r = extract(res, d, y, term, cov, spec, sample, controls, time_col, hypothesis=hyp, family=family, **extra)
    RESULTS.append(r.row())
    return r


def run_fe(df, y, terms, controls, spec, sample, hyp, family, focus, covs=COVS, time_col="quarter",
           bootstrap=False, other_effects=None):
    out = {}
    for cov in covs:
        res, d = fit(df, y, terms, controls, time_col=time_col, cov=cov, other_effects=other_effects)
        extra = {}
        if bootstrap and cov == "cluster_country":
            extra = wild_cluster_bootstrap(df, y, terms, controls, focus, time_col=time_col,
                                           reps=CFG["inference"]["bootstrap_reps"], seed=CFG["inference"]["seed"])
        for t in terms:
            record(res, d, y, t, cov, spec, sample, controls, family, hyp, time_col,
                   **(extra if t == focus else {}))
        out[cov] = (res, d)
    SPECS.append({"spec": spec, "outcome": y, "terms": terms, "controls": controls, "sample": sample,
                  "fixed_effects": "country + period", "time_unit": time_col, "covariances": covs})
    return out


# ---------------------------------------------------------------------------------------------
def h1(Q):
    for y, hyp in (("gross_inflows_gdp_w", "H1a"), ("gross_outflows_gdp_w", "H1b"),
                   ("net_flows_gdp_w", "H1c"), ("gross_inflows_vol8", "H1c"), ("gross_outflows_vol8", "H1c")):
        primary = hyp in ("H1a", "H1b")
        run_fe(Q, y, [PRE, POST], CTRL, "baseline", "quarterly 2015-2025", hyp,
               "primary" if primary else "secondary", PRE, bootstrap=primary)
        if primary:
            run_fe(Q, y, [PRE, POST], [], "baseline_no_controls", "quarterly 2015-2025", hyp, "robustness",
                   PRE, covs=["cluster_country"])
    # scheduled vs early decomposition (identifying sample = scheduled)
    for y, hyp in (("gross_inflows_gdp_w", "H1a"), ("gross_outflows_gdp_w", "H1b")):
        run_fe(Q, y, ["elec_exec_sched_pre", "elec_exec_sched_post", "elec_exec_early_pre", "elec_exec_early_post"],
               CTRL, "scheduled_vs_early", "quarterly 2015-2025", hyp, "secondary", "elec_exec_sched_pre",
               covs=["cluster_country"], bootstrap=True)


def h2(Q):
    mods = {"wgi_rl_2014": "primary", "wgi_rq_2014": "alt", "wgi_ge_2014": "alt", "wgi_va_2014": "alt",
            "wgi_cc_2014": "alt", "wgi_pv_2014": "alt", "v2x_jucon_2014": "alt", "v2xlg_legcon_2014": "alt"}
    me_rows = []
    for m, kind in mods.items():
        d = Q.copy()
        d["m_c"], cvals = center(d.dropna(subset=[m]), m)
        d["pre_x_m"], d["post_x_m"] = d[PRE] * d.m_c, d[POST] * d.m_c
        fam = "primary" if kind == "primary" else "H2_alternatives"
        out = run_fe(d, "gross_inflows_gdp_w", [PRE, POST, "pre_x_m", "post_x_m"], CTRL,
                     f"moderation_{m}", "quarterly 2015-2025", "H2", fam, "pre_x_m",
                     covs=COVS if kind == "primary" else ["cluster_country"], bootstrap=(kind == "primary"))
        res = out["cluster_country"][0]
        q = cvals.quantile([0.1, 0.5, 0.9])
        me = marginal_effect(res, PRE, "pre_x_m", {f"p{int(k*100)}": v for k, v in q.items()})
        me["moderator"] = m
        me["moderator_raw"] = (q + Q.drop_duplicates("iso3")[m].mean()).values
        me_rows.append(me)
    pd.concat(me_rows).to_csv(TABLES / "h2_marginal_effects.csv", index=False)


def h3(Q):
    for y in ["fdi_in_gdp_w", "pe_in_gdp_w", "pd_in_gdp_w", "oi_in_gdp_w"]:
        run_fe(Q, y, [PRE, POST], CTRL, "components", "quarterly 2015-2025", "H3", "H3_components", PRE,
               covs=["cluster_country", "driscoll_kraay"])
    for y in ["fdi_out_gdp_w", "port_out_gdp_w", "oi_out_gdp_w", "reserve_change_gdp_w"]:
        run_fe(Q, y, [PRE, POST], CTRL, "components_outflows", "quarterly 2015-2025", "H3", "secondary", PRE,
               covs=["cluster_country"])
    # equality of the pre-election coefficient across the four liability components (stacked SUR-style)
    long = []
    for y in ["fdi_in_gdp_w", "pe_in_gdp_w", "pd_in_gdp_w", "oi_in_gdp_w"]:
        t = Q[["iso3", "quarter", PRE, POST] + CTRL + [y]].rename(columns={y: "yy"}).dropna()
        t["comp"] = y
        long.append(t)
    L = pd.concat(long)
    for c in ["pe_in_gdp_w", "pd_in_gdp_w", "oi_in_gdp_w"]:
        L[f"pre_{c}"] = L[PRE] * (L.comp == c)
        L[f"post_{c}"] = L[POST] * (L.comp == c)
        for x in CTRL:
            L[f"{x}_{c}"] = L[x] * (L.comp == c)
    L["iso3_orig"] = L.iso3
    L["iso3"] = L.iso3 + "_" + L.comp      # component-specific country FE
    L["quarter_comp"] = L.quarter + "_" + L.comp
    inter = [f"pre_{c}" for c in ["pe_in_gdp_w", "pd_in_gdp_w", "oi_in_gdp_w"]]
    terms = [PRE, POST] + inter + [f"post_{c}" for c in ["pe_in_gdp_w", "pd_in_gdp_w", "oi_in_gdp_w"]]
    ctl = CTRL + [f"{x}_{c}" for x in CTRL for c in ["pe_in_gdp_w", "pd_in_gdp_w", "oi_in_gdp_w"]]
    from linearmodels.panel import PanelOLS
    L["_t"] = pd.PeriodIndex(L.quarter, freq="Q").to_timestamp()
    Li = L.set_index(["iso3", "_t"])
    oe = pd.DataFrame({"qc": Li.quarter_comp.astype("category").cat.codes}, index=Li.index)
    res = PanelOLS(Li.yy, Li[terms + ctl], entity_effects=True, other_effects=oe, check_rank=False,
                   drop_absorbed=True).fit(cov_type="clustered",
                                           clusters=pd.DataFrame({"c": Li.iso3_orig.astype("category").cat.codes}, index=Li.index))
    w = res.wald_test(formula=", ".join(f"{t} = 0" for t in inter))
    pd.DataFrame([{"test": "H3 equality of pre-election coefficient across FDI, PE, PD, OI inflows",
                   "stat": float(w.stat), "df": int(w.df), "p": float(w.pval), "nobs": int(res.nobs),
                   "note": "component-specific country FE, component-by-quarter FE and controls; clustered by country"}]
                 ).to_csv(TABLES / "h3_equality_test.csv", index=False)


def h5(Q):
    mods = {"wgi_rl_2014": "rule of law", "reserves_months_2014": "reserve cover", "st_debt_reserves_2014": "ST debt/reserves"}
    for m in mods:
        d = Q.copy()
        d["m_c"], _ = center(d.dropna(subset=[m]), m)
        d["m_c"] = d.m_c / d.drop_duplicates("iso3").m_c.std()   # per 1 SD of moderator
        d["vix_x_m"] = d.vix_std * d.m_c
        run_fe(d, "gross_inflows_gdp_w", ["vix_x_m"], CTRL, f"vix_x_{m}", "quarterly 2015-2025", "H5",
               "H5_family", "vix_x_m", covs=COVS, bootstrap=True)
    # joint specification
    d = Q.copy()
    terms = []
    for m in mods:
        d[f"{m}_c"], _ = center(d.dropna(subset=[m]), m)
        d[f"{m}_c"] = d[f"{m}_c"] / d.drop_duplicates("iso3")[f"{m}_c"].std()
        d[f"vix_x_{m}"] = d.vix_std * d[f"{m}_c"]
        terms.append(f"vix_x_{m}")
    run_fe(d, "gross_inflows_gdp_w", terms, CTRL, "vix_joint", "quarterly 2015-2025", "H5", "secondary",
           terms[0], covs=["cluster_country"])
    # volatility outcome
    run_fe(d, "gross_inflows_vol8", terms, CTRL, "vix_joint_volatility", "quarterly 2015-2025", "H5", "secondary",
           terms[0], covs=["cluster_country"])


def h6(Q):
    d = Q.copy()
    d["pre_x_emde"], d["post_x_emde"] = d[PRE] * d.emde, d[POST] * d.emde
    for y in ["gross_inflows_gdp_w", "gross_outflows_gdp_w"]:
        primary = y == "gross_inflows_gdp_w"
        run_fe(d, y, [PRE, POST, "pre_x_emde", "post_x_emde"], CTRL, "emde_interaction", "quarterly 2015-2025",
               "H6", "primary" if primary else "secondary", "pre_x_emde",
               covs=COVS if primary else ["cluster_country"], bootstrap=primary)
        for g in ["AE", "EMDE"]:
            run_fe(Q[Q.country_group == g], y, [PRE, POST], CTRL, f"group_{g}", f"quarterly 2015-2025, {g} only",
                   "H6", "secondary", PRE, covs=["cluster_country"])


def event_studies(Q):
    K, ref = CFG["elections"]["event_study_leads"], CFG["elections"]["reference_period"]
    rows = []
    for et, label in (("event_time_exec", "all executive-relevant"), ("event_time_exec_sched", "scheduled only")):
        d, names = event_dummies(Q, et, K, ref)
        for y in ["gross_inflows_gdp_w", "gross_outflows_gdp_w", "fdi_in_gdp_w", "pd_in_gdp_w", "pe_in_gdp_w", "oi_in_gdp_w"]:
            res, dd = fit(d, y, names, CTRL, cov="cluster_country")
            for n in names:
                rows.append({"design": f"TWFE, {label}", "outcome": y, "k": k_of(n), "coef": res.params[n],
                             "se": res.std_errors[n], "ci_low": res.params[n] - 1.96 * res.std_errors[n],
                             "ci_high": res.params[n] + 1.96 * res.std_errors[n], "nobs": res.nobs,
                             "n_countries": dd.index.get_level_values(0).nunique()})
            leads = [n for n in names if n in ("ev_m6", "ev_m5")]
            w = res.wald_test(formula=", ".join(f"{n} = 0" for n in leads))
            rows.append({"design": f"TWFE, {label}", "outcome": y, "k": "pretrend_joint_p(k=-6,-5)",
                         "coef": float(w.pval), "se": np.nan, "ci_low": np.nan, "ci_high": np.nan,
                         "nobs": res.nobs, "n_countries": dd.index.get_level_values(0).nunique()})
    # stacked clean-control design (scheduled elections)
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    ev = pe[pe.event_type.str.startswith("election") & (pe.exec_relevant == 1) &
            pe.verification_status.isin(["wikipedia+idea+vdem", "two_sources"])].copy()
    ev["quarter"] = pd.PeriodIndex(pd.to_datetime(ev.event_date), freq="Q").astype(str)
    allev = ev[["iso3", "quarter"]].drop_duplicates()
    sched = ev[(ev.scheduled_or_unexpected == "scheduled_rule_based")]
    sched = sched[sched.iso3.isin(Q.iso3.unique()) & (sched.quarter >= "2016Q3") & (sched.quarter <= "2024Q2")]
    for y in ["gross_inflows_gdp_w", "gross_outflows_gdp_w"]:
        # clean controls exclude any country with an exec-relevant election (scheduled or early) nearby
        out = _stacked(Q, sched, allev, y, K, ref)
        for r in out.itertuples():
            rows.append({"design": "stacked clean-control, scheduled only", "outcome": y, "k": r.k, "coef": r.coef,
                         "se": r.se, "ci_low": r.ci_low, "ci_high": r.ci_high, "nobs": out.attrs["nobs"],
                         "n_countries": out.attrs["n_countries"], "n_events": out.attrs["n_events"],
                         "pre_window_joint_p": out.attrs["pre_window_joint_p"]})
    pd.DataFrame(rows).to_csv(TABLES / "event_study_coefficients.csv", index=False)


def _stacked(Q, treated_events, all_events, y, K, ref):
    """Stacked clean-control event study.

    Treated: one scheduled executive-relevant election per stack. Controls: countries with no
    executive-relevant election (scheduled or early) within +/-2K quarters of the event, so
    no control is itself inside an election window during the stack. FE: stack-by-country and
    stack-by-quarter; errors clustered by country.
    """
    qi = lambda s: pd.PeriodIndex(s, freq="Q").map(lambda p: p.ordinal)
    ae = all_events.copy()
    ae["q0"] = qi(ae.quarter)
    te = treated_events[["iso3", "quarter"]].drop_duplicates().copy()
    d = Q.copy()
    d["qidx"] = qi(d.quarter)
    stacks = []
    for sid, r in enumerate(te.assign(q0=qi(te.quarter)).itertuples()):
        win = d[(d.qidx >= r.q0 - K) & (d.qidx <= r.q0 + K)]
        near = ae[(ae.q0 >= r.q0 - 2 * K) & (ae.q0 <= r.q0 + 2 * K)].iso3
        ctrl = win[~win.iso3.isin(near)]
        tr = win[win.iso3 == r.iso3]
        if len(tr) < 2 * K or ctrl.iso3.nunique() < 5:
            continue
        s = pd.concat([tr.assign(treated=1.0), ctrl.assign(treated=0.0)])
        s["rel"], s["stack_id"] = s.qidx - r.q0, sid
        stacks.append(s)
    St = pd.concat(stacks, ignore_index=True)
    names = []
    for k in range(-K, K + 1):
        if k == ref:
            continue
        n = f"ev_m{abs(k)}" if k < 0 else f"ev_p{k}"
        St[n] = ((St.rel == k) & (St.treated == 1)).astype(float)
        names.append(n)
    from linearmodels.panel import PanelOLS
    St = St.dropna(subset=[y] + CTRL)
    St["unit"] = St.iso3 + "_" + St.stack_id.astype(str)
    St["_t"] = pd.PeriodIndex(St.quarter, freq="Q").to_timestamp()
    Si = St.set_index(["unit", "_t"])
    oe = pd.DataFrame({"sq": (Si.stack_id.astype(str) + "_" + Si.quarter).astype("category").cat.codes}, index=Si.index)
    res = PanelOLS(Si[y], Si[names + CTRL], entity_effects=True, other_effects=oe, check_rank=False,
                   drop_absorbed=True).fit(cov_type="clustered",
                                           clusters=pd.DataFrame({"c": Si.iso3.astype("category").cat.codes}, index=Si.index))
    out = pd.DataFrame({"k": [k_of(n) for n in names], "coef": res.params[names].values, "se": res.std_errors[names].values})
    out["ci_low"], out["ci_high"] = out.coef - 1.96 * out.se, out.coef + 1.96 * out.se
    out.attrs.update(nobs=int(res.nobs), n_events=int(St.stack_id.nunique()), n_countries=int(St.iso3.nunique()))
    # average pre-window effect (k=-1,0) as a single number
    agg = res.wald_test(formula="ev_m1 = 0, ev_p0 = 0")
    out.attrs["pre_window_joint_p"] = float(agg.pval)
    return out


def annual_models(A):
    for y in ["gross_inflows_gdp_w", "gross_outflows_gdp_w", "net_flows_gdp_w", "fdi_in_gdp_w"]:
        run_fe(A, y, ["exec_election"], CTRL, "annual_election_year", "annual 2015-2025", "H1-annual", "secondary",
               "exec_election", covs=["cluster_country", "driscoll_kraay"], time_col="year")
    # within-country association with time-varying governance (associational; slow-moving)
    for g in ["wgi_rl_est", "wgi_pv_est", "wgi_rq_est", "wgi_ge_est", "v2x_jucon"]:
        run_fe(A, "gross_inflows_gdp_w", [g], CTRL, f"annual_within_{g}", "annual 2015-2025", "governance-within",
               "exploratory", g, covs=["cluster_country"], time_col="year")
    # Mundlak / correlated random effects for between-country governance association
    import statsmodels.formula.api as smf
    rows = []
    for g in ["wgi_rl_est", "wgi_pv_est", "wgi_rq_est"]:
        d = A.dropna(subset=["gross_inflows_gdp_w", g] + CTRL).copy()
        d[f"{g}_mean"] = d.groupby("iso3")[g].transform("mean")
        for c in CTRL:
            d[f"{c}_mean"] = d.groupby("iso3")[c].transform("mean")
        f = f"gross_inflows_gdp_w ~ {g} + {g}_mean + " + " + ".join(CTRL + [f"{c}_mean" for c in CTRL]) + " + C(year)"
        m = smf.ols(f, d).fit(cov_type="cluster", cov_kwds={"groups": d.iso3.astype("category").cat.codes})
        for t in [g, f"{g}_mean"]:
            rows.append({"governance": g, "term": t, "coef": m.params[t], "se": m.bse[t], "p": m.pvalues[t],
                         "nobs": int(m.nobs), "n_countries": d.iso3.nunique(),
                         "interpretation": "within-country" if t == g else "between-country (Mundlak mean; NOT causal)"})
    pd.DataFrame(rows).to_csv(TABLES / "annual_mundlak_governance.csv", index=False)


def reverse_direction(Q, A):
    """R1 exploratory: do recent sudden stops predict political events?"""
    q = Q.sort_values(["iso3", "quarter"]).copy()
    q["stop_l1to4"] = q.groupby("iso3").sudden_stop.transform(lambda s: s.shift(1).rolling(4, min_periods=4).max())
    q["unrest_event"] = q.rsui_event
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    early = pe[(pe.scheduled_or_unexpected == "early_rule_based") & pe.verification_status.isin(["wikipedia+idea+vdem", "two_sources"])]
    early_q = set(zip(early.iso3, pd.PeriodIndex(pd.to_datetime(early.event_date), freq="Q").astype(str)))
    q["early_election_q"] = [float((i, t) in early_q) for i, t in zip(q.iso3, q.quarter)]
    for y in ["unrest_event", "early_election_q"]:
        run_fe(q, y, ["stop_l1to4"], CTRL, f"reverse_{y}", "quarterly 2015-2025", "R1", "exploratory", "stop_l1to4",
               covs=["cluster_country"])
    a = A.copy()
    stops = q.groupby(["iso3", "year"]).sudden_stop.max().rename("stop_any").reset_index()
    stops["year"] += 1
    a = a.merge(stops.rename(columns={"stop_any": "L_stop_any"}), on=["iso3", "year"], how="left")
    for y in ["exec_change", "irregular_exec_change"]:
        run_fe(a, y, ["L_stop_any"], CTRL, f"reverse_{y}", "annual 2016-2025", "R1", "exploratory", "L_stop_any",
               covs=["cluster_country"], time_col="year")


def policy_exploratory(Q, A):
    """H4 exploratory associations; policy adoption is endogenous (protocol section 9)."""
    q = Q.sort_values(["iso3", "quarter"]).copy()
    q["d_policy_rate"] = q.groupby("iso3").policy_rate.diff()
    run_fe(q, "gross_inflows_gdp_w", ["d_policy_rate"], CTRL, "policy_rate_change", "quarterly, BIS-rate countries",
           "H4", "exploratory", "d_policy_rate", covs=["cluster_country"])
    a = A.sort_values(["iso3", "year"]).copy()
    k = pd.read_parquet(PROCESSED.parent / "interim" / "kaopen.parquet")
    a = a.merge(k[["iso3", "year", "ka_open"]], on=["iso3", "year"], how="left")
    a["d_ka_open"] = a.groupby("iso3").ka_open.diff()
    for y in ["gross_inflows_gdp_w", "port_in_gdp_w"]:
        run_fe(a, y, ["d_ka_open"], CTRL, "kaopen_change", "annual 2015-2023", "H4", "exploratory", "d_ka_open",
               covs=["cluster_country"], time_col="year")
    run_fe(a, "gross_inflows_gdp_w", ["fiscal_balance_gdp"], [c for c in CTRL if c != "L_fiscal_balance_gdp"],
           "fiscal_balance_contemporaneous", "annual 2015-2025", "H4", "exploratory", "fiscal_balance_gdp",
           covs=["cluster_country"], time_col="year")


def multiple_testing():
    R = pd.DataFrame(RESULTS)
    prim = R[R["cov"] == "clustered by country"]
    fam = {
        "primary": [("gross_inflows_gdp_w", PRE, "baseline"), ("gross_outflows_gdp_w", PRE, "baseline"),
                    ("gross_inflows_gdp_w", "pre_x_m", "moderation_wgi_rl_2014"),
                    ("gross_inflows_gdp_w", "pre_x_emde", "emde_interaction")],
        "H3_components": [(y, PRE, "components") for y in ["fdi_in_gdp_w", "pe_in_gdp_w", "pd_in_gdp_w", "oi_in_gdp_w"]],
        "H5_family": [("gross_inflows_gdp_w", "vix_x_m", f"vix_x_{m}") for m in
                      ["wgi_rl_2014", "reserves_months_2014", "st_debt_reserves_2014"]],
        "H2_alternatives": [("gross_inflows_gdp_w", "pre_x_m", f"moderation_{m}") for m in
                            ["wgi_rq_2014", "wgi_ge_2014", "wgi_va_2014", "wgi_cc_2014", "wgi_pv_2014",
                             "v2x_jucon_2014", "v2xlg_legcon_2014"]],
    }
    rows = []
    for f, items in fam.items():
        sel = []
        for y, t, sp in items:
            r = prim[(prim.outcome == y) & (prim.term == t) & (prim.spec == sp)]
            if len(r) == 1:
                sel.append(r.iloc[0])
        df = pd.DataFrame(sel)
        p_use = df["wcb_p"].fillna(df.p) if "wcb_p" in df else df.p
        df["p_used"] = p_use.values
        df["p_holm"] = holm(pd.Series(df.p_used.values, index=df.index)).values
        df["family"] = f
        rows.append(df)
    out = pd.concat(rows)
    out[["family", "hypothesis", "outcome", "term", "spec", "coef", "se", "p", "wcb_p", "p_used", "p_holm",
         "ci_low", "ci_high", "nobs", "n_countries"]].to_csv(TABLES / "multiple_testing.csv", index=False)


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    Q, A = quarterly(), annual()
    log.info("quarterly estimation sample: %d obs, %d countries", len(Q), Q.iso3.nunique())
    h1(Q); log.info("H1 done")
    h2(Q); log.info("H2 done")
    h3(Q); log.info("H3 done")
    h5(Q); log.info("H5 done")
    h6(Q); log.info("H6 done")
    event_studies(Q); log.info("event studies done")
    annual_models(A); log.info("annual done")
    reverse_direction(Q, A); log.info("reverse done")
    policy_exploratory(Q, A); log.info("policy done")
    pd.DataFrame(RESULTS).to_csv(TABLES / "all_estimates.csv", index=False)
    multiple_testing()
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "model_specs.json").write_text(json.dumps(SPECS, indent=1))
    log.info("analysis complete: %d estimates", len(RESULTS))


if __name__ == "__main__":
    main()
