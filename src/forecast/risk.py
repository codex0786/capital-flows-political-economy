"""Capital flows at risk and sudden-stop probabilities, with a real-time rolling evaluation.

Target (flows at risk): the average of gross inflows over the next four quarters, t+1..t+4
(annualised % of GDP), standardised by the country's own mean and SD in the training window:
    z_i,t+1:t+4 = (mean(y_i,t+1..t+4) - mu_i) / sd_i
Quantile regressions (tau = 0.05 ... 0.95) of z on conditions at t are pooled across countries,
then mapped back to each country's units: q_i = mu_i + sd_i * q_z. This location-scale approach
(in the spirit of IMF growth-at-risk / capital-flows-at-risk work, e.g. Gelos et al. 2019) lets
44 quarters per country inform a shared tail model.

Predictors at t (all known at t): VIX, US policy rate, 4-quarter change in the US 10-year yield and
in the broad dollar, the country's last-4-quarter average flow (standardised), previous-year
growth, inflation, current account, public debt, reserves (months of imports), an EMDE indicator,
and VIX x EMDE and VIX x reserves interactions.

Sudden stop: P(any sudden-stop quarter in t+1..t+4) from a pooled logit with the same predictors
plus the current stop status.

Real-time evaluation: for each origin quarter 2019Q4..2024Q4 the models are re-fitted using only
targets fully observed by that origin (t+4 <= origin) and evaluated on the realised outcome.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.quantile_regression import QuantReg

from src.common import INTERIM, PROCESSED, RESULTS, TABLES, get_logger

warnings.filterwarnings("ignore")
log = get_logger("risk")
TAUS = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
PRED = ["vix_z", "fed_z", "d4_ust_z", "d4_usd_z", "mom_z", "L_gdp_growth", "L_inflation_c", "L_ca_gdp",
        "L_public_debt_s", "res_months", "emde", "vix_x_emde", "vix_x_res"]
LABELS = {"vix_z": "Global risk (VIX)", "fed_z": "US policy rate", "d4_ust_z": "US 10-year yield, 1-year change",
          "d4_usd_z": "US dollar, 1-year change", "mom_z": "Recent inflows (last 4 quarters)", "L_gdp_growth": "GDP growth (last year)",
          "L_inflation_c": "Inflation (last year)", "L_ca_gdp": "Current account (last year)", "L_public_debt_s": "Public debt (last year, /100)",
          "res_months": "Reserves, months of imports", "emde": "Emerging/developing economy", "vix_x_emde": "VIX × EMDE",
          "vix_x_res": "VIX × reserves"}
CURRENT_Q = "2026Q4"


def qo(s):
    return pd.PeriodIndex(s, freq="Q").map(lambda p: p.ordinal)


def build() -> pd.DataFrame:
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet").sort_values(["iso3", "quarter"]).copy()
    Q["qo"] = qo(Q.quarter)
    main = Q.year.between(2015, 2025)
    lo, hi = np.nanpercentile(Q.loc[main, "gross_inflows_gdp"].dropna(), [1, 99])
    Q["y"] = Q.gross_inflows_gdp.clip(lo, hi)
    g = pd.read_parquet(INTERIM / "global_factors.parquet").sort_values("quarter").rename(
        columns={"VIXCLS": "vix", "FEDFUNDS": "fed", "DGS10": "ust", "DTWEXBGS": "usd"})
    g = g[g.quarter < CURRENT_Q]
    g["d4_ust"] = g.ust - g.ust.shift(4)
    g["d4_usd"] = 100 * (g.usd / g.usd.shift(4) - 1)
    ref = g[(g.quarter >= "2015Q1") & (g.quarter <= "2025Q4")]
    for c, n in (("vix", "vix_z"), ("fed", "fed_z"), ("d4_ust", "d4_ust_z"), ("d4_usd", "d4_usd_z")):
        g[n] = (g[c] - ref[c].mean()) / ref[c].std()
    Q = Q.drop(columns=[c for c in ["vix", "fed_funds"] if c in Q.columns]).merge(
        g[["quarter", "vix", "vix_z", "fed_z", "d4_ust_z", "d4_usd_z"]], on="quarter", how="left")
    # consecutive-quarter guard and forward/backward windows
    out = []
    for iso, c in Q.groupby("iso3"):
        c = c.set_index("qo").reindex(range(c.qo.min(), c.qo.max() + 1))
        c["iso3"] = iso
        c["quarter"] = [str(pd.Period(ordinal=o, freq="Q")) for o in c.index]
        c["fwd4"] = sum(c.y.shift(-k) for k in range(1, 5)) / 4
        c["back4"] = c.y.rolling(4, min_periods=4).mean()
        c["stop_fwd"] = pd.concat([c.sudden_stop.shift(-k) for k in range(1, 5)], axis=1).max(axis=1, skipna=False)
        out.append(c.reset_index().rename(columns={"index": "qo"}))
    Q = pd.concat(out, ignore_index=True)
    Q["country_group"] = Q.groupby("iso3").country_group.transform(lambda s: s.ffill().bfill())
    Q["emde"] = (Q.country_group == "EMDE").astype(float)
    Q["L_inflation_c"] = Q.L_inflation.clip(-5, 50)
    Q["L_public_debt_s"] = Q.L_public_debt_gdp / 100
    Q["res_months"] = Q.groupby("iso3").L_reserves_months.transform(lambda s: s.ffill()).clip(0, 24)
    Q["vix_x_emde"] = Q.vix_z * Q.emde
    Q["year"] = Q.quarter.str[:4].astype(int)
    return Q


def standardise(train: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    st = train.groupby("iso3").y.agg(["mean", "std"]).rename(columns={"mean": "mu", "std": "sd"})
    st["sd"] = st.sd.clip(lower=0.5)
    d = df.merge(st, left_on="iso3", right_index=True, how="inner")
    d["z_fwd"] = (d.fwd4 - d.mu) / d.sd
    d["mom_z"] = (d.back4 - d.mu) / d.sd
    rm = train.res_months.mean() if "res_months" in train else 0
    d["vix_x_res"] = d.vix_z * (d.res_months - rm)
    return d


LEAN = ["mom_z", "vix_z", "d4_usd_z", "emde", "vix_x_emde"]


def fit_models(train: pd.DataFrame, qpred=None):
    qpred = qpred or PRED
    d = standardise(train, train).dropna(subset=["z_fwd"] + PRED)
    X = sm.add_constant(d[qpred], has_constant="add")
    qr = {t: QuantReg(d.z_fwd, X).fit(q=t, max_iter=5000) for t in TAUS}
    dl = d.dropna(subset=["stop_fwd", "sudden_stop"])
    lcols = [c for c in PRED + ["sudden_stop"] if dl[c].std() > 0]
    if dl.stop_fwd.sum() < 15:          # too few training episodes: fall back to the base rate
        lg = {"base": float(dl.stop_fwd.mean()) if len(dl) else np.nan, "cols": None}
    else:
        m = sm.Logit(dl.stop_fwd, sm.add_constant(dl[lcols], has_constant="add")).fit(
            disp=0, cov_type="cluster", cov_kwds={"groups": dl.iso3.astype("category").cat.codes})
        lg = {"model": m, "cols": lcols, "base": float(dl.stop_fwd.mean())}
    qr["_cols"] = qpred
    return qr, lg, d


def predict(qr, lg, train, rows):
    d = standardise(train, rows).dropna(subset=PRED)
    X = sm.add_constant(d[qr["_cols"]], has_constant="add")
    qz = np.column_stack([qr[t].predict(X) for t in TAUS])
    qz.sort(axis=1)                                   # remove quantile crossing
    for j, t in enumerate(TAUS):
        d[f"q{int(t*100):02d}"] = d.mu + d.sd * qz[:, j]
    if lg.get("cols") is None:
        d["p_stop"], d["p_method"] = lg["base"], "base rate"
    else:
        Xl = sm.add_constant(d[lg["cols"]].fillna({"sudden_stop": 0}), has_constant="add")
        d["p_stop"], d["p_method"] = lg["model"].predict(Xl), "logit"
    return d


def pinball(y, q, t):
    e = y - q
    return np.mean(np.maximum(t * e, (t - 1) * e))


def auc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    r = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return (r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


METHODS_Q = ["full", "lean", "history", "blend", "blend_calibrated"]
TAIL = [0.05, 0.10, 0.90, 0.95]   # only the tails are recalibrated; the centre stays as forecast
METHODS_P = ["logit", "base", "blend"]


def climatology(train):
    h = standardise(train, train)
    return {t: h.groupby("iso3").fwd4.quantile(t) for t in TAUS}


def combine(pr_lean, cq):
    """Quantile averaging (Vincentisation) of the lean model and each country's history."""
    out = pr_lean.copy()
    for t in TAUS:
        k = f"q{int(t*100):02d}"
        c = out.iso3.map(cq[t])
        out[k] = np.where(c.notna(), 0.5 * out[k] + 0.5 * c, out[k])
    qs = np.sort(out[[f"q{int(t*100):02d}" for t in TAUS]].to_numpy(), axis=1)
    for j, t in enumerate(TAUS):
        out[f"q{int(t*100):02d}"] = qs[:, j]
    return out


