"""'Perche' sale o scende': per ogni variazione giornaliera rilevante separa la parte attesa dal mercato
(beta x indice), quella del settore e quella specifica, elenca gli eventi societari documentati e i
titoli di stampa usciti nella stessa finestra, e dichiara un livello di evidenza.

Fatti, ipotesi e opinioni restano distinti. Una coincidenza temporale non e' mai presentata come causa.
Il contenuto degli articoli non viene verificato ne' riassunto: si riporta il titolo e si rimanda alla fonte.
"""
from __future__ import annotations
import bisect
import statistics

import numpy as np

from . import db
from .fonti import gdelt

SEDUTE = 42            # finestra osservata: ultime 42 sedute (circa due mesi)
SOGLIA = 0.04          # variazione di almeno il 4%
N_SIGMA = 2.0          # oppure anomala oltre 2 deviazioni standard (calcolate sulle 252 sedute precedenti)
MIN_PARI = 3           # titoli dello stesso settore necessari per stimare la parte di settore
QUOTA_COMUNE = 0.6     # livello C: mercato + settore spiegano almeno il 60% della variazione, nello stesso verso
MAX_NOTIZIE = 3
MAX_GDELT = 30         # richieste GDELT per aggiornamento (una ogni 5 secondi)

LIVELLI = {"A": "A - evento societario documentato nella finestra", "B": "B - notizie coincidenti nella finestra",
           "C": "C - movimento in gran parte comune a mercato o settore", "D": "D - nessuna causa individuata"}


def beta_ols(r_titolo, r_indice):
    """Pendenza della regressione dei rendimenti del titolo su quelli dell'indice. None se non stimabile."""
    x, y = np.asarray(r_indice, float), np.asarray(r_titolo, float)
    if len(x) < 60 or len(x) != len(y):
        return None
    v = x.var()
    return float(((x - x.mean()) * (y - y.mean())).mean() / v) if v > 0 else None


def rendimenti_allineati(date_t: list[str], rett: list[float], idx: dict | None):
    """-> (rendimenti del titolo, rendimenti dell'indice nelle stesse date; None se l'indice manca)."""
    rt = [rett[i] / rett[i - 1] - 1 if rett[i - 1] else 0.0 for i in range(1, len(rett))]
    if not idx or not idx["data"]:
        return rt, None
    liv = []
    for d in date_t:
        j = bisect.bisect_right(idx["data"], d) - 1
        liv.append(idx["chius"][j] if j >= 0 else None)
    ri = [liv[i] / liv[i - 1] - 1 if liv[i] and liv[i - 1] else 0.0 for i in range(1, len(liv))]
    return rt, ri


def livello_evidenza(variazione: float, mercato, settore, eventi: list[str], n_notizie: int) -> str:
    if eventi:
        return "A"
    comune = (mercato or 0.0) + (settore or 0.0)
    if variazione and comune * variazione > 0 and abs(comune) >= QUOTA_COMUNE * abs(variazione):
        return "C"
    return "B" if n_notizie else "D"


def lettura(livello: str, eventi: list[str], mercato, settore) -> str:
    """Lettura possibile, sempre etichettata come ipotesi."""
    if livello == "A":
        return "Ipotesi: reazione a " + "; ".join(e.lower() for e in eventi) + ". Da confermare leggendo le fonti."
    if livello == "C":
        chi = "al mercato" if abs(mercato or 0) >= abs(settore or 0) else "al settore"
        return f"Ipotesi: movimento in gran parte comune {chi}, non specifico del titolo."
    if livello == "B":
        return ("Ipotesi: possibile legame con le notizie uscite nella stessa finestra (vedi titoli). "
                "La coincidenza temporale non prova la causa.")
    return "Nessuna causa individuata nei dati disponibili: nessuna ipotesi formulata."


