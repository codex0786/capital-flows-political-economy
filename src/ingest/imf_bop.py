"""IMF Balance of Payments (BPM6) financial-account transactions via the IMF SDMX 2.1 API.

Dataflow: IMF.STA:BOP (v21.0.0 at retrieval). Dimensions: COUNTRY.BOP_ACCOUNTING_ENTRY.INDICATOR.UNIT.FREQUENCY

Accounting entries used (BPM6 financial account):
  A_NFA_T    net acquisition of financial assets   -> resident outward transactions ("gross outflows")
  L_NIL_T    net incurrence of liabilities         -> non-resident inward transactions ("gross inflows")
  NNAFANIL_T net (assets minus liabilities)        -> BPM6 net lending(+)/borrowing(-) via the account
  A_T        reserve assets transactions (assets only)
  NETCD_T    balance (credit minus debit) for current/capital account items

Indicators: D_F direct investment, P_F portfolio, P_F3 portfolio debt securities,
P_F5 portfolio equity & investment-fund shares, O_F other investment, R_F reserve assets,
F_F7 financial derivatives, FAB financial account balance, CAB current account balance.
"""
from __future__ import annotations

import sys

from src.common import RAW, fetch_raw

BASE = "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,BOP"
ENTRIES = "A_NFA_T+L_NIL_T+NNAFANIL_T+A_T+NETCD_T"
INDICATORS = "D_F+P_F+P_F3+P_F5+O_F+R_F+FAB+CAB+F_F7"
CSV_HEADER = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}


def download(freq: str, refresh: bool = False):
    key = f".{ENTRIES}.{INDICATORS}.USD.{freq}"
    dest = RAW / "imf_bop" / f"imf_bop_{freq}_raw.csv"
    return fetch_raw(f"{BASE}/{key}", dest, "IMF BOP (IMF.STA:BOP)",
                     params={"startPeriod": "2014"}, headers=CSV_HEADER,
                     refresh=refresh, timeout=1200,
                     note=f"SDMX key {key}; startPeriod=2014; USD; BPM6")




def download_official_oi(freq: str = "Q", refresh: bool = False):
    """Other-investment liabilities of the central bank (S121) and general government (S13)
    by instrument (F2 deposits, F4 loans, F81 trade credit, F8AP other payables) plus SDR
    allocations (O_F12_S1N). Used to construct gross *private* inflows (post-hoc alignment with
    Arakelyan & Evdokimova 2025; see report/protocol_changelog.md).

    Note: a first query using O_FL1_S121/O_FL1_S13 returned only the SDR series (those
    sector codes are not published for O_FL1); that file is retained as imf_bop_official_oi_Q_raw.csv.
    """
    inst = "+".join(f"O_{i}_{s}" for i in ("F2", "F4", "F81", "F8AP") for s in ("S121", "S13"))
    key = f".L_NIL_T.{inst}+O_F12_S1N.USD.{freq}"
    dest = RAW / "imf_bop" / f"imf_bop_official_oi_by_instrument_{freq}_raw.csv"
    return fetch_raw(f"{BASE}/{key}", dest, "IMF BOP (IMF.STA:BOP)", params={"startPeriod": "2014"},
                     headers=CSV_HEADER, refresh=refresh, timeout=1200,
                     note=f"SDMX key {key}; official-sector other-investment liabilities")


if __name__ == "__main__":
    for f in (sys.argv[1:] or ["A", "Q"]):
        download(f)
