"""Parse archived raw files into tidy interim tables (data/interim/*.parquet).

Conventions
-----------
* Keys: ``iso3`` (ISO 3166-1 alpha-3), ``year`` (int) and, for quarterly data, ``quarter``
  as a pandas Period string "YYYYQn".
* Missing values stay missing (NaN). Nothing is zero-filled.
* Units are recorded in the variable dictionary; values here are in source units except
  where a column name states otherwise (e.g. ``*_usd``).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pyreadr

from src.common import INTERIM, RAW, get_logger

log = get_logger("cleaning")

# ----------------------------------------------------------------------------- BOP
BOP_MAP = {
    # (INDICATOR, BOP_ACCOUNTING_ENTRY): output column (USD)
    ("D_F", "L_NIL_T"): "fdi_in_usd",
    ("D_F", "A_NFA_T"): "fdi_out_usd",
    ("P_F", "L_NIL_T"): "port_in_usd",
    ("P_F", "A_NFA_T"): "port_out_usd",
    ("P_F5", "L_NIL_T"): "pe_in_usd",
    ("P_F5", "A_NFA_T"): "pe_out_usd",
    ("P_F3", "L_NIL_T"): "pd_in_usd",
    ("P_F3", "A_NFA_T"): "pd_out_usd",
    ("O_F", "L_NIL_T"): "oi_in_usd",
    ("O_F", "A_NFA_T"): "oi_out_usd",
    ("F_F7", "NNAFANIL_T"): "deriv_net_usd",
    ("R_F", "A_T"): "reserves_flow_usd",
    ("FAB", "NNAFANIL_T"): "fa_balance_usd",
    ("CAB", "NETCD_T"): "ca_balance_usd",
}


def parse_bop(freq: str) -> pd.DataFrame:
    """Return one row per country-period with BPM6 financial-account components in USD.

    OBS_VALUE is reported in US dollar units (SCALE is a display attribute only; verified
    against published Brazil 2015 FDI liabilities of ~USD 65bn).
    """
    path = RAW / "imf_bop" / f"imf_bop_{freq}_raw.csv"
    cols = ["COUNTRY", "BOP_ACCOUNTING_ENTRY", "INDICATOR", "UNIT", "FREQUENCY", "TIME_PERIOD", "OBS_VALUE"]
    d = pd.read_csv(path, usecols=cols, dtype={"TIME_PERIOD": str})
    d = d[(d["UNIT"] == "USD") & d.TIME_PERIOD.notna()]  # series headers with no observations carry no period
    d["var"] = [BOP_MAP.get((i, e)) for i, e in zip(d.INDICATOR, d.BOP_ACCOUNTING_ENTRY)]
    d = d.dropna(subset=["var"])
    dup = d.duplicated(["COUNTRY", "TIME_PERIOD", "var"], keep=False)
    if dup.any():
        raise ValueError(f"duplicate BOP keys: {d[dup].head()}")
    w = d.pivot(index=["COUNTRY", "TIME_PERIOD"], columns="var", values="OBS_VALUE").reset_index()
    w = w.rename(columns={"COUNTRY": "iso3"})
    if freq == "A":
        w["year"] = w.TIME_PERIOD.astype(int)
    else:
        w["quarter"] = w.TIME_PERIOD.str.replace("-", "")
        w["year"] = w.quarter.str[:4].astype(int)
    w = w.drop(columns="TIME_PERIOD")
    w.columns.name = None
    log.info("BOP %s: %d rows, %d economies", freq, len(w), w.iso3.nunique())
    return w


# ----------------------------------------------------------------------------- WEO
def parse_weo() -> pd.DataFrame:
    frames = []
    for p in sorted((RAW / "imf_weo").glob("weo_*.json")):
        code = p.stem.replace("weo_", "")
        if code.endswith("groups"):
            continue
        vals = json.loads(p.read_text())["values"][code]
        rows = [(k, int(y), v) for k, d in vals.items() for y, v in d.items()]
        frames.append(pd.DataFrame(rows, columns=["iso3", "year", code]).set_index(["iso3", "year"]))
    w = pd.concat(frames, axis=1).reset_index()
    w = w[w.iso3.str.len() == 3]  # drop group aggregates such as ADVEC/OEMDC
    return w


# ----------------------------------------------------------------------------- World Bank
def _wb_json(p) -> pd.DataFrame:
    j = json.loads(p.read_text())
    meta, rows = j[0], j[1] or []
    df = pd.DataFrame({
        "iso3": [r["countryiso3code"] for r in rows],
        "year": [int(r["date"]) for r in rows],
        "value": [r["value"] for r in rows],
    })
    # regional/income aggregates have blank or non-ISO codes; dropping them keeps keys unique
    df = df[df.iso3.str.len() == 3]
    if df.duplicated(["iso3", "year"]).any():
        raise ValueError(f"duplicate World Bank keys in {p.name}")
    return df, meta


def parse_wdi() -> pd.DataFrame:
    out = None
    for p in sorted((RAW / "worldbank").glob("wdi_*.json")):
        code = p.stem.replace("wdi_", "")
        df, meta = _wb_json(p)
        if int(meta["total"]) > int(meta["per_page"]):
            raise ValueError(f"{code}: paging incomplete")
        df = df.rename(columns={"value": code}).set_index(["iso3", "year"])
        out = df if out is None else out.join(df, how="outer")
    out = out.reset_index()
    return out[out.iso3.str.len() == 3]


def parse_wgi() -> pd.DataFrame:
    out = None
    for p in sorted((RAW / "worldbank").glob("wgi_[A-Z][A-Z].*.json")):  # excludes wgi_source_meta
        code = p.stem.replace("wgi_", "")  # e.g. RL.EST
        df, meta = _wb_json(p)
        name = "wgi_" + code.lower().replace(".", "_")
        df = df.rename(columns={"value": name}).set_index(["iso3", "year"])
        out = df if out is None else out.join(df, how="outer")
    out = out.reset_index()
    return out[out.iso3.str.len() == 3]


def parse_wb_meta() -> pd.DataFrame:
    j = json.loads((RAW / "worldbank" / "wb_country_meta.json").read_text())[1]
    m = pd.DataFrame([{
        "iso3": r["id"], "iso2": r["iso2Code"], "country_name": r["name"],
        "wb_region": r["region"]["value"], "wb_income": r["incomeLevel"]["value"],
        "is_aggregate": r["region"]["value"] == "Aggregates",
    } for r in j])
    return m[~m.is_aggregate].drop(columns="is_aggregate")


# ----------------------------------------------------------------------------- V-Dem
VDEM_VARS = [
    "country_name", "country_text_id", "year",
    "v2x_polyarchy", "v2x_libdem", "v2x_jucon", "v2xlg_legcon", "v2x_rule", "v2x_execorr",
    "v2x_regime", "v2x_elecreg", "v2xel_elecparl", "v2xel_elecpres",
    "v2eltype_0", "v2eltype_1", "v2eltype_6", "v2eltype_7",
    "v2elturnhog", "v2elturnhos", "v2exnamhos", "v2exnamhog", "v2ex_hosw", "v2exhoshog",
    "v2x_ex_direlect", "v2cademmob", "v2caconmob", "v2elvotlrg", "v2elfrfair",
]


def parse_vdem() -> pd.DataFrame:
    r = pyreadr.read_r(RAW / "vdem" / "vdem_v16.RData")
    df = list(r.values())[0]
    keep = [c for c in VDEM_VARS if c in df.columns]
    missing = set(VDEM_VARS) - set(keep)
    if missing:
        log.warning("V-Dem variables not found: %s", sorted(missing))
    hist = df.loc[df.year >= 1960, ["country_text_id", "year", "v2eltype_0", "v2eltype_1",
                                     "v2eltype_6", "v2eltype_7"]].rename(columns={"country_text_id": "iso3"})
    hist["year"] = hist.year.astype(int)
    hist.to_parquet(INTERIM / "vdem_election_history.parquet")  # for term-length rule
    v = df.loc[df.year >= 2005, keep].rename(columns={"country_text_id": "iso3"})
    v["year"] = v.year.astype(int)
    # V-Dem uses some non-ISO codes; map the ones relevant to this sample
    v["iso3"] = v.iso3.replace({"XKX": "XKX", "PSE": "PSE", "SML": "SOM_SL", "ZZB": "EAZ", "PSG": "PSE_G"})
    return v


# ----------------------------------------------------------------------------- IDEA elections
def parse_idea() -> pd.DataFrame:
    x = pd.read_excel(RAW / "idea" / "idea_voter_turnout_all.xlsx", sheet_name="All")
    x = x.rename(columns={"ISO3": "iso3", "Country": "country", "Election Type": "etype", "Year": "date"})
    x = x[x.etype.isin(["Parliamentary", "Presidential"])].copy()
    x["date"] = pd.to_datetime(x["date"], errors="coerce")
    bad = x.date.isna().sum()
    if bad:
        log.warning("IDEA: %d rows with unparseable dates dropped", bad)
    x = x.dropna(subset=["date"])
    x["etype"] = x.etype.str.lower()
    return x[["iso3", "country", "etype", "date", "Voter Turnout"]].rename(columns={"Voter Turnout": "turnout"})


# ----------------------------------------------------------------------------- uncertainty
def parse_wui() -> pd.DataFrame:
    t = pd.read_excel(RAW / "wui" / "WUI_Data_2026_07.xlsx", sheet_name="T2")
    t = t.melt(id_vars="year", var_name="iso3", value_name="wui")
    t["quarter"] = t.year.str.upper()
    return t[["iso3", "quarter", "wui"]].dropna()


def parse_gpr() -> pd.DataFrame:
    g = pd.read_excel(RAW / "gpr" / "data_gpr_export.xls")
    g["quarter"] = pd.PeriodIndex(g["month"], freq="Q").astype(str)
    cols = [c for c in g.columns if c.startswith("GPRC_")]
    q = g.groupby("quarter")[cols + ["GPR"]].mean()
    glob = q["GPR"].rename("gpr_global").reset_index()
    c = q[cols].reset_index().melt(id_vars="quarter", var_name="iso3", value_name="gpr_country")
    c["iso3"] = c.iso3.str.replace("GPRC_", "")
    return c.dropna(), glob


def parse_rsui() -> pd.DataFrame:
    r = pd.read_csv(RAW / "imf_rsui" / "rsui_raw.csv", usecols=["COUNTRY", "INDICATOR", "TIME_PERIOD", "OBS_VALUE"])
    r["month"] = pd.PeriodIndex(r.TIME_PERIOD.str.replace("-M", "-"), freq="M")
    r["quarter"] = r.month.dt.asfreq("Q").astype(str)
    agg =r.groupby(["COUNTRY", "quarter", "INDICATOR"]).OBS_VALUE.agg(["mean", "max", "count"]).unstack()
    out = pd.DataFrame({
        "rsui_index": agg[("mean", "HEADLINE")],
        "rsui_event": agg[("max", "EVENT")],            # 1 if a major unrest event in any month
        "rsui_months": agg[("count", "HEADLINE")],
    }).reset_index().rename(columns={"COUNTRY": "iso3"})
    return out


def parse_kaopen() -> pd.DataFrame:
    k = pd.read_excel(RAW / "chinn_ito" / "kaopen_2023.xls")
    return k.rename(columns={"ccode": "iso3"})[["iso3", "year", "kaopen", "ka_open"]]


def parse_bis_policy_rates(iso2_to_iso3: dict) -> pd.DataFrame:
    b = pd.read_csv(RAW / "bis" / "bis_cbpol_m.csv", usecols=["REF_AREA", "TIME_PERIOD", "OBS_VALUE"])
    b["iso3"] = b.REF_AREA.map(iso2_to_iso3)
    unmapped = b.loc[b.iso3.isna(), "REF_AREA"].unique()
    if len(unmapped):
        log.info("BIS policy rates not mapped to a single country: %s", list(unmapped))
    b = b.dropna(subset=["iso3"])
    b["quarter"] = pd.PeriodIndex(b.TIME_PERIOD, freq="M").asfreq("Q").astype(str)
    q = b.sort_values("TIME_PERIOD").groupby(["iso3", "quarter"]).OBS_VALUE.last().rename("policy_rate")
    return q.reset_index()


def parse_fred() -> pd.DataFrame:
    out = []
    for p in sorted((RAW / "fred").glob("*.csv")):
        s = pd.read_csv(p)
        s.columns = ["date", "value"]
        s["value"] = pd.to_numeric(s.value, errors="coerce")  # FRED uses "." for missing
        s["quarter"] = pd.PeriodIndex(pd.to_datetime(s.date), freq="Q").astype(str)
        if p.stem == "DTWEXBGS":
            q = s.groupby("quarter").value.last()
        else:
            q = s.groupby("quarter").value.mean()
        out.append(q.rename(p.stem))
    return pd.concat(out, axis=1).reset_index()


def _meta_iso2():
    meta = parse_wb_meta()
    meta.to_parquet(INTERIM / "wb_meta.parquet")
    return dict(zip(meta.iso2, meta.iso3))


def _gpr():
    gc, gg = parse_gpr()
    gc.to_parquet(INTERIM / "gpr_country.parquet")
    gg.to_parquet(INTERIM / "gpr_global.parquet")


STEPS = {
    "meta": _meta_iso2,
    "bop_a": lambda: parse_bop("A").to_parquet(INTERIM / "bop_annual.parquet"),
    "bop_q": lambda: parse_bop("Q").to_parquet(INTERIM / "bop_quarterly.parquet"),
    "weo": lambda: parse_weo().to_parquet(INTERIM / "weo.parquet"),
    "wdi": lambda: parse_wdi().to_parquet(INTERIM / "wdi.parquet"),
    "wgi": lambda: parse_wgi().to_parquet(INTERIM / "wgi.parquet"),
    "vdem": lambda: parse_vdem().to_parquet(INTERIM / "vdem.parquet"),
    "idea": lambda: parse_idea().to_parquet(INTERIM / "idea_elections.parquet"),
    "wui": lambda: parse_wui().to_parquet(INTERIM / "wui.parquet"),
    "gpr": _gpr,
    "rsui": lambda: parse_rsui().to_parquet(INTERIM / "rsui.parquet"),
    "kaopen": lambda: parse_kaopen().to_parquet(INTERIM / "kaopen.parquet"),
    "policy": lambda: parse_bis_policy_rates(_meta_iso2()).to_parquet(INTERIM / "policy_rates.parquet"),
    "fred": lambda: parse_fred().to_parquet(INTERIM / "global_factors.parquet"),
}


if __name__ == "__main__":
    # Each step runs in its own process (see Makefile/run_pipeline.sh): V-Dem alone needs ~2 GB RAM.
    import sys
    INTERIM.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or STEPS:
        STEPS[name]()
        log.info("interim step %s done", name)
