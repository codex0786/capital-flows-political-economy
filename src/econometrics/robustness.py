"""Pre-specified robustness programme (protocol section 11).

For each test the pre-election coefficient (primary, H1a/H1b) and the post-election
coefficient (secondary, reported because it is the only election-window term with p < 0.05
in the baseline) are re-estimated. Output: results/tables/robustness_matrix.csv, with the
threat each test addresses, plus leave-one-out and placebo distributions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import INTERIM, PROCESSED, TABLES, get_logger, load_config
from src.econometrics.models import fit, twfe_demean, _cluster_t
from src.econometrics.run_analysis import CTRL, POST, PRE, quarterly

log = get_logger("robustness")
CFG = load_config()
OUTCOMES = ["gross_inflows_gdp_w", "gross_outflows_gdp_w"]


def _windows(Q: pd.DataFrame, events: pd.DataFrame, pre: int, post: int, prefix: str) -> pd.DataFrame:
    """Recompute pre/post windows for an alternative event list or window length."""
    qi = lambda s: pd.PeriodIndex(s, freq="Q").map(lambda p: p.ordinal)
    k = Q[["iso3", "quarter"]].copy()
    k["qidx"] = qi(k.quarter)
    ev = events[["iso3", "quarter"]].drop_duplicates().copy()
    ev["q0"] = qi(ev.quarter)
    m = k.merge(ev[["iso3", "q0"]], on="iso3", how="left")
    m["rel"] = m.qidx - m.q0
    pre_s = m[(m.rel >= -pre) & (m.rel <= 0)].groupby(["iso3", "quarter"]).size()
    post_s = m[(m.rel >= 1) & (m.rel <= post)].groupby(["iso3", "quarter"]).size()
    idx = pd.MultiIndex.from_frame(Q[["iso3", "quarter"]])
    Q = Q.copy()
    Q[f"{prefix}_pre"] = pre_s.reindex(idx).notna().astype(int).values
    Q[f"{prefix}_post"] = post_s.reindex(idx).notna().astype(int).values
    return Q


def election_events(filter_fn=None) -> pd.DataFrame:
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    ev = pe[pe.event_type.str.startswith("election")].copy()
    ev["quarter"] = pd.PeriodIndex(pd.to_datetime(ev.event_date), freq="Q").astype(str)
    return ev if filter_fn is None else ev[filter_fn(ev)]


def est(df, y, pre, post, controls=CTRL, cov="cluster_country"):
    res, d = fit(df, y, [pre, post], controls, cov=cov)
    out = {}
    for lab, t in (("pre", pre), ("post", post)):
        out[f"{lab}_coef"] = res.params[t]
        out[f"{lab}_se"] = res.std_errors[t]
        out[f"{lab}_p"] = res.pvalues[t]
    out["nobs"], out["n_countries"] = int(res.nobs), d.index.get_level_values(0).nunique()
    return out


def run():
    Q = quarterly()
    corrob = lambda e: e.verification_status.isin(["wikipedia+idea+vdem", "two_sources"])
    exec_ev = election_events(lambda e: corrob(e) & (e.exec_relevant == 1))
    rows = []

    def add(test, threat, df, y, pre=PRE, post=POST, **kw):
        r = est(df, y, pre, post, **kw)
        rows.append({"test": test, "threat_addressed": threat, "outcome": y, **r})

    for y in OUTCOMES:
        add("baseline", "-", Q, y)
        add("no controls", "bad controls / over-control", Q, y, controls=[])
        q2 = Q.merge(pd.read_parquet(PROCESSED / "annual_country_panel.parquet")[
            ["iso3", "year", "gdp_growth", "inflation", "ca_gdp", "fiscal_balance_gdp", "public_debt_gdp", "log_gdp_pc"]],
            on=["iso3", "year"], how="left")
        add("contemporaneous-year controls", "omitted current fundamentals (risk of mediator control)", q2, y,
            controls=["gdp_growth", "inflation", "ca_gdp", "fiscal_balance_gdp", "public_debt_gdp", "log_gdp_pc"])
        raw = y.replace("_w", "")
        add("unwinsorised outcome", "outlier treatment", Q, raw)
        q3 = Q.copy()
        main = q3[raw].notna()
        lo, hi = np.nanpercentile(q3.loc[main, raw], [2.5, 97.5])
        q3["y25"] = q3[raw].clip(lo, hi)
        add("winsorise 2.5/97.5", "outlier influence", q3, "y25")
        add("exclude financial centres", "SPE/pass-through flows", Q[Q.financial_centre == 0], y)
        add("exclude 2020", "pandemic coinciding with elections", Q[Q.year != 2020], y)
        add("balanced panel only", "sample composition",
            Q[Q.groupby("iso3")[y].transform(lambda s: s.notna().sum()) == 44], y)
        # previous-year GDP as denominator
        g = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")[["iso3", "year", "gdp_usd"]]
        g["year"] += 1
        q4 = Q.merge(g.rename(columns={"gdp_usd": "gdp_prev"}), on=["iso3", "year"], how="left")
        base_usd = {"gross_inflows_gdp_w": "gross_in_usd", "gross_outflows_gdp_w": "gross_out_usd"}[y]
        q4["y_prevgdp"] = 400 * q4[base_usd] / q4.gdp_prev
        lo, hi = np.nanpercentile(q4.y_prevgdp.dropna(), [1, 99])
        q4["y_prevgdp"] = q4.y_prevgdp.clip(lo, hi)
        add("scale by previous-year GDP", "denominator endogeneity", q4, "y_prevgdp")
        # alternative windows and event definitions
        add("window: election quarter only (pre=0)", "window choice", _windows(Q, exec_ev, 0, 2, "w0"), y, "w0_pre", "w0_post")
        add("window: pre = 3 quarters", "window choice", _windows(Q, exec_ev, 2, 2, "w3"), y, "w3_pre", "w3_post")
        add("any national election", "executive-relevance coding", _windows(Q, election_events(corrob), 1, 2, "any"), y, "any_pre", "any_post")
        add("3-source elections only", "event-coding error",
            _windows(Q, election_events(lambda e: (e.verification_status == "wikipedia+idea+vdem") & (e.exec_relevant == 1)), 1, 2, "v3"),
            y, "v3_pre", "v3_post")
        # classification sensitivity (effect within groups)
        for col, g_ in (("country_group_alt_pre_euro", "EMDE"), ("country_group_alt_wb", "non-HIC")):
            meta = pd.read_csv(PROCESSED / "country_metadata.csv").set_index("iso3")[col]
            add(f"{g_} only ({col})", "classification", Q[Q.iso3.map(meta) == g_], y)
        add("Driscoll-Kraay SE", "cross-sectional dependence", Q, y, cov="driscoll_kraay")
        add("two-way clustered SE", "common shocks", Q, y, cov="twoway_cluster")
    R = pd.DataFrame(rows)
    R.to_csv(TABLES / "robustness_matrix.csv", index=False)
    log.info("robustness matrix: %d rows", len(R))

    loo_placebo(Q, exec_ev)


def _fast_coef(d, y, terms, controls, groups=None):
    D = twfe_demean(d, [y] + terms + controls)
    X = D[terms + controls].to_numpy()
    b = np.linalg.lstsq(X, D[y].to_numpy(), rcond=None)[0]
    return b[:len(terms)]


def loo_placebo(Q, exec_ev):
    rng = np.random.default_rng(CFG["inference"]["seed"])
    rows = []
    for y in OUTCOMES:
        base = Q.dropna(subset=[y, PRE, POST] + CTRL).copy()
        base["_tid"] = base.quarter
        for c in sorted(base.iso3.unique()):
            b = _fast_coef(base[base.iso3 != c].copy(), y, [PRE, POST], CTRL)
            rows.append({"analysis": "leave_one_country_out", "outcome": y, "dropped_or_draw": c,
                         "pre_coef": b[0], "post_coef": b[1]})
        # placebo: shift each country's whole election calendar by a random 8-12 quarters (wrapped)
        ev = exec_ev[["iso3", "quarter"]].drop_duplicates()
        qs = sorted(base.quarter.unique())
        qpos = {q: i for i, q in enumerate(qs)}
        for draw in range(500):
            shift = {c: int(rng.integers(8, 13)) * rng.choice([-1, 1]) for c in ev.iso3.unique()}
            pev = ev[ev.quarter.isin(qpos)].copy()
            pev["quarter"] = [qs[(qpos[q] + shift[c]) % len(qs)] for c, q in zip(pev.iso3, pev.quarter)]
            P = _windows(base, pev, 1, 2, "pl")
            b = _fast_coef(P, y, ["pl_pre", "pl_post"], CTRL)
            rows.append({"analysis": "placebo_shifted_calendar", "outcome": y, "dropped_or_draw": draw,
                         "pre_coef": b[0], "post_coef": b[1]})
    L = pd.DataFrame(rows)
    L.to_csv(TABLES / "robustness_loo_placebo.csv", index=False)
    summ = []
    R = pd.read_csv(TABLES / "robustness_matrix.csv")
    for y in OUTCOMES:
        b = R[(R.test == "baseline") & (R.outcome == y)].iloc[0]
        loo = L[(L.analysis == "leave_one_country_out") & (L.outcome == y)]
        pl = L[(L.analysis == "placebo_shifted_calendar") & (L.outcome == y)]
        for lab in ("pre", "post"):
            summ.append({"outcome": y, "term": lab, "baseline": b[f"{lab}_coef"],
                         "loo_min": loo[f"{lab}_coef"].min(), "loo_max": loo[f"{lab}_coef"].max(),
                         "loo_most_influential": loo.loc[(loo[f"{lab}_coef"] - b[f"{lab}_coef"]).abs().idxmax(), "dropped_or_draw"],
                         "placebo_p_two_sided": float((pl[f"{lab}_coef"].abs() >= abs(b[f"{lab}_coef"])).mean()),
                         "placebo_sd": pl[f"{lab}_coef"].std(), "placebo_draws": len(pl)})
    pd.DataFrame(summ).to_csv(TABLES / "robustness_loo_placebo_summary.csv", index=False)


if __name__ == "__main__":
    run()
