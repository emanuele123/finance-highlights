"""Collaudi senza rete: universo, lettura delle risposte delle fonti, controlli di qualita'."""
import io
import zipfile
from datetime import date

import numpy as np
import pandas as pd

from gsi import db
from gsi.aggiorna import controlla_qualita, salva_prezzi
from gsi.controlli import nome_somiglia, salti_anomali, valuta_titolo, valuta_unita
from gsi.fonti import bce, gdelt, sec, yahoo
from gsi.universo import ESCLUSI, PER_TICKER, UNIVERSO


def test_universo():
    assert len(UNIVERSO) == 120
    assert "REC.MI" in ESCLUSI and "REC.MI" not in PER_TICKER
    h = PER_TICKER["HSBA.L"]
    assert (h.valuta, h.in_centesimi, h.valuta_bilancio) == ("GBP", True, "USD")
    assert sum(t.in_centesimi for t in UNIVERSO) == 4
    assert PER_TICKER["AZN"].indice == "^GSPC" and "Non più ADR" in PER_TICKER["AZN"].adr
    assert PER_TICKER["TSM"].valuta_bilancio == "TWD"
    assert "ROP.SW" in PER_TICKER and "ROG.SW" not in PER_TICKER


def _storico():
    idx = pd.DatetimeIndex(["2026-11-18", "2026-11-19", "2026-11-20"], tz="Europe/London")
    return pd.DataFrame({"Open": [1300.0, 1290.0, 1260.0], "High": [1320.0, 1300.0, 1265.0],
                         "Low": [1290.0, 1280.0, 1234.0], "Close": [1292.0, 1280.0, np.nan],
                         "Adj Close": [1285.0, 1280.0, np.nan], "Volume": [10, 20, 30],
                         "Dividends": [0.0, 7.5, 0.0], "Stock Splits": [0.0, 0.0, 0.0]}, index=idx)


def test_storico_centesimi_e_ultima_seduta():
    r = yahoo.normalizza_storico(_storico(), True)
    assert len(r) == 2                                   # la seduta senza chiusura e' scartata
    assert r[0][0] == "2026-11-18" and abs(r[0][4] - 12.92) < 1e-9 and abs(r[0][5] - 12.85) < 1e-9
    assert abs(r[1][7] - 0.075) < 1e-12                  # dividendo in sterline, non in pence
    meta = {"regularMarketPrice": 1234.0, "regularMarketTime": pd.Timestamp("2026-11-20 18:03", tz="Europe/London")}
    r = yahoo.normalizza_storico(_storico(), True, meta)
    assert len(r) == 3 and abs(r[2][4] - 12.34) < 1e-9
    meta["regularMarketTime"] = pd.Timestamp("2026-11-19 18:03", tz="Europe/London")   # data diversa: niente
    assert len(yahoo.normalizza_storico(_storico(), True, meta)) == 2
    assert yahoo.normalizza_storico(_storico(), False)[0][4] == 1292.0
    assert yahoo.normalizza_storico(pd.DataFrame(), False) == []


def test_prospetto_scarta_i_vuoti():
    df = pd.DataFrame({pd.Timestamp("2025-12-31"): [100.0, np.nan], pd.Timestamp("2024-12-31"): [90.0, 5.0]},
                      index=["TotalRevenue", "NetIncome"])
    r = yahoo.normalizza_prospetto(df)
    assert ("2025-12-31", "TotalRevenue", 100.0) in r and ("2024-12-31", "NetIncome", 5.0) in r and len(r) == 3


def test_anagrafica_utili_revisioni_notizie():
    a = yahoo.normalizza_anagrafica({"longName": "HSBC Holdings plc", "currency": "GBp", "financialCurrency": "USD",
                                     "marketCap": 2.1e11, "regularMarketPrice": 1234.0, "quoteType": "EQUITY"})
    assert a["valuta_fonte"] == "GBp" and a["valuta_bilancio_fonte"] == "USD" and a["eps_atteso"] is None
    idx = pd.DatetimeIndex(["2027-01-28 16:00", "2026-11-02 16:00"], tz="America/New_York", name="Earnings Date")
    d = yahoo.normalizza_date_utili(pd.DataFrame({"EPS Estimate": [2.91, 1.98], "Reported EPS": [np.nan, 2.10],
                                                  "Surprise(%)": [np.nan, 5.8]}, index=idx))
    assert d[0] == ("2026-11-02", "16:00", 1.98, 2.10, 5.8) and d[1][3] is None
    rv = yahoo.normalizza_revisioni(pd.DataFrame({"upLast7days": [10], "upLast30days": [11], "downLast30days": [2],
                                                  "downLast7Days": [1]}, index=pd.Index(["0q"], name="period")))
    assert rv == [("0q", 10.0, 11.0, 1.0, 2.0)]
    n = yahoo.normalizza_notizie([{"content": {"title": " Titolo ", "pubDate": "2026-11-20T16:42:26Z",
                                               "provider": {"displayName": "Testata"},
                                               "canonicalUrl": {"url": "https://x.test/a"}}},
                                  {"content": {"title": "senza link"}}, "rotto"])
    assert n == [("https://x.test/a", "Titolo", "Testata", "2026-11-20T16:42:26Z")]


def test_bce():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("eurofxref-hist.csv", "Date,USD,JPY,RUB,\n2026-11-20,1.05,160.1,N/A,\n2014-01-02,1.3,140,40,\n")
    assert bce.valute_disponibili(buf.getvalue()) == {"USD", "JPY", "RUB"}
    r = bce.leggi_zip(buf.getvalue(), {"USD", "RUB", "TWD"})
    assert r == [("2026-11-20", "USD", 1.05)]


