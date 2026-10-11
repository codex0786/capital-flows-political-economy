"""Write literature/bibliography.csv and literature/literature_matrix.csv.

Bibliography: every journal/working-paper entry carries a DOI verified against Crossref
(literature/crossref_verification.csv). Datasets and institutional documents are cited by
their official URL and the version actually used.

Matrix: summaries are written from (a) the full text where it was read (IMF WP/25/243),
(b) the abstract retrieved from OpenAlex (literature/sources/openalex_abstracts.json), or
(c) where no abstract could be retrieved, only the study's design facts that are widely
documented; such rows are marked verification_level = 'metadata_only' and should be checked
against the full text before submission.
"""
from __future__ import annotations

import json

import pandas as pd

from src.common import ROOT

LIT = ROOT / "literature"

INSTITUTIONAL = [
    ("arakelyan_evdokimova_2025", "Arakelyan, M.; Evdokimova, T.", 2025, "Elections Matter: Capital Flows and Political Cycles",
     "IMF Working Paper WP/25/243", "https://www.imf.org/en/publications/wp/issues/2025/11/14/elections-matter-capital-flows-and-political-cycles-571782",
     "full text read (literature/sources/imf_wp25243.txt)"),
    ("imf_bop_2026", "International Monetary Fund", 2026, "Balance of Payments and International Investment Position Statistics (BOP), dataflow IMF.STA:BOP v21.0.0",
     "Dataset", "https://data.imf.org/Datasets/BOP", "retrieved 2026-10-11 via SDMX 2.1 API"),
    ("imf_weo_2026", "International Monetary Fund", 2026, "World Economic Outlook database (DataMapper API, current vintage at retrieval)",
     "Dataset", "https://www.imf.org/external/datamapper", "retrieved 2026-10-11; group membership verified against ADVEC aggregate"),
    ("wb_wgi_2026", "World Bank", 2026, "Worldwide Governance Indicators, 2026 release (source 3, last updated 2026-09-25)",
     "Dataset", "https://datacatalog.worldbank.org/search/dataset/0038026/worldwide-governance-indicators", "retrieved 2026-10-11"),
    ("wb_wdi_2026", "World Bank", 2026, "World Development Indicators (last updated 2026-10-08)", "Dataset", "https://data.worldbank.org/", "retrieved 2026-10-11"),
    ("vdem_v16", "Coppedge, M. et al.", 2026, "V-Dem Country-Year Dataset v16 (distributed in the vdemdata package, release commit 2026-03-17)",
     "Dataset", "https://github.com/vdeminstitute/vdemdata", "retrieved 2026-10-11"),
    ("idea_vtd", "International IDEA", 2026, "Voter Turnout Database", "Dataset", "https://www.idea.int/data-tools/data/voter-turnout-database", "retrieved 2026-10-11"),
    ("wikipedia_calendars", "Wikipedia contributors", 2026, "<year> national electoral calendar, 2010-2026 (revision IDs archived)",
     "Encyclopedia (CC BY-SA 4.0)", "https://en.wikipedia.org/wiki/2025_national_electoral_calendar", "retrieved 2026-10-11; used for dates only, triangulated"),
    ("wui_2026", "Ahir, H.; Bloom, N.; Furceri, D.", 2026, "World Uncertainty Index data (July 2026 update)", "Dataset",
     "https://worlduncertaintyindex.com/data/", "retrieved 2026-10-11"),
    ("gpr_2026", "Caldara, D.; Iacoviello, M.", 2026, "Geopolitical Risk Index data", "Dataset", "https://www.matteoiacoviello.com/gpr.htm", "retrieved 2026-10-11"),
    ("rsui_2026", "Barrett, P. et al. / IMF", 2026, "Reported Social Unrest Index (IMF.WHD:RSUI)", "Dataset", "https://data.imf.org", "retrieved 2026-10-11"),
    ("kaopen_2023", "Chinn, M.; Ito, H.", 2025, "Chinn-Ito Financial Openness Index, 2023 update", "Dataset", "https://web.pdx.edu/~ito/Chinn-Ito_website.htm", "retrieved 2026-10-11"),
    ("bis_cbpol", "Bank for International Settlements", 2026, "Central bank policy rates (WS_CBPOL)", "Dataset", "https://www.bis.org/statistics/cbpol.htm", "retrieved 2026-10-11"),
    ("fred", "Federal Reserve Bank of St. Louis", 2026, "FRED series VIXCLS, FEDFUNDS, DGS10, DTWEXBGS, POILBREUSDM, BAMLH0A0HYM2", "Dataset",
     "https://fred.stlouisfed.org", "retrieved 2026-10-11"),
]

