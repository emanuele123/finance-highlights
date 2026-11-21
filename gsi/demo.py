"""Versione dimostrativa: societa' INVENTATE con dati INVENTATI, etichettate come tali.

Serve a provare il cruscotto senza rete e ad alimentare i collaudi automatici. Nessun numero qui
dentro riguarda societa' reali; i ticker iniziano tutti con DEMO.
"""
from __future__ import annotations
import math
import random
from datetime import date, timedelta

from . import db
from .universo import Titolo

INDICE = "^DEMO"

# ticker, nome, area, settore, modello, valuta, valuta di bilancio, profilo
_SOCIETA = [
    ("DEMO01", "Alfa Software (inventata)", "USA", "Tecnologia e semiconduttori", "STD", "USD", "USD", "ottima"),
    ("DEMO02", "Beta Bevande (inventata)", "Europa", "Consumi e grande distribuzione", "STD", "EUR", "EUR", "buona"),
    ("DEMO03", "Gamma Moda (inventata)", "Italia", "Lusso", "STD", "EUR", "EUR", "buona"),
    ("DEMO04", "Delta Acciai (inventata)", "Europa", "Materie prime", "CIC", "EUR", "EUR", "ciclica"),
    ("DEMO05", "Epsilon Petroli (inventata)", "USA", "Energia", "CIC", "USD", "USD", "ciclica"),
    ("DEMO06", "Zeta Reti (inventata)", "Italia", "Utilities e infrastrutture", "UTL", "EUR", "EUR", "regolata"),
    ("DEMO07", "Eta Telecom (inventata)", "Europa", "Telecomunicazioni", "UTL", "EUR", "EUR", "debole"),
    ("DEMO08", "Theta Banca (inventata)", "Italia", "Banche e servizi finanziari", "BAN", "EUR", "EUR", "banca"),
    ("DEMO09", "Iota Bank (inventata)", "USA", "Banche e servizi finanziari", "BAN", "USD", "USD", "banca"),
    ("DEMO10", "Kappa Assicura (inventata)", "Europa", "Assicurazioni", "ASS", "EUR", "EUR", "banca"),
    ("DEMO11", "Lambda Immobili (inventata)", "USA", "Immobiliare", "REIT", "USD", "USD", "regolata"),
    ("DEMO12", "Mi Aerospazio (inventata)", "Europa", "Industria e difesa", "STD", "EUR", "EUR", "perdita"),
    ("DEMO13", "Ni Chip (inventata)", "Emergenti", "Tecnologia e semiconduttori", "STD", "USD", "USD", "ottima"),
    ("DEMO14", "Xi Farmaci (inventata)", "Europa", "Sanità e farmaceutica", "STD", "EUR", "EUR", "vecchia"),
    ("DEMO15", "Omicron Cloud (inventata)", "USA", "Tecnologia e semiconduttori", "STD", "USD", "USD", "buona"),
    ("DEMO16", "Pi Sensori (inventata)", "Giappone", "Tecnologia e semiconduttori", "STD", "USD", "USD", "debole"),
]

UNIVERSO_DEMO = [Titolo(tk, nome, area, sett, mod, val, False, vb, INDICE, "") for tk, nome, area, sett, mod, val, vb, _ in _SOCIETA]
_PROFILI = {  # crescita ricavi, margine EBIT, debito/ricavi, deriva annua del prezzo, volatilita' annua
    "ottima": (0.14, 0.32, 0.05, 0.22, 0.28), "buona": (0.07, 0.20, 0.25, 0.10, 0.20), "ciclica": (0.02, 0.11, 0.30, 0.04, 0.30),
    "regolata": (0.03, 0.24, 1.60, 0.06, 0.16), "debole": (-0.01, 0.07, 1.20, -0.08, 0.26), "banca": (0.05, 0.0, 0.0, 0.09, 0.24),
    "perdita": (0.04, -0.06, 0.70, -0.15, 0.40), "vecchia": (0.05, 0.18, 0.20, 0.05, 0.18),
}


