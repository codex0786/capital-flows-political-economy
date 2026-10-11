"""Macroeconomic, governance, uncertainty and global-factor sources.

Each function archives the original response unmodified under data/raw/<source>/.
Parsing into tidy tables happens in src/cleaning/, never here.
"""
from __future__ import annotations

import json
import sys

from src.common import RAW, fetch_raw, get_logger

log = get_logger("ingest.macro")

# --- IMF World Economic Outlook (DataMapper API; current WEO vintage at retrieval) ---
WEO_INDICATORS = {
    "NGDPD": "GDP, current prices, billions of USD",
    "NGDP_RPCH": "Real GDP growth, annual percent change",
    "NGDPDPC": "GDP per capita, current prices, USD",
    "PCPIPCH": "Inflation, average consumer prices, annual percent change",
    "BCA_NGDPD": "Current account balance, percent of GDP",
    "GGXCNL_NGDP": "General government net lending/borrowing, percent of GDP",
    "GGXWDG_NGDP": "General government gross debt, percent of GDP",
    "LP": "Population, millions",
}


def weo_datamapper():
    for code in WEO_INDICATORS:
        fetch_raw(f"https://www.imf.org/external/datamapper/api/v1/{code}",
                  RAW / "imf_weo" / f"weo_{code}.json", "IMF WEO DataMapper",
                  note=WEO_INDICATORS[code], use_curl=True)
    # group composition endpoints are not exposed; aggregates used for classification checks
    fetch_raw("https://www.imf.org/external/datamapper/api/v1/NGDPD/ADVEC/OEMDC",
              RAW / "imf_weo" / "weo_NGDPD_groups.json", "IMF WEO DataMapper",
              note="Group aggregates used to verify advanced-economy membership", use_curl=True)


# --- World Bank: WDI, WGI, country metadata ---
WDI_INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "NE.TRD.GNFS.ZS": "Trade (% of GDP)",
    "FI.RES.TOTL.CD": "Total reserves including gold (current US$)",
    "FI.RES.TOTL.MO": "Total reserves in months of imports",
    "DT.DOD.DECT.CD": "External debt stocks, total (DOD, current US$)",
    "DT.DOD.DSTC.IR.ZS": "Short-term debt (% of total reserves)",
    "FS.AST.PRVT.GD.ZS": "Domestic credit to private sector (% of GDP)",
    "CM.MKT.LCAP.GD.ZS": "Market capitalization of listed domestic companies (% of GDP)",
    "FR.INR.RINR": "Real interest rate (%)",
    "SP.POP.TOTL": "Population, total",
    "NY.GDP.TOTL.RT.ZS": "Total natural resources rents (% of GDP)",
    "TX.VAL.FUEL.ZS.UN": "Fuel exports (% of merchandise exports)",
}
WGI_INDICATORS = ["VA", "PV", "GE", "RQ", "RL", "CC"]  # 2026 release codes: GOV_WGI_<x>.<stat>


def wb_validator(body: bytes):
    """World Bank API returns HTTP 200 with a 'message' payload on invalid queries."""
    try:
        j = json.loads(body)
    except ValueError:
        return "not JSON"
    if isinstance(j, list) and j and isinstance(j[0], dict) and "message" in j[0]:
        return str(j[0]["message"])[:200]
    return None


def _wb(url: str, dest, note: str):
    fetch_raw(url, dest, "World Bank API v2", validator=wb_validator,
              params={"format": "json", "per_page": 30000, "date": "2010:2026"}, note=note)


def world_bank():
    for code, label in WDI_INDICATORS.items():
        _wb(f"https://api.worldbank.org/v2/country/all/indicator/{code}",
            RAW / "worldbank" / f"wdi_{code}.json", label)
    for c in WGI_INDICATORS:
        for suffix in ("EST", "SE", "SC"):
            code = f"GOV_WGI_{c}.{suffix}"
            fetch_raw(f"https://api.worldbank.org/v2/country/all/indicator/{code}",
                      RAW / "worldbank" / f"wgi_{c}.{suffix}.json", "World Bank WGI (API source 3)",
                      params={"format": "json", "per_page": 30000, "date": "2010:2026", "source": 3},
                      note=f"WGI {code}, 2026 release", validator=wb_validator)
    fetch_raw("https://api.worldbank.org/v2/country", RAW / "worldbank" / "wb_country_meta.json",
              "World Bank API v2", params={"format": "json", "per_page": 400},
              note="Country metadata: region, income level (current FY classification)")
    fetch_raw("https://api.worldbank.org/v2/sources/3", RAW / "worldbank" / "wgi_source_meta.json",
              "World Bank API v2", params={"format": "json"}, note="WGI source metadata / last updated")


# --- FRED (global factors; public CSV endpoint, no key required) ---
FRED_SERIES = {
    "VIXCLS": "CBOE Volatility Index, daily",
    "FEDFUNDS": "Effective federal funds rate, monthly",
    "DGS10": "10-year US Treasury constant maturity, daily",
    "DTWEXBGS": "Nominal broad US dollar index, daily",
    "POILBREUSDM": "Global price of Brent crude, USD/barrel, monthly",
    "BAMLH0A0HYM2": "ICE BofA US High Yield OAS, daily",
}