def calcola_movimenti(con, universo: list, sedute: int = SEDUTE) -> list[dict]:
    """Elenco delle variazioni rilevanti delle ultime `sedute` sedute, dalla piu' recente."""
    dati, indici = {}, {}
    for t in universo:
        r = con.execute("SELECT data, chiusura, chiusura_rett, dividendo, frazionamento FROM prezzi WHERE ticker=? "
                        "ORDER BY data", (t.ticker,)).fetchall()
        if len(r) < 320:
            continue
        if t.indice not in indici:
            x = con.execute("SELECT data, chiusura FROM prezzi WHERE ticker=? ORDER BY data", (t.indice,)).fetchall()
            indici[t.indice] = {"data": [a[0] for a in x], "chius": [a[1] for a in x]}
        r = r[-(sedute + 260):]
        d = [x[0] for x in r]
        rt, ri = rendimenti_allineati(d, [x[2] for x in r], indici[t.indice])
        dati[t.ticker] = {"t": t, "date": d[1:], "r": rt, "ri": ri, "div": [x[3] for x in r][1:],
                          "fraz": [x[4] for x in r][1:], "prec": d[:-1]}
    # beta e parte non spiegata dal mercato, per data (serve alla mediana di settore)
    residui: dict[str, dict[str, float]] = {}
    for tk, x in dati.items():
        n = len(x["r"])
        x["beta"], x["sigma"] = {}, {}
        for i in range(max(0, n - sedute), n):
            ini = max(0, i - 252)
            x["sigma"][i] = statistics.pstdev(x["r"][ini:i]) if i - ini >= 60 else None
            x["beta"][i] = beta_ols(x["r"][ini:i], x["ri"][ini:i]) if x["ri"] else None
            b = x["beta"][i]
            res = x["r"][i] - b * x["ri"][i] if b is not None else None
            if res is not None:
                residui.setdefault(x["date"][i], {})[tk] = res
    out = []
    for tk, x in dati.items():
        t, n = x["t"], len(x["r"])
        pari = [k for k, y in dati.items() if y["t"].settore == t.settore and k != tk]
        utili = [u[0] for u in con.execute("SELECT data FROM date_utili WHERE ticker=? AND eps_reale IS NOT NULL", (tk,))]
        for i in range(max(0, n - sedute), n):
            r, sig, giorno, prima = x["r"][i], x["sigma"][i], x["date"][i], x["prec"][i]
            grande = abs(r) >= SOGLIA
            anomala = sig is not None and sig > 0 and abs(r) > N_SIGMA * sig
            if not (grande or anomala):
                continue
            b = x["beta"][i]
            mercato = b * x["ri"][i] if b is not None else None
            altri = [residui.get(giorno, {}).get(k) for k in pari]
            altri = [a for a in altri if a is not None]
            settore = statistics.median(altri) if len(altri) >= MIN_PARI else None
            eventi = []
            for u in utili:
                if prima <= u <= giorno:
                    eventi.append(f"Risultati pubblicati il {u[8:10]}/{u[5:7]}/{u[:4]}")
            if x["div"][i]:
                eventi.append(f"Stacco del dividendo di {x['div'][i]:.4g} per azione")
            if x["fraz"][i]:
                eventi.append(f"Frazionamento o raggruppamento (fattore {x['fraz'][i]:g})")
            notizie = con.execute(
                "SELECT titolo, testata, url, fonte FROM notizie WHERE ticker=? AND substr(pubblicato,1,10) BETWEEN ? AND ? "
                "ORDER BY pubblicato DESC", (tk, prima, giorno)).fetchall()
            # lo stacco del dividendo non spiega una variazione misurata sul total return: da solo non vale come evento
            visti, uniche = set(), []
            for v in notizie:                 # lo stesso titolo ripreso da piu' testate conta una volta
                if v[0].lower() not in visti:
                    visti.add(v[0].lower())
                    uniche.append(v)
            notizie = uniche
            causali = [e for e in eventi if not e.startswith("Stacco")]
            liv = livello_evidenza(r, mercato, settore, causali, len(notizie))
            out.append({"ticker": tk, "nome": t.nome, "data": giorno, "variazione": r, "sigma": sig,
                        "tipo": ("Almeno 4% e anomala" if grande and anomala else "Almeno 4%" if grande else "Anomala (oltre 2 dev. std)"),
                        "beta": b, "indice": x["ri"][i] if x["ri"] else None, "mercato": mercato, "settore": settore,
                        "eventi": eventi, "notizie": [tuple(v) for v in notizie[:MAX_NOTIZIE]], "n_notizie": len(notizie),
                        "livello": liv, "lettura": lettura(liv, causali, mercato, settore)})
    out.sort(key=lambda m: (m["data"], abs(m["variazione"])), reverse=True)
    return out