NOT_CONSULTED = [
    ("unctad_wir_2026", "UNCTAD", 2026, "World Investment Report 2026", "Report", "https://unctad.org/topic/investment/world-investment-report",
     "NOT consulted in v1.0 — listed in the brief; not cited in the report"),
    ("imf_gfsr_apr2026", "International Monetary Fund", 2026, "Global Financial Stability Report, April 2026", "Report",
     "https://www.imf.org/en/Publications/GFSR", "NOT consulted in v1.0 — listed in the brief; not cited in the report"),
]

# Curated evidence matrix. 'level' = full_text | abstract | metadata_only
MATRIX = [
    dict(key="arakelyan_evdokimova_2025", level="full_text",
         question="Do elections (as a proxy for political uncertainty) reduce capital inflows to emerging markets?",
         sample="38 emerging markets (China excluded: no DPI/NELDA election dates)", period="1990–2020, quarterly",
         dv="Gross private capital inflows (official OI liabilities and SDR allocations removed), scaled by HP-filtered trend GDP; also by type",
         iv="Election-quarter dummy (exec-relevant: legislative in parliamentary, executive in presidential systems; DPI2020 + NELDA); 1–2 and 3–4 quarter leads/lags; ICRG political stability; WGI",
         method="Panel FE (country FE, country trends; time FE in robustness); push-pull controls",
         ident="Election timing; pre-determined vs off-cycle elections distinguished; no causal design beyond timing",
         findings="Election quarters associated with lower gross private inflows; no significant run-up decline; effects up to two quarters after; bottom-quartile ICRG stability ≈ −1.25% of trend GDP (≈28% of pre-election inflows); stronger institutions mitigate",
         limits="EM-only; ends 2020; ICRG is proprietary; trend-GDP scaling",
         relevance="Benchmark for H1, H2, H6; our post-hoc analysis aligns window and outcome to it",
         replication="Partially replicable with public BOP + election dates; ICRG not public"),
    dict(key="julio_yook_2016", level="metadata_only",
         question="Does political (election) uncertainty affect US firms' cross-border flows of capital?",
         sample="FDI flows from US companies to foreign affiliates across host countries", period="see paper",
         dv="FDI flows from US parents to affiliates; foreign portfolio flows (comparison)",
         iv="Host-country national election timing", method="Panel regressions around election dates",
         ident="Election timing (scheduled elections)",
         findings="FDI falls before elections and recovers after; no comparable cycle in portfolio flows; smaller variation with higher institutional quality (per FEDS 2013-64 abstract)",
         limits="US source country only; bilateral affiliate flows rather than total BOP flows",
         relevance="Motivates H1 timing and H3 (irreversible FDI vs reversible portfolio flows) and H2",
         replication="Requires BEA affiliate data"),
    dict(key="julio_yook_2012", level="abstract",
         question="Do corporate investment cycles follow national elections?", sample="Firms across many countries", period="see paper",
         dv="Corporate investment expenditure", iv="Election-year indicator", method="Firm-level panel",
         ident="Election timing", findings="Investment falls 4.8% in election years vs non-election years; evidence consistent with uncertainty channel",
         limits="Real investment, not cross-border flows", relevance="Mechanism for H1 (wait-and-see under uncertainty)", replication="Firm data needed"),
    dict(key="canes_wrone_park_2012", level="abstract",
         question="Do elections with high policy uncertainty produce pre-election declines in investment?", sample="10 OECD countries",
         period="1975–2006, quarterly", dv="Private fixed investment", iv="Pre-election periods × polarisation/competitiveness",
         method="Time-series cross-section", ident="Election timing; conditional on polarisation",
         findings="Reverse electoral business cycles exist when polarisation and competitiveness are high",
         limits="OECD only; domestic investment", relevance="Suggests election effects are conditional, supporting heterogeneous effects in H2/H6", replication="Public OECD data"),
    dict(key="kelly_pastor_veronesi_2016", level="abstract",
         question="Is political uncertainty priced in option markets?", sample="Equity options, many countries", period="see paper",
         dv="Option prices/implied volatility", iv="National elections and global summits within option lives", method="Event-based comparisons",
         ident="Timing of elections relative to option maturity", findings="Options spanning political events are more expensive; effects spill over across countries",
         limits="Prices, not flows", relevance="Supports elections as dated political-uncertainty events (financial-market response outcome)", replication="Option data needed"),
    dict(key="alfaro_etal_2008", level="abstract",
         question="Why doesn't capital flow from rich to poor countries?", sample="Cross-country", period="1970–2000",
         dv="Foreign investment inflows (cross-section)", iv="Institutional quality and fundamentals", method="Cross-country regressions with IV",
         ident="Historical instruments for institutions", findings="Low institutional quality is the leading explanation of the Lucas paradox",
         limits="Long-run cross-section; not time-varying politics", relevance="Motivates institutional moderation (H2) and between-country Mundlak analysis", replication="Public data"),
    dict(key="jensen_2003", level="abstract",
         question="Do democratic regimes attract more FDI?", sample=">100 countries", period="see paper",
         dv="FDI inflows", iv="Democracy", method="Cross-section and TSCS", ident="Associational",
         findings="Democracies attract more FDI, across and within countries", limits="Regime type ≠ policy predictability",
         relevance="Regime type vs election uncertainty distinction (Rule 6)", replication="Public data"),
    dict(key="li_resnick_2003", level="abstract",
         question="Does democracy promote or hinder FDI to developing countries?", sample="Developing countries", period="see paper",
         dv="FDI inflows", iv="Democratic institutions; property-rights protection", method="Panel", ident="Associational",
         findings="Competing effects; net effect depends on property-rights protection vs democratic constraints",
         limits="Associational", relevance="Institutions vs regime distinction; H2 moderators", replication="Public data"),
    dict(key="koepke_2019", level="abstract",
         question="What drives capital flows to EMs? (survey)", sample="Literature review", period="—",
         dv="Portfolio debt/equity, banking flows", iv="Push and pull factors", method="Survey", ident="—",
         findings="Push factors matter most for portfolio flows; pull factors matter for all components, most for banking flows",
         limits="EM focus", relevance="Framework for controls and component-specific hypotheses (H3, H5)", replication="—"),
    dict(key="eichengreen_etal_2018", level="abstract",
         question="Are capital flows fickle, by type?", sample="Emerging markets", period="see paper",
         dv="Inflows/outflows by type", iv="Push and pull factors", method="Panel/volatility analysis", ident="Associational",
         findings="FDI more stable than non-FDI; portfolio debt and bank flows most volatile; FDI driven by pull, portfolio by push factors",
         limits="EM focus", relevance="H3 expectations and volatility outcomes", replication="Public BOP"),
    dict(key="avdjiev_etal_2022", level="abstract",
         question="How do gross flows differ by domestic sector?", sample="Advanced and emerging economies", period="see paper",
         dv="Gross flows by banks, corporates, sovereigns", iv="Descriptive facts; global factors", method="New quarterly dataset",
         ident="Descriptive", findings="Inflow-outflow co-movement driven by banks; sovereign flows often offset private flows, especially in EMs",
         limits="—", relevance="Justifies separating private from official flows (post-hoc analysis) and the gross inflow/outflow retrenchment pattern", replication="Public BOP + BIS"),
    dict(key="forbes_warnock_2012", level="metadata_only",
         question="What drives extreme gross capital-flow episodes (surges, stops, flight, retrenchment)?", sample="Large panel of countries", period="see paper",
         dv="Episodes defined on gross inflows/outflows", iv="Global and domestic factors", method="Episode definitions + probit-type models",
         ident="Associational", findings="Global factors, especially global risk, are central to episodes; domestic factors matter less",
         limits="—", relevance="Sudden-stop definition used in R1; motivates H5", replication="Public BOP"),
    dict(key="rey_2013", level="metadata_only",
         question="Is there a global financial cycle constraining monetary independence?", sample="Global", period="see paper",
         dv="Capital flows, credit, asset prices", iv="VIX/global factor", method="Factor/VAR evidence", ident="—",
         findings="A global financial cycle co-moving with VIX drives flows and credit", limits="—", relevance="VIX as push factor; H5", replication="—"),
    dict(key="barrett_etal_2022", level="abstract",
         question="Can media reports measure social unrest?", sample="130 countries", period="1985– (monthly)", dv="Reported Social Unrest Index",
         iv="—", method="Text-based measurement", ident="—", findings="See abstract (openalex_abstracts.json)", limits="Media coverage changes",
         relevance="Source of rsui_index / rsui_event", replication="Public via IMF"),
]