def fred():
    for sid, label in FRED_SERIES.items():
        fetch_raw("https://fred.stlouisfed.org/graph/fredgraph.csv", RAW / "fred" / f"{sid}.csv",
                  "FRED (Federal Reserve Bank of St. Louis)", params={"id": sid}, note=label,
                  use_curl=True)


# --- Uncertainty, geopolitical risk, social unrest, capital-account openness ---
def uncertainty_indices():
    fetch_raw("https://worlduncertaintyindex.com/wp-content/uploads/2026/07/WUI_Data.xlsx",
              RAW / "wui" / "WUI_Data_2026_07.xlsx", "World Uncertainty Index (Ahir, Bloom & Furceri)",
              note="Quarterly WUI, July 2026 update")
    fetch_raw("https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls",
              RAW / "gpr" / "data_gpr_export.xls", "Geopolitical Risk Index (Caldara & Iacoviello)",
              note="Monthly global and country-specific GPR")
    fetch_raw("https://web.pdx.edu/~ito/kaopen_2023.xls", RAW / "chinn_ito" / "kaopen_2023.xls",
              "Chinn-Ito Financial Openness Index", note="KAOPEN, update through 2023")
    fetch_raw("https://api.imf.org/external/sdmx/2.1/data/IMF.WHD,RSUI/all",
              RAW / "imf_rsui" / "rsui_raw.csv", "IMF Reported Social Unrest Index (IMF.WHD:RSUI)",
              params={"startPeriod": "2013"},
              headers={"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}, timeout=900,
              note="Monthly RSUI (Barrett et al.)")


def bis():
    fetch_raw("https://stats.bis.org/api/v1/data/WS_CBPOL/M", RAW / "bis" / "bis_cbpol_m.csv",
              "BIS Central bank policy rates (WS_CBPOL)",
              params={"startPeriod": "2013-01", "format": "csv"}, note="Monthly policy rates")


ALL = {"weo": weo_datamapper, "wb": world_bank, "fred": fred, "unc": uncertainty_indices, "bis": bis}



# --- International IDEA Voter Turnout Database (exact national election dates) ---
def idea_elections():
    fetch_raw("https://www.idea.int/data-tools/export", RAW / "idea" / "idea_voter_turnout_all.xlsx",
              "International IDEA Voter Turnout Database",
              params={"type": "region_only", "themeId": "293", "world": "all", "loc": "home"},
              headers={"User-Agent": "Mozilla/5.0 (academic research; capital-flows-political-economy)"},
              note="Parliamentary, presidential and EU Parliament elections with exact dates")


ALL["idea"] = idea_elections


# --- V-Dem v16 (country-year), as distributed by the V-Dem Institute's vdemdata package ---
def vdem():
    """The v-dem.net download requires a registration form (email + terms); the identical
    country-year dataset is published by the V-Dem Institute in its GitHub package."""
    base = "https://raw.githubusercontent.com/vdeminstitute/vdemdata/master/data"
    fetch_raw(f"{base}/vdem.RData", RAW / "vdem" / "vdem_v16.RData", "V-Dem v16 (vdemdata GitHub)",
              note="country-year full+others, v16 release commit 2026-03-17", timeout=600)
    fetch_raw(f"{base}/codebook.RData", RAW / "vdem" / "codebook_v16.RData", "V-Dem v16 (vdemdata GitHub)",
              note="codebook")


ALL["vdem"] = vdem


# --- IMF commodity terms of trade and real effective exchange rates (driver-model additions) ---
SDMX = "https://api.imf.org/external/sdmx/2.1/data"
CSV_ACCEPT = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}


def ctot_eer():
    fetch_raw(f"{SDMX}/IMF.RES,CTOT/.CEMPI_CTOTXM_GDP.R_RW_IX.M", RAW / "imf_ctot" / "ctot_m.csv",
              "IMF Commodity Terms of Trade (IMF.RES:CTOT)", params={"startPeriod": "2012"}, headers=CSV_ACCEPT,
              timeout=1200, note="Commodity export-minus-import price index, rolling weights, weighted by net commodity trade/GDP; monthly")
    fetch_raw(f"{SDMX}/IMF.STA,EER/.REER_IX_RY2010_ACW_RCPI.Q", RAW / "imf_eer" / "reer_q.csv",
              "IMF Effective Exchange Rates (IMF.STA:EER)", params={"startPeriod": "2012"}, headers=CSV_ACCEPT,
              timeout=1200, note="CPI-based real effective exchange rate index (2010=100), quarterly")


ALL["ctot_eer"] = ctot_eer

if __name__ == "__main__":
    for name in (sys.argv[1:] or ALL):
        try:
            ALL[name]()
        except RuntimeError as e:  # record failure and continue with other sources
            log.error("source group %s failed: %s", name, e)
