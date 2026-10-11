"""Verify candidate references against Crossref (api.crossref.org) and record the match.

Each candidate is a free-text citation. The best Crossref match is stored with its DOI,
title, journal, year and authors; ``verified`` is set only when the title similarity is
high and the year matches. Unmatched candidates are kept and flagged, never invented.
"""
from __future__ import annotations

import difflib
import json
import time

import pandas as pd
import requests

from src.common import ROOT, USER_AGENT

CANDIDATES = [
    # (key, expected title, first-author surname, year, stream)
    ("forbes_warnock_2012", "Capital flow waves: Surges, stops, flight, and retrenchment", "Forbes", 2012, "sudden stops / gross flows"),
    ("broner_etal_2013", "Gross capital flows: Dynamics and crises", "Broner", 2013, "gross flows"),
    ("fratzscher_2012", "Capital flows, push versus pull factors and the global financial crisis", "Fratzscher", 2012, "push-pull"),
    ("koepke_2019", "What drives capital flows to emerging markets? A survey of the empirical literature", "Koepke", 2019, "push-pull"),
    ("koepke_paetzold_2024", "Capital flow data—A guide for empirical analysis and real-time tracking", "Koepke", 2024, "measurement"),
    ("cerutti_etal_2019", "Push factors and capital flows to emerging markets: why knowing your lender matters more than fundamentals", "Cerutti", 2019, "push-pull"),
    ("rey_2013", "Dilemma not trilemma: The global financial cycle and monetary policy independence", "Rey", 2013, "global financial cycle"),
    ("miranda_agrippino_rey_2020", "U.S. Monetary Policy and the Global Financial Cycle", "Miranda-Agrippino", 2020, "global financial cycle"),
    ("calvo_1998", "Capital flows and capital-market crises: the simple economics of sudden stops", "Calvo", 1998, "sudden stops"),
    ("ghosh_etal_2014", "Surges", "Ghosh", 2014, "surges"),
    ("eichengreen_etal_2018", "Are capital flows fickle? Increasingly? And does the answer still depend on type?", "Eichengreen", 2018, "volatility by type"),
    ("avdjiev_etal_2022", "Gross capital flows by banks, corporates, and sovereigns", "Avdjiev", 2022, "gross flows by sector"),
    ("julio_yook_2012", "Political uncertainty and corporate investment cycles", "Julio", 2012, "political uncertainty"),
    ("julio_yook_2016", "Policy uncertainty, irreversibility, and cross-border flows of capital", "Julio", 2016, "political uncertainty / FDI"),
    ("pastor_veronesi_2013", "Political uncertainty and risk premia", "Pástor", 2013, "political uncertainty"),
    ("kelly_pastor_veronesi_2016", "The price of political uncertainty: Theory and evidence from the option market", "Kelly", 2016, "political uncertainty"),
    ("baker_bloom_davis_2016", "Measuring economic policy uncertainty", "Baker", 2016, "policy uncertainty"),
    ("caldara_iacoviello_2022", "Measuring geopolitical risk", "Caldara", 2022, "geopolitical risk"),
    ("barrett_etal_2022", "Measuring social unrest using media reports", "Barrett", 2022, "social unrest"),
    ("canes_wrone_park_2012", "Electoral business cycles in OECD countries", "Canes-Wrone", 2012, "elections / investment"),
    ("brender_drazen_2005", "Political budget cycles in new versus established democracies", "Brender", 2005, "political budget cycles"),
    ("jensen_2003", "Democratic governance and multinational corporations: Political regimes and inflows of foreign direct investment", "Jensen", 2003, "political institutions / FDI"),
    ("li_resnick_2003", "Reversal of fortunes: Democratic institutions and foreign direct investment inflows to developing countries", "Li", 2003, "political institutions / FDI"),
    ("alfaro_etal_2008", "Why doesn't capital flow from rich to poor countries? An empirical investigation", "Alfaro", 2008, "institutions / capital flows"),
    ("papaioannou_2009", "What drives international financial flows? Politics, institutions and other determinants", "Papaioannou", 2009, "institutions / bank flows"),
    ("busse_hefeker_2007", "Political risk, institutions and foreign direct investment", "Busse", 2007, "political risk / FDI"),
    ("kaufmann_kraay_mastruzzi_2011", "The Worldwide Governance Indicators: Methodology and Analytical Issues", "Kaufmann", 2011, "governance measurement"),
    ("chinn_ito_2006", "What matters for financial development? Capital controls, institutions, and interactions", "Chinn", 2006, "capital controls"),
    ("fernandez_etal_2016", "Capital control measures: A new dataset", "Fernández", 2016, "capital controls"),
    ("forbes_etal_2015", "Capital-flow management measures: What are they good for?", "Forbes", 2015, "capital controls"),
    ("driscoll_kraay_1998", "Consistent covariance matrix estimation with spatially dependent panel data", "Driscoll", 1998, "inference"),
    ("cameron_gelbach_miller_2008", "Bootstrap-based improvements for inference with clustered errors", "Cameron", 2008, "inference"),
    ("roodman_etal_2019", "Fast and wild: Bootstrap inference in Stata using boottest", "Roodman", 2019, "inference"),
    ("cengiz_etal_2019", "The effect of minimum wages on low-wage jobs", "Cengiz", 2019, "stacked DiD"),
    ("sun_abraham_2021", "Estimating dynamic treatment effects in event studies with heterogeneous treatment effects", "Sun", 2021, "event studies"),
    ("callaway_santanna_2021", "Difference-in-Differences with multiple time periods", "Callaway", 2021, "staggered DiD"),
    ("de_chaisemartin_dhaultfoeuille_2020", "Two-way fixed effects estimators with heterogeneous treatment effects", "de Chaisemartin", 2020, "TWFE"),
    ("goodman_bacon_2021", "Difference-in-differences with variation in treatment timing", "Goodman-Bacon", 2021, "TWFE"),
    ("mundlak_1978", "On the pooling of time series and cross section data", "Mundlak", 1978, "CRE"),
    ("hyde_marinov_2012", "Which elections can be lost?", "Hyde", 2012, "election data (NELDA)"),
    ("coppedge_etal_vdem", "V-Dem Codebook v16", "Coppedge", 2026, "V-Dem (not in Crossref; cite codebook)"),
    ("ahir_bloom_furceri_2022", "The World Uncertainty Index", "Ahir", 2022, "WUI (NBER WP 29763)"),
]


