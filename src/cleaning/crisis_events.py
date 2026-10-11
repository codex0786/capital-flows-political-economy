"""Build data/processed/crisis_events.csv: a sourced, typed crisis and event database (2012–2026).

Event types and sources
  banking_crisis       IMF WP/26/94 (2026 update of Laeven & Valencia), Table A1 start/end years. Borderline
                       episodes (Table 1, marked *) are kept with verification='borderline'.
  sovereign_default    BoC–BoE Sovereign Default Database 2026: years in which the sovereign had debt in default
                       (any creditor), with the USD amount; an episode starts in the first such year after a
                       year without default.
  currency_crisis      Derived from IMF exchange rates using the Laeven–Valencia rule: annual depreciation
                       against the USD of at least 30% that is also at least 10 percentage points above the
                       previous year's depreciation.
  imf_financing        Derived from IMF Fund Accounts: IMF credit outstanding rises by at least 25% of quota
                       within four quarters (a large new disbursement), quarter of the first such rise per episode.
  high_inflation       Derived from IMF WEO: annual CPI inflation of 40% or more (Reinhart & Rogoff threshold).
  capital_control_tightening / easing
                       Derived from Bergant, Fernández, Teoh & Uribe (2025) iBoP-C: quarters with net tightening
                       (or easing) of cross-border flow restrictions of 2+ measures.
Every row carries its source, the rule that produced it and a verification label.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.common import INTERIM, PROCESSED, RAW, get_logger

log = get_logger("crisis_events")
ALIASES = {"Republic of the Congo": "COG", "Republic of Congo": "COG", "Democratic Republic of Congo": "COD", "São Tomé and Príncipe": "STP",
           "Sao Tome and Principe": "STP", "Cote d'Ivoire": "CIV", "Côte d'Ivoire": "CIV", "Vietnam": "VNM", "Russia": "RUS",
           "Kyrgyz Republic": "KGZ", "Slovak Republic": "SVK", "Czech Republic": "CZE", "Korea": "KOR", "Laos": "LAO",
           "Lao PDR": "LAO", "Egypt": "EGY", "Iran": "IRN", "Syria": "SYR", "Venezuela": "VEN", "Yemen": "YEM",
           "Gambia": "GMB", "Bahamas": "BHS", "Macedonia": "MKD", "North Macedonia": "MKD", "Turkey": "TUR", "Türkiye": "TUR",
           "Cape Verde": "CPV", "Swaziland": "SWZ", "Eswatini": "SWZ", "United States": "USA", "United Kingdom": "GBR",
           "Bosnia and Herzegovina": "BIH", "Central African Republic": "CAF", "Dominican Republic": "DOM",
           "Equatorial Guinea": "GNQ", "Guinea-Bissau": "GNB", "Sri Lanka": "LKA", "Hong Kong": "HKG", "Taiwan": "TWN",
           "Congo, Rep.": "COG", "Congo, Dem. Rep.": "COD", "Micronesia": "FSM", "St. Lucia": "LCA", "St. Kitts and Nevis": "KNA"}


def name_map():
    meta = pd.read_parquet(INTERIM / "wb_meta.parquet")
    m = dict(zip(meta.country_name, meta.iso3))
    m.update(ALIASES)
    return m


def banking():
    tp = INTERIM / "wp26094.txt"
    if not tp.exists():
        from pypdf import PdfReader
        pages = PdfReader(RAW / "imf_crises" / "wpiea2026094.pdf").pages
        tp.write_text("".join(f"<<<PAGE {i}>>>\n{pg.extract_text()}\n" for i, pg in enumerate(pages, 1)))
    txt = tp.read_text()
    a, b = txt.index("Table A1. Banking Crises Dates"), txt.index("Table A2. Banking Crisis Policy Responses")
    lines = [l.strip() for l in txt[a:b].splitlines()]
    rows, carry = [], ""
    pat = re.compile(r"^(?P<name>[A-Za-zÀ-ÿ'’\.\- ]+?)\s*(?P<fn>\d/)?\s+(?P<start>(19|20)\d{2})\s+(?P<end>(19|20)\d{2}|…|\.\.\.)")
    for l in lines:
        if not l or l.startswith(("Country", "IMF WORKING", "INTERNATIONAL", "<<<PAGE", "Table A1", "1/", "2/", "3/", "4/", "5/", "Note", "Source")):
            carry = "" if l.startswith(("Country", "<<<PAGE")) else carry
            continue
        cand = (carry + " " + l).strip() if carry else l
        m = pat.match(cand)
        if m:
            end = m.group("end")
            rows.append({"country": m.group("name").strip(), "start": int(m.group("start")),
                         "end": 2025 if not end[:1].isdigit() else int(end), "ongoing": not end[:1].isdigit(),
                         "footnote": (m.group("fn") or "").strip()})
            carry = ""
        elif not re.search(r"\d{4}", l):
            carry = cand          # country name wrapped onto the next line
    d = pd.DataFrame(rows)
    borderline = {"Nicaragua": 2018, "Vietnam": 2022, "Sri Lanka": 2023}
    for c, y in borderline.items():          # Table 1 borderline episodes absent from Table A1
        if not ((d.country == c) & (d.start == y)).any():
            d = pd.concat([d, pd.DataFrame([{"country": c, "start": y, "end": y, "footnote": "", "ongoing": False,
                                             "from_table1": True}])], ignore_index=True)
    nm = name_map()
    d["iso3"] = d.country.map(nm)
    d["verification"] = ["borderline" if borderline.get(c) == s else "published" for c, s in zip(d.country, d.start)]
    unmapped = d[d.iso3.isna()].country.unique()
    if len(unmapped):
        log.info("banking: unmapped names %s", list(unmapped)[:20])
    d = d[d.end >= 2012]
    notes = {("Ghana", 2017): "Table 1 of the paper lists the start as 2015; Table A1 gives 2017 (Table A1 used).",
             ("Angola", 2016): "Table 1 of the paper lists the start as 2015; Table A1 gives 2016 (Table A1 used).",
             ("Vietnam", 2022): "Borderline episode listed in Table 1 only; end year not given.",
             ("Sri Lanka", 2023): "Ongoing in the source (end not given); shown to 2025."}
    return pd.DataFrame({
        "iso3": d.iso3, "event_type": "banking_crisis", "start": d.start.astype(str), "end": d.end.astype(str),
        "detail": "Systemic banking crisis" + np.where(d.verification == "borderline", " (borderline)", ""),
        "magnitude": np.nan, "source": "IMF WP/26/94, Table A1 (Systemic Banking Crises Database 1970–2025)",
        "rule": "As published", "verification": d.verification,
        "notes": [notes.get((c, s), "") for c, s in zip(d.country, d.start)]})


DEFAULT_TYPES = {
    # event type: (creditor rows, minimum stock in default, US$ millions, label)
    "sovereign_default_private": (["FC bonds", "FC bank loans"], 50,
                                  "Default to private foreign-currency creditors (bonds, bank loans)"),
    "other_private_arrears": (["Other private creditors"], 500,
                              "Arrears to other private creditors (e.g. arbitration awards, suppliers)"),
    "official_arrears": (["IMF", "IBRD", "IDA", "IADB", "Paris Club", "China", "Other official creditors"], 500,
                         "Arrears to official creditors"),
    "local_currency_default": (["LC debt"], 100, "Default on local-currency debt"),
}


def default_panel() -> pd.DataFrame:
    """Country-year stocks in default by creditor group, US$ millions (BoC–BoE 2026 edition; 2025 preliminary)."""
    df = pd.read_excel(RAW / "boc_boe" / "BoC-BoE-Database-2026.xlsx", sheet_name="2026 in progress", header=None)
    years = {}
    for j, v in df.iloc[0].items():
        m = re.match(r"^(\d{4})p?$", str(v).replace(".0", ""))
        if m:
            years[j] = int(m.group(1))
    nm = name_map()
    first = df.index[df[1].astype(str).str.strip().eq("Argentina")][0]
    rows, iso = [], None
    for i in range(first, len(df)):
        name = df.iloc[i, 1]
        if not isinstance(name, str) and pd.notna(df.iloc[i, 2]) and df.iloc[i, 0] == 157:
            # The 2026 workbook leaves this country's name cell blank. It sits alphabetically between Uruguay
            # and Uzbekistan, carries defaulted (repudiated) debt from 1960 and a 2022 foreign-currency bond
            # default: USSR/Russia. Mapped to RUS and flagged in the event notes.
            iso = "RUS"
            continue
        if not isinstance(name, str):
            if pd.notna(df.iloc[i, 2]):
                iso = None          # any other unnamed block is skipped rather than misattributed
            continue
        name = name.strip()
        if not name.startswith("-"):
            iso = nm.get(name)
            continue
        if iso is None:
            continue
        cred = name.lstrip("- ").strip()
        for j, y in years.items():
            if 2011 <= y <= 2025:
                rows.append({"iso3": iso, "year": y, "creditor": cred, "usd_m": pd.to_numeric(df.iloc[i, j], errors="coerce")})
    return pd.DataFrame(rows)


def defaults():
    P = default_panel()
    out = []
    for etype, (creds, thr, label) in DEFAULT_TYPES.items():
        g = P[P.creditor.isin(creds)].groupby(["iso3", "year"]).usd_m.sum(min_count=1).reset_index()
        g["on"] = g.usd_m.fillna(0) >= thr
        for iso, c in g.sort_values("year").groupby("iso3"):
            c = c.reset_index(drop=True)
            k = 0
            while k < len(c):
                if c.on[k]:
                    j = k
                    while j + 1 < len(c) and c.on[j + 1]:
                        j += 1
                    start = "before 2012" if (k == 0 and c.year[0] == 2011) else str(int(c.year[k]))
                    end = int(c.year[j])
                    if end >= 2012:
                        peak = c.usd_m[k:j + 1].max()
                        out.append({"iso3": iso, "event_type": etype, "start": start, "end": str(end),
                                    "detail": f"{label} (peak US${peak/1000:.1f} bn)", "magnitude": round(peak / 1000, 2),
                                    "source": "BoC–BoE Sovereign Default Database, 2026 edition (Bank of Canada / Bank of England); 2025 preliminary",
                                    "rule": f"Consecutive years with at least US${thr}m in default to these creditors: {', '.join(creds)}",
                                    "verification": "published",
                                    "notes": "; ".join(x for x in ["Still in default at end-2025" if end >= 2025 else "",
                                                                   "Name cell blank in the 2026 workbook; identified as USSR/Russia (see code)" if iso == "RUS" else ""] if x)})
                    k = j + 1
                else:
                    k += 1
    return pd.DataFrame(out)


def currency(meta_iso):
    e = pd.read_csv(RAW / "imf_er" / "er_m.csv", usecols=["COUNTRY", "INDICATOR", "TYPE_OF_TRANSFORMATION", "TIME_PERIOD", "OBS_VALUE"])
    e = e[(e.INDICATOR == "XDC_USD") & (e.TYPE_OF_TRANSFORMATION == "PA_RT")]
    e["year"] = e.TIME_PERIOD.str[:4].astype(int)
    a = e.groupby(["COUNTRY", "year"]).OBS_VALUE.mean().rename("rate").reset_index().sort_values(["COUNTRY", "year"])
    a["dep"] = 100 * (a.rate / a.groupby("COUNTRY").rate.shift() - 1)          # % rise in local currency per USD
    a["dep_prev"] = a.groupby("COUNTRY").dep.shift()
    hit = a[(a.dep >= 30) & ((a.dep - a.dep_prev) >= 10) & a.year.between(2012, 2026)]
    return pd.DataFrame({"iso3": hit.COUNTRY, "event_type": "currency_crisis", "start": hit.year.astype(str), "end": hit.year.astype(str),
                         "detail": "Currency lost " + (100 * (1 - 1 / (1 + hit.dep / 100))).round(0).astype(int).astype(str)
                                   + "% of its value against the USD (US dollar price up " + hit.dep.round(0).astype(int).astype(str) + "%, annual average)",
                         "magnitude": hit.dep.round(1), "source": "IMF exchange rates (IMF.STA:ER), annual average of monthly rates",
                         "rule": "Depreciation >= 30% and >= 10 pp above previous year (Laeven–Valencia)", "verification": "derived", "notes": ""})


def imf_financing():
    f = pd.read_csv(RAW / "imf_fa" / "fa_q.csv", usecols=["COUNTRY", "INDICATOR", "TIME_PERIOD", "OBS_VALUE"])
    q = f[(f.INDICATOR == "CLIMF_POQT_PT_A_PT") & f.COUNTRY.str.fullmatch(r"[A-Z]{3}")].copy()   # drop IMF group aggregates (G309, U202, ...)
    q["quarter"] = q.TIME_PERIOD.str.replace("-", "")
    q = q.sort_values(["COUNTRY", "quarter"])
    q["rise4"] = q.OBS_VALUE - q.groupby("COUNTRY").OBS_VALUE.shift(4)
    q["big"] = q.rise4 >= 25
    q["start"] = q.big & ~q.groupby("COUNTRY").big.shift(1, fill_value=False)
    hit = q[q.big & (q.quarter >= "2012Q1")].copy()
    hit["qo"] = pd.PeriodIndex(hit.quarter, freq="Q").map(lambda p: p.ordinal)
    out = []
    for iso, g in hit.groupby("COUNTRY"):
        g = g.sort_values("qo")
        ep = (g.qo.diff().fillna(99) > 6).cumsum()       # disbursements < 6 quarters apart = one episode
        for _, e in g.groupby(ep):
            out.append({"iso3": iso, "event_type": "imf_financing", "start": e.quarter.iloc[0], "end": e.quarter.iloc[-1],
                        "detail": f"Large IMF financing: credit outstanding reached {e.OBS_VALUE.max():.0f}% of quota "
                                  f"(rises of at least 25% of quota in {len(e)} quarter{'s' if len(e) > 1 else ''})",
                        "magnitude": round(float(e.OBS_VALUE.max()), 1),
                        "source": "IMF Fund Accounts (IMF.STA:FA), credit outstanding as % of quota",
                        "rule": "Credit outstanding rises >= 25% of quota within four quarters; quarters < 6 apart merged into one episode",
                        "verification": "derived", "notes": "Proxy for a disbursing IMF arrangement; precautionary (undrawn) arrangements are not captured"})
    return pd.DataFrame(out)


def high_inflation():
    w = pd.read_parquet(INTERIM / "weo.parquet")[["iso3", "year", "PCPIPCH"]].dropna()
    w = w[w.year.between(2012, 2025)].sort_values(["iso3", "year"])
    w["hi"] = w.PCPIPCH >= 40
    w["start"] = w.hi & ~w.groupby("iso3").hi.shift(1, fill_value=False)
    runs = []
    for iso, g in w[w.hi].groupby("iso3"):
        yrs = g.year.tolist()
        s = yrs[0]
        for y0, y1 in zip(yrs, yrs[1:] + [None]):
            if y1 != y0 + 1:
                runs.append((iso, s, y0, g[g.year.between(s, y0)].PCPIPCH.max()))
                s = y1
    r = pd.DataFrame(runs, columns=["iso3", "s", "e", "peak"])
    return pd.DataFrame({"iso3": r.iso3, "event_type": "high_inflation", "start": r.s.astype(str), "end": r.e.astype(str),
                         "detail": "Inflation above 40% (peak " + r.peak.round(0).astype(int).astype(str) + "%)", "magnitude": r.peak.round(1),
                         "source": "IMF WEO, CPI inflation", "rule": "Annual inflation >= 40% (Reinhart–Rogoff)", "verification": "derived", "notes": ""})


def capital_control_panel() -> pd.DataFrame:
    """Quarterly changes in cross-border flow restrictions (iBoP-C cumulative net tightenings), 2012–2023."""
    x = pd.read_excel(RAW / "capital_controls" / "BFTU_iBoPC.xlsx", sheet_name="Quarterly")
    x = x.rename(columns={"code_wdi": "iso3"})
    x["quarter"] = x.qdate.str.replace("-", "")
    x = x[(x.quarter >= "2011Q1")].sort_values(["iso3", "quarter"])
    for c in ["total", "total_in", "total_out", "c7.capital_account", "c1.fx_markets"]:
        x[f"d_{c}"] = x.groupby("iso3")[c].diff()
    return x[["iso3", "quarter", "total", "total_in", "total_out", "d_total", "d_total_in", "d_total_out",
              "d_c7.capital_account", "d_c1.fx_markets"]]


def capital_controls():
    x = capital_control_panel()
    x = x[x.quarter >= "2012Q1"]
    rows = []
    for _, r in x[(x.d_total.abs() >= 2)].iterrows():
        kind = "capital_control_tightening" if r.d_total > 0 else "capital_control_easing"
        parts = []
        if pd.notna(r.d_total_in) and r.d_total_in != 0:
            parts.append(f"inflow-related {int(r.d_total_in):+d}")
        if pd.notna(r.d_total_out) and r.d_total_out != 0:
            parts.append(f"outflow-related {int(r.d_total_out):+d}")
        rows.append({"iso3": r.iso3, "event_type": kind, "start": r.quarter, "end": r.quarter,
                     "detail": f"Net {'tightening' if r.d_total > 0 else 'easing'} of cross-border flow restrictions: {int(abs(r.d_total))} measures"
                               + (f" ({', '.join(parts)})" if parts else ""),
                     "magnitude": float(r.d_total),
                     "source": "Bergant, Fernández, Teoh & Uribe (2025), iBoP-C (from IMF AREAER), quarterly",
                     "rule": "Quarterly change in cumulative net tightenings of at least 2 measures in either direction",
                     "verification": "published (measure counts); event threshold derived", "notes": "Coverage ends 2023"})
    return pd.DataFrame(rows)


def build():
    meta = pd.read_csv(PROCESSED / "country_metadata.csv")
    names = dict(zip(meta.iso3, meta.country_name))
    parts = [banking(), defaults(), currency(None), imf_financing(), high_inflation(), capital_controls()]
    E = pd.concat(parts, ignore_index=True)
    E = E[E.iso3.str.fullmatch(r"[A-Z]{3}", na=False)]
    E = E[E.iso3.notna()]
    E["country"] = E.iso3.map(names)
    E["in_quarterly_sample"] = E.iso3.isin(meta[meta.in_quarterly_sample].iso3)
    E["start_year"] = E.start.str.extract(r"(\d{4})")[0].astype(float)
    E.loc[E.start == "before 2012", "start_year"] = 2011
    E["end_year"] = E.end.str[:4].astype(int)
    E = E.sort_values(["iso3", "start_year", "event_type"])
    E["event_id"] = E.iso3 + "_" + E.event_type + "_" + E.start.str.replace(" ", "")
    cols = ["event_id", "iso3", "country", "event_type", "start", "end", "start_year", "end_year", "detail", "magnitude",
            "source", "rule", "verification", "notes", "in_quarterly_sample"]
    E[cols].to_csv(PROCESSED / "crisis_events.csv", index=False)
    log.info("crisis events: %s", E.event_type.value_counts().to_dict())
    return E[cols]


if __name__ == "__main__":
    E = build()
    print(E.event_type.value_counts().to_string())
