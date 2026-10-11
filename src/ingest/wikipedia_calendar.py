"""Exact national election dates from Wikipedia's "<year> national electoral calendar" pages.

Why: International IDEA records ~half of post-2013 elections with a year-only placeholder
(YYYY-01-01). Quarterly event analysis needs the actual polling date. The Wikipedia
calendars list national (not sub-national, not by-) elections with day-level dates.

Wikipedia is used as a date source only; each election is triangulated with IDEA and
V-Dem in src/features/elections.py. Content licence: CC BY-SA 4.0 (cited in the source register).
"""
from __future__ import annotations

import json
import re

import pandas as pd

from src.common import RAW, fetch_raw, get_logger

API = "https://en.wikipedia.org/w/api.php"
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}


def _valid(body: bytes):
    j = json.loads(body)
    return None if "parse" in j else str(j.get("error", j))[:200]


def download(start: int = 2008, end: int = 2026):
    import time
    for y in range(start, end + 1):
        dest = RAW / "wikipedia_calendar" / f"national_electoral_calendar_{y}.json"
        if dest.exists():
            continue
        time.sleep(6)  # Wikimedia rate-limit etiquette for unauthenticated clients
        try:
            _fetch_year(y, dest)
        except RuntimeError as e:
            if "missingtitle" in str(e):
                get_logger("wikipedia").warning("no calendar page for %d", y)
                continue
            raise


def _fetch_year(y, dest):
    fetch_raw(API, RAW / "wikipedia_calendar" / f"national_electoral_calendar_{y}.json",
                  "Wikipedia national electoral calendar (CC BY-SA)",
                  params={"action": "parse", "page": f"{y} national electoral calendar",
                          "prop": "wikitext|revid", "format": "json", "formatversion": 2},
                  note=f"{y} national electoral calendar; revision id stored in file",
                  validator=_valid, retries=6)


LINK = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]|\[\[([^\]|]+)\]\]")


def _clean(s: str) -> str:
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    return s


def _classify(desc: str):
    d = desc.lower()
    out = []
    rnd = 2 if re.search(r"2nd round|second round|run-?off", d) else 1
    if "president" in d:
        out.append(("presidential", rnd))
    legis = re.search(r"parliament|chamber|house of|legislat|national assembly|general|congress|"
                      r"assembly|diet|bundestag|lok sabha|knesset|duma|sejm|majlis|riksdag|storting|"
                      r"folketing|cortes|national council|grand national", d)
    senate_only = ("senate" in d or "upper house" in d or "rajya" in d) and not legis
    if legis and not senate_only:
        # 'President and Parliament (1st round)' -> parliament round from text as well
        out.append(("parliamentary", rnd if "parliament (" in d or "(1st round)" not in d else 1))
    return out


def parse_year(path) -> pd.DataFrame:
    j = json.loads(path.read_text())
    year = int(re.search(r"(\d{4})", path.stem).group(1))
    text = _clean(j["parse"]["wikitext"])
    rows, cur_date, month = [], None, None
    for line in text.splitlines():
        h = re.match(r"^==\s*([A-Za-z]+)\s*==", line)
        if h:
            month = MONTHS.get(h.group(1))
            continue
        if month is None or not line.startswith("*"):
            continue
        body = line.lstrip("*").strip()
        m = re.match(r"^(\d{1,2})(?:\s*[–-]\s*\d{1,2})?(?:\s+([A-Z][a-z]+))?(?:\s*[–-]\s*\d{1,2}\s+[A-Z][a-z]+)?\s*:\s*(.*)$", body)
        if m and not line.startswith("**"):
            day, mon = int(m.group(1)), MONTHS.get(m.group(2), month) if m.group(2) else month
            cur_date = pd.Timestamp(year=year, month=mon, day=day)
            body = m.group(3)
            if not body.strip():
                continue
        if cur_date is None:
            continue
        if body.startswith("''"):
            continue  # italics = dependent territory / non-sovereign entity
        links = LINK.findall(body)
        if len(links) < 2:
            continue
        country = links[0][1] or links[0][2]
        article = links[1][0] or links[1][2]
        desc = links[1][1] or links[1][2]
        for etype, rnd in _classify(desc):
            rows.append({"date": cur_date, "country_wp": country.strip(), "article": article.strip(),
                         "desc": desc.strip(), "etype": etype, "round": rnd,
                         "revid": j["parse"].get("revid")})
    return pd.DataFrame(rows)


def parse_all() -> pd.DataFrame:
    frames = [parse_year(p) for p in sorted((RAW / "wikipedia_calendar").glob("*.json"))]
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    download()
    df = parse_all()
    print(df.shape, df.etype.value_counts().to_dict())
