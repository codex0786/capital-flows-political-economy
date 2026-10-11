"""Crisis/event, policy-lever and market-price sources (v3 additions).

Crises and events
  * BoC–BoE Sovereign Default Database, 2026 edition (Bank of Canada / Bank of England), 1960–2025
  * IMF WP/26/94 (2026 update of Laeven & Valencia systemic banking crises, through 2025) — PDF archived;
    episode dates are transcribed from its tables in src/cleaning/crisis_events.py with page references
  * IMF Fund Accounts (IMF.STA:FA): IMF credit outstanding, used to date IMF financing episodes
Policy levers
  * Fernández, Klein, Rebucci, Schindler & Uribe (2016) capital-control measures, 2021 update (Columbia)
  * Bergant, Fernández, Teoh & Uribe (2025) "Beyond Capital Controls": iBoP-C quarterly cumulative net
    tightenings of cross-border flow restrictions and FKRSU LLM extension (GitHub, free use with citation)
  * IMF FX intervention dataset (Adler et al.; IMF.STA:WPFXI)
  * IMF Monetary and Financial Statistics, monetary-policy-related rate (IMF.STA:MFS_IR, MFS166)
Market prices
  * IMF exchange rates (IMF.STA:ER): national currency per USD, monthly, end of period and average
  * IMF MFS_IR government bond and treasury-bill yields, monthly
  * FRED daily exchange rates (Federal Reserve H.10) for the emerging-market currencies it publishes
"""
from __future__ import annotations

import sys

from src.common import RAW, fetch_raw, get_logger

log = get_logger("ingest.v3")
SDMX = "https://api.imf.org/external/sdmx/2.1/data"
CSV = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}


def crises():
    fetch_raw("https://www.bankofcanada.ca/wp-content/uploads/2026/10/BoC-BoE-Database-2026.xlsx",
              RAW / "boc_boe" / "BoC-BoE-Database-2026.xlsx", "BoC–BoE Sovereign Default Database (2026 edition)",
              note="Sovereign debt in default by creditor type, 1960–2025; Staff Analytical Paper 2026-48", use_curl=True)
    fetch_raw("https://www.imf.org/-/media/files/publications/wp/2026/english/wpiea2026094-source-pdf.pdf",
              RAW / "imf_crises" / "wpiea2026094.pdf", "IMF WP/26/94 Systemic Banking Crises Database 1970–2025",
              note="Update of Laeven & Valencia (2013, 2020)", use_curl=True)
    fetch_raw(f"{SDMX}/IMF.STA,FA/.CLIMF_POQT_PT_A_PT+CLIMF_USD+F4IMFGRA_USD+F4PRGT_USD.Q", RAW / "imf_fa" / "fa_q.csv",
              "IMF Fund Accounts (IMF.STA:FA)", params={"startPeriod": "2012"}, headers=CSV, timeout=1500,
              note="IMF credit outstanding (% of quota, USD), GRA and PRGT loans; quarterly")


def policy():
    fetch_raw("http://www.columbia.edu/~mu2166/fkrsu/2021-FKRSU-Update-12-08-2021.xlsx", RAW / "capital_controls" / "FKRSU_2021.xlsx",
              "Fernández et al. capital control measures, 2021 update", use_curl=True, headers={"User-Agent": "Mozilla/5.0 (academic research)"},
              note="Annual restrictiveness indices by asset class, inflows/outflows")
    base = "https://raw.githubusercontent.com/kteoh37/bftu_cross_border/main/excel_files"
    for f in ("BFTU_iBoPC.xlsx", "FKRSU_LLM.xlsx"):
        fetch_raw(f"{base}/{f}", RAW / "capital_controls" / f, "Bergant, Fernández, Teoh & Uribe (2025) cross-border flow restrictions",
                  timeout=600, note="Free use with citation of 'Beyond Capital Controls' (2025)")
    fetch_raw(f"{SDMX}/IMF.STA,WPFXI/.FXI_BROAD_PROXY_GDP+FXI_SPOT_PROXY_GDP+FXI_BROAD_PUB_GDP+DE_FACTO_EXR_REGIME.Q",
              RAW / "imf_fxi" / "fxi_q.csv", "IMF FX intervention dataset (IMF.STA:WPFXI)", params={"startPeriod": "2012"},
              headers=CSV, timeout=1500, note="Adler, Chang, Mano & Shao; quarterly, % of GDP")
    fetch_raw(f"{SDMX}/IMF.STA,MFS_IR/.MFS166_RT_PT_A_PT+S13BONDS_RT_PT_A_PT+S13BONDSML_RT_PT_A_PT+S13BOND_RT_PT_A_PT+GSTBILY_RT_PT_A_PT.M",
              RAW / "imf_ir" / "ir_m.csv", "IMF MFS interest rates (IMF.STA:MFS_IR)", params={"startPeriod": "2012"},
              headers=CSV, timeout=1500, note="Monetary-policy-related rate; government bond and T-bill yields; monthly")


FRED_FX = {"DEXBZUS": "BRA", "DEXMXUS": "MEX", "DEXINUS": "IND", "DEXSFUS": "ZAF", "DEXKOUS": "KOR", "DEXTHUS": "THA",
           "DEXMAUS": "MYS", "DEXCHUS": "CHN", "DEXTAUS": "TWN", "DEXSLUS": "LKA", "DEXHKUS": "HKG", "DEXSIUS": "SGP"}


def markets():
    fetch_raw(f"{SDMX}/IMF.STA,ER/.XDC_USD.EOP_RT+PA_RT.M", RAW / "imf_er" / "er_m.csv", "IMF exchange rates (IMF.STA:ER)",
              params={"startPeriod": "2012"}, headers=CSV, timeout=1500, note="National currency per USD, monthly, end of period and average")
    for sid, iso in FRED_FX.items():
        fetch_raw("https://fred.stlouisfed.org/graph/fredgraph.csv", RAW / "fred_fx" / f"{sid}.csv", "FRED H.10 daily exchange rates",
                  params={"id": sid}, use_curl=True, note=f"{iso} currency per USD, daily (noon buying rates)")


ALL = {"crises": crises, "policy": policy, "markets": markets}

if __name__ == "__main__":
    for name in (sys.argv[1:] or ALL):
        try:
            ALL[name]()
        except RuntimeError as e:
            log.error("group %s failed: %s", name, e)
