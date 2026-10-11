"""Estimator checks on simulated data with known parameters."""
import numpy as np
import pandas as pd

from src.econometrics.models import _cluster_t, fit, holm, twfe_demean, wild_cluster_bootstrap


def sim(beta=1.5, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(60):
        a = rng.normal()
        for t in range(40):
            if rng.random() < 0.1:
                continue
            x = rng.normal() + 0.3 * a
            z = rng.normal()
            rows.append((f"C{i:02d}", f"{2015 + t // 4}Q{t % 4 + 1}", x, z, beta * x - 0.5 * z + a + 0.1 * t + rng.normal()))
    return pd.DataFrame(rows, columns=["iso3", "quarter", "x", "z", "y"])


def test_twfe_recovers_beta():
    res, _ = fit(sim(), "y", ["x"], ["z"])
    assert abs(res.params["x"] - 1.5) < 0.1


def test_demeaning_matches_linearmodels():
    d = sim()
    res, _ = fit(d, "y", ["x"], ["z"])
    d["_tid"] = d.quarter
    D = twfe_demean(d, ["y", "x", "z"])
    b, _ = _cluster_t(D[["x", "z"]].to_numpy(), D.y.to_numpy(), d.iso3.astype("category").cat.codes.to_numpy(), 0)
    assert abs(b - res.params["x"]) < 1e-6


def test_wild_bootstrap_size_under_null():
    """Under beta=0 the WCB p-value should not be systematically tiny."""
    ps = [wild_cluster_bootstrap(sim(beta=0.0, seed=s), "y", ["x"], ["z"], "x", reps=199)["wcb_p"] for s in range(5)]
    assert np.median(ps) > 0.05


def test_holm():
    p = pd.Series([0.01, 0.04, 0.03])
    assert np.allclose(holm(p).values, [0.03, 0.06, 0.06])
