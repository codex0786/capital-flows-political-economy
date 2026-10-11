"""Generate config/variable_dictionary.csv and data/processed/source_register.csv.

Missingness and observed ranges are computed from the processed panels (main sample
2015-2025), so the dictionary documents the data as delivered.
"""
from __future__ import annotations

import pandas as pd

from src.common import CONFIG, PROCESSED, RAW

BOP = ("IMF BOP", "IMF.STA:BOP v21", "https://data.imf.org/Datasets/BOP")
WEO = ("IMF WEO (DataMapper)", "", "https://www.imf.org/external/datamapper")
WGI = ("World Bank WGI 2026", "GOV_WGI_*", "https://datacatalog.worldbank.org/search/dataset/0038026")
WDI = ("World Bank WDI", "", "https://data.worldbank.org/")
VDEM = ("V-Dem v16", "", "https://github.com/vdeminstitute/vdemdata")
ELEC = ("Wikipedia calendars + IDEA + V-Dem", "", "see political_events.csv")
SIGN_IN = "positive = non-residents increase claims on residents (inflow); negative = repayment/withdrawal"
SIGN_OUT = "positive = residents acquire foreign assets (outflow); negative = repatriation/disinvestment"

D = [
    # name, label, concept, source tuple, unit, freq, currency, sign, transformation, role
    ("gross_inflows_gdp", "Gross capital inflows, % GDP", "capital flows", BOP, "% of GDP (quarterly: annualised)", "A/Q", "USD-based ratio", SIGN_IN,
     "100*(D_F+P_F+O_F net incurrence of liabilities)/GDP; quarterly x4; requires all three components", "primary outcome (H1a,H2,H5,H6)"),
    ("gross_outflows_gdp", "Gross capital outflows, % GDP", "capital flows", BOP, "% of GDP", "A/Q", "USD-based ratio", SIGN_OUT,
     "100*(D_F+P_F+O_F net acquisition of assets)/GDP; reserves excluded", "primary outcome (H1b)"),
    ("net_flows_gdp", "Net capital flows, % GDP", "capital flows", BOP, "% of GDP", "A/Q", "USD-based ratio",
     "positive = net inflow (= minus BPM6 FA balance excl. reserves and derivatives)", "gross_inflows - gross_outflows", "secondary outcome"),
    ("fdi_in_gdp", "FDI inflows (liabilities), % GDP", "capital flows", BOP, "% of GDP", "A/Q", "", SIGN_IN, "D_F L_NIL_T / GDP", "H3"),
    ("pe_in_gdp", "Portfolio equity & fund-share inflows, % GDP", "capital flows", BOP, "% of GDP", "A/Q", "", SIGN_IN, "P_F5 L_NIL_T / GDP", "H3"),
    ("pd_in_gdp", "Portfolio debt inflows, % GDP", "capital flows", BOP, "% of GDP", "A/Q", "", SIGN_IN, "P_F3 L_NIL_T / GDP", "H3"),
    ("oi_in_gdp", "Other investment inflows, % GDP", "capital flows", BOP, "% of GDP", "A/Q", "", SIGN_IN, "O_F L_NIL_T / GDP (includes official sector)", "H3"),
    ("fdi_out_gdp", "FDI outflows (assets), % GDP", "capital flows", BOP, "% of GDP", "A/Q", "", SIGN_OUT, "D_F A_NFA_T / GDP", "secondary"),
    ("port_out_gdp", "Portfolio outflows, % GDP", "capital flows", BOP, "% of GDP", "A/Q", "", SIGN_OUT, "P_F A_NFA_T / GDP", "secondary"),
    ("oi_out_gdp", "Other investment outflows, % GDP", "capital flows", BOP, "% of GDP", "A/Q", "", SIGN_OUT, "O_F A_NFA_T / GDP", "secondary"),
    ("reserve_change_gdp", "Reserve asset transactions, % GDP", "reserves", BOP, "% of GDP", "A/Q", "", "positive = reserve accumulation", "R_F A_T / GDP", "secondary"),
    ("*_gdp_w", "Winsorised version of the ratio", "capital flows", BOP, "% of GDP", "A/Q", "", "as underlying", "clipped at pooled 1st/99th pct within 2015-2025", "estimation outcome"),
    ("gross_inflows_vol8", "Inflow volatility", "volatility", BOP, "pp of GDP", "Q", "", "n/a", "rolling 8-quarter SD of gross_inflows_gdp (requires 8 obs)", "H1c, H5 secondary"),
    ("sudden_stop", "Sudden stop episode", "flow episodes", BOP, "0/1", "Q", "", "n/a", "Forbes-Warnock-style on 4Q-sum gross inflows; 2SD entry, 1SD continuation, rolling 20Q moments", "R1"),
    ("gdp_usd", "GDP, current USD", "denominator", WEO, "USD", "A", "USD", "n/a", "NGDPD x 1e9; WDI fallback; 2026 = projection (flagged)", "denominator"),
    ("elec_exec_pre", "Pre-election window", "elections", ELEC, "0/1", "Q", "", "n/a", "1 in quarter of, or before, an exec-relevant election (corroborated by >=2 sources)", "H1-H3, H6 treatment"),
    ("elec_exec_post", "Post-election window", "elections", ELEC, "0/1", "Q", "", "n/a", "1 in the two quarters after an exec-relevant election", "control / secondary"),
    ("elec_exec_sched_pre", "Pre-election window, scheduled elections", "elections", ELEC, "0/1", "Q", "", "n/a", "as elec_exec_pre for elections with early==0 (rule-based)", "identifying sample"),
    ("event_time_exec", "Quarters relative to nearest exec-relevant election", "elections", ELEC, "quarters", "Q", "", "negative = before", "nearest election within +/-6 quarters, else missing", "event study"),
    ("exec_election", "Exec-relevant election in year", "elections", ELEC, "0/1", "A", "", "n/a", "any corroborated exec-relevant contest in calendar year", "annual H1"),
    ("exec_change", "Chief-executive change", "political transitions", VDEM, "0/1", "A", "", "n/a", "V-Dem leader name differs from previous year (HOS if directly elected chief exec, else HOG)", "R1 outcome"),
    ("irregular_exec_change", "Chief-executive change without exec election", "political transitions", VDEM, "0/1", "A", "", "n/a", "exec_change==1 & exec_election==0", "R1 outcome"),
    ("wgi_rl_est", "Rule of Law estimate", "institutions", WGI, "approx -2.5..2.5", "A", "", "higher = better", "2026 release (revised history)", "annual within/Mundlak"),
    ("wgi_rl_2014", "Rule of Law, 2014", "institutions", WGI, "approx -2.5..2.5", "fixed", "", "higher = better", "2014 value, centred in models", "H2 primary moderator, H5"),
    ("wgi_[rq|ge|va|cc|pv]_2014", "Other WGI dimensions, 2014", "institutions", WGI, "approx -2.5..2.5", "fixed", "", "higher = better", "2014 value", "H2 alternatives"),
    ("v2x_jucon_2014 / v2xlg_legcon_2014", "Judicial / legislative constraints on executive, 2014", "institutions", VDEM, "0..1", "fixed", "", "higher = more constraint", "2014 value", "H2 alternatives"),
    ("reserves_months_2014", "Reserves in months of imports, 2014", "buffers", WDI, "months", "fixed", "", "n/a", "FI.RES.TOTL.MO", "H5 moderator"),
    ("st_debt_reserves_2014", "Short-term external debt, % of reserves, 2014", "vulnerability", WDI, "%", "fixed", "", "n/a", "DT.DOD.DSTC.IR.ZS (EMDE debtors only)", "H5 moderator"),
    ("L_gdp_growth", "Real GDP growth, previous year", "macro control", WEO, "%", "A", "", "n/a", "NGDP_RPCH lagged one year", "baseline control"),
    ("L_inflation", "CPI inflation, previous year", "macro control", WEO, "%", "A", "", "n/a", "PCPIPCH lagged", "baseline control"),
    ("L_ca_gdp", "Current account, % GDP, previous year", "macro control", WEO, "% GDP", "A", "", "positive = surplus", "BCA_NGDPD lagged", "baseline control"),
    ("L_fiscal_balance_gdp", "Gen. gov. net lending, % GDP, previous year", "macro control", WEO, "% GDP", "A", "", "positive = surplus", "GGXCNL_NGDP lagged", "baseline control"),
    ("L_public_debt_gdp", "Gen. gov. gross debt, % GDP, previous year", "macro control", WEO, "% GDP", "A", "", "n/a", "GGXWDG_NGDP lagged", "baseline control"),
    ("L_log_gdp_pc", "Log GDP per capita (USD), previous year", "macro control", WEO, "log USD", "A", "", "n/a", "log(NGDPDPC) lagged", "baseline control"),
    ("vix", "VIX, quarterly mean", "global risk", ("FRED", "VIXCLS", "https://fred.stlouisfed.org/series/VIXCLS"), "index", "Q", "", "n/a", "mean of daily; standardised in H5", "H5 (interaction only)"),
    ("wui", "World Uncertainty Index", "uncertainty", ("WUI (Ahir, Bloom, Furceri)", "T2", "https://worlduncertaintyindex.com/data/"), "index", "Q", "", "higher = more uncertainty", "as published", "descriptive / not baseline (mediator risk)"),
    ("rsui_index / rsui_event", "Reported Social Unrest Index / major event", "unrest", ("IMF RSUI", "HEADLINE/EVENT", "https://data.imf.org"), "index / 0-1", "Q", "", "n/a", "quarterly mean / max of monthly", "R1 outcome, events file"),
    ("gpr_country", "Country geopolitical risk", "geopolitics", ("Caldara & Iacoviello", "GPRC_*", "https://www.matteoiacoviello.com/gpr.htm"), "index", "Q", "", "n/a", "quarterly mean", "descriptive (44 countries)"),
    ("policy_rate", "Central bank policy rate", "monetary policy", ("BIS", "WS_CBPOL", "https://www.bis.org/statistics/cbpol.htm"), "% p.a.", "Q", "", "n/a", "end of quarter", "H4 exploratory"),
    ("ka_open", "Chinn-Ito financial openness (normalised)", "capital controls", ("Chinn-Ito", "ka_open", "https://web.pdx.edu/~ito/Chinn-Ito_website.htm"), "0..1", "A", "", "higher = more open", "as published (to 2023)", "H4 exploratory; 2014 moderator"),
    ("private_inflows_gdp", "Gross private inflows, % GDP (post-hoc)", "capital flows", BOP, "% of GDP", "Q", "", SIGN_IN,
     "gross inflows minus CB/GG OI liabilities (F2,F4,F81,F8AP) and SDR allocations", "POST-HOC alignment only"),
]