def _sedute(fine: date, n: int) -> list[date]:
    out, d = [], fine
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


def crea_archivio(percorso, oggi: date | None = None, seme: int = 7):
    """Crea (da zero) un archivio con le societa' inventate. -> connessione aperta."""
    oggi = oggi or date.today()
    rnd = random.Random(seme)
    con = db.apri(percorso)
    for tab in ("prezzi", "anagrafica", "bilanci", "date_utili", "revisioni", "stime_utili", "notizie", "cambi", "qualita", "scarichi"):
        con.execute(f"DELETE FROM {tab}")
    ultima = oggi - timedelta(days=1)
    while ultima.weekday() >= 5:
        ultima -= timedelta(days=1)
    giorni = _sedute(ultima, 2800)
    # indice e cambio inventati
    idx, righe = 1000.0, []
    for d in giorni:
        idx *= math.exp(rnd.gauss(0.07 / 252, 0.15 / math.sqrt(252)))
        righe.append((INDICE, d.isoformat(), idx, idx * 1.004, idx * 0.996, idx, idx, 0.0, 0.0, 0.0))
    con.executemany("INSERT INTO prezzi VALUES(?,?,?,?,?,?,?,?,?,?)", righe)
    fx = 1.10
    for d in giorni:
        fx *= math.exp(rnd.gauss(0, 0.07 / math.sqrt(252)))
        con.execute("INSERT INTO cambi VALUES(?,?,?,'DEMO')", (d.isoformat(), "USD", fx))

    for n_soc, (tk, nome, area, sett, mod, val, vb, profilo) in enumerate(_SOCIETA):
        cresc, marg, leva, deriva, vola = _PROFILI[profilo]
        # ---- prezzi: passeggiata casuale con deriva, dividendi trimestrali
        p, righe = 20.0 + 15 * n_soc, []
        div = 0.0 if profilo in ("perdita", "ottima") else 0.006
        for j, d in enumerate(giorni):
            r = rnd.gauss(deriva / 252, vola / math.sqrt(252))
            ap = p
            p *= math.exp(r)
            mx, mn = max(ap, p) * (1 + abs(rnd.gauss(0, 0.004))), min(ap, p) * (1 - abs(rnd.gauss(0, 0.004)))
            dv = p * div if j % 63 == 62 else 0.0
            righe.append([tk, d.isoformat(), ap, mx, mn, p, p, rnd.uniform(0.6, 1.6) * 2e6, dv, 0.0])
        fatt = 1.0                                       # chiusura rettificata per i dividendi (total return)
        for riga in reversed(righe):
            riga[6] = riga[5] * fatt
            if riga[8]:
                fatt *= 1 - riga[8] / riga[5]
        con.executemany("INSERT INTO prezzi VALUES(?,?,?,?,?,?,?,?,?,?)", righe)
        prezzo = righe[-1][5]
        azioni = 500e6 + 100e6 * n_soc
        # ---- bilanci annuali (5 esercizi; la societa' 'vecchia' ha l'ultimo esercizio di due anni fa)
        ultimo_anno = oggi.year - (3 if profilo == "vecchia" else 1)
        ricavi = prezzo * azioni / (6.0 if mod not in ("BAN", "ASS") else 3.0)
        ricavi /= (1 + cresc) ** 4
        patr = ricavi * (0.9 if mod not in ("BAN", "ASS") else 1.4)
        b = []
        for k in range(5):
            anno = ultimo_anno - 4 + k
            d = f"{anno}-12-31"
            rr = ricavi * (1 + cresc + rnd.uniform(-0.03, 0.03)) ** k
            if mod in ("BAN", "ASS"):
                utile = patr * rnd.uniform(0.09, 0.13)
                ebit = None
                attivo = patr * 13
            else:
                ebit = rr * (marg + rnd.uniform(-0.02, 0.02))
                attivo = rr * 1.8
            debito = rr * leva
            interessi = debito * 0.04
            if ebit is not None:
                ante = ebit - interessi
                tasse = max(0.0, ante * 0.24)
                utile = ante - tasse
            else:
                ante, tasse = utile / 0.76, utile / 0.76 * 0.24
            da = rr * (0.12 if mod in ("UTL", "REIT") else 0.05)
            fcf = utile * (0.6 if mod in ("UTL", "CIC") else 0.95) if utile > 0 else utile * 1.2
            dividendi = 0.0 if div == 0 else max(0.0, utile) * 0.5
            cassa = rr * (0.25 if profilo == "ottima" else 0.08)
            ce = {"TotalRevenue": rr, "NetIncomeCommonStockholders": utile, "NetIncome": utile, "TaxProvision": tasse,
                  "PretaxIncome": ante, "InterestExpense": interessi, "ReconciledDepreciation": da,
                  "DilutedEPS": utile / azioni, "DilutedAverageShares": azioni * (1 - 0.01 * k if profilo == "buona" else 1)}
            if ebit is not None:
                ce.update({"EBIT": ebit, "OperatingIncome": ebit, "EBITDA": ebit + da, "GrossProfit": rr * (marg + 0.3)})
            sp = {"TotalDebt": debito, "StockholdersEquity": patr, "TotalEquityGrossMinorityInterest": patr * 1.02,
                  "TotalAssets": attivo, "CashCashEquivalentsAndShortTermInvestments": cassa,
                  "CurrentLiabilities": rr * 0.25, "CurrentDebt": debito * 0.15,
                  "GoodwillAndOtherIntangibleAssets": patr * (0.8 if profilo == "debole" else 0.2),
                  "TangibleBookValue": patr * (0.2 if profilo == "debole" else 0.8), "OrdinarySharesNumber": azioni}
            rf = {"FreeCashFlow": fcf, "CashDividendsPaid": -dividendi, "StockBasedCompensation": rr * 0.01}
            for prosp, voci in (("CE", ce), ("SP", sp), ("RF", rf)):
                b += [(tk, prosp, "A", d, v, x, "yahoo") for v, x in voci.items()]
            patr += utile - dividendi
        con.executemany("INSERT INTO bilanci VALUES(?,?,?,?,?,?,?)", b)
        eps = utile / azioni
        con.execute("INSERT INTO anagrafica(ticker,tipo,nome_fonte,valuta_fonte,valuta_bilancio_fonte,borsa,capitalizzazione,"
                    "prezzo_fonte,azioni_fonte,beta,json,aggiornato) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tk, "EQUITY", nome, val, vb, "Borsa dimostrativa", prezzo * azioni, prezzo, azioni,
                     round(rnd.uniform(0.6, 1.5), 2), "{}", db.adesso()))
        # ---- utili, stime, revisioni
        passata = giorni[-1 - rnd.randint(8, 70)]
        prossima = oggi + timedelta(days=rnd.choice([4, 20, 45, 70]))
        con.execute("INSERT INTO date_utili VALUES(?,?,?,?,?,?)", (tk, passata.isoformat(), "16:00", eps / 4, eps / 4 * 1.03, 3.0))
        con.execute("INSERT INTO date_utili VALUES(?,?,?,?,?,?)", (tk, prossima.isoformat(), "16:00", eps / 4, None, None))
        if eps > 0:
            con.execute("INSERT INTO stime_utili VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (tk, "+1y", eps * 1.08, eps, eps * 1.2, eps, 12, vb, "normalized", db.adesso()))
        con.execute("INSERT INTO revisioni VALUES(?,?,?,?,?,?,?)",
                    (tk, "0y", 1, rnd.randint(0, 8), 1, rnd.randint(0, 8), db.adesso()))
        con.execute("INSERT INTO qualita VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (tk, "OK", "Dati dimostrativi inventati", righe[-1][1], len(righe), f"{ultimo_anno}-12-31", 5, 0, 0, db.adesso()))
    con.execute("INSERT OR REPLACE INTO meta VALUES('demo', '1')")
    con.commit()
    return con