def rolling_eval(Q: pd.DataFrame):
    origins = [str(pd.Period("2019Q4", freq="Q") + k) for k in range(0, 21)]   # 2019Q4..2024Q4
    rows = []
    for o in origins:
        oo = pd.Period(o, freq="Q").ordinal
        train = Q[(Q.qo <= oo - 4) & (Q.quarter >= "2015Q1")]                    # targets observed by the origin
        test = Q[(Q.qo == oo)].dropna(subset=["fwd4"])
        qf, lg, _ = fit_models(train)
        ql, _, _ = fit_models(train, LEAN)
        pf, pl = predict(qf, lg, train, test), predict(ql, lg, train, test)
        cq = climatology(train)
        pb = combine(pl, cq)
        for m, pr in (("full", pf), ("lean", pl), ("blend", pb), ("history", None)):
            src = pl if pr is None else pr
            for _, r in src.iterrows():
                rec = {"origin": o, "method": m, "iso3": r.iso3, "group": r.country_group, "y": r.fwd4, "sd": r.sd,
                       "stop": r.stop_fwd, "p_logit": r.p_stop, "p_base": lg["base"], "p_method": r.p_method}
                for t in TAUS:
                    k = f"q{int(t*100):02d}"
                    rec[k] = cq[t].get(r.iso3, np.nan) if m == "history" else r[k]
                rows.append(rec)
        log.info("origin %s: %d countries", o, len(pl))
    E = pd.DataFrame(rows)
    E["p_blend"] = 0.5 * E.p_logit + 0.5 * E.p_base
    # real-time calibration of the blend (split-conformal style): at each origin, shift each quantile by the
    # tau-quantile of standardised errors from earlier forecasts whose outcomes were already known
    Bl = E[E.method == "blend"].copy()
    Bl["oo"] = qo(Bl.origin)
    cal = []
    for o, g in Bl.groupby("origin"):
        oo = pd.Period(o, freq="Q").ordinal
        past = Bl[(Bl.oo <= oo - 4)].dropna(subset=["y"])
        g = g.copy()
        g["method"] = "blend_calibrated"
        for t in TAIL:
            k = f"q{int(t*100):02d}"
            if len(past) >= 200:
                g[k] = g[k] + g.sd * np.quantile((past.y - past[k]) / past.sd, t)
        qs = np.sort(g[[f"q{int(t*100):02d}" for t in TAUS]].to_numpy(), axis=1)
        for j, t in enumerate(TAUS):
            g[f"q{int(t*100):02d}"] = qs[:, j]
        g["calibrated"] = len(past) >= 200
        cal.append(g.drop(columns="oo"))
    E = pd.concat([E, pd.concat(cal)], ignore_index=True)
    windows = [("All origins 2019Q4–2024Q4", lambda e: e), ("Origins before 2020 shock (2019Q4–2020Q3)", lambda e: e[e.origin.between("2019Q4", "2020Q3")]),
               ("Origins before 2022 tightening (2021Q4–2022Q3)", lambda e: e[e.origin.between("2021Q4", "2022Q3")]),
               ("Advanced economies", lambda e: e[e.group == "AE"]), ("Emerging & developing", lambda e: e[e.group == "EMDE"])]
    summ = []
    for name, f in windows:
        for m in METHODS_Q:
            sub = f(E[E.method == m]).dropna(subset=["y", "q05"])
            s_ = {"window": name, "method": m, "forecasts": len(sub)}
            for t in TAUS:
                k = f"q{int(t*100):02d}"
                s_[f"cover_{k}"] = round(float((sub.y <= sub[k]).mean()), 3)
                s_[f"pinball_{k}"] = round(pinball(sub.y, sub[k], t), 3)
            s_["pinball_avg"] = round(float(np.mean([s_[f"pinball_q{int(t*100):02d}"] for t in TAUS])), 3)
            summ.append(s_)
    S = pd.DataFrame(summ)
    psum = []
    L0 = E[(E.method == "lean") & E.stop.notna() & (E.p_method == "logit")]
    for name, f in windows:
        L = f(L0)
        for m in METHODS_P:
            psum.append({"window": name, "method": m, "forecasts": len(L), "events": int(L.stop.sum()),
                         "auc": round(float(auc(L.stop, L[f"p_{m}"])), 3) if m != "base" else 0.5,
                         "brier": round(float(((L[f"p_{m}"] - L.stop) ** 2).mean()), 4)})
    return E, S, pd.DataFrame(psum)


