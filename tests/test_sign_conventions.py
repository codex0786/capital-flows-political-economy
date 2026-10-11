"""BPM6 sign conventions and the financial-account identity."""
import numpy as np


def test_net_equals_gross_difference(quarterly):
    q = quarterly.dropna(subset=["gross_in_usd", "gross_out_usd", "net_usd"])
    assert np.allclose(q.net_usd, q.gross_in_usd - q.gross_out_usd)


def test_fa_identity(annual):
    a = annual[annual.year.between(2015, 2025)].dropna(subset=["fa_balance_usd", "gross_in_usd", "gross_out_usd", "reserves_flow_usd"])
    implied = a.gross_out_usd - a.gross_in_usd + a.deriv_net_usd.fillna(0) + a.reserves_flow_usd
    resid_pct = 100 * (a.fa_balance_usd - implied).abs() / a.gdp_usd
    assert (resid_pct < 0.5).mean() > 0.99


def test_fa_balance_tracks_current_account(annual):
    """BPM6: CA + KA ~ FA (net lending), up to errors & omissions -> strongly correlated."""
    a = annual[annual.year.between(2015, 2025)].dropna(subset=["fa_balance_usd", "ca_balance_usd"])
    assert np.corrcoef(a.fa_balance_usd / a.gdp_usd, a.ca_balance_usd / a.gdp_usd)[0, 1] > 0.8


def test_brazil_known_magnitude(annual):
    """Brazil 2015 FDI liabilities ~ USD 65bn (IMF BOP; sanity check on units)."""
    v = annual.set_index(["iso3", "year"]).loc[("BRA", 2015), "fdi_in_usd"]
    assert 5e10 < v < 8e10
