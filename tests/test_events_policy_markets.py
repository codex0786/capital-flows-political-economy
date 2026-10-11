"""Checks on the crisis/event database and the policy and market panels (run after the pipeline)."""
import json

import pandas as pd
import pytest

from src.common import PROCESSED, RESULTS

E = PROCESSED / "crisis_events.csv"
pytestmark = pytest.mark.skipif(not E.exists(), reason="event database not built")

TYPES = {"banking_crisis", "sovereign_default_private", "official_arrears", "other_private_arrears", "local_currency_default",
         "currency_crisis", "imf_financing", "high_inflation", "capital_control_tightening", "capital_control_easing"}


def events():
    return pd.read_csv(E)


def test_event_schema_and_types():
    d = events()
    assert {"iso3", "event_type", "start", "start_year", "end_year", "source"} <= set(d.columns)
    assert set(d.event_type) <= TYPES
    assert d.iso3.str.fullmatch(r"[A-Z]{3}").all()
    assert (d.end_year >= d.start_year).all()
    assert d.source.notna().all()


def test_known_episodes_present():
    d = events()
    has = lambda iso, t, y: ((d.iso3 == iso) & (d.event_type == t) & (d.start_year <= y) & (d.end_year >= y)).any()
    assert has("LKA", "sovereign_default_private", 2022)    # 2022 default
    assert has("ARG", "imf_financing", 2018)                # 2018 Stand-By
    assert has("TUR", "currency_crisis", 2022)              # lira 2021-22 (annual averages: 2021 rise was 27%, below the 30% rule)
    assert has("UKR", "banking_crisis", 2014)
    assert has("RUS", "sovereign_default_private", 2022)    # unnamed BoC-BoE block mapped to RUS


def test_no_spurious_uruguay_default():
    d = events()
    assert not ((d.iso3 == "URY") & (d.event_type == "sovereign_default_private")).any()


def test_policy_and_market_panels():
    p = pd.read_parquet(PROCESSED / "policy_quarterly.parquet")
    assert not p.duplicated(["iso3", "quarter"]).any()
    m = pd.read_parquet(PROCESSED / "market_monthly.parquet")
    assert not m.duplicated(["iso3", "month"]).any()
    assert (m.fx.dropna() > 0).all()
    assert m.yld.dropna().between(-5, 200).all()
    d = pd.read_parquet(PROCESSED / "market_daily.parquet")
    assert d.iso3.nunique() == 12 and (d.fx > 0).all()


def test_analysis_outputs():
    t = RESULTS / "tables"
    a = pd.read_csv(t / "event_attribution.csv")
    assert a.share_largest_decile.between(0, 1).all()
    pol = pd.read_csv(t / "policy_lever_associations.csv")
    assert pol.p.between(0, 1).all()
    daily = json.loads((t / "market_elections_daily.json").read_text())
    assert daily["n"] > 0 and len(daily["mean"]) == len(daily["days"])
