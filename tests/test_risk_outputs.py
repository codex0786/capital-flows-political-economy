"""Sanity checks on the country-tool outputs (run after the pipeline)."""
import json

import pytest

from src.common import RESULTS

P = RESULTS / "prototype"
pytestmark = pytest.mark.skipif(not (P / "risk.json").exists(), reason="country tool not built")


def test_quantiles_ordered():
    r = json.loads((P / "risk.json").read_text())
    for iso, c in r["countries"].items():
        for k in ("gross_in", "net"):
            if k in c:
                q = list(c[k]["quantiles"].values())
                assert q == sorted(q), (iso, k)


def test_probabilities_in_range():
    r = json.loads((P / "risk.json").read_text())
    for c in r["countries"].values():
        for p in c.get("p_stop", {}).values():
            assert 0 <= p <= 1


def test_heldout_windows_disjoint():
    r = json.loads((P / "risk.json").read_text())
    sel = r["selection"]
    assert sel["select_window"].endswith("2022Q4") and sel["test_window"].startswith("origins 2023Q1")


def test_financing_gap_nonnegative_and_exemptions():
    v = json.loads((P / "vulnerability.json").read_text())["countries"]
    for iso, c in v.items():
        b = c["buffers"]
        if b["gap_pp"] is not None:
            assert b["gap_pp"] >= 0
    assert v["USA"]["buffers"]["reserve_tests_apply"] is False
    assert v["GRC"]["indicators"]["reserves_months"]["status"] == "n/a"


def test_early_warning_scores_bounded():
    e = json.loads((P / "early_warning.json").read_text())
    for d in e["definitions"].values():
        for c in d["countries"].values():
            if c["score"] is not None:
                assert 0 <= c["score"] <= 1