def query(title: str, author: str, journal_only: bool = True):
    params = {"query.bibliographic": title, "query.author": author, "rows": 8,
              "select": "DOI,title,container-title,issued,author,type,volume,page"}
    if journal_only:
        params["filter"] = "type:journal-article"   # prefer the version of record over WP copies
    r = requests.get("https://api.crossref.org/works", params=params,
                     headers={"User-Agent": USER_AGENT + " (mailto:not-provided)"}, timeout=60)
    r.raise_for_status()
    return r.json()["message"]["items"]


def main():
    raw = {}
    rows = []
    for key, title, author, year, stream in CANDIDATES:
        try:
            items = query(title, author)
            if not items:
                items = query(title, author, journal_only=False)
        except requests.RequestException as e:
            rows.append({"key": key, "verified": False, "note": f"query failed: {e}"})
            continue
        raw[key] = items
        best, score = None, 0.0
        for it in items:
            t = (it.get("title") or [""])[0]
            s = difflib.SequenceMatcher(None, t.lower(), title.lower()).ratio()
            yy = it.get("issued", {}).get("date-parts", [[None]])[0][0]
            if yy is not None and abs(int(yy) - year) <= 1:
                s += 0.05  # tie-break toward the expected publication year
            if s > score:
                best, score = it, s
        y = best.get("issued", {}).get("date-parts", [[None]])[0][0] if best else None
        auth = "; ".join(f"{a.get('family','')}, {a.get('given','')}" for a in (best or {}).get("author", [])[:6])
        rows.append({
            "key": key, "stream": stream, "expected_title": title, "expected_year": year,
            "matched_title": (best.get("title") or [""])[0] if best else None,
            "journal": (best.get("container-title") or [""])[0] if best else None,
            "year": y, "volume": best.get("volume") if best else None, "pages": best.get("page") if best else None,
            "authors": auth, "doi": best.get("DOI") if best else None, "title_similarity": round(min(score, 1.0), 3),
            "verified": bool(best and score >= 0.85 and y is not None and abs(int(y) - year) <= 1),
        })
        time.sleep(1)
    out = pd.DataFrame(rows)
    (ROOT / "literature" / "sources").mkdir(parents=True, exist_ok=True)
    (ROOT / "literature" / "sources" / "crossref_raw.json").write_text(json.dumps(raw, indent=1))
    out.to_csv(ROOT / "literature" / "crossref_verification.csv", index=False)
    print(out[["key", "verified", "title_similarity", "year", "journal", "doi"]].to_string())


if __name__ == "__main__":
    main()
