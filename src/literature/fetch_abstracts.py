"""Fetch abstracts for verified DOIs from OpenAlex (CC0) to ground the literature matrix.

Abstracts are reconstructed from OpenAlex's inverted index. They are used to check the
literature-matrix summaries; where no abstract is available the matrix says so.
"""
from __future__ import annotations

import json
import time

import pandas as pd
import requests

from src.common import ROOT, USER_AGENT

OVERRIDES = {  # DOIs resolved by direct lookup (see literature/crossref_verification.csv notes)
    "fratzscher_2012": "10.1016/j.jinteco.2012.05.003",
    "caldara_iacoviello_2022": "10.1257/aer.20191823",
    "hyde_marinov_2012": "10.1093/pan/mpr040",
    "rey_2013": "10.3386/w21162",
    "ahir_bloom_furceri_2022": "10.3386/w29763",
    "koepke_paetzold_2024": "10.1002/ijfe.2687",
}


def main():
    v = pd.read_csv(ROOT / "literature" / "crossref_verification.csv")
    for k, d in OVERRIDES.items():
        v.loc[v.key == k, ["doi", "verified"]] = [d, True]
    v.loc[v.key == "coppedge_etal_vdem", "verified"] = False
    out = {}
    for r in v[v.verified].itertuples():
        resp = requests.get(f"https://api.openalex.org/works/https://doi.org/{r.doi}",
                            headers={"User-Agent": USER_AGENT}, timeout=60)
        if resp.status_code != 200:
            out[r.key] = {"doi": r.doi, "abstract": None, "status": resp.status_code}
            continue
        j = resp.json()
        inv = j.get("abstract_inverted_index") or {}
        words = sorted(((p, w) for w, ps in inv.items() for p in ps))
        out[r.key] = {"doi": r.doi, "title": j.get("title"), "year": j.get("publication_year"),
                      "venue": ((j.get("primary_location") or {}).get("source") or {}).get("display_name"),
                      "authors": [a["author"]["display_name"] for a in j.get("authorships", [])],
                      "abstract": " ".join(w for _, w in words) or None}
        time.sleep(0.3)
    (ROOT / "literature" / "sources" / "openalex_abstracts.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    v.to_csv(ROOT / "literature" / "crossref_verification.csv", index=False)
    print(sum(1 for x in out.values() if x.get("abstract")), "abstracts of", len(out))


if __name__ == "__main__":
    main()
