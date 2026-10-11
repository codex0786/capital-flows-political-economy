"""Capital flows at risk, sudden-stop probabilities and their honest out-of-sample evaluation (v2).

Targets (next four quarters, t+1..t+4, annualised % of GDP):
  gross_in : average gross inflows
  net      : average net capital inflows (gross inflows - gross outflows). Reserves must cover a
             shortfall in *net* financing, so buffer tests use this target.

Flows at risk: pooled location-scale quantile regressions on the country-standardised target,
blended 50/50 with each country's own history of the target (quantile averaging); tail quantiles
(5th, 10th, 90th, 95th) can be recalibrated in real time from earlier forecast errors, pooled or
by country group.

Sudden stops: probability that an episode STARTS in t+1..t+4, under two definitions:
  fw_gross : Forbes-Warnock-style episodes on gross inflows
  fw_net   : the same algorithm on net capital inflows (closer to the Calvo sudden-stop concept)
Contagion: share of other economies in the same World Bank region in an episode at t.

Honest evaluation: at each origin quarter 2019Q4..2024Q4 every model is re-fitted on outcomes known
by then. Methods are SELECTED on origins 2019Q4-2022Q4 and REPORTED on untouched origins
2023Q1-2024Q4, with 90% intervals from a bootstrap over origins.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.quantile_regression import QuantReg

from src.common import INTERIM, PROCESSED, RESULTS, TABLES, get_logger
from src.features.build_panels import sudden_stop_episodes

warnings.filterwarnings("ignore")
log = get_logger("risk")
TAUS = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
TAIL = [0.05, 0.10, 0.90, 0.95]
CURRENT_Q = "2026Q4"
SELECT_END, TEST_START = "2022Q4", "2023Q1"
TARGETS = {"gross_in": "gross_inflows_gdp", "net": "net_flows_gdp"}
STOP_TARGET = {"fw_gross": "gross_in", "fw_net": "net"}
STOPDEFS = {"fw_gross": "Rapid fall in gross inflows (Forbes–Warnock)",
            "fw_net": "Rapid fall in net capital inflows (Calvo-style)"}
FULL = ["vix_z", "fed_z", "d4_ust_z", "d4_usd_z", "mom_z", "L_gdp_growth", "L_inflation_c", "L_ca_gdp",
        "L_public_debt_s", "res_months", "emde", "vix_x_emde", "vix_x_res"]
LEAN = ["mom_z", "vix_z", "d4_usd_z", "emde", "vix_x_emde"]
MARKET = ["dep_q", "d_yld_q", "yld_obs"]      # v3: currency depreciation in the quarter; yield change (0 where unobserved) + flag
LEAN_M = LEAN + MARKET
LOGIT = ["mom_z", "vix_z", "d4_usd_z", "fed_z", "res_months", "L_ca_gdp", "L_public_debt_s", "emde"]
QMETHODS = ["full", "lean", "history", "blend", "blend_cal", "blend_cal_group", "lean_market", "blend_market", "blend_market_cal"]
PMETHODS = ["logit", "logit_contagion", "base", "blend", "blend_contagion", "logit_market", "blend_market"]
LABELS = {"vix_z": "Global risk (VIX)", "fed_z": "US policy rate", "d4_ust_z": "US 10-year yield, 1-year change",
          "d4_usd_z": "US dollar, 1-year change", "mom_z": "Recent flows (last 4 quarters)", "L_gdp_growth": "GDP growth (last year)",
          "L_inflation_c": "Inflation (last year)", "L_ca_gdp": "Current account (last year)", "L_public_debt_s": "Public debt (last year, /100)",
          "res_months": "Reserves, months of imports", "emde": "Emerging/developing economy", "vix_x_emde": "VIX × EMDE",
          "vix_x_res": "VIX × reserves", "in": "Currently in a sudden stop", "peer": "Regional peers in a sudden stop (contagion)",
          "dep_q": "Currency depreciation in the quarter (%)", "d_yld_q": "Change in government yield (pp)", "yld_obs": "Yield observed"}


def qo(s):
    return pd.PeriodIndex(s, freq="Q").map(lambda p: p.ordinal)


def qk(t):
    return f"q{int(t * 100):02d}"


# ------------------------------------------------------------------------------------- data
def build() -> pd.DataFrame:
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet").sort_values(["iso3", "quarter"]).copy()
    Q["qo"] = qo(Q.quarter)
    main = Q.year.between(2015, 2025)
    for k, col in TARGETS.items():
        lo, hi = np.nanpercentile(Q.loc[main, col].dropna(), [1, 99])
        Q[f"y_{k}"] = Q[col].clip(lo, hi)
    net_ss = sudden_stop_episodes(Q[["iso3", "quarter", "net_usd"]].copy(), var="net_usd")
    Q = Q.merge(net_ss[["iso3", "quarter", "sudden_stop"]].rename(columns={"sudden_stop": "ss_net"}),
                on=["iso3", "quarter"], how="left").rename(columns={"sudden_stop": "ss_gross"})
    g = pd.read_parquet(INTERIM / "global_factors.parquet").sort_values("quarter").rename(
        columns={"VIXCLS": "vix", "FEDFUNDS": "fed", "DGS10": "ust", "DTWEXBGS": "usd"})
    g = g[g.quarter < CURRENT_Q]
    g["d4_ust"] = g.ust - g.ust.shift(4)
    g["d4_usd"] = 100 * (g.usd / g.usd.shift(4) - 1)
    ref = g[(g.quarter >= "2015Q1") & (g.quarter <= "2025Q4")]
    for c, n in (("vix", "vix_z"), ("fed", "fed_z"), ("d4_ust", "d4_ust_z"), ("d4_usd", "d4_usd_z")):
        g[n] = (g[c] - ref[c].mean()) / ref[c].std()
    Q = Q.drop(columns=[c for c in ["vix", "fed_funds"] if c in Q.columns]).merge(
        g[["quarter", "vix_z", "fed_z", "d4_ust_z", "d4_usd_z"]], on="quarter", how="left")
    out = []
    for iso, c in Q.groupby("iso3"):
        c = c.set_index("qo").reindex(range(c.qo.min(), c.qo.max() + 1))
        c["iso3"] = iso
        c["quarter"] = [str(pd.Period(ordinal=o, freq="Q")) for o in c.index]
        for k in TARGETS:
            c[f"fwd4_{k}"] = sum(c[f"y_{k}"].shift(-j) for j in range(1, 5)) / 4
            c[f"back4_{k}"] = c[f"y_{k}"].rolling(4, min_periods=4).mean()
        for d, col in (("fw_gross", "ss_gross"), ("fw_net", "ss_net")):
            prev = c[col].shift(1)
            start = ((c[col] == 1) & (prev == 0)).astype(float).where(c[col].notna() & prev.notna())
            c[f"fwd_{d}"] = pd.concat([start.shift(-j) for j in range(1, 5)], axis=1).max(axis=1, skipna=False)
            c[f"in_{d}"] = c[col]
        out.append(c.reset_index().rename(columns={"index": "qo"}))
    Q = pd.concat(out, ignore_index=True)
    Q["country_group"] = Q.groupby("iso3").country_group.transform(lambda s: s.ffill().bfill())
    meta = pd.read_csv(PROCESSED / "country_metadata.csv").set_index("iso3")
    Q["region"] = Q.iso3.map(meta.wb_region)
    Q["emde"] = (Q.country_group == "EMDE").astype(float)
    Q["L_inflation_c"] = Q.L_inflation.clip(-5, 50)
    Q["L_public_debt_s"] = Q.L_public_debt_gdp / 100
    Q["res_months"] = Q.groupby("iso3").L_reserves_months.transform(lambda s: s.ffill()).clip(0, 24)
    Q["vix_x_emde"] = Q.vix_z * Q.emde
    Q["year"] = Q.quarter.str[:4].astype(int)
    Q = add_market(Q)
    for d in STOPDEFS:   # contagion: share of OTHER economies in the region in an episode at t
        col = f"in_{d}"
        tot = Q.groupby(["region", "quarter"])[col].transform("sum")
        cnt = Q.groupby(["region", "quarter"])[col].transform("count")
        own = Q[col].fillna(0)
        Q[f"peer_{d}"] = (tot - own) / (cnt - Q[col].notna().astype(int)).replace(0, np.nan)
    return Q


def add_market(Q):
    """Quarter-end market signals known at the forecast origin (v3)."""
    p = PROCESSED / "market_monthly.parquet"
    if not p.exists():
        Q["dep_q"], Q["d_yld_q"], Q["yld_obs"] = np.nan, 0.0, 0.0
        return Q
    M = pd.read_parquet(p)
    M["quarter"] = pd.PeriodIndex(M.month, freq="M").asfreq("Q").astype(str)
    q = M.sort_values("month").groupby(["iso3", "quarter"]).agg(fx=("fx", "last"), yld=("yld", "last")).reset_index().sort_values(["iso3", "quarter"])
    q["dep_q"] = (100 * (q.fx / q.groupby("iso3").fx.shift() - 1)).clip(-20, 60)
    q["d_yld_q"] = q.groupby("iso3").yld.diff().clip(-10, 10)
    Q = Q.merge(q[["iso3", "quarter", "dep_q", "d_yld_q"]], on=["iso3", "quarter"], how="left")
    Q["yld_obs"] = Q.d_yld_q.notna().astype(float)
    Q["d_yld_q"] = Q.d_yld_q.fillna(0.0)
    Q["dep_q"] = Q.dep_q.fillna(0.0)        # exchange rates cover nearly all economies; missing = no change
    return Q


# ------------------------------------------------------------------------------------- models
def standardise(train, df, k):
    st = train.groupby("iso3")[f"y_{k}"].agg(["mean", "std"]).rename(columns={"mean": "mu", "std": "sd"})
    st["sd"] = st.sd.clip(lower=0.5)
    d = df.drop(columns=[c for c in ["mu", "sd"] if c in df.columns]).merge(st, left_on="iso3", right_index=True, how="inner")
    d["z_fwd"] = (d[f"fwd4_{k}"] - d.mu) / d.sd
    d["mom_z"] = (d[f"back4_{k}"] - d.mu) / d.sd
    d["vix_x_res"] = d.vix_z * (d.res_months - train.res_months.mean())
    return d


def fit_q(train, k, cols):
    d = standardise(train, train, k).dropna(subset=["z_fwd"] + cols)
    X = sm.add_constant(d[cols], has_constant="add")
    m = {t: QuantReg(d.z_fwd, X).fit(q=t, max_iter=5000) for t in TAUS}
    m["_cols"] = cols
    return m, d


def predict_q(m, train, rows, k):
    d = standardise(train, rows, k).dropna(subset=m["_cols"])
    X = sm.add_constant(d[m["_cols"]], has_constant="add")
    qz = np.sort(np.column_stack([m[t].predict(X) for t in TAUS]), axis=1)
    for j, t in enumerate(TAUS):
        d[qk(t)] = d.mu + d.sd * qz[:, j]
    return d


def history_q(train, k):
    h = train.dropna(subset=[f"fwd4_{k}"])
    return {t: h.groupby("iso3")[f"fwd4_{k}"].quantile(t) for t in TAUS}


def sort_q(df):
    qs = np.sort(df[[qk(t) for t in TAUS]].to_numpy(), axis=1)
    for j, t in enumerate(TAUS):
        df[qk(t)] = qs[:, j]
    return df


def blend(pr, hq):
    out = pr.copy()
    for t in TAUS:
        c = out.iso3.map(hq[t])
        out[qk(t)] = np.where(c.notna(), 0.5 * out[qk(t)] + 0.5 * c, out[qk(t)])
    return sort_q(out)


def logit_cols(d, with_peer):
    return LOGIT + [f"in_{d}"] + ([f"peer_{d}"] if with_peer else [])


def fit_logit(train_std, d, cols):
    y = f"fwd_{d}"
    dl = train_std.dropna(subset=[y] + cols)
    cols = [c for c in cols if dl[c].std() > 0]
    if dl[y].sum() < 15:
        return {"base": float(dl[y].mean()) if len(dl) else np.nan, "cols": None}
    m = sm.Logit(dl[y], sm.add_constant(dl[cols], has_constant="add")).fit(
        disp=0, cov_type="cluster", cov_kwds={"groups": dl.iso3.astype("category").cat.codes})
    return {"model": m, "cols": cols, "base": float(dl[y].mean())}


def predict_logit(lg, rows):
    if lg.get("cols") is None:
        return pd.Series(lg["base"], index=rows.index)
    X = sm.add_constant(rows[lg["cols"]].fillna(0), has_constant="add")
    return pd.Series(np.asarray(lg["model"].predict(X)), index=rows.index)


# ------------------------------------------------------------------------------------- evaluation
def pinball(y, q, t):
    e = y - q
    return float(np.mean(np.maximum(t * e, (t - 1) * e)))


def auc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    r = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return (r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def tail_shift(past, t, k):
    return float(np.quantile((past.y - past[k]) / past.sd, t))


def calibrate(E, by_group: bool):
    """Real-time tail recalibration from earlier forecasts whose outcomes were known at the origin."""
    E = E.copy()
    E["oo"] = qo(E.origin)
    out = []
    for o, g in E.groupby("origin"):
        oo = pd.Period(o, freq="Q").ordinal
        g = g.copy()
        past_all = E[(E.oo <= oo - 4)].dropna(subset=["y"])
        for grp, gg in (g.groupby("group") if by_group else [("all", g)]):
            past = past_all[past_all.group == grp] if by_group else past_all
            if len(past) >= 150:
                for t in TAIL:
                    g.loc[gg.index, qk(t)] = gg[qk(t)] + gg.sd * tail_shift(past, t, qk(t))
        out.append(sort_q(g).drop(columns="oo"))
    return pd.concat(out)


def rolling(Q):
    origins = [str(pd.Period("2019Q4", freq="Q") + i) for i in range(0, 21)]
    qrows, prows = [], []
    for o in origins:
        oo = pd.Period(o, freq="Q").ordinal
        train = Q[(Q.qo <= oo - 4) & (Q.quarter >= "2015Q1")]
        test = Q[Q.qo == oo]
        for k in TARGETS:
            te = test.dropna(subset=[f"fwd4_{k}"])
            mf, _ = fit_q(train, k, FULL)
            ml, _ = fit_q(train, k, LEAN)
            mm, _ = fit_q(train, k, LEAN_M)
            pf, pl = predict_q(mf, train, te, k), predict_q(ml, train, te, k)
            pm = predict_q(mm, train, te, k)
            hq = history_q(train, k)
            ph = pl.copy()
            for t in TAUS:
                ph[qk(t)] = ph.iso3.map(hq[t])
            for m, pr in (("full", pf), ("lean", pl), ("history", ph), ("blend", blend(pl, hq)),
                          ("lean_market", pm), ("blend_market", blend(pm, hq))):
                for _, r in pr.iterrows():
                    qrows.append({"target": k, "origin": o, "method": m, "iso3": r.iso3, "group": r.country_group,
                                  "y": r[f"fwd4_{k}"], "sd": r.sd, **{qk(t): r[qk(t)] for t in TAUS}})
        for d, k in STOP_TARGET.items():
            tr = standardise(train, train, k)
            te = standardise(train, test.dropna(subset=[f"fwd_{d}"]), k)
            l0, l1 = fit_logit(tr, d, logit_cols(d, False)), fit_logit(tr, d, logit_cols(d, True))
            l2 = fit_logit(tr, d, logit_cols(d, False) + MARKET)
            p0, p1, p2 = predict_logit(l0, te), predict_logit(l1, te), predict_logit(l2, te)
            for i, r in te.iterrows():
                prows.append({"def": d, "origin": o, "iso3": r.iso3, "group": r.country_group, "y": r[f"fwd_{d}"],
                              "p_logit": p0[i], "p_logit_contagion": p1[i], "p_logit_market": p2[i], "p_base": l0["base"],
                              "fitted": all(x.get("cols") is not None for x in (l0, l1, l2))})
        log.info("origin %s done", o)
    E = pd.DataFrame(qrows)
    cal = []
    for k in TARGETS:
        b = E[(E.target == k) & (E.method == "blend")]
        cal += [calibrate(b, False).assign(method="blend_cal"), calibrate(b, True).assign(method="blend_cal_group")]
        bm = E[(E.target == k) & (E.method == "blend_market")]
        cal += [calibrate(bm, False).assign(method="blend_market_cal")]
    E = pd.concat([E] + cal, ignore_index=True)
    P = pd.DataFrame(prows)
    P["p_blend"] = 0.5 * P.p_logit + 0.5 * P.p_base
    P["p_blend_contagion"] = 0.5 * P.p_logit_contagion + 0.5 * P.p_base
    P["p_blend_market"] = 0.5 * P.p_logit_market + 0.5 * P.p_base
    return E, P


def q_metrics(sub):
    out = {"forecasts": len(sub)}
    for t in TAUS:
        out[f"cover_{qk(t)}"] = round(float((sub.y <= sub[qk(t)]).mean()), 3) if len(sub) else None
        out[f"pinball_{qk(t)}"] = round(pinball(sub.y, sub[qk(t)], t), 3) if len(sub) else None
    out["pinball_avg"] = round(float(np.mean([out[f"pinball_{qk(t)}"] for t in TAUS])), 3) if len(sub) else None
    return out


def boot_cover(sub, k, reps=500, seed=20261011):
    """90% interval for coverage, resampling whole origins (forecasts made at one origin are correlated)."""
    rng = np.random.default_rng(seed)
    origins = sub.origin.unique()
    groups = {o: sub[sub.origin == o] for o in origins}
    vals = []
    for _ in range(reps):
        b = pd.concat([groups[o] for o in rng.choice(origins, size=len(origins), replace=True)])
        vals.append((b.y <= b[k]).mean())
    return [round(float(np.quantile(vals, 0.05)), 3), round(float(np.quantile(vals, 0.95)), 3)]


def evaluate(E, P):
    E = E.dropna(subset=["y", "q05"])
    windows = (("selection", E[E.origin <= SELECT_END]), ("test", E[E.origin >= TEST_START]), ("all", E))
    rows, choice = [], {}
    for k in TARGETS:
        for wname, W in windows:
            for m in QMETHODS:
                sub = W[(W.target == k) & (W.method == m)]
                for grp, gs in (("all", sub), ("AE", sub[sub.group == "AE"]), ("EMDE", sub[sub.group == "EMDE"])):
                    r = {"target": k, "window": wname, "method": m, "group": grp, **q_metrics(gs)}
                    if wname == "test":
                        r["cover_q05_ci90"], r["cover_q95_ci90"] = boot_cover(gs, "q05"), boot_cover(gs, "q95")
                    rows.append(r)
        for wsel in ("selection", "all"):
            S = pd.DataFrame([r for r in rows if r["target"] == k and r["window"] == wsel])
            # rule v2 (changed 2026-10-11 after the first held-out run; see protocol_changelog.md):
            # among methods whose pooled 5th-percentile coverage is within 2 points of 5%, lowest 5th-pct loss;
            # if none qualifies, the method whose 5th-percentile coverage is closest to 5%
            allrow = S[S.group == "all"].set_index("method")
            ok = allrow[(allrow.cover_q05 - 0.05).abs() <= 0.02]
            choice[(k, wsel)] = ok.pinball_q05.idxmin() if len(ok) else (allrow.cover_q05 - 0.05).abs().idxmin()
    prow, pchoice = [], {}
    for d in STOPDEFS:
        Pd = P[(P["def"] == d) & P.fitted].dropna(subset=["y"])
        for wname, W in (("selection", Pd[Pd.origin <= SELECT_END]), ("test", Pd[Pd.origin >= TEST_START]), ("all", Pd)):
            for m in PMETHODS:
                prow.append({"def": d, "window": wname, "method": m, "forecasts": len(W), "events": int(W.y.sum()),
                             "auc": 0.5 if m == "base" else round(float(auc(W.y, W[f"p_{m}"])), 3),
                             "brier": round(float(((W[f"p_{m}"] - W.y) ** 2).mean()), 4)})
        for wsel in ("selection", "all"):
            sel = pd.DataFrame([r for r in prow if r["def"] == d and r["window"] == wsel]).set_index("method")
            pchoice[(d, wsel)] = sel.brier.idxmin()
    return pd.DataFrame(rows), pd.DataFrame(prow), choice, pchoice


# ------------------------------------------------------------------------------------- final outputs
def run():
    Q = build()
    E, P = rolling(Q)
    E.to_csv(TABLES / "far_rolling_forecasts.csv", index=False)
    P.to_csv(TABLES / "stop_rolling_forecasts.csv", index=False)
    QS, PS, ch, pch = evaluate(E, P)
    QS.to_csv(TABLES / "far_rolling_summary.csv", index=False)
    PS.to_csv(TABLES / "stop_rolling_summary.csv", index=False)
    # the reported test performance belongs to the rule applied on 2019Q4-2022Q4 ("selection");
    # the live forecast re-applies the same rule to the full 2019Q4-2024Q4 record ("all")
    choice = {k: ch[(k, "all")] for k in TARGETS}
    pchoice = {d: pch[(d, "all")] for d in STOPDEFS}
    choice_sel = {k: ch[(k, "selection")] for k in TARGETS}
    pchoice_sel = {d: pch[(d, "selection")] for d in STOPDEFS}
    log.info("live FaR %s stop %s; held-out-selected FaR %s stop %s", choice, pchoice, choice_sel, pchoice_sel)

    end = pd.Period("2025Q4", freq="Q").ordinal
    train = Q[(Q.quarter >= "2015Q1") & (Q.qo <= end - 4)]
    out, coefs = {}, {}
    for k in TARGETS:
        use_m = "market" in choice[k]
        ml, _ = fit_q(train, k, LEAN_M if use_m else LEAN)
        mf, d_f = fit_q(train, k, FULL)
        hq = history_q(train, k)
        lt = Q.dropna(subset=[f"back4_{k}", "vix_z"]).sort_values("qo").groupby("iso3").tail(1)
        if use_m:
            lt = lt.copy()
            lt["dep_q"] = lt.dep_q.fillna(0.0)
        cur = blend(predict_q(ml, train, lt, k), hq)
        if choice[k].endswith("_cal") or choice[k] == "blend_cal_group":
            Eb = E[(E.target == k) & (E.method == ("blend_market" if use_m else "blend"))].dropna(subset=["y"])
            for t in TAIL:
                if choice[k] == "blend_cal_group":
                    for grp in ("AE", "EMDE"):
                        idx = cur.country_group == grp
                        cur.loc[idx, qk(t)] += cur.loc[idx, "sd"] * tail_shift(Eb[Eb.group == grp], t, qk(t))
                else:
                    cur[qk(t)] += cur.sd * tail_shift(Eb, t, qk(t))
            cur = sort_q(cur)
        hist = Q[Q.quarter >= "2015Q1"].dropna(subset=[f"fwd4_{k}"])
        for _, r in cur.iterrows():
            h = hist[hist.iso3 == r.iso3]
            o = out.setdefault(r.iso3, {"origin": r.quarter,
                                        "horizon": f"{pd.Period(r.quarter, freq='Q') + 1}–{pd.Period(r.quarter, freq='Q') + 4}"})
            o[k] = {"quantiles": {qk(t): round(float(r[qk(t)]), 2) for t in TAUS}, "mu": round(float(r.mu), 2),
                    "sd": round(float(r.sd), 2), "hist": [{"quarter": q, "v": round(float(v), 2)} for q, v in zip(h.quarter, h[f"fwd4_{k}"])]}
        rng = np.random.default_rng(20261011)
        isos = d_f.iso3.unique()
        bs = {0.05: [], 0.50: []}
        for _ in range(150):
            b = pd.concat([d_f[d_f.iso3 == i] for i in rng.choice(isos, size=len(isos), replace=True)])
            X = sm.add_constant(b[FULL], has_constant="add")
            for t in bs:
                try:
                    bs[t].append(QuantReg(b.z_fwd, X).fit(q=t, max_iter=3000).params)
                except Exception:
                    pass
        B5, B50 = pd.DataFrame(bs[0.05]), pd.DataFrame(bs[0.50])
        coefs[k] = [{"variable": v, "label": LABELS[v], "q05": round(float(mf[0.05].params[v]), 3), "q50": round(float(mf[0.50].params[v]), 3),
                     "q05_lo": round(float(B5[v].quantile(0.025)), 3), "q05_hi": round(float(B5[v].quantile(0.975)), 3),
                     "q50_lo": round(float(B50[v].quantile(0.025)), 3), "q50_hi": round(float(B50[v].quantile(0.975)), 3)}
                    for v in FULL if v not in ("emde", "vix_x_emde")]
    stop_coefs, base_rates = {}, {}
    for d, k in STOP_TARGET.items():
        tr = standardise(train, train, k)
        lg = fit_logit(tr, d, logit_cols(d, pchoice[d].endswith("contagion")) + (MARKET if pchoice[d].endswith("market") else []))
        base_rates[d] = round(lg["base"], 3)
        lt = standardise(train, Q.dropna(subset=[f"back4_{k}", "vix_z"]).sort_values("qo").groupby("iso3").tail(1), k)
        lt["dep_q"] = lt.dep_q.fillna(0.0)
        p = predict_logit(lg, lt)
        if pchoice[d].startswith("blend"):
            p = 0.5 * p + 0.5 * lg["base"]
        elif pchoice[d] == "base":
            p = pd.Series(lg["base"], index=lt.index)
        for iso, v in zip(lt.iso3, p):
            out.setdefault(iso, {}).setdefault("p_stop", {})[d] = round(float(v), 3)
        if lg.get("cols"):
            lab = lambda c: LABELS["in"] if c.startswith("in_") else LABELS["peer"] if c.startswith("peer_") else LABELS.get(c, c)
            stop_coefs[d] = [{"variable": c, "label": lab(c), "coef": round(float(lg["model"].params[c]), 3),
                              "p": round(float(lg["model"].pvalues[c]), 3)} for c in lg["cols"]]
    res = {"countries": out, "coefficients": coefs, "stop_coefficients": stop_coefs, "base_rates": base_rates,
           "selection": {"far_live": choice, "stop_live": pchoice, "far_heldout": choice_sel, "stop_heldout": pchoice_sel,
                         "select_window": "origins 2019Q4–2022Q4", "test_window": "origins 2023Q1–2024Q4", "live_window": "origins 2019Q4–2024Q4"},
           "summary": json.loads(QS.to_json(orient="records")), "stop_summary": json.loads(PS.to_json(orient="records")),
           "stopdefs": STOPDEFS, "taus": TAUS}
    (RESULTS / "prototype" / "risk.json").write_text(json.dumps(res, separators=(",", ":")))
    return QS, PS, {"live": choice, "heldout": choice_sel}, {"live": pchoice, "heldout": pchoice_sel}


if __name__ == "__main__":
    QS, PS, c, pc = run()
    pd.set_option("display.width", 250)
    t = QS[(QS.group == "all") & (QS.window.isin(["test", "all"]))]
    print(t[["target", "window", "method", "forecasts", "cover_q05", "cover_q10", "cover_q50", "cover_q90", "cover_q95", "pinball_q05", "pinball_avg", "cover_q05_ci90"]].to_string(index=False))
    t2 = QS[QS.method.isin(["blend_cal", "blend_cal_group"]) & (QS.window == "test")]
    print(t2[["target", "method", "group", "cover_q05", "cover_q95", "pinball_q05"]].to_string(index=False))
    print(PS.to_string(index=False))
    print("selected", c, pc)
