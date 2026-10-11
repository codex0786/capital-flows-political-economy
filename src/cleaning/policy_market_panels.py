"""Policy-lever and market-price panels.

data/processed/policy_quarterly.parquet  iso3, quarter:
  ccr_total / ccr_in / ccr_out        cumulative net tightenings of cross-border flow restrictions (iBoP-C)
  d_ccr_total / d_ccr_in / d_ccr_out  change in the quarter (measures tightened minus eased)
  fxi_gdp                             FX intervention, broad proxy, % of GDP (IMF WPFXI; + = purchases of FX)
  fxi_spot_gdp                        spot intervention proxy, % of GDP
  policy_rate / d_policy_rate         monetary-policy-related rate (IMF MFS_IR MFS166), end of quarter; BIS rate fills gaps
data/processed/market_monthly.parquet iso3, month:
  fx / fx_avg / dep_m                 local currency per USD (end of month / average); % depreciation in the month
  yld / yld_source                    government bond yield (S13BONDS > S13BONDSML > S13BOND), else treasury-bill yield
  spread_us                           yld minus the US 10-year Treasury yield (FRED DGS10, monthly average)
data/processed/market_daily.parquet   iso3, date, fx (FRED H.10), dep_d (% daily change, + = depreciation)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import INTERIM, PROCESSED, RAW, get_logger
from src.cleaning.crisis_events import capital_control_panel
from src.ingest.events_policy_markets import FRED_FX

log = get_logger("panels_v3")


def sdmx(path, cols=("COUNTRY", "INDICATOR", "TIME_PERIOD", "OBS_VALUE")):
    d = pd.read_csv(path, usecols=lambda c: c in cols or c == "TYPE_OF_TRANSFORMATION", low_memory=False)
    return d.dropna(subset=["TIME_PERIOD"])


def policy_quarterly():
    cc = capital_control_panel().rename(columns={"total": "ccr_total", "total_in": "ccr_in", "total_out": "ccr_out",
                                                  "d_total": "d_ccr_total", "d_total_in": "d_ccr_in", "d_total_out": "d_ccr_out"})
    cc = cc[["iso3", "quarter", "ccr_total", "ccr_in", "ccr_out", "d_ccr_total", "d_ccr_in", "d_ccr_out"]]
    f = sdmx(RAW / "imf_fxi" / "fxi_q.csv")
    f["quarter"] = f.TIME_PERIOD.str.replace("-", "")
    fx = f.pivot_table(index=["COUNTRY", "quarter"], columns="INDICATOR", values="OBS_VALUE", aggfunc="first").reset_index()
    fx = fx.rename(columns={"COUNTRY": "iso3", "FXI_BROAD_PROXY_GDP": "fxi_gdp", "FXI_SPOT_PROXY_GDP": "fxi_spot_gdp",
                            "DE_FACTO_EXR_REGIME": "exr_regime_de_facto"})
    keep = [c for c in ["iso3", "quarter", "fxi_gdp", "fxi_spot_gdp", "exr_regime_de_facto"] if c in fx.columns]
    fx = fx[keep]
    ir = sdmx(RAW / "imf_ir" / "ir_m.csv")
    pr = ir[ir.INDICATOR == "MFS166_RT_PT_A_PT"].copy()
    pr["quarter"] = pd.PeriodIndex(pr.TIME_PERIOD.str.replace("-M", "-"), freq="M").asfreq("Q").astype(str)
    pr = pr.sort_values("TIME_PERIOD").groupby(["COUNTRY", "quarter"]).OBS_VALUE.last().rename("policy_rate").reset_index().rename(columns={"COUNTRY": "iso3"})
    bis = pd.read_parquet(INTERIM / "policy_rates.parquet").rename(columns={"policy_rate": "bis_rate"})
    pr = pr.merge(bis, on=["iso3", "quarter"], how="outer")
    pr["policy_rate_source"] = np.where(pr.policy_rate.notna(), "IMF MFS166", np.where(pr.bis_rate.notna(), "BIS", None))
    pr["policy_rate"] = pr.policy_rate.fillna(pr.bis_rate)
    pr = pr.drop(columns="bis_rate").sort_values(["iso3", "quarter"])
    pr["d_policy_rate"] = pr.groupby("iso3").policy_rate.diff()
    P = cc.merge(fx, on=["iso3", "quarter"], how="outer").merge(pr, on=["iso3", "quarter"], how="outer")
    P = P[(P.quarter >= "2012Q1") & P.iso3.str.fullmatch(r"[A-Z]{3}", na=False)]
    P.to_parquet(PROCESSED / "policy_quarterly.parquet", index=False)
    return P


def market_monthly():
    e = sdmx(RAW / "imf_er" / "er_m.csv")
    e = e[e.INDICATOR == "XDC_USD"]
    e["month"] = e.TIME_PERIOD.str.replace("-M", "-")
    w = e.pivot_table(index=["COUNTRY", "month"], columns="TYPE_OF_TRANSFORMATION", values="OBS_VALUE", aggfunc="first").reset_index()
    w = w.rename(columns={"COUNTRY": "iso3", "EOP_RT": "fx", "PA_RT": "fx_avg"}).sort_values(["iso3", "month"])
    w["dep_m"] = 100 * (w.fx / w.groupby("iso3").fx.shift() - 1)
    ir = sdmx(RAW / "imf_ir" / "ir_m.csv")
    ir["month"] = ir.TIME_PERIOD.str.replace("-M", "-")
    y = ir.pivot_table(index=["COUNTRY", "month"], columns="INDICATOR", values="OBS_VALUE", aggfunc="first").reset_index().rename(columns={"COUNTRY": "iso3"})
    order = [("S13BONDS_RT_PT_A_PT", "government bond"), ("S13BONDSML_RT_PT_A_PT", "government bond (medium/long)"),
             ("S13BOND_RT_PT_A_PT", "government bond"), ("GSTBILY_RT_PT_A_PT", "treasury bill")]
    y["yld"], y["yld_source"] = np.nan, None
    for col, lab in order:
        if col in y.columns:
            m = y.yld.isna() & y[col].notna()
            y.loc[m, "yld"], y.loc[m, "yld_source"] = y.loc[m, col], lab
    y = y[["iso3", "month", "yld", "yld_source"]]
    us = pd.read_csv(RAW / "fred" / "DGS10.csv")
    us.columns = ["date", "v"]
    us["v"] = pd.to_numeric(us.v, errors="coerce")
    us["month"] = pd.to_datetime(us.date).dt.strftime("%Y-%m")
    us = us.groupby("month").v.mean().rename("ust10").reset_index()
    M = w.merge(y, on=["iso3", "month"], how="outer").merge(us, on="month", how="left")
    M["spread_us"] = M.yld - M.ust10
    M = M[(M.month >= "2012-01") & M.iso3.str.fullmatch(r"[A-Z]{3}", na=False)]
    M.to_parquet(PROCESSED / "market_monthly.parquet", index=False)
    return M


def market_daily():
    out = []
    for sid, iso in FRED_FX.items():
        p = RAW / "fred_fx" / f"{sid}.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p)
        d.columns = ["date", "fx"]
        d["fx"] = pd.to_numeric(d.fx, errors="coerce")
        d = d.dropna()
        d["date"] = pd.to_datetime(d.date)
        d = d[d.date >= "2012-01-01"].sort_values("date")
        d["dep_d"] = 100 * (d.fx / d.fx.shift() - 1)
        d["iso3"] = iso
        out.append(d)
    D = pd.concat(out, ignore_index=True)
    D.to_parquet(PROCESSED / "market_daily.parquet", index=False)
    return D


if __name__ == "__main__":
    P = policy_quarterly()
    M = market_monthly()
    D = market_daily()
    q = P[P.quarter.between("2015Q1", "2025Q4")]
    print("policy: countries", P.iso3.nunique(), {c: round(float(q[c].notna().mean()), 2) for c in ["ccr_total", "fxi_gdp", "policy_rate"]})
    m = M[M.month.between("2015-01", "2025-12")]
    print("market: countries", M.iso3.nunique(), {c: round(float(m[c].notna().mean()), 2) for c in ["fx", "yld", "spread_us"]},
          "yield countries", m.dropna(subset=["yld"]).iso3.nunique(), m.yld_source.value_counts().to_dict())
    print("daily:", D.iso3.nunique(), D.date.min().date(), D.date.max().date())