# Metadata from direct Crossref DOI lookups (api.crossref.org/works/<doi>, 2026-10-11), used where the
# bibliographic search first matched a working-paper copy or where online-first year differs from issue year.
DOI_META = {
    "fratzscher_2012": dict(year=2012, journal="Journal of International Economics", volume="88", pages="341-356", authors="Fratzscher, Marcel"),
    "caldara_iacoviello_2022": dict(year=2022, journal="American Economic Review", volume="112(4)", pages="1194-1225", authors="Caldara, Dario; Iacoviello, Matteo"),
    "hyde_marinov_2012": dict(year=2012, journal="Political Analysis", volume="20(2)", pages="191-210", authors="Hyde, Susan D.; Marinov, Nikolay"),
    "rey_2013": dict(year=2015, journal="NBER Working Paper 21162 (Jackson Hole Economic Policy Symposium, 2013)", volume=None, pages=None, authors="Rey, Hélène",
                     matched_title="Dilemma not Trilemma: The Global Financial Cycle and Monetary Policy Independence"),
    "ahir_bloom_furceri_2022": dict(year=2022, journal="NBER Working Paper 29763", volume=None, pages=None, authors="Ahir, Hites; Bloom, Nicholas; Furceri, Davide",
                                    matched_title="The World Uncertainty Index"),
    "koepke_paetzold_2024": dict(year=2024, journal="International Journal of Finance & Economics", volume="29(1)", pages="311-331", authors="Koepke, Robin; Paetzold, Simon"),
}


