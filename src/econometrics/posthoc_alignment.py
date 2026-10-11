"""POST-HOC (not pre-registered) alignment analysis with Arakelyan & Evdokimova (2025, IMF WP/25/243).

Added on 2026-10-11 AFTER the protocol-v1.0 results had been seen; logged in
report/protocol_changelog.md. Purpose: determine whether differences between our null
pre-election result and the IMF paper reflect (i) the outcome definition (they remove
official-sector other-investment liabilities: "gross private inflows"), (ii) the window
(they use the election quarter itself, plus 1-2 quarters before/after), or (iii) the sample
(they study 38 emerging markets). All results here are EXPLORATORY.

Private gross inflows = gross inflows - official other-investment liabilities, where official =
central bank (S121) and general government (S13) liabilities in deposits, loans, trade credit and
other payables, plus SDR allocations. Instruments not published for a country are treated as not
reported (sum over available series); ``official_instruments`` records how many were available.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import RAW, TABLES, get_logger
from src.econometrics.models import fit, wild_cluster_bootstrap
from src.econometrics.run_analysis import CTRL, quarterly

log = get_logger("posthoc")


def official_oi() -> pd.DataFrame:
    d = pd.read_csv(RAW / "imf_bop" / "imf_bop_official_oi_by_instrument_Q_raw.csv",
                    usecols=["COUNTRY", "INDICATOR", "UNIT", "TIME_PERIOD", "OBS_VALUE"])
    d = d[(d.UNIT == "USD") & d.TIME_PERIOD.notna()]
    w = d.pivot_table(index=["COUNTRY", "TIME_PERIOD"], columns="INDICATOR", values="OBS_VALUE", aggfunc="first")
    out = pd.DataFrame({
        "official_oi_usd": w.sum(axis=1, min_count=1),
        "official_instruments": w.drop(columns=["O_F12_S1N"], errors="ignore").notna().sum(axis=1),
    }).reset_index().rename(columns={"COUNTRY": "iso3"})
    out["quarter"] = out.TIME_PERIOD.str.replace("-", "")
    return out.drop(columns="TIME_PERIOD")


def event_windows(Q: pd.DataFrame) -> pd.DataFrame:
    """IMF-style dummies: election quarter (k=0), 1-2 quarters before, 1-2 after."""
    et = Q.event_time_exec
    Q = Q.copy()
    Q["eq_k0"] = (et == 0).astype(float)
    Q["eq_pre12"] = et.isin([-2, -1]).astype(float)
    Q["eq_post12"] = et.isin([1, 2]).astype(float)
    return Q


def main():
    Q = quarterly().merge(official_oi(), on=["iso3", "quarter"], how="left")
    Q["private_in_usd"] = Q.gross_in_usd - Q.official_oi_usd
    Q["private_inflows_gdp"] = 100 * 4 * Q.private_in_usd / Q.gdp_usd
    lo, hi = np.nanpercentile(Q.private_inflows_gdp.dropna(), [1, 99])
    Q["private_inflows_gdp_w"] = Q.private_inflows_gdp.clip(lo, hi)
    Q = event_windows(Q)
    pv = Q.drop_duplicates("iso3").set_index("iso3").wgi_pv_2014
    Q["low_pv"] = Q.iso3.map((pv <= pv.quantile(0.25)).astype(float))
    for t in ["eq_k0", "eq_pre12", "eq_post12"]:
        Q[f"{t}_x_lowpv"] = Q[t] * Q.low_pv
    meta = pd.read_csv(TABLES.parents[1] / "data" / "processed" / "country_metadata.csv").set_index("iso3")
    Q["emde_pre_euro"] = Q.iso3.map(meta.country_group_alt_pre_euro) == "EMDE"

    terms = ["eq_pre12", "eq_k0", "eq_post12"]
    rows = []
    specs = [
        ("all economies, gross inflows (our outcome)", Q, "gross_inflows_gdp_w", terms),
        ("all economies, private gross inflows", Q, "private_inflows_gdp_w", terms),
        ("EMDE, gross inflows", Q[Q.emde_pre_euro], "gross_inflows_gdp_w", terms),
        ("EMDE, private gross inflows (closest to IMF WP/25/243)", Q[Q.emde_pre_euro], "private_inflows_gdp_w", terms),
        ("EMDE, private inflows x low political stability (bottom quartile WGI PV 2014)", Q[Q.emde_pre_euro],
         "private_inflows_gdp_w", terms + [f"{t}_x_lowpv" for t in terms]),
        ("all economies, private inflows x low political stability", Q, "private_inflows_gdp_w",
         terms + [f"{t}_x_lowpv" for t in terms]),
    ]
    for label, df, y, tt in specs:
        res, d = fit(df, y, tt, CTRL, cov="cluster_country")
        wcb = wild_cluster_bootstrap(df, y, tt, CTRL, "eq_k0", reps=999, seed=20261011)
        sd_within = (d[y] - d.groupby(level=0)[y].transform("mean")).std()
        for t in tt:
            rows.append({"specification": label, "outcome": y, "term": t, "coef": res.params[t],
                         "se": res.std_errors[t], "p": res.pvalues[t],
                         "wcb_p": wcb["wcb_p"] if t == "eq_k0" else np.nan,
                         "ci_low": res.params[t] - 1.96 * res.std_errors[t],
                         "ci_high": res.params[t] + 1.96 * res.std_errors[t],
                         "within_sd_outcome": sd_within, "nobs": int(res.nobs),
                         "n_countries": d.index.get_level_values(0).nunique(), "status": "POST-HOC / EXPLORATORY"})
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "posthoc_imf_alignment.csv", index=False)
    cov = Q[Q.year.between(2015, 2025)]
    pd.DataFrame([{
        "share_quarters_private_inflows_available": cov.private_inflows_gdp.notna().mean(),
        "countries_with_private_inflows": cov.loc[cov.private_inflows_gdp.notna(), "iso3"].nunique(),
        "median_official_instruments": cov.official_instruments.median(),
        "median_official_share_of_gross_inflows_abs": (cov.official_oi_usd.abs() / cov.gross_in_usd.abs()).median(),
    }]).to_csv(TABLES / "posthoc_private_inflows_coverage.csv", index=False)
    log.info("post-hoc alignment written")
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()


def placebo_k0(draws: int = 1000, seed: int = 20261011):
    """Calendar-shift placebo for the post-hoc EMDE election-quarter coefficient.

    Each country's executive-relevant election quarters are shifted by +/-8-12 quarters
    (wrapped within the sample window); the k=0 / pre / post dummies are rebuilt and the
    model re-estimated. Two-sided placebo p = share of |placebo coef| >= |actual coef|.
    """
    from src.econometrics.robustness import _fast_coef, election_events
    Q = quarterly().merge(official_oi(), on=["iso3", "quarter"], how="left")
    Q["private_inflows_gdp"] = 100 * 4 * (Q.gross_in_usd - Q.official_oi_usd) / Q.gdp_usd
    lo, hi = np.nanpercentile(Q.private_inflows_gdp.dropna(), [1, 99])
    Q["private_inflows_gdp_w"] = Q.private_inflows_gdp.clip(lo, hi)
    meta = pd.read_csv(TABLES.parents[1] / "data" / "processed" / "country_metadata.csv").set_index("iso3")
    Q = Q[Q.iso3.map(meta.country_group_alt_pre_euro) == "EMDE"]
    ev = election_events(lambda e: e.verification_status.isin(["wikipedia+idea+vdem", "two_sources"]) & (e.exec_relevant == 1))
    ev = ev[["iso3", "quarter"]].drop_duplicates()
    qs = sorted(Q.quarter.unique())
    qpos = {q: i for i, q in enumerate(qs)}
    qi = {q: pd.Period(q, freq="Q").ordinal for q in qs}

    def dummies(df, events):
        e = events[events.quarter.isin(qpos)]
        evq = e.groupby("iso3").quarter.apply(lambda s: [qi[x] for x in s]).to_dict()
        out = df.copy()
        rel = [min((qi[q] - x for x in evq.get(c, [])), key=abs, default=99) for c, q in zip(out.iso3, out.quarter)]
        rel = np.array(rel)
        out["eq_k0"], out["eq_pre12"], out["eq_post12"] = (rel == 0) * 1.0, np.isin(rel, [-2, -1]) * 1.0, np.isin(rel, [1, 2]) * 1.0
        return out

    rng = np.random.default_rng(seed)
    rows = []
    for y in ["gross_inflows_gdp_w", "private_inflows_gdp_w"]:
        base = Q.dropna(subset=[y] + CTRL).copy()
        base["_tid"] = base.quarter
        actual = _fast_coef(dummies(base, ev), y, ["eq_k0", "eq_pre12", "eq_post12"], CTRL)[0]
        pl = []
        for _ in range(draws):
            shift = {c: int(rng.integers(8, 13)) * rng.choice([-1, 1]) for c in ev.iso3.unique()}
            pev = ev[ev.quarter.isin(qpos)].copy()
            pev["quarter"] = [qs[(qpos[q] + shift[c]) % len(qs)] for c, q in zip(pev.iso3, pev.quarter)]
            pl.append(_fast_coef(dummies(base, pev), y, ["eq_k0", "eq_pre12", "eq_post12"], CTRL)[0])
        pl = np.array(pl)
        rows.append({"outcome": y, "sample": "EMDE (pre-euro classification)", "actual_k0": actual,
                     "placebo_mean": pl.mean(), "placebo_sd": pl.std(), "placebo_p_two_sided": float((np.abs(pl) >= abs(actual)).mean()),
                     "draws": draws, "status": "POST-HOC / EXPLORATORY"})
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "posthoc_placebo_k0.csv", index=False)
    print(out.round(4).to_string(index=False))


def seasonality_check():
    """Country x quarter-of-year fixed effects (absorbing country-specific seasonality, which
    could coincide with fixed election calendars) plus quarter FE; clustered by country."""
    from scipy import stats

    from src.econometrics.models import _cluster_t, twfe_demean
    Q = quarterly().merge(official_oi(), on=["iso3", "quarter"], how="left")
    Q["private_inflows_gdp"] = 100 * 4 * (Q.gross_in_usd - Q.official_oi_usd) / Q.gdp_usd
    lo, hi = np.nanpercentile(Q.private_inflows_gdp.dropna(), [1, 99])
    Q["private_inflows_gdp_w"] = Q.private_inflows_gdp.clip(lo, hi)
    Q = event_windows(Q)
    meta = pd.read_csv(TABLES.parents[1] / "data" / "processed" / "country_metadata.csv").set_index("iso3")
    Q["emde"] = Q.iso3.map(meta.country_group_alt_pre_euro) == "EMDE"
    Q["iso_season"] = Q.iso3 + "_" + Q.quarter.str[-1]
    terms = ["eq_pre12", "eq_k0", "eq_post12"]
    rows = []
    for label, df in (("EMDE", Q[Q.emde]), ("all", Q)):
        for y in ["gross_inflows_gdp_w", "private_inflows_gdp_w"]:
            for fe in ("country", "country_x_season"):
                d = df.dropna(subset=[y] + terms + CTRL).copy()
                d["_tid"] = d.quarter
                ent = "iso3" if fe == "country" else "iso_season"
                D = twfe_demean(d, [y] + terms + CTRL, ent=ent)
                g = d.iso3.astype("category").cat.codes.to_numpy()
                b, se = _cluster_t(D[terms + CTRL].to_numpy(), D[y].to_numpy(), g, 1)
                G = g.max() + 1
                rows.append({"sample": label, "outcome": y, "entity_fe": fe, "term": "eq_k0", "coef": b, "se": se,
                             "p": 2 * stats.t.sf(abs(b / se), G - 1), "nobs": len(d), "status": "POST-HOC / EXPLORATORY"})
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "posthoc_seasonality_check.csv", index=False)
    print(out.round(3).to_string(index=False))
