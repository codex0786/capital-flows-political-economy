"""Missing values are never zero-filled; aggregates require complete components."""


def test_aggregate_missing_when_component_missing(quarterly):
    q = quarterly
    incomplete = q[["fdi_in_usd", "port_in_usd", "oi_in_usd"]].isna().any(axis=1)
    assert q.loc[incomplete, "gross_in_usd"].isna().all()


def test_no_artificial_zero_inflation(quarterly):
    """Exact zeros in gross inflows should be rare (they would signal zero-filling)."""
    assert (quarterly.gross_in_usd == 0).mean() < 0.005


def test_core_coverage(quarterly):
    m = quarterly[quarterly.year.between(2015, 2025)]
    assert m.gross_inflows_gdp.notna().mean() > 0.95