def bootstrap_coefs(d, reps=200, seed=20261011):
    """Country-cluster bootstrap for q05 and q50 coefficients (targets overlap, so iid SEs are wrong)."""
    rng = np.random.default_rng(seed)
    isos = d.iso3.unique()
    out = {0.05: [], 0.50: []}
    for _ in range(reps):
        pick = rng.choice(isos, size=len(isos), replace=True)
        b = pd.concat([d[d.iso3 == i] for i in pick])
        X = sm.add_constant(b[PRED])
        for t in out:
            try:
                out[t].append(QuantReg(b.z_fwd, X).fit(q=t, max_iter=3000).params)
            except Exception:  # rare non-convergence in a resample
                pass
    return {t: pd.DataFrame(v) for t, v in out.items()}


def run():
    Q = build()
    E, S, P = rolling_eval(Q)
    E.to_csv(TABLES / "far_rolling_forecasts.csv", index=False)
    S.to_csv(TABLES / "far_rolling_summary.csv", index=False)
    P.to_csv(TABLES / "stop_rolling_summary.csv", index=False)
    allw = S[S.window.str.startswith("All")].set_index("method")
    # selection rule for a flows-at-risk tool: among methods whose 5th-percentile coverage is within
    # 2 points of 5%, take the lowest 5th-percentile pinball loss; if none qualifies, lowest average loss
    ok = allw[(allw.cover_q05 - 0.05).abs() <= 0.02]
    best_q = ok.pinball_q05.idxmin() if len(ok) else allw.pinball_avg.idxmin()
    # calibration shifts for the live forecast use every forecast whose outcome is known
    Bl = E[(E.method == "blend")].dropna(subset=["y"])
    shift = {t: (float(np.quantile((Bl.y - Bl[f"q{int(t*100):02d}"]) / Bl.sd, t)) if t in TAIL else 0.0) for t in TAUS}
    pw = P[P.window.str.startswith("All")].set_index("method")
    best_p = pw.brier.idxmin()
    log.info("selected quantile method %s, probability method %s", best_q, best_p)
    # final models on all observed targets (2015Q1 .. 2025Q4 outcomes)
    train = Q[(Q.quarter >= "2015Q1") & (Q.qo <= pd.Period("2025Q4", freq="Q").ordinal - 4)]
    qr, lg, d = fit_models(train)
    ql, _, _ = fit_models(train, LEAN)
    bs = bootstrap_coefs(d)
    coefs = []
    for v in PRED:
        row = {"variable": v, "label": LABELS[v]}
        for t in (0.05, 0.50):
            row[f"q{int(t*100):02d}"] = round(float(qr[t].params[v]), 3)
            row[f"q{int(t*100):02d}_lo"] = round(float(bs[t][v].quantile(0.025)), 3)
            row[f"q{int(t*100):02d}_hi"] = round(float(bs[t][v].quantile(0.975)), 3)
        row["logit"] = round(float(lg["model"].params.get(v, np.nan)), 3)
        row["logit_p"] = round(float(lg["model"].pvalues.get(v, np.nan)), 3)
        coefs.append(row)
    C = pd.DataFrame(coefs)
    C.to_csv(TABLES / "far_coefficients.csv", index=False)
    # current outlook: latest quarter with the needed inputs per country
    last = Q.dropna(subset=["back4", "vix_z"]).sort_values("qo").groupby("iso3").tail(1)
    cur_full, cur_lean = predict(qr, lg, train, last), predict(ql, lg, train, last)
    cq = climatology(train)
    cur_bl = combine(cur_lean, cq)
    cur_cal = cur_bl.copy()
    for t in TAUS:
        cur_cal[f"q{int(t*100):02d}"] = cur_cal[f"q{int(t*100):02d}"] + cur_cal.sd * shift[t]
    qs_ = np.sort(cur_cal[[f"q{int(t*100):02d}" for t in TAUS]].to_numpy(), axis=1)
    for j, t in enumerate(TAUS):
        cur_cal[f"q{int(t*100):02d}"] = qs_[:, j]
    cur = {"full": cur_full, "lean": cur_lean, "blend": cur_bl, "blend_calibrated": cur_cal}.get(best_q)
    if cur is None:  # history only
        cur = cur_lean.copy()
        for t in TAUS:
            cur[f"q{int(t*100):02d}"] = cur.iso3.map(cq[t])
    cur["p_stop"] = {"logit": cur_lean.p_stop, "base": lg["base"], "blend": 0.5 * cur_lean.p_stop + 0.5 * lg["base"]}[best_p]
    out = {}
    hist_fwd = Q[(Q.quarter >= "2015Q1")].dropna(subset=["fwd4"])
    for _, r in cur.iterrows():
        h = hist_fwd[hist_fwd.iso3 == r.iso3]
        out[r.iso3] = {
            "origin": r.quarter, "horizon": f"{pd.Period(r.quarter, freq='Q') + 1}–{pd.Period(r.quarter, freq='Q') + 4}",
            "quantiles": {f"q{int(t*100):02d}": round(float(r[f"q{int(t*100):02d}"]), 2) for t in TAUS},
            "p_stop": round(float(r.p_stop), 3), "mu": round(float(r.mu), 2), "sd": round(float(r.sd), 2),
            "hist": [{"quarter": q, "fwd4": round(float(v), 2)} for q, v in zip(h.quarter, h.fwd4)],
            "hist_q05": round(float(h.fwd4.quantile(0.05)), 2) if len(h) > 10 else None,
            "drivers": {v: round(float(r[v]), 2) for v in ["vix_z", "mom_z", "res_months"]},
        }
    res = {"countries": out, "coefficients": coefs, "rolling": json.loads(S.to_json(orient="records")),
           "rolling_stop": json.loads(P.to_json(orient="records")), "method_q": best_q, "method_p": best_p,
           "calibration_shift": {f"q{int(t*100):02d}": round(v, 3) for t, v in shift.items()},
           "base_rate_stop": round(lg["base"], 3),
           "n_train": int(len(d)), "taus": TAUS}
    (RESULTS / "prototype" / "risk.json").write_text(json.dumps(res, separators=(",", ":")))
    print(S[["window", "method", "forecasts", "cover_q05", "cover_q10", "cover_q50", "cover_q90", "cover_q95", "pinball_q05", "pinball_q50", "pinball_avg"]].to_string(index=False))
    print(P.to_string(index=False)); print("selected", best_q, best_p)
    print(C[["label", "q05", "q05_lo", "q05_hi", "q50", "logit", "logit_p"]].to_string(index=False))
    return res


if __name__ == "__main__":
    run()
