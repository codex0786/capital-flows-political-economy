"""Panel keys, period ranges, partial-year flags and election coding."""
import pandas as pd

from src.features.elections import collapse_rounds


def test_unique_keys(annual, quarterly):
    assert not annual.duplicated(["iso3", "year"]).any()
    assert not quarterly.duplicated(["iso3", "quarter"]).any()


def test_partial_year_flag(annual, quarterly):
    assert (annual.loc[annual.year == 2026, "partial_year"] == 1).all()
    assert (quarterly.loc[quarterly.year <= 2025, "partial_year"] == 0).all()


def test_quarter_format(quarterly):
    assert quarterly.quarter.str.fullmatch(r"\d{4}Q[1-4]").all()


def test_windows_are_binary(quarterly):
    for c in ["elec_exec_pre", "elec_exec_post"]:
        assert set(quarterly[c].unique()) <= {0, 1}


def test_collapse_rounds_runoff():
    e = pd.DataFrame({"iso3": ["BRA"] * 3, "etype": ["presidential"] * 3, "chamber": ["executive"] * 3,
                      "date": pd.to_datetime(["2022-10-02", "2022-10-30", "2026-10-04"])})
    out = collapse_rounds(e, ("iso3", "etype"), gap_days=90)
    assert len(out) == 2 and out.runoff.tolist() == [1, 0]
    assert out.date.iloc[0] == pd.Timestamp("2022-10-02")


def test_known_elections_present():
    pe = pd.read_csv("data/processed/political_events.csv")
    keys = set(zip(pe.iso3, pe.event_date))
    for k in [("GBR", "2019-12-12"), ("ISR", "2019-09-17"), ("TUR", "2015-11-01"), ("BRA", "2022-10-02"), ("JPN", "2026-02-08")]:
        assert k in keys, k
