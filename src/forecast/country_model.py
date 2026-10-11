"""Country analysis engine: driver attribution ("why"), narratives ("what happened") and
near-term forecasts ("outlook") for each economy in the quarterly sample.

Model (estimated separately for advanced and for emerging/developing economies, 2015Q1-2025Q4):

    y_it = a_i + rho * y_i,t-1 + b_i' G_t + g' D_i,y(t)-1 + d' E_it + e_it

  y  = outcome, annualised % of GDP (gross inflows, gross outflows or net flows), clipped at the
       pooled 1st/99th percentiles of 2015-2025
  G  = global push factors, standardised: VIX level, US policy rate level, change in the US
       10-year yield, % change in the broad dollar index, % change in Brent
  D  = previous-year domestic pull factors (IMF WEO): real growth, inflation (clipped to
       [-5, 50]), current account, fiscal balance, public debt (% GDP)
  E  = election quarter and the two quarters after an executive-relevant election
  b_i = country-specific global loadings, empirical-Bayes shrunk toward the group estimate

Attribution: with country fixed effects, fitted deviations from a country's own average split
exactly into contributions coef_j * (x_jit - mean_i(x_j)) plus momentum rho*(y_t-1 - mean),
and the residual is "unexplained".

Interpretation: contributions are associational (a statistical decomposition), not causal
effects. Forecasts are conditional on stated driver paths. A pseudo out-of-sample backtest
(estimate to 2023Q4, forecast 2024Q1-2025Q4) is reported against naive benchmarks.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.common import INTERIM, PROCESSED, RESULTS, get_logger
from src.econometrics.models import _cluster_t

log = get_logger("country_model")
OUT = RESULTS / "prototype"

GLOBAL = ["vix", "fed_funds", "d_ust10y", "usd_chg", "brent_chg"]
DOMESTIC = ["L_gdp_growth", "L_inflation_c", "L_ca_gdp", "L_fiscal_balance_gdp", "L_public_debt_gdp"]
POLITICAL = ["eq_k0", "eq_post12"]
CATEGORY = {
    "vix": "Global risk appetite", "fed_funds": "US interest rates", "d_ust10y": "US interest rates",
    "usd_chg": "US dollar", "brent_chg": "Oil prices", "L_gdp_growth": "Domestic growth",
    "L_inflation_c": "Domestic inflation", "L_ca_gdp": "External balance",
    "L_fiscal_balance_gdp": "Public finances", "L_public_debt_gdp": "Public finances",
    "eq_k0": "Elections", "eq_post12": "Elections", "lag": "Momentum",
}
CATS = ["Global risk appetite", "US interest rates", "US dollar", "Oil prices", "Domestic growth",
        "Domestic inflation", "External balance", "Public finances", "Elections", "Momentum", "Unexplained"]
OUTCOMES = {"gross_in": ("gross_inflows_gdp", "gross inflows"), "gross_out": ("gross_outflows_gdp", "gross outflows"),
            "net": ("net_flows_gdp", "net flows")}
EST_END, BT_END = "2025Q4", "2023Q4"
CURRENT_Q = "2026Q4"
GLOBAL_RAW = None  # quarter in progress on the retrieval date (2026-10-11)


# ------------------------------------------------------------------------------------- data
def qord(s):
    return pd.PeriodIndex(s, freq="Q").map(lambda p: p.ordinal)


def future_elections() -> pd.DataFrame:
    """Executive-relevant national contests 2026-2027 from the Wikipedia calendars (not yet
    corroborated: IDEA/V-Dem do not cover future contests)."""
    from src.features.elections import UPPER, EXCLUDE, WP_ALIASES  # noqa: F401
    from src.features.elections import collapse_rounds, wikipedia_events
    idea = pd.read_parquet(INTERIM / "idea_elections.parquet")
    meta = pd.read_parquet(INTERIM / "wb_meta.parquet")
    wp = wikipedia_events(meta, idea)
    wp = wp[(wp.chamber != "upper") & (wp.date >= "2026-01-01")]
    el = collapse_rounds(wp, ("iso3", "etype"), gap_days=90)
    v = pd.read_parquet(INTERIM / "vdem.parquet").dropna(subset=["v2x_ex_direlect"]).sort_values("year")
    de = v.groupby("iso3").v2x_ex_direlect.last()
    el["direlect"] = el.iso3.map(de)
    el["exec_relevant"] = np.where(el.direlect.isna(), np.nan,
                                   np.where(el.direlect >= 0.5, el.etype == "presidential", el.etype == "parliamentary")).astype(float)
    el["quarter"] = pd.PeriodIndex(el.date, freq="Q").astype(str)
    return el


def build_data() -> tuple[pd.DataFrame, dict]:
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet").sort_values(["iso3", "quarter"]).copy()
    Q["qo"] = qord(Q.quarter)
    main = Q.year.between(2015, 2025)
    clip = {}
    for k, (col, _) in OUTCOMES.items():
        lo, hi = np.nanpercentile(Q.loc[main, col].dropna(), [1, 99])
        clip[k] = (lo, hi)
        Q[f"y_{k}"] = Q[col].clip(lo, hi)
        prev = Q.groupby("iso3")[f"y_{k}"].shift()
        consecutive = Q.groupby("iso3").qo.diff() == 1
        Q[f"lag_{k}"] = prev.where(consecutive)
    g = pd.read_parquet(INTERIM / "global_factors.parquet").sort_values("quarter")
    g = g.rename(columns={"VIXCLS": "vix", "FEDFUNDS": "fed_funds", "DGS10": "ust10y", "DTWEXBGS": "usd", "POILBREUSDM": "brent"})
    g["d_ust10y"] = g.ust10y.diff()
    g["usd_chg"] = 100 * g.usd.pct_change()
    g["brent_chg"] = 100 * g.brent.pct_change()
    Q = Q.drop(columns=[c for c in ["vix", "fed_funds", "usd_broad_chg", "brent_chg", "ust10y"] if c in Q.columns])
    Q = Q.merge(g[["quarter"] + GLOBAL], on="quarter", how="left")
    gm = g[(g.quarter >= "2015Q1") & (g.quarter <= EST_END)]
    zstats = {c: (float(gm[c].mean()), float(gm[c].std())) for c in GLOBAL}
    for c in GLOBAL:
        Q[c] = (Q[c] - zstats[c][0]) / zstats[c][1]
    Q["L_inflation_c"] = Q.L_inflation.clip(-5, 50)
    # election dummies from the corroborated event-time variable
    Q["eq_k0"] = (Q.event_time_exec == 0).astype(float)
    Q["eq_post12"] = Q.event_time_exec.isin([1, 2]).astype(float)
    return Q, {"zstats": zstats, "clip": clip, "global_latest": g}


# ------------------------------------------------------------------------------------- estimation
def within(df, cols, ent="iso3"):
    return df[cols] - df.groupby(ent)[cols].transform("mean")


def estimate_group(df: pd.DataFrame, k: str) -> dict:
    y, lag = f"y_{k}", f"lag_{k}"
    X = GLOBAL + DOMESTIC + POLITICAL + [lag]
    d = df.dropna(subset=[y] + X).copy()
    D = within(d, [y] + X)
    g = d.iso3.astype("category").cat.codes.to_numpy()
    coefs, ses = {}, {}
    for j, c in enumerate(X):
        b, se = _cluster_t(D[X].to_numpy(), D[y].to_numpy(), g, j)
        coefs[c], ses[c] = b, se
    b = np.array([coefs[c] for c in X])
    resid = D[y].to_numpy() - D[X].to_numpy() @ b
    r2 = 1 - resid.var() / D[y].var()
    return {"coef": coefs, "se": ses, "X": X, "within_r2": float(r2), "n": len(d), "countries": d.iso3.nunique()}


def shrink_loadings(df: pd.DataFrame, k: str, grp: dict) -> dict:
    """Country-specific loadings on global factors, empirical-Bayes shrunk to the group value."""
    y, lag = f"y_{k}", f"lag_{k}"
    X = grp["X"]
    d = df.dropna(subset=[y] + X).copy()
    other = [c for c in X if c not in GLOBAL]
    part = d[y] - sum(grp["coef"][c] * d[c] for c in other)     # partial residual: global part + noise
    d["part"] = part
    raw, var = {}, {}
    for iso, c in d.groupby("iso3"):
        if len(c) < 20:
            continue
        Xc = (c[GLOBAL] - c[GLOBAL].mean()).to_numpy()
        yc = (c.part - c.part.mean()).to_numpy()
        XtX = Xc.T @ Xc
        if np.linalg.cond(XtX) > 1e8:
            continue
        bi = np.linalg.solve(XtX, Xc.T @ yc)
        res = yc - Xc @ bi
        s2 = res @ res / max(len(c) - len(GLOBAL) - 1, 1)
        raw[iso], var[iso] = bi, np.diag(np.linalg.inv(XtX)) * s2
    B, V = np.array(list(raw.values())), np.array(list(var.values()))
    gb = np.array([grp["coef"][c] for c in GLOBAL])
    tau2 = np.maximum(B.var(axis=0) - V.mean(axis=0), 1e-6)
    out = {}
    for iso in d.iso3.unique():
        if iso in raw:
            w = tau2 / (tau2 + var[iso])
            out[iso] = w * raw[iso] + (1 - w) * gb
        else:
            out[iso] = gb.copy()
    return out


def country_params(df, k, grp, load):
    """Country intercepts given group coefs and shrunk global loadings."""
    y, lag = f"y_{k}", f"lag_{k}"
    d = df.dropna(subset=[y] + grp["X"])
    means = d.groupby("iso3")[[y] + grp["X"]].mean()
    params = {}
    for iso, m in means.iterrows():
        b = dict(grp["coef"])
        for j, c in enumerate(GLOBAL):
            b[c] = float(load[iso][j])
        alpha = m[y] - sum(b[c] * m[c] for c in grp["X"])
        params[iso] = {"b": b, "alpha": float(alpha), "means": m.to_dict()}
    return params


def contributions(df, k, params, grp):
    y, lag = f"y_{k}", f"lag_{k}"
    rows = []
    for iso, c in df.groupby("iso3"):
        if iso not in params:
            continue
        p = params[iso]
        c = c.dropna(subset=[y] + grp["X"])
        for _, r in c.iterrows():
            contrib = {}
            for x in grp["X"]:
                key = "lag" if x == lag else x
                contrib[CATEGORY[key]] = contrib.get(CATEGORY[key], 0.0) + p["b"][x] * (r[x] - p["means"][x])
            fitted_dev = sum(contrib.values())
            contrib["Unexplained"] = (r[y] - p["means"][y]) - fitted_dev
            rows.append({"iso3": iso, "quarter": r.quarter, "year": int(r.year), "actual": r[y],
                         "mean": p["means"][y], "fitted": p["means"][y] + fitted_dev, **contrib})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------- forecasting
def path_drivers(Q, iso, start_q: int, H: int, weo: pd.DataFrame, fut_el: pd.DataFrame, zstats, glob):
    """Driver values for forecast quarters start_q+1..start_q+H (baseline assumptions)."""
    gl = glob.set_index("quarter")
    # the current quarter (2026Q4 at retrieval) is incomplete, so it is never treated as observed
    complete = gl.dropna(subset=["vix", "fed_funds", "usd_chg", "brent_chg", "d_ust10y"])
    last_full = complete.index[complete.index < CURRENT_Q].max()
    out = []
    w = weo[weo.iso3 == iso].set_index("year")
    ev = fut_el[(fut_el.iso3 == iso) & (fut_el.exec_relevant == 1)]
    evq = sorted(set(qord(ev.quarter))) if len(ev) else []
    # corroborated past elections too (for post-window carry-over)
    past = Q[(Q.iso3 == iso) & (Q.event_time_exec == 0)].qo.tolist()
    evq_all = sorted(set(evq) | set(past))
    for h in range(1, H + 1):
        qo = start_q + h
        qs = str(pd.Period(ordinal=qo, freq="Q"))
        yr = int(qs[:4])
        row = {"quarter": qs, "h": h}
        src = qs if (qs in gl.index and gl.loc[qs, ["vix", "fed_funds"]].notna().all() and qs <= last_full) else last_full
        for c in GLOBAL:
            v = gl.loc[src, c] if src == qs else (gl.loc[last_full, c] if c in ("vix", "fed_funds") else 0.0)
            row[c] = (v - zstats[c][0]) / zstats[c][1]
        row["global_source"] = "observed" if src == qs else f"held at {last_full}"
        prev = w.loc[yr - 1] if (yr - 1) in w.index else None
        row["L_gdp_growth"] = prev["NGDP_RPCH"] if prev is not None else np.nan
        row["L_inflation_c"] = float(np.clip(prev["PCPIPCH"], -5, 50)) if prev is not None else np.nan
        row["L_ca_gdp"] = prev["BCA_NGDPD"] if prev is not None else np.nan
        row["L_fiscal_balance_gdp"] = prev["GGXCNL_NGDP"] if prev is not None else np.nan
        row["L_public_debt_gdp"] = prev["GGXWDG_NGDP"] if prev is not None else np.nan
        row["weo_year"] = yr - 1
        rel = [qo - e for e in evq_all]
        row["eq_k0"] = float(0 in rel)
        row["eq_post12"] = float(any(r in (1, 2) for r in rel))
        row["election"] = "; ".join(f"{t} {d.date()}" for t, d, q in zip(ev.etype, ev.date, qord(ev.quarter)) if q == qo)
        out.append(row)
    return pd.DataFrame(out)


def forecast_country(Q, iso, k, p, grp, sigma, H, weo, fut_el, zstats, glob, start_q=None, actual_drivers=False):
    y, lag = f"y_{k}", f"lag_{k}"
    c = Q[(Q.iso3 == iso)].dropna(subset=[y]).sort_values("qo")
    if start_q is None:
        start_q = int(c.qo.max())
    last = c[c.qo == start_q]
    if last.empty:
        return None
    ylag = float(last[y].iloc[0])
    if actual_drivers:
        drv = Q[(Q.iso3 == iso) & (Q.qo > start_q) & (Q.qo <= start_q + H)].sort_values("qo").copy()
        drv["h"] = range(1, len(drv) + 1)
    else:
        drv = path_drivers(Q, iso, start_q, H, weo, fut_el, zstats, glob)
    rho = p["b"][lag]
    rows = []
    for _, r in drv.iterrows():
        x = {cname: r[cname] for cname in GLOBAL + DOMESTIC + POLITICAL}
        if any(pd.isna(v) for v in x.values()):
            # fall back to country mean for a missing driver (zero contribution)
            x = {cname: (p["means"][cname] if pd.isna(v) else v) for cname, v in x.items()}
        contrib = {}
        for cname, v in x.items():
            contrib[CATEGORY[cname]] = contrib.get(CATEGORY[cname], 0.0) + p["b"][cname] * (v - p["means"][cname])
        contrib["Momentum"] = rho * (ylag - p["means"][lag])
        yhat = p["means"][y] + sum(contrib.values())
        h = int(r["h"])
        sd = sigma * np.sqrt(sum(rho ** (2 * j) for j in range(h)))
        rows.append({"quarter": r["quarter"], "h": h, "mean": yhat, "sd": sd,
                     "lo80": yhat - 1.2816 * sd, "hi80": yhat + 1.2816 * sd, "lo95": yhat - 1.96 * sd, "hi95": yhat + 1.96 * sd,
                     "contrib": contrib, "election": r.get("election", ""), "global_source": r.get("global_source", "observed"),
                     "weo_year": r.get("weo_year")})
        ylag = yhat
    return rows


# ------------------------------------------------------------------------------------- narratives
def lc(cat):
    return cat[0].lower() + cat[1:] if not cat.startswith("US") else cat


def f1(x):
    return f"{x:+.1f}" if x is not None and not pd.isna(x) else "n/a"


def narrative(iso, name, group, k, label, C, p, fc, bt, A, ev, Q):
    c = C[C.iso3 == iso].sort_values("quarter")
    ann = c.groupby("year").agg(actual=("actual", "mean"), **{cat: (cat, "mean") for cat in CATS if cat in c.columns})
    mean_all = p["means"][f"y_{k}"]
    txt = {}
    # what happened
    a = ann.actual
    early, mid, late = a.loc[2015:2019].mean(), a.loc[2020:2021].mean(), a.loc[2022:2025].mean()
    peak, trough = a.idxmax(), a.idxmin()
    stops = Q[(Q.iso3 == iso) & (Q.sudden_stop == 1) & Q.year.between(2015, 2025)].quarter.tolist()
    def runs(qs):
        if not qs:
            return []
        o = sorted(pd.Period(q, freq="Q").ordinal for q in qs)
        out, s = [], o[0]
        for x, y_ in zip(o, o[1:] + [None]):
            if y_ != x + 1:
                out.append(f"{pd.Period(ordinal=s, freq='Q')}" + ("" if s == x else f"–{pd.Period(ordinal=x, freq='Q')}"))
                if y_ is not None:
                    s = y_
        return out
    happened = [f"Between 2015 and 2025, {name}'s {label} averaged {mean_all:.1f}% of GDP a year (quarterly flows annualised). "
                f"They averaged {early:.1f}% in 2015–19, {mid:.1f}% in 2020–21 and {late:.1f}% in 2022–25."]
    happened.append(f"The strongest year was {peak} ({a[peak]:.1f}%) and the weakest {trough} ({a[trough]:.1f}%).")
    if k == "gross_in" and A is not None:
        fd = A[A.iso3 == iso].set_index("year")
        def pct_gdp(col, yrs):
            sub = fd.reindex(list(yrs))
            return 100 * sub[col].sum() / sub.gdp_usd.sum() if sub.gdp_usd.sum() else np.nan
        parts = {lab: (pct_gdp(col, range(2015, 2020)), pct_gdp(col, range(2021, 2026)))
                 for col, lab in (("fdi_in_usd", "FDI"), ("port_in_usd", "portfolio"), ("oi_in_usd", "other investment"))}
        if all(pd.notna(v) for pair in parts.values() for v in pair):
            happened.append("By type, inflows moved from " + ", ".join(f"{lab} {a:.1f}%" for lab, (a, _) in parts.items())
                            + " of GDP in 2015–19 to " + ", ".join(f"{lab} {b:.1f}%" for lab, (_, b) in parts.items()) + " in 2021–25.")
    sr = runs(stops)
    if sr:
        happened.append(f"Sudden-stop episodes (a sharp, unusual fall in gross inflows) were flagged in {', '.join(sr)}.")
    if len(ev):
        happened.append(f"National elections in the event file: {', '.join(ev)}.")
    txt["happened"] = happened
    # why
    tot = {cat: c[cat].abs().mean() for cat in CATS if cat in c.columns}
    top = sorted([(v, k_) for k_, v in tot.items() if k_ != "Unexplained"], reverse=True)[:3]
    expl_share = 1 - (c["Unexplained"].var() / (c.actual - c["mean"]).var()) if (c.actual - c["mean"]).var() > 0 else np.nan
    share = max(0.0, 100 * expl_share) if pd.notna(expl_share) else 0.0
    why = [(f"The driver model accounts for about {share:.0f}%" if share >= 5 else "The driver model accounts for less than 5%")
           + f" of the quarter-to-quarter variation in {name}'s {label} around its own average. "
           "Most movement is country-specific: large one-off deals, bank and corporate balance-sheet moves, valuation and reporting changes. "
           "The modelled drivers explain direction and timing better than size."]
    why.append("Over the period, the largest systematic influences were " + ", ".join(f"{lc(k_)} (average swing {v:.1f} pp)" for v, k_ in top) + ".")
    gl = GLOBAL_RAW.copy()
    gl["year"] = gl.quarter.str[:4].astype(int)
    gy = gl.groupby("year")[["vix", "fed_funds"]].mean()
    an = A[A.iso3 == iso].set_index("year") if A is not None else pd.DataFrame()
    yrs = []
    for yr, r in ann.iterrows():
        dev = r.actual - mean_all
        drivers = sorted(((r[cat], cat) for cat in CATS if cat != "Unexplained" and cat in r.index), key=lambda t: -abs(t[0]))[:2]
        dtext = " and ".join(f"{lc(cat)} ({f1(v)} pp)" for v, cat in drivers if abs(v) >= 0.05)
        un = r.get("Unexplained", 0.0)
        ctx = []
        if yr in gy.index:
            ctx.append(f"Global backdrop: VIX averaged {gy.loc[yr, 'vix']:.0f} and the US policy rate {gy.loc[yr, 'fed_funds']:.2f}%.")
        if yr in an.index:
            pol = []
            if an.loc[yr, "exec_election"] == 1:
                pol.append("executive-relevant election" + (" (early)" if an.loc[yr, "early_exec_election"] == 1 else ""))
            if an.loc[yr, "exec_change"] == 1:
                pol.append("change of chief executive")
            if an.loc[yr, "rsui_event"] == 1:
                pol.append("major social unrest reported")
            if pol:
                ctx.append("Domestic politics: " + ", ".join(pol) + ".")
        yrs.append({"year": int(yr), "actual": round(float(r.actual), 2), "dev": round(float(dev), 2),
                    "text": f"{label.capitalize()} were {abs(dev):.1f} pp {'above' if dev >= 0 else 'below'} {name}'s average. "
                            + (f"Main modelled drivers: {dtext}. " if dtext else "No modelled driver stands out. ")
                            + f"Unexplained remainder: {f1(un)} pp.",
                    "context": " ".join(ctx)})
    txt["years"] = yrs
    txt["why"] = why
    # outlook
    if fc:
        m = np.mean([r["mean"] for r in fc])
        recent = fc[0].get("anchor_last4", c.actual.tail(4).mean())
        cdrv = {}
        for r in fc:
            for cat, v in r["contrib"].items():
                cdrv[cat] = cdrv.get(cat, 0) + v / len(fc)
        topf = sorted(cdrv.items(), key=lambda t: -abs(t[1]))[:3]
        els = [r["election"] for r in fc if r["election"]]
        out = [f"For {fc[0]['quarter']}–{fc[-1]['quarter']}, the central forecast averages {m:.1f}% of GDP, against {recent:.1f}% over the last four reported quarters and a 2015–25 average of {mean_all:.1f}%."]
        w = fc[0]["w"]
        out.append(f"It blends the driver model ({w['model']:.0%}), the recent level ({w['last4']:.0%}) and the long-run average ({w['mean']:.0%})"
                   + (", plus the modelled election effect" if w.get("election_overlay") else "")
                   + "; this combination had the lowest forecast error for this country group in the 2024–25 backtest.")
        model_avg = np.mean([r["model"] for r in fc])
        if w["model"] == 0:
            out.append(f"The driver model gets no weight in the central path because it did not improve accuracy in the backtest. On its own it would point to {model_avg:.1f}%, "
                       "with its largest pushes from " + ", ".join(f"{lc(cat)} ({f1(v)} pp)" for cat, v in topf) + ".")
        else:
            out.append("Within the driver model, the largest pushes are " + ", ".join(f"{lc(cat)} ({f1(v)} pp)" for cat, v in topf) + ".")
        if els:
            out.append(f"Scheduled executive-relevant election in the window: {'; '.join(els)} (date from the Wikipedia calendar, not yet corroborated).")
        width = fc[0]["hi80"] - fc[0]["lo80"]
        out.append(f"Uncertainty is large: the 80% interval for the next quarter spans {width:.1f} pp of GDP.")
        if bt:
            better = bt["rmse_model"] < bt["rmse_mean"]
            rel = bt["rmse_comb"] / bt["rmse_mean"] if bt["rmse_mean"] else 1
            verdict = ("The blend was clearly more accurate here." if rel < 0.95 else
                       "The blend and the simple average did about equally well here." if rel <= 1.05 else
                       "The blend did worse than the simple average here, so read the central path as a rough guide.")
            out.append(f"In the 2024–25 backtest, the blended forecast's error (RMSE) for {name} was {bt['rmse_comb']:.1f} pp of GDP, against {bt['rmse_mean']:.1f} pp for the country's average alone. " + verdict)
        txt["outlook"] = out
    return txt


# ------------------------------------------------------------------------------------- main
WGRID = [(m / 4, l / 4, (4 - m - l) / 4) for m in range(5) for l in range(5 - m)]


def run():
    Q, aux = build_data()
    global GLOBAL_RAW
    GLOBAL_RAW = aux["global_latest"][["quarter", "vix", "fed_funds"]].copy()
    GLOBAL_RAW = GLOBAL_RAW[(GLOBAL_RAW.quarter >= "2015Q1") & (GLOBAL_RAW.quarter <= EST_END)]
    weo = pd.read_parquet(INTERIM / "weo.parquet")
    fut = future_elections()
    A = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")
    pe = pd.read_csv(PROCESSED / "political_events.csv")
    meta = pd.read_csv(PROCESSED / "country_metadata.csv").set_index("iso3")
    est = Q[(Q.quarter >= "2015Q1") & (Q.quarter <= EST_END)]
    btset = Q[(Q.quarter >= "2015Q1") & (Q.quarter <= BT_END)]
    H, zs, glob = 4, aux["zstats"], aux["global_latest"]
    sq_bt = int(qord(pd.Series([BT_END]))[0])
    result = {"countries": {}, "models": {}, "backtest": {}, "assumptions": {
        "global": "Global factors (VIX, US policy rate, US 10-year yield, broad dollar, Brent) use FRED values for completed quarters. "
                  f"From {CURRENT_Q} on (in progress on the retrieval date) the VIX and the policy rate are held at their last complete-quarter level and changes in yields, the dollar and oil are set to zero.",
        "domestic": "Domestic drivers enter with a one-year lag from the IMF WEO: 2025 values (partly estimates) for 2026 quarters, 2026 projections for 2027 quarters.",
        "elections": "Upcoming executive-relevant elections come from the Wikipedia 2026–2027 national electoral calendars and are not yet corroborated by a second source.",
        "combination": "The central forecast blends the driver model, the average of the last four reported quarters and the 2015–25 country average. Weights are chosen per country group and outcome by minimising 2024–25 backtest error; interval widths come from the backtest errors at each horizon, scaled by the country's own volatility.",
        "zstats": {c: {"mean": round(m, 3), "sd": round(sd, 3)} for c, (m, sd) in zs.items()}}}
    for k, (col, label) in OUTCOMES.items():
        for gname in ["AE", "EMDE"]:
            Eg, Bg = est[est.country_group == gname], btset[btset.country_group == gname]
            grp = estimate_group(Eg, k)
            params = country_params(Eg, k, grp, shrink_loadings(Eg, k, grp))
            C = contributions(Eg, k, params, grp)
            result["models"][f"{k}_{gname}"] = {
                "within_r2": round(grp["within_r2"], 3), "n": grp["n"], "countries": int(grp["countries"]),
                "coef": {c: {"b": round(grp["coef"][c], 3), "se": round(grp["se"][c], 3)} for c in grp["X"]}}
            sig = {iso: float(C[C.iso3 == iso]["Unexplained"].std()) for iso in params}
            med_sig = float(np.median(list(sig.values())))
            # ---- backtest (estimate to 2023Q4; forecast 2024Q1-2025Q4 with realised drivers)
            gb = estimate_group(Bg, k)
            pb = country_params(Bg, k, gb, shrink_loadings(Bg, k, gb))
            bt_err = []
            for iso in params:
                if iso not in pb:
                    continue
                fb = forecast_country(Q, iso, k, pb[iso], gb, sig[iso], 8, weo, fut, zs, glob, start_q=sq_bt, actual_drivers=True)
                act = Q[(Q.iso3 == iso) & (Q.quarter > BT_END) & (Q.quarter <= EST_END)].set_index("quarter")[f"y_{k}"].dropna()
                hist = Bg[Bg.iso3 == iso][f"y_{k}"].dropna()
                if not fb or len(act) < 4 or hist.empty:
                    continue
                for r in fb:
                    if r["quarter"] in act.index:
                        bt_err.append({"iso3": iso, "quarter": r["quarter"], "h": min(r["h"], 4), "actual": act[r["quarter"]],
                                       "model": r["mean"], "mean": hist.mean(), "last4": hist.tail(4).mean(),
                                       "elec": r["contrib"].get("Elections", 0.0)})
            E = pd.DataFrame(bt_err)
            # candidate blends; optionally add the model's election component on top of the blend
            # (tested in the backtest and kept only if it lowers error)
            cands = [(w, e) for w in WGRID for e in (0.0, 1.0)]
            blend = lambda w, e: w[0]*E.model + w[1]*E.last4 + w[2]*E["mean"] + e*(1 - w[0])*E.elec
            best, eadd = min(cands, key=lambda c_: np.sqrt(((E.actual - blend(*c_)) ** 2).mean()))
            wdict = {"model": best[0], "last4": best[1], "mean": best[2], "election_overlay": eadd}
            E["comb"] = blend(best, eadd)
            no_overlay = min(WGRID, key=lambda w: np.sqrt(((E.actual - blend(w, 0.0)) ** 2).mean()))
            rmse_no_overlay = float(np.sqrt(((E.actual - blend(no_overlay, 0.0)) ** 2).mean()))
            E["scale"] = E.iso3.map(lambda i: sig[i] / med_sig)
            rmse_h = {h: float(np.sqrt((((E.actual - E.comb) / E.scale) ** 2)[E.h == h].mean())) for h in range(1, 5)}
            E["covered"] = [(abs(a - c) <= 1.2816 * rmse_h[h] * sc) for a, c, h, sc in zip(E.actual, E.comb, E.h, E.scale)]
            rm = lambda col: float(np.sqrt(((E.actual - E[col]) ** 2).mean()))
            per = E.groupby("iso3").apply(lambda d: pd.Series({c_: np.sqrt(((d.actual - d[c_]) ** 2).mean()) for c_ in ["model", "mean", "last4", "comb"]}))
            result["backtest"][f"{k}_{gname}"] = {
                "countries": int(E.iso3.nunique()), "quarters": "2024Q1–2025Q4", "weights": wdict,
                "rmse_model": round(rm("model"), 2), "rmse_mean": round(rm("mean"), 2), "rmse_last4": round(rm("last4"), 2),
                "rmse_comb": round(rm("comb"), 2), "rmse_best_without_election_overlay": round(rmse_no_overlay, 2), "share_comb_beats_mean": round(float((per["comb"] < per["mean"]).mean()), 2),
                "coverage80": round(float(E.covered.mean()), 2)}
            log.info("%s %s backtest %s", k, gname, result["backtest"][f"{k}_{gname}"])
            # ---- forecasts and narratives
            for iso, p in params.items():
                ci = C[C.iso3 == iso]
                hist_all = Q[(Q.iso3 == iso)].dropna(subset=[f"y_{k}"]).sort_values("qo")
                fc = forecast_country(Q, iso, k, p, grp, sig[iso], H, weo, fut, zs, glob)
                last4 = float(hist_all[f"y_{k}"].tail(4).mean())
                mu = float(p["means"][f"y_{k}"])
                for r in fc or []:
                    r["model"] = r["mean"]
                    r["mean"] = best[0]*r["model"] + best[1]*last4 + best[2]*mu + eadd*(1 - best[0])*r["contrib"].get("Elections", 0.0)
                    sd = rmse_h[min(r["h"], 4)] * sig[iso] / med_sig
                    r.update(sd=sd, lo80=r["mean"]-1.2816*sd, hi80=r["mean"]+1.2816*sd, lo95=r["mean"]-1.96*sd, hi95=r["mean"]+1.96*sd,
                             w=wdict, anchor_last4=last4, anchor_mean=mu)
                bt = None
                if not E.empty and iso in per.index:
                    d = E[E.iso3 == iso]
                    bt = {"rmse_model": float(per.loc[iso, "model"]), "rmse_mean": float(per.loc[iso, "mean"]),
                          "rmse_last4": float(per.loc[iso, "last4"]), "rmse_comb": float(per.loc[iso, "comb"]),
                          "path": [{"quarter": q, "actual": round(float(a_), 2), "forecast": round(float(c_), 2)}
                                   for q, a_, c_ in zip(d.quarter, d.actual, d.comb)]}
                name = meta.loc[iso, "country_name"]
                ev = pe[(pe.iso3 == iso) & pe.event_type.str.startswith("election") & (pe.exec_relevant == 1)
                        & pe.verification_status.isin(["wikipedia+idea+vdem", "two_sources"])]
                ev = ev[pd.to_datetime(ev.event_date).dt.year.between(2015, 2025)]
                evl = [f"{t.replace('election_', '')} {d_}" + (" (early)" if s_ == "early_rule_based" else "")
                       for t, d_, s_ in zip(ev.event_type, ev.event_date, ev.scheduled_or_unexpected)]
                nar = narrative(iso, name, gname, k, label, C, p, fc, bt, A, evl, Q)
                hist_q = Q[(Q.iso3 == iso) & (Q.quarter >= "2015Q1")].sort_values("quarter")
                cc = ci.set_index("quarter")
                rnd = lambda v: None if v is None or pd.isna(v) else round(float(v), 2)
                entry = result["countries"].setdefault(iso, {"name": name, "group": gname})
                entry[k] = {
                    "quarters": hist_q.quarter.tolist(), "actual": [rnd(v) for v in hist_q[f"y_{k}"]],
                    "partial": hist_q.partial_year.astype(int).tolist(),
                    "fitted": [rnd(cc.loc[q, "fitted"]) if q in cc.index else None for q in hist_q.quarter],
                    "mean": rnd(mu), "last4": rnd(last4),
                    "annual": [{"year": int(yr), **{cat: rnd(v) for cat, v in g_[CATS].mean().items()}, "actual": rnd(g_.actual.mean())}
                               for yr, g_ in ci.groupby("year")],
                    "forecast": [{"quarter": r["quarter"], "h": int(r["h"]), "mean": rnd(r["mean"]), "model": rnd(r["model"]),
                                  "lo80": rnd(r["lo80"]), "hi80": rnd(r["hi80"]), "lo95": rnd(r["lo95"]), "hi95": rnd(r["hi95"]),
                                  "election": r.get("election") or "", "global_source": r.get("global_source", ""),
                                  "contrib": {c_: rnd(v) for c_, v in r["contrib"].items()}} for r in (fc or [])],
                    "weights": wdict, "loadings": {c: round(float(p["b"][c]), 3) for c in GLOBAL},
                    "rho": round(float(p["b"][f"lag_{k}"]), 3), "sigma": rnd(sig[iso]), "backtest": bt, "narrative": nar,
                }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "country_analysis.json").write_text(json.dumps(result, separators=(",", ":"), default=lambda o: None))
    pd.DataFrame([{"outcome_group": k, **{x: v for x, v in d.items() if x != "weights"}, **{f"w_{x}": v for x, v in d["weights"].items()}}
                  for k, d in result["backtest"].items()]).to_csv(RESULTS / "tables" / "country_model_backtest.csv", index=False)
    return result


if __name__ == "__main__":
    r = run()
    print(pd.read_csv(RESULTS / "tables" / "country_model_backtest.csv").to_string(index=False))


# ------------------------------------------------------------------------------------- rolling backtest
ORIGINS = ["2019Q4", "2020Q4", "2021Q4", "2022Q4", "2023Q4", "2024Q4"]


def rolling_point_backtest():
    """Ex-ante rolling evaluation of the point forecasts, origins 2019Q4..2024Q4, 4 quarters ahead.

    At each origin the group models are re-estimated on data up to the origin. Global factors are frozen
    at their origin values (levels held, changes set to zero), as a forecaster would have had to do;
    lagged domestic fundamentals and election dates are those known for the forecast quarters.
    Blend weights at each origin are chosen from the errors of earlier origins only (real time);
    the first origin uses 50% recent level / 50% long-run average.
    """
    Q, aux = build_data()
    zs = aux["zstats"]
    rows = []
    for k in OUTCOMES:
        y = f"y_{k}"
        for gname in ["AE", "EMDE"]:
            for o in ORIGINS:
                oo = pd.Period(o, freq="Q").ordinal
                train = Q[(Q.quarter >= "2015Q1") & (Q.qo <= oo) & (Q.country_group == gname)]
                grp = estimate_group(train, k)
                params = country_params(train, k, grp, shrink_loadings(train, k, grp))
                for iso, p in params.items():
                    hist = train[train.iso3 == iso][y].dropna()
                    last = Q[(Q.iso3 == iso) & (Q.qo == oo)]
                    drv = Q[(Q.iso3 == iso) & (Q.qo > oo) & (Q.qo <= oo + 4)].sort_values("qo").copy()
                    if last.empty or pd.isna(last[y].iloc[0]) or drv.empty or hist.empty:
                        continue
                    for c in GLOBAL:   # freeze global factors at the origin
                        drv[c] = last[c].iloc[0] if c in ("vix", "fed_funds") else (0 - zs[c][0]) / zs[c][1]
                    ylag = float(last[y].iloc[0])
                    for h, (_, r) in enumerate(drv.iterrows(), start=1):
                        x = {c: (p["means"][c] if pd.isna(r[c]) else r[c]) for c in GLOBAL + DOMESTIC + POLITICAL}
                        dev = sum(p["b"][c] * (x[c] - p["means"][c]) for c in x)
                        dev += p["b"][f"lag_{k}"] * (ylag - p["means"][f"lag_{k}"])
                        yhat = p["means"][y] + dev
                        elec = sum(p["b"][c] * (x[c] - p["means"][c]) for c in POLITICAL)
                        rows.append({"outcome": k, "group": gname, "origin": o, "iso3": iso, "h": h, "quarter": r.quarter,
                                     "actual": r[y], "model": yhat, "mean": hist.mean(), "last4": hist.tail(4).mean(), "elec": elec})
                        ylag = yhat
    E = pd.DataFrame(rows).dropna(subset=["actual"])
    # real-time blend weights
    out = []
    for (k, gname), G in E.groupby(["outcome", "group"]):
        for o in ORIGINS:
            cur = G[G.origin == o].copy()
            past = G[G.origin < o]
            past = past[past.quarter <= o]   # outcomes known by the origin (YYYYQn strings sort chronologically)
            if len(past) < 50:
                w, e = (0.0, 0.5, 0.5), 0.0
            else:
                cands = [(w_, e_) for w_ in WGRID for e_ in (0.0, 1.0)]
                f = lambda w_, e_, d: w_[0]*d.model + w_[1]*d.last4 + w_[2]*d["mean"] + e_*(1 - w_[0])*d.elec
                w, e = min(cands, key=lambda c_: np.sqrt(((past.actual - f(*c_, past)) ** 2).mean()))
            cur["blend_rt"] = w[0]*cur.model + w[1]*cur.last4 + w[2]*cur["mean"] + e*(1 - w[0])*cur.elec
            cur["w_model"], cur["w_last4"], cur["w_mean"], cur["w_elec"] = w[0], w[1], w[2], e
            out.append(cur)
    E = pd.concat(out)
    E.to_csv(RESULTS / "tables" / "rolling_point_forecasts.csv", index=False)
    rm = lambda d, c: float(np.sqrt(((d.actual - d[c]) ** 2).mean()))
    S = []
    for (k, gname, o), d in E.groupby(["outcome", "group", "origin"]):
        S.append({"outcome": k, "group": gname, "origin": o, "target_year": int(o[:4]) + 1, "forecasts": len(d),
                  **{f"rmse_{c}": round(rm(d, c), 2) for c in ["model", "mean", "last4", "blend_rt"]}})
    for (k, gname), d in E.groupby(["outcome", "group"]):
        S.append({"outcome": k, "group": gname, "origin": "all", "target_year": "2020–2025", "forecasts": len(d),
                  **{f"rmse_{c}": round(rm(d, c), 2) for c in ["model", "mean", "last4", "blend_rt"]}})
    S = pd.DataFrame(S)
    S.to_csv(RESULTS / "tables" / "rolling_point_summary.csv", index=False)
    return S