def parola_chiave(nome: str) -> str:
    """Parola piu' lunga del nome della societa' (es. 'Schneider' per 'Schneider Electric')."""
    return max(nome.replace("&", " ").split(), key=len).lower()


def pertinenti(nome: str, righe: list[tuple]) -> list[tuple]:
    """GDELT cerca nel testo degli articoli e restituisce anche pezzi che citano la societa' di sfuggita:
    si tengono solo i titoli che ne contengono il nome, senza ripetere lo stesso titolo ripreso da piu' testate."""
    chiave, visti, out = parola_chiave(nome), set(), []
    for r in righe:
        t = r[1].lower()
        if chiave in t and t not in visti:
            visti.add(t)
            out.append(r)
    return out


def scarica_notizie_gdelt(con, universo: list, registra=print, massimo: int = MAX_GDELT) -> int:
    """Titoli di stampa da GDELT solo per i titoli che si sono mossi (una richiesta ogni 5 secondi).
    Tre errori consecutivi fermano il passo per questo aggiornamento, senza fermare il resto. -> titoli salvati"""
    con.execute("CREATE TABLE IF NOT EXISTS gdelt_richieste(ticker TEXT, data TEXT, quando TEXT, esito TEXT, "
                "PRIMARY KEY(ticker, data))")
    fatte = {(r[0], r[1]) for r in con.execute("SELECT ticker, data FROM gdelt_richieste")}
    mov = [m for m in calcola_movimenti(con, universo) if (m["ticker"], m["data"]) not in fatte]
    mov.sort(key=lambda m: -abs(m["variazione"] - (m["mercato"] or 0) - (m["settore"] or 0)))
    salvati = errori = 0
    for m in mov[:massimo]:
        g = m["data"].replace("-", "")
        prima = con.execute("SELECT MAX(data) FROM prezzi WHERE ticker=? AND data<?", (m["ticker"], m["data"])).fetchone()[0]
        nome = m["nome"].split("(")[0].strip()
        if len(nome) < 6:                    # GDELT rifiuta le frasi troppo corte (es. "A2A", "SAP")
            con.execute("INSERT OR REPLACE INTO gdelt_richieste VALUES(?,?,?,'nome troppo corto')",
                        (m["ticker"], m["data"], db.adesso()))
            continue
        try:
            righe = gdelt.cerca(f'"{nome}"', (prima or m["data"]).replace("-", "") + "000000", g + "235959", 10)
            errori = 0
        except Exception as e:  # noqa: BLE001
            db.registra_errore(con, m["ticker"], "notizie GDELT", f"{type(e).__name__}: {e}")
            errori += 1
            if errori >= 3:
                registra("  GDELT: tre errori consecutivi, passo interrotto per questo aggiornamento")
                break
            continue
        righe = pertinenti(nome, righe)
        with con:
            con.executemany("INSERT OR IGNORE INTO notizie VALUES(?,?,?,?,?,'GDELT',?,?)",
                            [(m["ticker"], u, ti, te, p, lingua, db.adesso()) for u, ti, te, p, lingua in righe])
            con.execute("INSERT OR REPLACE INTO gdelt_richieste VALUES(?,?,?,'ok')", (m["ticker"], m["data"], db.adesso()))
        salvati += len(righe)
    return salvati
