"""SEC EDGAR companyfacts (facoltativo): allunga a 10 anni ricavi, utili, cassa e patrimonio
delle societa' che depositano il 10-K. Richiede un User-Agent con nome ed e-mail dell'utente.
"""
from __future__ import annotations
import calendar
import time

import requests

from .. import config

URL_TICKER = "https://www.sec.gov/files/company_tickers.json"
URL_FATTI = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# voce interna (nome Yahoo) -> concetti us-gaap in ordine di preferenza
CONCETTI = {
    ("CE", "TotalRevenue"): ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                             "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"],
    ("CE", "NetIncome"): ["NetIncomeLoss"],
    ("CE", "DilutedEPS"): ["EarningsPerShareDiluted"],
    ("CE", "OperatingIncome"): ["OperatingIncomeLoss"],
    ("SP", "CashAndCashEquivalents"): ["CashAndCashEquivalentsAtCarryingValue",
                                       "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    ("SP", "StockholdersEquity"): ["StockholdersEquity"],
    ("SP", "TotalAssets"): ["Assets"],
}
_ultima = 0.0


def fine_mese(data_iso: str) -> str:
    """Allinea una data di chiusura al fine mese piu' vicino (es. 2024-09-28 -> 2024-09-30,
    2025-02-01 -> 2025-01-31) per non duplicare gli esercizi rispetto a Yahoo."""
    a, m, g = (int(x) for x in data_iso[:10].split("-"))
    if g <= 7:               # esercizi a 52/53 settimane che sconfinano nel mese dopo
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return f"{a:04d}-{m:02d}-{calendar.monthrange(a, m)[1]:02d}"


def _get(url: str, ua: str):
    global _ultima
    att = config.PAUSA_SEC - (time.monotonic() - _ultima)
    if att > 0:
        time.sleep(att)
    _ultima = time.monotonic()
    r = requests.get(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=60)
    r.raise_for_status()
    return r.json()


def mappa_cik(ua: str) -> dict[str, int]:
    return {v["ticker"].upper(): int(v["cik_str"]) for v in _get(URL_TICKER, ua).values()}


def estrai_annuali(fatti: dict) -> list[tuple]:
    """companyfacts -> righe (prospetto, data_chiusura_fine_mese, voce, valore) dei soli 10-K.

    Per i flussi (CE) si tengono i periodi di 330-380 giorni; per ogni data vince il
    deposito piu' recente (eventuali riesposizioni).
    """
    gaap = (fatti.get("facts") or {}).get("us-gaap") or {}
    out: dict[tuple, tuple] = {}
    for (prospetto, voce), concetti in CONCETTI.items():
        trovati: dict[str, tuple] = {}
        for c in concetti:
            for unita, lista in ((gaap.get(c) or {}).get("units") or {}).items():
                if not unita.startswith("USD"):
                    continue
                for f in lista:
                    if f.get("form") not in ("10-K", "10-K/A") or f.get("val") is None or not f.get("end"):
                        continue
                    if prospetto == "CE":
                        if not f.get("start"):
                            continue
                        gg = (_giorni(f["end"]) - _giorni(f["start"]))
                        if not 330 <= gg <= 380:
                            continue
                    d = fine_mese(f["end"])
                    prec = trovati.get(d)
                    if prec is None or (f.get("filed") or "") > prec[0]:
                        trovati[d] = (f.get("filed") or "", float(f["val"]))
            if trovati:
                # i concetti successivi integrano solo le date mancanti
                for d, (dep, v) in trovati.items():
                    out.setdefault((prospetto, d, voce), (dep, v))
        del trovati
    return sorted((p, d, voce, v) for (p, d, voce), (_, v) in out.items())


def _giorni(iso: str) -> int:
    from datetime import date
    return date.fromisoformat(iso[:10]).toordinal()


def scarica_fatti(cik: int, ua: str) -> dict:
    return _get(URL_FATTI.format(cik=cik), ua)