def dictionary():
    A = pd.read_parquet(PROCESSED / "annual_country_panel.parquet")
    Q = pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")
    Am, Qm = A[A.year.between(2015, 2025)], Q[Q.year.between(2015, 2025)]
    rows = []
    for name, label, concept, (src, code, url), unit, freq, cur, sign, trans, role in D:
        df = Qm if name in Qm.columns else (Am if name in Am.columns else None)
        miss = rng = ""
        if df is not None and df[name].dtype.kind in "fi":
            miss = f"{df[name].isna().mean():.3f} ({'Q' if df is Qm else 'A'} 2015-25)"
            rng = f"p1={df[name].quantile(.01):.2f}, p99={df[name].quantile(.99):.2f}"
        rows.append({"variable_name": name, "variable_label": label, "concept": concept, "source_name": src,
                     "source_series_code": code, "source_url": url, "unit": unit, "frequency": freq, "currency": cur,
                     "sign_convention": sign, "transformation": trans, "expected_range": rng, "missingness": miss,
                     "data_vintage": "retrieved 2026-10-11 (see source_register.csv)",
                     "methodological_notes": "BPM6 definitions" if src == "IMF BOP" else "", "role_in_model": role})
    pd.DataFrame(rows).to_csv(CONFIG / "variable_dictionary.csv", index=False)