def main():
    v = pd.read_csv(LIT / "crossref_verification.csv")
    v = v[v.verified].copy().astype({"volume": "object", "pages": "object", "year": "object"})
    for k, m in DOI_META.items():
        for col, val in m.items():
            v.loc[v.key == k, col] = val
    bib = pd.DataFrame({
        "key": v.key, "authors": v.authors, "year": v.year.astype("Int64"), "title": v.matched_title,
        "venue": v.journal.str.replace("&amp;", "&"), "volume": v.volume, "pages": v.pages,
        "doi_or_url": "https://doi.org/" + v.doi, "verification": "Crossref DOI match (title similarity ≥0.85, year ±1) or direct DOI lookup",
        "stream": v.stream, "cited_in_report": True,
    })
    inst = pd.DataFrame([dict(key=k, authors=a, year=y, title=t, venue=ve, volume=None, pages=None, doi_or_url=u,
                              verification=n, stream="data/institutional", cited_in_report=True)
                         for k, a, y, t, ve, u, n in INSTITUTIONAL])
    nc = pd.DataFrame([dict(key=k, authors=a, year=y, title=t, venue=ve, volume=None, pages=None, doi_or_url=u,
                            verification=n, stream="institutional", cited_in_report=False)
                       for k, a, y, t, ve, u, n in NOT_CONSULTED])
    bib = pd.concat([inst, bib, nc], ignore_index=True)
    bib.to_csv(LIT / "bibliography.csv", index=False)

    abstracts = json.loads((LIT / "sources" / "openalex_abstracts.json").read_text())
    doi = dict(zip(bib.key, bib.doi_or_url))
    rows = []
    for m in MATRIX:
        rows.append({
            "citation_key": m["key"], "doi_or_url": doi.get(m["key"]), "research_question": m["question"],
            "sample": m["sample"], "period": m["period"], "dependent_variables": m["dv"],
            "main_explanatory_variables": m["iv"], "methodology": m["method"], "identification": m["ident"],
            "main_findings": m["findings"], "limitations": m["limits"], "relevance": m["relevance"],
            "replication_potential": m["replication"], "verification_level": m["level"],
            "abstract_available": bool(abstracts.get(m["key"], {}).get("abstract")),
        })
    pd.DataFrame(rows).to_csv(LIT / "literature_matrix.csv", index=False)
    print(len(bib), "bibliography entries;", len(rows), "matrix rows")


if __name__ == "__main__":
    main()
