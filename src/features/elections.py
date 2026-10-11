"""Election event coding.

Sources: Wikipedia national electoral calendars (event list, exact dates), International
IDEA Voter Turnout Database (corroboration; long history for term lengths) and V-Dem v16
election-type indicators (corroboration of year and type). IDEA alone is insufficient:
about half of its post-2013 records carry a year-only placeholder date (YYYY-01-01).

Coding rules (fixed in research protocol v1.0, before any regression was estimated):

1. Rounds or phases of the same contest within 90 days are one election; the event date is
   the first round / first polling phase and ``runoff`` = 1 if a later round exists.
2. Upper-chamber-only contests, vice-presidential, indirect and referendum items are
   excluded from the event list; concurrent presidential and parliamentary contests are
   separate rows that share an event quarter.
3. ``exec_relevant`` = presidential election in countries where V-Dem codes the chief
   executive as directly elected (v2x_ex_direlect == 1 in the election year, else the
   nearest year), otherwise parliamentary election. This approximates the election that
   determines who holds executive power.
4. ``early`` (snap) election: the interval since the previous same-type contest is more
   than ``early_election_rule_months`` shorter than the modal term length, where the modal
   term is the most common gap between election years in V-Dem for 1990-2014 (fallback
   1960-2014; see ``term_basis``). The first contest after 2010 in each series has no
   previous date in the event list and is left unclassified (NaN). This is a rule-based classification, not a
   legal determination of whether an election was constitutionally early.
5. ``verification``: number of independent sources recording the contest in that year
   (Wikipedia, IDEA, V-Dem). Main analyses use ``corroborated`` (>= 2 sources). V-Dem v16
   ends in 2025, so 2026 contests can reach at most two sources.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import INTERIM, load_config


WP_ALIASES = {
    "Burma (Myanmar)": "MMR", "Cape Verde": "CPV", "Czech Republic": "CZE",
    "Democratic Republic of Congo": "COD", "Democratic Republic of the Congo": "COD",
    "East Timor": "TLS", "Federated States of Micronesia": "FSM", "Micronesia": "FSM",
    "Gambia": "GMB", "Iran": "IRN", "Ivory Coast": "CIV", "Laos": "LAO", "Macedonia": "MKD",
    "Republic of Macedonia": "MKD", "North Korea": "PRK", "Republic of Congo": "COG",
    "Republic of the Congo": "COG", "Russia": "RUS", "South Korea": "KOR", "Swaziland": "SWZ",
    "Syria": "SYR", "The Bahamas": "BHS", "Vietnam": "VNM",
    # non-sovereign / not in sample: Abkhazia, European Union, Jersey, Nagorno-Karabakh,
    # Northern Cyprus, Sint Maarten, Somaliland, South Ossetia, Transnistria -> dropped
}
UPPER = r"senate|councillors|house of lords|rajya|bundesrat|federation council|upper house|house of councillors"
EXCLUDE = r"vice president|referend|constituent|primar|recall"


def wikipedia_events(meta: pd.DataFrame, idea: pd.DataFrame) -> pd.DataFrame:
    from src.ingest.wikipedia_calendar import parse_all
    wp = parse_all()
    name_map = {**dict(zip(meta.country_name, meta.iso3)),
                **dict(zip(idea.country, idea.iso3)), **WP_ALIASES}
    wp["iso3"] = wp.country_wp.map(name_map)
    wp = wp.dropna(subset=["iso3"])
    d = wp.desc.str.lower()
    wp = wp[~d.str.contains(EXCLUDE)]
    d = wp.desc.str.lower()
    # an item is upper-house-only if it names an upper chamber and no lower chamber
    lower = d.str.contains(r"chamber of deputies|house of representatives|house of the people|national assembly|"
                           r"parliament|bundestag|knesset|duma|sejm|lower house|congress|general|legislat|assembly")
    wp["chamber"] = np.where(wp.etype == "presidential", "executive",
                             np.where(d.str.contains(UPPER) & ~lower, "upper", "lower"))
    return wp


def collapse_rounds(e: pd.DataFrame, keys=("iso3", "etype", "chamber"), gap_days=90) -> pd.DataFrame:
    """Rounds/phases of the same contest within ``gap_days`` become one event (first-round date)."""
    e = e.sort_values(list(keys) + ["date"]).copy()
    new = (e.groupby(list(keys)).date.diff().dt.days.fillna(1e9) > gap_days).astype(int)
    e["contest"] = new.groupby([e[k] for k in keys]).cumsum()
    g = e.groupby(list(keys) + ["contest"])
    out = g.agg(date=("date", "min"), last_round_date=("date", "max"), rounds=("date", "nunique")).reset_index()
    out["runoff"] = (out.rounds > 1).astype(int)
    return out.drop(columns="contest")


def modal_terms(hist: pd.DataFrame) -> pd.DataFrame:
    """Modal interval (years) between national election years, 1990-2014, from V-Dem.

    Uses year-level V-Dem election indicators so no exact dates are needed. Falls back to
    1960-2014 when fewer than three intervals exist in 1990-2014.
    """
    rows = []
    for etype, cols in {"parliamentary": ["v2eltype_0"], "presidential": ["v2eltype_6"]}.items():
        h = hist[(hist[cols].fillna(0) == 1).any(axis=1)][["iso3", "year"]].drop_duplicates()
        for iso3, g in h.groupby("iso3"):
            yrs = g.year.sort_values()
            for lo, basis in ((1990, "vdem_1990_2014"), (1960, "vdem_1960_2014")):
                y = yrs[(yrs >= lo) & (yrs <= 2014)]
                gaps = y.diff().dropna()
                if len(gaps) >= 3:
                    rows.append((iso3, etype, float(gaps.mode().max()), basis))
                    break
            else:
                rows.append((iso3, etype, np.nan, "insufficient_history"))
    return pd.DataFrame(rows, columns=["iso3", "etype", "modal_term_years", "term_basis"])


def classify_early(el: pd.DataFrame, terms: pd.DataFrame, rule_months: int) -> pd.DataFrame:
    el = el.sort_values(["iso3", "etype", "date"]).copy()
    el["prev_date"] = el.groupby(["iso3", "etype"]).date.shift()
    el["interval_months"] = (el.date - el.prev_date).dt.days / 30.4375
    el = el.merge(terms, on=["iso3", "etype"], how="left")
    threshold = el.modal_term_years * 12 - rule_months
    el["early"] = np.where(el.interval_months.isna() | el.modal_term_years.isna(), np.nan,
                           (el.interval_months < threshold).astype(float))
    return el


def build_election_events() -> pd.DataFrame:
    """National election events 2010-2026, triangulated across Wikipedia, IDEA and V-Dem.

    Event list and dates: Wikipedia national electoral calendars (lower chamber and
    presidential contests, sovereign states). IDEA history (1945-) is used for the term-length
    rule and as a corroborating source; V-Dem v16 corroborates the year and type.
    """
    cfg = load_config()
    idea = pd.read_parquet(INTERIM / "idea_elections.parquet")
    vdem = pd.read_parquet(INTERIM / "vdem.parquet")
    meta = pd.read_parquet(INTERIM / "wb_meta.parquet")

    wp = wikipedia_events(meta, idea)
    wp = wp[wp.chamber != "upper"]
    el = collapse_rounds(wp, ("iso3", "etype"), gap_days=90)

    terms = modal_terms(pd.read_parquet(INTERIM / "vdem_election_history.parquet"))
    el = classify_early(el, terms, cfg["elections"]["early_election_rule_months"])
    idea_c = collapse_rounds(idea.assign(chamber="na"), ("iso3", "etype"), gap_days=90)

    el["year"] = el.date.dt.year
    el["quarter"] = pd.PeriodIndex(el.date, freq="Q").astype(str)

    # IDEA corroboration (same country, type, year) and date agreement where IDEA has a day
    idea_c["year"] = idea_c.date.dt.year
    idea_c["idea_exact"] = ~((idea_c.date.dt.month == 1) & (idea_c.date.dt.day == 1))
    ic = idea_c.groupby(["iso3", "etype", "year"]).agg(
        idea_n=("date", "size"), idea_dates=("date", lambda s: ";".join(s.dt.strftime("%Y-%m-%d"))))
    el = el.merge(ic.reset_index(), on=["iso3", "etype", "year"], how="left")
    el["idea_match"] = el.idea_n.notna()

    def date_gap(r):
        if not isinstance(r.idea_dates, str):
            return np.nan
        ds = [pd.Timestamp(x) for x in r.idea_dates.split(";") if not x.endswith("-01-01")]
        return min(abs((r.date - x).days) for x in ds) if ds else np.nan
    el["idea_date_gap_days"] = el.apply(date_gap, axis=1)

    v = vdem[["iso3", "year", "v2eltype_0", "v2eltype_1", "v2eltype_6", "v2eltype_7",
              "v2x_ex_direlect", "v2elturnhog", "v2elturnhos"]].copy()
    el = el.merge(v, on=["iso3", "year"], how="left")
    parl_v = (el.v2eltype_0 == 1) | (el.v2eltype_1 == 1)
    pres_v = (el.v2eltype_6 == 1) | (el.v2eltype_7 == 1)
    el["vdem_match"] = np.where(el.year > 2025, np.nan,
                                (((el.etype == "parliamentary") & parl_v) |
                                 ((el.etype == "presidential") & pres_v)).astype(float))
    n_src = 1 + el.idea_match.astype(int) + el.vdem_match.fillna(0).astype(int)
    el["n_sources"] = n_src
    el["verification"] = np.select(
        [n_src >= 3, n_src == 2], ["wikipedia+idea+vdem", "two_sources"], "wikipedia_only")
    el["corroborated"] = (n_src >= 2).astype(int)

    de = vdem.dropna(subset=["v2x_ex_direlect"]).sort_values("year")
    de_last = de.groupby("iso3").v2x_ex_direlect.last()
    el["direlect"] = el.v2x_ex_direlect.fillna(el.iso3.map(de_last))
    el["exec_relevant"] = np.where(
        el.direlect.isna(), np.nan,
        np.where(el.direlect >= 0.5, (el.etype == "presidential").astype(float),
                 (el.etype == "parliamentary").astype(float)))
    turn = np.where(el.direlect >= 0.5, el.v2elturnhos, el.v2elturnhog)
    el["exec_turnover_at_election"] = np.where(pd.isna(turn), np.nan, (turn == 2).astype(float))
    el["event_id"] = el.iso3 + "_" + el.etype.str[:4] + "_" + el.date.dt.strftime("%Y%m%d")
    return el.drop(columns=["v2eltype_0", "v2eltype_1", "v2eltype_6", "v2eltype_7",
                            "v2elturnhog", "v2elturnhos", "v2x_ex_direlect", "idea_n"])


def quarterly_election_indicators(el: pd.DataFrame, panel_keys: pd.DataFrame) -> pd.DataFrame:
    """Election-window indicators on a country-quarter grid.

    elec_pre   : quarter of, or the quarter before, an executive-relevant election
    elec_post  : the two quarters after an executive-relevant election
    elec_any_pre : as elec_pre but for any national election
    event_time : quarters relative to the nearest executive-relevant election (|k| <= 6)
    """
    cfg = load_config()["elections"]
    pre_w, post_w = cfg["pre_window_quarters"], cfg["post_window_quarters"]
    K = max(cfg["event_study_leads"], cfg["event_study_lags"])
    k = panel_keys[["iso3", "quarter"]].drop_duplicates().copy()
    k["qidx"] = pd.PeriodIndex(k.quarter, freq="Q").map(lambda p: p.ordinal)
    out = k.copy()
    specs = {
        "exec": el[el.exec_relevant == 1],
        "exec_sched": el[(el.exec_relevant == 1) & (el.early == 0)],
        "exec_early": el[(el.exec_relevant == 1) & (el.early == 1)],
        "any": el,
    }
    for name, sub in specs.items():
        ev = sub[["iso3", "quarter"]].drop_duplicates().copy()
        ev["ev_qidx"] = pd.PeriodIndex(ev.quarter, freq="Q").map(lambda p: p.ordinal)
        m = k.merge(ev[["iso3", "ev_qidx"]], on="iso3", how="left")
        m["rel"] = m.qidx - m.ev_qidx          # >0 after election, <0 before
        pre = m[(m.rel >= -pre_w) & (m.rel <= 0)].groupby(["iso3", "quarter"]).size()
        post = m[(m.rel >= 1) & (m.rel <= post_w)].groupby(["iso3", "quarter"]).size()
        out = out.set_index(["iso3", "quarter"])
        out[f"elec_{name}_pre"] = pre.reindex(out.index).notna().astype(int)
        out[f"elec_{name}_post"] = post.reindex(out.index).notna().astype(int)
        if name in ("exec", "exec_sched"):
            near = m.dropna(subset=["rel"]).copy()
            near["absrel"] = near.rel.abs()
            near = near.sort_values("absrel").groupby(["iso3", "quarter"]).rel.first()
            out[f"event_time_{name}"] = near.reindex(out.index).where(lambda s: s.abs() <= K)
        out = out.reset_index()
    return out.drop(columns="qidx")