REGISTER = [
    ("imf_bop", "International Monetary Fund (STA)", "SDMX 2.1 REST API, CSV", "BOP v21.0.0; data to 2026Q2 for 61 sample economies", "Open (IMF terms of use)", "IMF (2026), BOP/IIP Statistics"),
    ("imf_weo", "International Monetary Fund (RES)", "DataMapper JSON API (curl)", "Current WEO vintage at retrieval; 2026 values are projections", "Open", "IMF World Economic Outlook database"),
    ("worldbank", "World Bank", "API v2 JSON", "WDI updated 2026-10-08; WGI updated 2026-09-25 (2026 release, historical revisions)", "CC BY 4.0", "World Bank WDI; Kaufmann & Kraay WGI 2026"),
    ("vdem", "V-Dem Institute", "GitHub raw file (vdemdata R package, .RData)", "v16 (commit 2026-03-17); data through 2025", "CC BY-SA 4.0; website download requires registration form (not used)", "Coppedge et al. (2026) V-Dem v16"),
    ("idea", "International IDEA", "Website export endpoint (xlsx)", "As at 2026-10-11; ~half of post-2013 rows year-only dates", "Open with attribution", "International IDEA Voter Turnout Database"),
    ("wikipedia_calendar", "Wikipedia contributors", "MediaWiki API (rate-limited, 6 s spacing)", "Revision IDs stored in each JSON file", "CC BY-SA 4.0", "Wikipedia, '<year> national electoral calendar'"),
    ("wui", "Ahir, Bloom & Furceri", "Direct xlsx download", "July 2026 update (to 2026Q2)", "Open with citation", "Ahir, Bloom & Furceri (2022) NBER WP 29763"),
    ("gpr", "Caldara & Iacoviello", "Direct xls download", "As at retrieval (monthly to 2026-09)", "Open with citation", "Caldara & Iacoviello (2022) AER"),
    ("imf_rsui", "IMF (WHD)", "SDMX 2.1 REST API, CSV", "IMF.WHD:RSUI 1.0.0; to 2026-05", "Open", "Barrett et al. (2022) JDE"),
    ("chinn_ito", "Chinn & Ito", "Direct xls download", "2023 update", "Open with citation", "Chinn & Ito (2006) JDE"),
    ("bis", "Bank for International Settlements", "BIS SDMX API v1, CSV", "WS_CBPOL monthly", "Open (BIS terms)", "BIS central bank policy rates"),
    ("fred", "Federal Reserve Bank of St. Louis", "fredgraph CSV endpoint (curl)", "As at retrieval", "Public domain / source terms (VIX: CBOE; HY OAS: ICE)", "FRED series as listed"),
]


def register():
    log = pd.read_csv(RAW / "source_register_log.csv")
    log["folder"] = log.file.str.split("/").str[2]
    agg = log.groupby("folder").agg(files=("file", "nunique"), first_retrieved=("retrieved_utc", "min"),
                                    last_retrieved=("retrieved_utc", "max"), total_bytes=("bytes", "sum")).reset_index()
    reg = pd.DataFrame(REGISTER, columns=["folder", "source_owner", "retrieval_method", "data_vintage", "access_restrictions", "citation"])
    reg = reg.merge(agg, on="folder", how="left")
    reg.to_csv(PROCESSED / "source_register.csv", index=False)


if __name__ == "__main__":
    dictionary()
    register()
    print(pd.read_csv(PROCESSED / "source_register.csv")[["folder", "files", "first_retrieved"]].to_string())
