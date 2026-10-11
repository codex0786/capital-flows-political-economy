"""Panel estimators and inference used by the analysis scripts.

All regressions are two-way fixed-effects OLS (entity and time effects) estimated with
``linearmodels.PanelOLS``. Every result records its specification (formula, sample size,
countries, FE, covariance) so tables can be regenerated and audited.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from scipy import stats

COV_LABEL = {
    "cluster_country": "clustered by country",
    "driscoll_kraay": "Driscoll-Kraay (Bartlett, bw=4)",
    "twoway_cluster": "two-way clustered (country, period)",
}


@dataclass
class Result:
    outcome: str
    term: str
    coef: float
    se: float
    t: float
    p: float
    ci_low: float
    ci_high: float
    nobs: int
    n_countries: int
    n_periods: int
    cov: str
    spec: str
    sample: str
    controls: str
    extra: dict = field(default_factory=dict)

    def row(self):
        d = asdict(self)
        d.update(d.pop("extra"))
        return d


def _prep(df: pd.DataFrame, time_col: str) -> pd.DataFrame:
    d = df.copy()
    if time_col == "quarter":
        d["_t"] = pd.PeriodIndex(d.quarter, freq="Q").to_timestamp()
    else:
        d["_t"] = pd.to_datetime(d[time_col].astype(int).astype(str) + "-01-01")
    return d.set_index(["iso3", "_t"])


def fit(df: pd.DataFrame, y: str, terms: list[str], controls: list[str], time_col: str = "quarter",
        cov: str = "cluster_country", time_effects: bool = True, entity_effects: bool = True,
        other_effects: pd.DataFrame | None = None):
    """Fit Y on terms+controls with FE; drop rows with missing values (listwise)."""
    cols = [y] + terms + controls
    d = _prep(df.dropna(subset=cols), time_col)
    exog = d[terms + controls].astype(float)
    mod = PanelOLS(d[y].astype(float), exog, entity_effects=entity_effects,
                   time_effects=time_effects, other_effects=other_effects, drop_absorbed=True,
                   check_rank=False)
    if cov == "cluster_country":
        res = mod.fit(cov_type="clustered", cluster_entity=True)
    elif cov == "twoway_cluster":
        res = mod.fit(cov_type="clustered", cluster_entity=True, cluster_time=True)
    elif cov == "driscoll_kraay":
        res = mod.fit(cov_type="kernel", kernel="bartlett", bandwidth=4)
    else:
        raise ValueError(cov)
    return res, d


def extract(res, d, y, term, cov, spec, sample, controls, time_col="quarter", **extra) -> Result:
    b, se = float(res.params[term]), float(res.std_errors[term])
    tval = b / se
    # t reference with G-1 df for clustered errors (conservative with ~100 clusters)
    g = d.index.get_level_values(0).nunique()
    dfree = g - 1 if cov != "driscoll_kraay" else res.df_resid
    p = 2 * stats.t.sf(abs(tval), dfree)
    crit = stats.t.ppf(0.975, dfree)
    return Result(y, term, b, se, tval, p, b - crit * se, b + crit * se, int(res.nobs), g,
                  d.index.get_level_values(1).nunique(), COV_LABEL[cov], spec, sample,
                  ",".join(controls) if controls else "none", extra)


# --------------------------------------------------------------------------- two-way demeaning
def twfe_demean(df: pd.DataFrame, cols: list[str], ent="iso3", tim="_tid", tol=1e-10, maxit=500) -> pd.DataFrame:
    """Alternating projections to sweep out entity and time means (unbalanced panels)."""
    X = df[cols].to_numpy(dtype=float).copy()
    e = df[ent].astype("category").cat.codes.to_numpy()
    t = df[tim].astype("category").cat.codes.to_numpy()
    ne, nt = e.max() + 1, t.max() + 1
    ce, ct = np.bincount(e, minlength=ne), np.bincount(t, minlength=nt)
    for _ in range(maxit):
        old = X.copy()
        for j in range(X.shape[1]):
            X[:, j] -= (np.bincount(e, X[:, j], ne) / ce)[e]
            X[:, j] -= (np.bincount(t, X[:, j], nt) / ct)[t]
        if np.max(np.abs(X - old)) < tol:
            break
    return pd.DataFrame(X, columns=cols, index=df.index)


def _cluster_t(Xd, yd, groups, k):
    XtX_inv = np.linalg.pinv(Xd.T @ Xd)
    b = XtX_inv @ Xd.T @ yd
    u = yd - Xd @ b
    G = groups.max() + 1
    S = np.zeros((G, Xd.shape[1]))
    np.add.at(S, groups, Xd * u[:, None])
    meat = S.T @ S
    n, p = Xd.shape
    adj = G / (G - 1) * (n - 1) / (n - p)
    V = adj * XtX_inv @ meat @ XtX_inv
    return b[k], np.sqrt(V[k, k])


def wild_cluster_bootstrap(df: pd.DataFrame, y: str, terms: list[str], controls: list[str], target: str,
                           time_col="quarter", reps=999, seed=20261011) -> dict:
    """Restricted wild cluster bootstrap-t (WCR, Rademacher) for H0: beta_target = 0.

    Fixed effects are swept out by two-way demeaning once (they are invariant to the
    bootstrap DGP because the null model includes them). Returns p-value and the original t.
    """
    cols = [y] + terms + controls
    d = df.dropna(subset=cols).copy()
    d["_tid"] = d[time_col].astype(str)
    D = twfe_demean(d, cols)
    X = D[terms + controls].to_numpy()
    yv = D[y].to_numpy()
    k = (terms + controls).index(target)
    groups = d["iso3"].astype("category").cat.codes.to_numpy()
    b0, se0 = _cluster_t(X, yv, groups, k)
    t0 = b0 / se0
    Xr = np.delete(X, k, axis=1)
    br = np.linalg.lstsq(Xr, yv, rcond=None)[0]
    fitted_r = Xr @ br
    u_r = yv - fitted_r
    rng = np.random.default_rng(seed)
    G = groups.max() + 1
    tb = np.empty(reps)
    for r in range(reps):
        w = rng.choice([-1.0, 1.0], size=G)[groups]
        ystar = fitted_r + u_r * w
        bb, sb = _cluster_t(X, ystar, groups, k)
        tb[r] = bb / sb
    p = (np.sum(np.abs(tb) >= abs(t0)) + 1) / (reps + 1)
    return {"wcb_p": float(p), "wcb_t": float(t0), "wcb_reps": reps, "wcb_seed": seed}


# --------------------------------------------------------------------------- marginal effects
def marginal_effect(res, base: str, inter: str, values: dict) -> pd.DataFrame:
    """dY/dU = b_base + b_inter * m evaluated at m in ``values`` (label -> centred value)."""
    V = res.cov
    rows = []
    for label, m in values.items():
        est = res.params[base] + res.params[inter] * m
        var = V.loc[base, base] + m ** 2 * V.loc[inter, inter] + 2 * m * V.loc[base, inter]
        se = np.sqrt(var)
        rows.append({"at": label, "moderator_centred": m, "effect": est, "se": se,
                     "ci_low": est - 1.96 * se, "ci_high": est + 1.96 * se})
    return pd.DataFrame(rows)


def holm(pvals: pd.Series) -> pd.Series:
    """Holm-Bonferroni adjusted p-values (step-down, monotone)."""
    order = pvals.sort_values()
    m = len(order)
    adj = np.maximum.accumulate([(m - i) * p for i, p in enumerate(order.values)])
    return pd.Series(np.minimum(adj, 1.0), index=order.index).reindex(pvals.index)


# --------------------------------------------------------------------------- event study
def event_dummies(df: pd.DataFrame, etcol: str, K: int, ref: int) -> tuple[pd.DataFrame, list[str]]:
    d = df.copy()
    names = []
    for k in range(-K, K + 1):
        if k == ref:
            continue
        n = f"ev_m{abs(k)}" if k < 0 else f"ev_p{k}"
        d[n] = (d[etcol] == k).astype(float)
        names.append(n)
    return d, names


def k_of(name: str) -> int:
    return -int(name[4:]) if name.startswith("ev_m") else int(name[4:])