def test_sec():
    assert sec.fine_mese("2024-09-28") == "2024-09-30"
    assert sec.fine_mese("2025-02-01") == "2025-01-31"
    assert sec.fine_mese("2025-01-03") == "2024-12-31"
    assert sec.fine_mese("2025-12-31") == "2025-12-31"
    f = lambda s, e, v, form="10-K", filed="2025-11-01": {"start": s, "end": e, "val": v, "form": form, "filed": filed}
    fatti = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [f("2023-10-01", "2024-09-28", 100), f("2024-06-30", "2024-09-28", 30),
                                       f("2023-10-01", "2024-09-28", 101, filed="2026-01-01"),
                                       f("2022-10-01", "2023-09-30", 90, form="10-Q")]}},
        "StockholdersEquity": {"units": {"USD": [{"end": "2024-09-28", "val": 50, "form": "10-K", "filed": "2024-11-01"}]}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": [f("2023-10-01", "2024-09-28", 6.1)]}}}}}
    r = sec.estrai_annuali(fatti)
    assert ("CE", "2024-09-30", "TotalRevenue", 101.0) in r       # periodo annuale, deposito piu' recente
    assert ("SP", "2024-09-30", "StockholdersEquity", 50.0) in r
    assert ("CE", "2024-09-30", "DilutedEPS", 6.1) in r and len(r) == 3


def test_gdelt():
    r = gdelt.leggi_risposta({"articles": [{"url": "https://a.test/1", "title": "Titolo", "domain": "a.test",
                                            "seendate": "20261120T143000Z", "language": "Italian"},
                                           {"url": "", "title": "x"}]})
    assert r == [("https://a.test/1", "Titolo", "a.test", "2026-11-20T14:30:00Z", "Italian")]
    assert gdelt.leggi_risposta({}) == []


def test_nome_somiglia():
    ok = [("TSMC (ADR)", "Taiwan Semiconductor Manufacturing Company Limited"), ("NTT", "NTT, Inc."),
          ("Alphabet (classe A)", "Alphabet Inc."), ("LVMH", "LVMH Moët Hennessy - Louis Vuitton, Société Européenne"),
          ("Nestlé", "Nestle S.A."), ("L'Oréal", "L'Oreal S.A."), ("Telecom Italia (TIM)", "Telecom Italia S.p.A."),
          ("JPMorgan Chase", "JPMorgan Chase & Co."), ("Roche (buono di godimento)", "Roche Holding AG"),
          ("A2A", "A2A S.p.A."), ("S&P Global", "S&P Global Inc.")]
    for a, f in ok:
        assert nome_somiglia(a, f), (a, f)
    for a, f in [("Apple", "Microsoft Corporation"), ("Enel", "Eni S.p.A."), ("Sanofi", "Banco Santander, S.A."),
                 ("Apple", None)]:
        assert not nome_somiglia(a, f), (a, f)


def _base(**k):
    d = dict(oggi=date(2026, 11, 21), n_prezzi=2700, ultimo_prezzo="2026-11-20", valuta_attesa="GBP",
             centesimi_attesi=True, valuta_fonte="GBp", valuta_bil_attesa="USD", valuta_bil_fonte="USD",
             nome_atteso="HSBC Holdings", nome_fonte="HSBC Holdings plc", salti=[], richiede_bilanci=True,
             ultimo_esercizio="2025-12-31", n_esercizi=4)
    d.update(k)
    return valuta_titolo(**d)


def test_controlli():
    assert valuta_unita("GBp") == ("GBP", True) and valuta_unita("EUR") == ("EUR", False)
    assert _base() == ("OK", [])
    assert _base(n_prezzi=0, ultimo_prezzo=None)[0] == "ERRORE"
    for k, parola in [(dict(ultimo_prezzo="2026-11-10"), "vecchio"), (dict(valuta_fonte="USD"), "valuta di quotazione"),
                      (dict(valuta_fonte="GBP"), "centesimi"), (dict(valuta_bil_fonte="GBP"), "valuta di bilancio"),
                      (dict(nome_fonte="Barclays PLC"), "nome"), (dict(ultimo_esercizio="2024-12-31"), "esercizio"),
                      (dict(n_esercizi=0, ultimo_esercizio=None), "nessun bilancio"),
                      (dict(salti=["salto del +1000% il 2026-06-15"]), "storico")]:
        stato, motivi = _base(**k)
        assert stato == "DA VERIFICARE" and parola in "; ".join(motivi), (k, motivi)
    assert salti_anomali([("a", 0.5), ("b", 5.5), ("c", 5.4)]) == ["salto del +1000% il b"]
    assert salti_anomali([("a", 10.0), ("b", 11.0)]) == []


def test_archivio_e_qualita():
    con = db.apri(":memory:")
    salva_prezzi(con, "AAPL", [("2026-11-19", 1, 1, 1, 1, 1, 10, 0, 0), ("2026-11-20", 1, 1, 1, 1, 1, 10, 0, 0)])
    salva_prezzi(con, "AAPL", [("2026-11-20", 2, 2, 2, 2, 2, 10, 0, 0)])        # sostituzione integrale
    assert con.execute("SELECT COUNT(*), MAX(chiusura) FROM prezzi").fetchone()[:] == (1, 2.0)
    controlla_qualita(con, date(2026, 11, 21))
    q = {r["ticker"]: r for r in con.execute("SELECT * FROM qualita")}
    assert len(q) == 120 + 10 + 2
    assert q["AAPL"]["stato"] == "DA VERIFICARE" and "nessun bilancio" in q["AAPL"]["motivi"]
    assert q["MSFT"]["stato"] == "ERRORE"
    db.registra_errore(con, "X", "prezzi", "prova")
    assert con.execute("SELECT COUNT(*) FROM errori").fetchone()[0] == 1
