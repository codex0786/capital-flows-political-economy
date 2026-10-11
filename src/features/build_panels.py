"""Build the analytical datasets in data/processed/.

Outputs
-------
country_metadata.csv          country universe with inclusion decisions and reasons
annual_country_panel.parquet  country-year, 2014-2026 (2026 flagged partial)
quarterly_country_panel.parquet  country-quarter, 2014Q1-latest
political_events.csv          elections (triangulated), executive changes, major unrest months
policy_events.csv             data-derived policy events (see docstring of policy_events())

Flow ratios
-----------
Annual:    100 * flow_usd / GDP_usd (IMF WEO NGDPD, same calendar year).
Quarterly: 100 * 4 * flow_usd / GDP_usd(year)  -> annualised percent of annual GDP. For 2026
           the denominator is the WEO 2026 projection (flagged ``gdp_denominator_projected``).
Gross inflows  = FDI + portfolio + other investment, net incurrence of liabilities (BPM6).
Gross outflows = FDI + portfolio + other investment, net acquisition of assets (excl. reserves).
Net flows      = gross inflows - gross outflows (positive = net capital inflow); this equals
                 minus the BPM6 financial-account balance excluding reserves and derivatives.
Aggregates are only computed when all three components are present (never zero-filled).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import INTERIM, PROCESSED, get_logger, load_config
from src.features.elections import build_election_events, quarterly_election_indicators

log = get_logger("panels")
CFG = load_config()

ADVANCED_IMF_CURRENT = [
    # IMF WEO advanced-economy group as of the current DataMapper vintage. Verified: the
    # sum of these economies' NGDPD equals the published ADVEC aggregate to within USD 1m
    # in 2015, 2019, 2024 and 2025 (see results/diagnostics/ae_membership_check.csv).
    "AND", "AUS", "AUT", "BEL", "CAN", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU",
    "GRC", "HKG", "ISL", "IRL", "ISR", "ITA", "JPN", "KOR", "LVA", "LTU", "LUX", "MAC", "MLT",
    "NLD", "NZL", "NOR", "PRT", "PRI", "SMR", "SGP", "SVK", "SVN", "ESP", "SWE", "CHE", "TWN",
    "GBR", "USA", "BGR", "LIE",
]
# Reclassified recently on euro adoption (HRV: April 2023 WEO; BGR: 2026). Alternative
# classification treats them as emerging for the whole sample.
RECENT_AE = ["HRV", "BGR"]

COMPONENTS_IN = ["fdi_in_usd", "port_in_usd", "oi_in_usd"]
COMPONENTS_OUT = ["fdi_out_usd", "port_out_usd", "oi_out_usd"]
FLOW_VARS = {
    "fdi_in": "fdi_in_usd", "fdi_out": "fdi_out_usd", "port_in": "port_in_usd",
    "port_out": "port_out_usd", "pe_in": "pe_in_usd", "pd_in": "pd_in_usd",
    "oi_in": "oi_in_usd", "oi_out": "oi_out_usd", "reserve_change": "reserves_flow_usd",
    "gross_inflows": "gross_in_usd", "gross_outflows": "gross_out_usd", "net_flows": "net_usd",
}


def add_aggregates(b: pd.DataFrame) -> pd.DataFrame:
    b = b.copy()
    b["gross_in_usd"] = b[COMPONENTS_IN].sum(axis=1, min_count=3)
    b["gross_out_usd"] = b[COMPONENTS_OUT].sum(axis=1, min_count=3)
    b["net_usd"] = b.gross_in_usd - b.gross_out_usd
    return b


def gdp_table() -> pd.DataFrame:
    weo = pd.read_parquet(INTERIM / "weo.parquet")
    g = weo[["iso3", "year", "NGDPD"]].dropna().copy()
    g["gdp_usd"] = g.NGDPD * 1e9
    wdi = pd.read_parquet(INTERIM / "wdi.parquet")[["iso3", "year", "NY.GDP.MKTP.CD"]]
    g = g.merge(wdi, on=["iso3", "year"], how="outer")
    g["gdp_usd_wdi"] = g["NY.GDP.MKTP.CD"]
    g["gdp_source"] = np.where(g.gdp_usd.notna(), "WEO", np.where(g.gdp_usd_wdi.notna(), "WDI", None))
    g["gdp_usd"] = g.gdp_usd.fillna(g.gdp_usd_wdi)
    g["gdp_projected"] = (g.year >= CFG["sample"]["extension_year"]).astype(int)
    return g[["iso3", "year", "gdp_usd", "gdp_usd_wdi", "gdp_source", "gdp_projected"]]


def country_universe(bop_a: pd.DataFrame, bop_q: pd.DataFrame) -> pd.DataFrame:
    """Apply the documented inclusion rule; every candidate gets a decision and reason."""
    s = CFG["sample"]
    rule = CFG["country_inclusion"]
    meta = pd.read_parquet(INTERIM / "wb_meta.parquet")
    weo = pd.read_parquet(INTERIM / "weo.parquet")
    wgi = pd.read_parquet(INTERIM / "wgi.parquet")
    cand = pd.DataFrame({"iso3": sorted(set(bop_a.iso3) | set(bop_q.iso3))})
    cand = cand[cand.iso3.str.fullmatch(r"[A-Z]{3}")]
    cand = cand.merge(meta, on="iso3", how="left")
    names = weo  # WEO has TWN which the World Bank does not list
    cand.loc[cand.iso3 == "TWN", ["country_name", "wb_region", "wb_income"]] = [
        "Taiwan Province of China", "East Asia & Pacific", "High income"]

    pop = weo[weo.year == s["pre_sample_year"]].set_index("iso3").LP
    a = bop_a[bop_a.year.between(s["main_start_year"], s["main_end_year"])]
    yrs_ok = a.dropna(subset=["gross_in_usd", "gross_out_usd"]).groupby("iso3").year.nunique()
    q = bop_q[bop_q.year.between(s["main_start_year"], s["main_end_year"])]
    q_ok = q.dropna(subset=["gross_in_usd", "gross_out_usd"]).groupby("iso3").quarter.nunique()
    wgi_ok = wgi[(wgi.year == s["pre_sample_year"]) & wgi.wgi_rl_est.notna()].iso3

    cand["pop_2014_m"] = cand.iso3.map(pop)
    cand["annual_bop_years_2015_2025"] = cand.iso3.map(yrs_ok).fillna(0).astype(int)
    cand["quarterly_bop_quarters_2015_2025"] = cand.iso3.map(q_ok).fillna(0).astype(int)
    cand["wgi_2014"] = cand.iso3.isin(wgi_ok)

    reasons = []
    for r in cand.itertuples():
        why = []
        if pd.isna(r.country_name):
            why.append("not a World Bank-listed economy")
        if not (r.pop_2014_m >= rule["min_population_millions"]):
            why.append(f"population < {rule['min_population_millions']}m (WEO 2014) or missing")
        if r.annual_bop_years_2015_2025 < rule["min_annual_bop_years"]:
            why.append(f"annual gross flows for {r.annual_bop_years_2015_2025}/11 years")
        if rule["require_wgi"] and not r.wgi_2014:
            why.append("no WGI 2014")
        reasons.append("; ".join(why))
    cand["exclusion_reason"] = reasons
    cand["in_annual_sample"] = cand.exclusion_reason.eq("")
    cand["in_quarterly_sample"] = cand.in_annual_sample & (
        cand.quarterly_bop_quarters_2015_2025 >= rule["min_quarterly_bop_quarters"])
    cand["country_group"] = np.where(cand.iso3.isin(ADVANCED_IMF_CURRENT), "AE", "EMDE")
    cand["country_group_alt_pre_euro"] = np.where(cand.iso3.isin(RECENT_AE), "EMDE", cand.country_group)
    cand["country_group_alt_wb"] = np.where(cand.wb_income == "High income", "HIC", "non-HIC")
    cand["low_income"] = (cand.wb_income == "Low income").astype(int)
    cand["financial_centre"] = cand.iso3.isin(CFG["country_inclusion"]["financial_centres"]).astype(int)
    cand["classification_source"] = "IMF WEO advanced-economy group (DataMapper vintage retrieved 2026-10-11)"
    return cand


def predetermined_moderators() -> pd.DataFrame:
    """Country characteristics measured in the pre-sample year (2014), fixed thereafter."""
    y = CFG["sample"]["pre_sample_year"]
    wgi = pd.read_parquet(INTERIM / "wgi.parquet")
    w = wgi[wgi.year == y].set_index("iso3")[[c for c in wgi.columns if c.endswith("_est")]]
    w.columns = [c.replace("_est", "_2014") for c in w.columns]
    v = pd.read_parquet(INTERIM / "vdem.parquet")
    v = v[v.year == y].set_index("iso3")[["v2x_jucon", "v2xlg_legcon", "v2x_polyarchy"]]
    v.columns = [c + "_2014" for c in v.columns]
    k = pd.read_parquet(INTERIM / "kaopen.parquet")
    k = k[k.year == y].set_index("iso3")[["ka_open"]].rename(columns={"ka_open": "ka_open_2014"})
    wdi = pd.read_parquet(INTERIM / "wdi.parquet")
    d = wdi[wdi.year == y].set_index("iso3")
    x = pd.DataFrame({
        "reserves_months_2014": d["FI.RES.TOTL.MO"],
        "st_debt_reserves_2014": d["DT.DOD.DSTC.IR.ZS"],
        "ext_debt_gdp_2014": 100 * d["DT.DOD.DECT.CD"] / d["NY.GDP.MKTP.CD"],
        "private_credit_gdp_2014": d["FS.AST.PRVT.GD.ZS"],
        "mktcap_gdp_2014": d["CM.MKT.LCAP.GD.ZS"],
        "fuel_exports_2014": d["TX.VAL.FUEL.ZS.UN"],
    })
    return w.join(v, how="outer").join(k, how="outer").join(x, how="outer").reset_index()


def annual_controls() -> pd.DataFrame:
    weo = pd.read_parquet(INTERIM / "weo.parquet").rename(columns={
        "NGDP_RPCH": "gdp_growth", "PCPIPCH": "inflation", "BCA_NGDPD": "ca_gdp",
        "GGXCNL_NGDP": "fiscal_balance_gdp", "GGXWDG_NGDP": "public_debt_gdp",
        "NGDPDPC": "gdp_pc_usd", "LP": "population_m"})
    wdi = pd.read_parquet(INTERIM / "wdi.parquet").rename(columns={
        "NE.TRD.GNFS.ZS": "trade_open_gdp", "FI.RES.TOTL.MO": "reserves_months",
        "DT.DOD.DSTC.IR.ZS": "st_debt_reserves", "FR.INR.RINR": "real_rate_wdi",
        "FS.AST.PRVT.GD.ZS": "private_credit_gdp", "CM.MKT.LCAP.GD.ZS": "mktcap_gdp"})
    wdi["ext_debt_gdp"] = 100 * wdi["DT.DOD.DECT.CD"] / wdi["NY.GDP.MKTP.CD"]
    keep_w = ["iso3", "year", "gdp_growth", "inflation", "ca_gdp", "fiscal_balance_gdp",
              "public_debt_gdp", "gdp_pc_usd", "population_m"]
    keep_d = ["iso3", "year", "trade_open_gdp", "reserves_months", "st_debt_reserves",
              "real_rate_wdi", "private_credit_gdp", "mktcap_gdp", "ext_debt_gdp"]
    c = weo[keep_w].merge(wdi[keep_d], on=["iso3", "year"], how="outer")
    c["log_gdp_pc"] = np.log(c.gdp_pc_usd)
    c["weo_projection"] = (c.year >= CFG["sample"]["extension_year"]).astype(int)
    return c


def executive_changes(vdem: pd.DataFrame) -> pd.DataFrame:
    """Annual change of the chief executive from V-Dem leader names (end-of-year snapshots).

    chief executive = head of state if V-Dem codes the HOS as directly elected/dominant
    (v2x_ex_direlect >= 0.5), else head of government. A change is recorded when the name
    at the V-Dem coding date differs from the previous year. Intra-year changes that are
    reversed before the coding date are not captured (documented limitation).
    """
    v = vdem.sort_values(["iso3", "year"]).copy()
    for r in ("hos", "hog"):
        prev = v.groupby("iso3")[f"v2exnam{r}"].shift()
        v[f"{r}_change"] = np.where(prev.isna() | v[f"v2exnam{r}"].isna(), np.nan,
                                    (prev != v[f"v2exnam{r}"]).astype(float))
    pres = v.v2x_ex_direlect >= 0.5
    v["exec_change"] = np.where(pres, v.hos_change, v.hog_change)
    return v[["iso3", "year", "exec_change", "hos_change", "hog_change"]]


def sudden_stop_episodes(q: pd.DataFrame, var: str = "gross_in_usd") -> pd.DataFrame:
    """Forbes & Warnock (2012)-style episodes on the 4-quarter rolling sum of gross inflows.

    C_t = S_t - S_{t-4}, S_t = 4-quarter sum. Stop when C_t < mean - 2 sd (rolling 20 quarters,
    min 12), extending while C_t < mean - 1 sd. Surge symmetric. Requires consecutive quarters.
    """
    out = []
    for iso3, g in q.sort_values("quarter").groupby("iso3"):
        g = g.set_index(pd.PeriodIndex(g.quarter, freq="Q"))
        idx = pd.period_range(g.index.min(), g.index.max(), freq="Q")
        x = g[var].reindex(idx)
        s4 = x.rolling(4, min_periods=4).sum()
        c = s4 - s4.shift(4)
        m = c.rolling(20, min_periods=12).mean().shift(1)
        sd = c.rolling(20, min_periods=12).std().shift(1)
        stop = pd.Series(0.0, index=idx)
        surge = pd.Series(0.0, index=idx)
        in_stop = in_surge = False
        for t in idx:
            if pd.isna(c[t]) or pd.isna(m[t]):
                stop[t] = surge[t] = np.nan
                in_stop = in_surge = False
                continue
            in_stop = c[t] < m[t] - 2 * sd[t] or (in_stop and c[t] < m[t] - sd[t])
            in_surge = c[t] > m[t] + 2 * sd[t] or (in_surge and c[t] > m[t] + sd[t])
            stop[t], surge[t] = float(in_stop), float(in_surge)
        out.append(pd.DataFrame({"iso3": iso3, "quarter": idx.astype(str),
                                 "sudden_stop": stop.values, "surge": surge.values}))
    return pd.concat(out, ignore_index=True)


def winsorize(s: pd.Series, lo: float, hi: float) -> pd.Series:
    a, b = np.nanpercentile(s.dropna(), [lo, hi]) if s.notna().any() else (np.nan, np.nan)
    return s.clip(a, b)


def build() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    s = CFG["sample"]
    bop_a = add_aggregates(pd.read_parquet(INTERIM / "bop_annual.parquet"))
    bop_q = add_aggregates(pd.read_parquet(INTERIM / "bop_quarterly.parquet"))
    gdp = gdp_table()

    universe = country_universe(bop_a, bop_q)
    universe.to_csv(PROCESSED / "country_metadata.csv", index=False)
    sample_a = set(universe[universe.in_annual_sample].iso3)
    sample_q = set(universe[universe.in_quarterly_sample].iso3)
    log.info("universe: %d candidates, annual sample %d, quarterly sample %d",
             len(universe), len(sample_a), len(sample_q))

    moder = predetermined_moderators()
    ctrl = annual_controls()
    vdem = pd.read_parquet(INTERIM / "vdem.parquet")
    wgi = pd.read_parquet(INTERIM / "wgi.parquet")
    lo, hi = CFG["outcomes"]["winsorize_pct"]
    grp = universe[["iso3", "country_name", "country_group", "country_group_alt_pre_euro",
                    "country_group_alt_wb", "low_income", "financial_centre"]]

    # ------------------------------------------------------------------ elections
    el = build_election_events()

    # ------------------------------------------------------------------ annual panel
    A = bop_a[bop_a.iso3.isin(sample_a) & bop_a.year.between(s["pre_sample_year"], s["extension_year"])]
    A = A.merge(gdp, on=["iso3", "year"], how="left")
    for k, v in FLOW_VARS.items():
        A[f"{k}_gdp"] = 100 * A[v] / A.gdp_usd
    A = A.merge(grp, on="iso3", how="left")
    A = A.merge(ctrl, on=["iso3", "year"], how="left")
    lagc = ["gdp_growth", "inflation", "ca_gdp", "fiscal_balance_gdp", "public_debt_gdp",
            "log_gdp_pc", "trade_open_gdp", "reserves_months"]
    lagged = ctrl[["iso3", "year"] + lagc].copy()
    lagged["year"] += 1
    A = A.merge(lagged.rename(columns={c: f"L_{c}" for c in lagc}), on=["iso3", "year"], how="left")
    A = A.merge(wgi[["iso3", "year"] + [c for c in wgi.columns if c.endswith(("_est", "_se"))]],
                on=["iso3", "year"], how="left")
    A = A.merge(vdem.drop(columns=["country_name"]), on=["iso3", "year"], how="left")
    A = A.merge(executive_changes(vdem), on=["iso3", "year"], how="left")
    A = A.merge(moder, on="iso3", how="left")
    ec = el[el.corroborated == 1]
    ann = ec.groupby(["iso3", "year"]).agg(
        n_elections=("event_id", "size"),
        exec_election=("exec_relevant", lambda x: float((x == 1).any())),
        early_exec_election=("early", lambda x: float(((x == 1)).any())))
    A = A.merge(ann.reset_index(), on=["iso3", "year"], how="left")
    for c in ["n_elections", "exec_election", "early_exec_election"]:
        A[c] = A[c].fillna(0)  # absence of a corroborated election in the event list = no election
    A["irregular_exec_change"] = np.where(A.exec_change.isna(), np.nan,
                                          ((A.exec_change == 1) & (A.exec_election == 0)).astype(float))
    wui = pd.read_parquet(INTERIM / "wui.parquet")
    wui["year"] = wui.quarter.str[:4].astype(int)
    A = A.merge(wui.groupby(["iso3", "year"]).wui.mean().reset_index(), on=["iso3", "year"], how="left")
    rs = pd.read_parquet(INTERIM / "rsui.parquet")
    rs["year"] = rs.quarter.str[:4].astype(int)
    A = A.merge(rs.groupby(["iso3", "year"]).agg(rsui_index=("rsui_index", "mean"),
                                                 rsui_event=("rsui_event", "max")).reset_index(),
                on=["iso3", "year"], how="left")
    A["partial_year"] = (A.year >= s["extension_year"]).astype(int)
    for k in FLOW_VARS:
        A[f"{k}_gdp_w"] = winsorize(A[f"{k}_gdp"].where(A.year.between(s["main_start_year"], s["main_end_year"])), lo, hi) \
            .combine_first(A[f"{k}_gdp"].where(~A.year.between(s["main_start_year"], s["main_end_year"])))
    A = A.sort_values(["iso3", "year"])
    assert not A.duplicated(["iso3", "year"]).any()
    A.to_parquet(PROCESSED / "annual_country_panel.parquet", index=False)
    log.info("annual panel %s", A.shape)

    # ------------------------------------------------------------------ quarterly panel
    Q = bop_q[bop_q.iso3.isin(sample_q) & (bop_q.year >= s["pre_sample_year"])].copy()
    Q = Q.merge(gdp, on=["iso3", "year"], how="left")
    for k, v in FLOW_VARS.items():
        Q[f"{k}_gdp"] = 100 * 4 * Q[v] / Q.gdp_usd
    Q["gdp_denominator_projected"] = Q.gdp_projected
    Q = Q.merge(grp, on="iso3", how="left")
    lagged_q = lagged.rename(columns={c: f"L_{c}" for c in lagc})
    Q = Q.merge(lagged_q, on=["iso3", "year"], how="left")   # previous-year fundamentals
    Q = Q.merge(moder, on="iso3", how="left")
    Q = Q.merge(quarterly_election_indicators(ec, Q), on=["iso3", "quarter"], how="left")
    Q = Q.merge(wui, on=["iso3", "quarter"], how="left", suffixes=("", "_y")).drop(columns=["year_y"], errors="ignore")
    Q = Q.merge(pd.read_parquet(INTERIM / "gpr_country.parquet"), on=["iso3", "quarter"], how="left")
    Q = Q.merge(rs[["iso3", "quarter", "rsui_index", "rsui_event"]], on=["iso3", "quarter"], how="left")
    Q = Q.merge(pd.read_parquet(INTERIM / "policy_rates.parquet"), on=["iso3", "quarter"], how="left")
    glob = pd.read_parquet(INTERIM / "global_factors.parquet").rename(columns={
        "VIXCLS": "vix", "FEDFUNDS": "fed_funds", "DGS10": "ust10y", "DTWEXBGS": "usd_broad",
        "POILBREUSDM": "brent", "BAMLH0A0HYM2": "us_hy_oas"})
    glob = glob.merge(pd.read_parquet(INTERIM / "gpr_global.parquet"), on="quarter", how="left")
    glob = glob.sort_values("quarter")
    glob["usd_broad_chg"] = 100 * glob.usd_broad.pct_change()
    glob["brent_chg"] = 100 * glob.brent.pct_change()
    Q = Q.merge(glob, on="quarter", how="left")
    Q = Q.merge(sudden_stop_episodes(bop_q[bop_q.iso3.isin(sample_q)]), on=["iso3", "quarter"], how="left")
    Q = Q.sort_values(["iso3", "quarter"])
    for k in ["gross_inflows", "gross_outflows", "net_flows"]:
        Q[f"{k}_vol4"] = Q.groupby("iso3")[f"{k}_gdp"].transform(lambda x: x.rolling(4, min_periods=4).std())
        Q[f"{k}_vol8"] = Q.groupby("iso3")[f"{k}_gdp"].transform(lambda x: x.rolling(8, min_periods=8).std())
    main = Q.year.between(s["main_start_year"], s["main_end_year"])
    for k in FLOW_VARS:
        w = winsorize(Q.loc[main, f"{k}_gdp"], lo, hi)
        Q[f"{k}_gdp_w"] = Q[f"{k}_gdp"]
        Q.loc[main, f"{k}_gdp_w"] = w
    Q["partial_year"] = (Q.year >= s["extension_year"]).astype(int)
    assert not Q.duplicated(["iso3", "quarter"]).any()
    Q.to_parquet(PROCESSED / "quarterly_country_panel.parquet", index=False)
    log.info("quarterly panel %s", Q.shape)

    write_event_files(el, vdem, rs, universe)


def write_event_files(el, vdem, rs, universe):
    meta = universe.set_index("iso3").country_name
    ev = el.copy()
    ev["country"] = ev.iso3.map(meta)
    ev["event_type"] = "election_" + ev.etype
    ev["event_date"] = ev.date.dt.date
    ev["announcement_date"] = pd.NaT       # not systematically available; see protocol
    ev["effective_date"] = ev.last_round_date.dt.date
    ev["scheduled_or_unexpected"] = np.select([ev.early == 1, ev.early == 0], ["early_rule_based", "scheduled_rule_based"], "unclassified")
    ev["treatment_definition"] = np.where(ev.exec_relevant == 1, "exec-relevant election: elec_exec_pre/post windows",
                                          "non-executive national election: elec_any windows only")
    ev["primary_source"] = "Wikipedia national electoral calendar " + ev.year.astype(str) + " (revision archived)"
    ev["verification_status"] = ev.verification
    ev["coding_notes"] = ("rounds=" + ev.rounds.astype(int).astype(str) + "; modal_term=" + ev.modal_term_years.astype(str)
                          + " (" + ev.term_basis.astype(str) + "); idea_dates=" + ev.idea_dates.fillna("none")
                          + np.where(ev.idea_date_gap_days > 7, "; DATE CONFLICT WITH IDEA >7 days", ""))
    cols = ["event_id", "iso3", "country", "event_type", "event_date", "announcement_date", "effective_date",
            "scheduled_or_unexpected", "exec_relevant", "runoff", "exec_turnover_at_election",
            "treatment_definition", "primary_source", "verification_status", "n_sources", "coding_notes"]
    elec = ev[cols]

    x = executive_changes(vdem)
    x = x[(x.exec_change == 1) & x.year.between(2015, 2025)].copy()
    x["event_id"] = x.iso3 + "_execchange_" + x.year.astype(str)
    x["country"] = x.iso3.map(meta)
    x["event_type"] = "chief_executive_change"
    x["event_date"] = x.year.astype(str) + " (year only; V-Dem end-of-year coding)"
    x["primary_source"] = "V-Dem v16 v2exnamhos/v2exnamhog"
    x["verification_status"] = "single_source"
    x["coding_notes"] = "name differs from previous year's coding; includes electoral and non-electoral changes"
    unrest = rs[rs.rsui_event == 1].copy()
    unrest["event_id"] = unrest.iso3 + "_unrest_" + unrest.quarter
    unrest["country"] = unrest.iso3.map(meta)
    unrest["event_type"] = "major_social_unrest_quarter"
    unrest["event_date"] = unrest.quarter + " (quarter)"
    unrest["primary_source"] = "IMF Reported Social Unrest Index (Barrett et al. 2022), EVENT series"
    unrest["verification_status"] = "single_source"
    unrest["coding_notes"] = "at least one month in the quarter flagged as a major unrest event"
    pe = pd.concat([elec, x.reindex(columns=cols), unrest.reindex(columns=cols)], ignore_index=True)
    pe.to_csv(PROCESSED / "political_events.csv", index=False)
    log.info("political events: %s", pe.event_type.value_counts().to_dict())
    policy_events(universe).to_csv(PROCESSED / "policy_events.csv", index=False)


def policy_events(universe: pd.DataFrame) -> pd.DataFrame:
    """Data-derived policy events (no manual coding of policy quality or direction intent).

    1. Capital-account regime changes: |change in Chinn-Ito ka_open| >= 0.10 in a year
       (index range 0-1), 2015-2023 (latest KAOPEN year).
    2. Large monetary-policy moves: |quarterly change in BIS policy rate| >= 2 percentage points.

    Hand-coded legislative/regulatory events (investment screening, repatriation rules,
    sanctions) are NOT included in v1.0: see report/research_protocol.md, section 9.
    """
    meta = universe.set_index("iso3").country_name
    k = pd.read_parquet(INTERIM / "kaopen.parquet").sort_values(["iso3", "year"])
    k["d"] = k.groupby("iso3").ka_open.diff()
    kk = k[k.year.between(2015, 2023) & (k.d.abs() >= 0.10)].copy()
    kk = pd.DataFrame({
        "event_id": kk.iso3 + "_kaopen_" + kk.year.astype(str), "iso3": kk.iso3,
        "country": kk.iso3.map(meta), "policy_domain": "capital_account",
        "announcement_date": None, "implementation_date": kk.year.astype(str) + " (year)",
        "affected_sectors": "cross-border financial transactions",
        "policy_instrument": "de jure capital-account restrictions (IMF AREAER-based index)",
        "legal_status": "as coded in AREAER", "geographic_scope": "national",
        "intended_mechanism": "not coded",
        "exposure_definition": np.where(kk.d > 0, "liberalisation (ka_open up)", "tightening (ka_open down)"),
        "magnitude": kk.d.round(3), "primary_source": "Chinn & Ito KAOPEN 2023 update",
        "coding_rationale": "rule: |annual change| >= 0.10"})
    p = pd.read_parquet(INTERIM / "policy_rates.parquet").sort_values(["iso3", "quarter"])
    p["d"] = p.groupby("iso3").policy_rate.diff()
    pp = p[(p.quarter >= "2015Q1") & (p.d.abs() >= 2)].copy()
    pp = pd.DataFrame({
        "event_id": pp.iso3 + "_policyrate_" + pp.quarter, "iso3": pp.iso3, "country": pp.iso3.map(meta),
        "policy_domain": "monetary", "announcement_date": None,
        "implementation_date": pp.quarter + " (quarter, end-of-period rate)",
        "affected_sectors": "economy-wide", "policy_instrument": "policy rate",
        "legal_status": "central-bank decision", "geographic_scope": "national",
        "intended_mechanism": "not coded",
        "exposure_definition": np.where(pp.d > 0, "tightening", "easing"),
        "magnitude": pp.d.round(2), "primary_source": "BIS central bank policy rates (WS_CBPOL)",
        "coding_rationale": "rule: |quarterly change| >= 2pp"})
    return pd.concat([kk, pp], ignore_index=True)


if __name__ == "__main__":
    build()
