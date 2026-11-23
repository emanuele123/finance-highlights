"""Dati per il foglio PORTAFOGLIO: rendimenti settimanali in euro a 3 anni, volatilita', matrice di
correlazione e beta rispetto al mercato mondiale. Funzioni pure dove possibile."""
from __future__ import annotations
import bisect
import math
from datetime import date, timedelta

import numpy as np

ANNI = 3
MIN_SETTIMANE = 52


def settimanali(date_: list[str], valori: list[float]) -> dict[tuple, float]:
    """Ultimo valore di ogni settimana ISO. -> {(anno, settimana): valore}"""
    out = {}
    for d, v in zip(date_, valori):
        a, s, _ = date.fromisoformat(d).isocalendar()
        out[(a, s)] = v
    return out


def serie_eur(con, ticker: str, valuta: str, dal: str) -> dict[tuple, float]:
    """Chiusure rettificate (total return) convertite in euro, una per settimana."""
    r = con.execute("SELECT data, chiusura_rett FROM prezzi WHERE ticker=? AND data>=? ORDER BY data", (ticker, dal)).fetchall()
    if valuta == "EUR":
        return settimanali([x[0] for x in r], [x[1] for x in r])
    fx = con.execute("SELECT data, tasso FROM cambi WHERE valuta=? ORDER BY data", (valuta,)).fetchall()
    fd, fv = [x[0] for x in fx], [x[1] for x in fx]
    d, v = [], []
    for g, p in r:
        j = bisect.bisect_right(fd, g) - 1
        if j >= 0 and fv[j]:
            d.append(g)
            v.append(p / fv[j])
    return settimanali(d, v)


def rendimenti(serie: dict[tuple, float], settimane: list[tuple]) -> np.ndarray:
    """Rendimenti settimanali sulle settimane date (NaN dove manca un estremo)."""
    liv = np.array([serie.get(s, np.nan) for s in settimane], float)
    return liv[1:] / liv[:-1] - 1


def statistiche(con, universo: list, mercato: str | None, valuta_mercato: str = "EUR", anni: int = ANNI,
                 extra: list[tuple[str, str]] | None = None) -> dict:
    """-> {"tickers", "vol": {tk: volatilita' annua}, "beta": {tk: beta}, "corr": matrice (None dove non stimabile)}
    extra: strumenti aggiunti in coda alla matrice, come (ticker, valuta) (es. il fondo di riferimento)."""
    from types import SimpleNamespace
    universo = list(universo) + [SimpleNamespace(ticker=k, valuta=v) for k, v in (extra or [])]
    fine = con.execute("SELECT MAX(data) FROM prezzi").fetchone()[0]
    tickers = [t.ticker for t in universo]
    if not fine:
        return {"tickers": tickers, "vol": {}, "beta": {}, "corr": [[None] * len(tickers) for _ in tickers]}
    dal = (date.fromisoformat(fine) - timedelta(days=int(365.25 * anni) + 7)).isoformat()
    serie = {t.ticker: serie_eur(con, t.ticker, t.valuta, dal) for t in universo}
    sm = serie_eur(con, mercato, valuta_mercato, dal) if mercato else {}
    settimane = sorted(set().union(*[set(s) for s in serie.values()], set(sm)))
    R = {tk: rendimenti(s, settimane) for tk, s in serie.items()}
    rm = rendimenti(sm, settimane) if sm else None
    vol, beta = {}, {}
    for tk, r in R.items():
        ok = ~np.isnan(r)
        vol[tk] = float(np.std(r[ok], ddof=1) * math.sqrt(52)) if ok.sum() >= MIN_SETTIMANE else None
        beta[tk] = None
        if rm is not None:
            ok2 = ok & ~np.isnan(rm)
            if ok2.sum() >= MIN_SETTIMANE and np.var(rm[ok2]) > 0:
                beta[tk] = float(np.cov(r[ok2], rm[ok2], ddof=1)[0, 1] / np.var(rm[ok2], ddof=1))
    n = len(tickers)
    corr = [[None] * n for _ in range(n)]
    for i, a in enumerate(tickers):
        for j in range(i, n):
            b = tickers[j]
            ok = ~np.isnan(R[a]) & ~np.isnan(R[b])
            if ok.sum() >= MIN_SETTIMANE and np.std(R[a][ok]) > 0 and np.std(R[b][ok]) > 0:
                c = 1.0 if i == j else float(np.corrcoef(R[a][ok], R[b][ok])[0, 1])
                corr[i][j] = corr[j][i] = c
    return {"tickers": tickers, "vol": vol, "beta": beta, "corr": corr}


def volatilita_portafoglio(pesi: list[float], vol: list[float], corr: list[list[float]]) -> float:
    """Radice di somma_i somma_j w_i w_j s_i s_j rho_ij (la liquidita' ha peso senza volatilita')."""
    w, s, c = np.asarray(pesi, float), np.asarray(vol, float), np.asarray(corr, float)
    return float(math.sqrt(max(0.0, (w * s) @ c @ (w * s))))



# ------------------------------------------------------------------ fondo di riferimento e confronto
def info_fondo(con, ticker: str, ingressi: dict, stat: dict, simboli: dict) -> dict:
    """Dati del fondo di riferimento e peso stimato nel fondo di ogni titolo dell'universo.

    Peso stimato = capitalizzazione in euro / capitalizzazione totale stimata dell'indice. La capitalizzazione
    totale e' calibrata sui primi titoli dichiarati dal fondo (mediana di capitalizzazione / peso): ignora il
    flottante e le restrizioni per gli stranieri, quindi e' una stima, aggiornata ai prezzi di oggi."""
    righe = con.execute("SELECT tipo, chiave, nome, valore FROM fondi WHERE ticker=?", (ticker,)).fetchall()
    primi = [(r[1], r[2], r[3]) for r in righe if r[0] == "primi"]
    settori = {r[1]: r[3] for r in righe if r[0] == "settore"}
    pe = next((r[3] for r in righe if r[0] == "valutazione" and r[1] == "pe"), None)
    p = con.execute("SELECT data, chiusura FROM prezzi WHERE ticker=? ORDER BY data DESC LIMIT 1", (ticker,)).fetchone()
    per_tk: dict[str, float] = {}
    for sim, _nome, w in primi:
        tk = simboli.get(sim, sim)
        if tk in ingressi:
            per_tk[tk] = per_tk.get(tk, 0.0) + w
    rapporti = sorted(ingressi[tk]["capitalizzazione_eur"] / w for tk, w in per_tk.items()
                      if w > 0 and ingressi[tk].get("capitalizzazione_eur"))
    totale = rapporti[len(rapporti) // 2] if len(rapporti) % 2 else (
        (rapporti[len(rapporti) // 2 - 1] + rapporti[len(rapporti) // 2]) / 2 if rapporti else None)
    idx = stat["tickers"].index(ticker) if ticker in stat["tickers"] else None
    for tk, i in ingressi.items():
        i["peso_etf"] = i["capitalizzazione_eur"] / totale if totale and i.get("capitalizzazione_eur") else None
        j = stat["tickers"].index(tk) if tk in stat["tickers"] else None
        c = stat["corr"][j][idx] if idx is not None and j is not None else None
        i["corr_etf"] = round(c, 4) if c is not None else None
    return {"ticker": ticker, "prezzo": p[1] if p else None, "data": p[0] if p else None, "pe": pe,
            "vol": stat["vol"].get(ticker), "beta": stat["beta"].get(ticker), "settori": settori,
            "primi": [(sim, nome, w, per_tk.get(simboli.get(sim, sim))) for sim, nome, w in primi],
            "cap_totale": totale, "n_calibrazione": len(rapporti)}


def confronto(ingressi: dict, fondo: dict, stat: dict, posizioni: list[tuple[str, float]], valore_fondo: float,
              liquidita: float, importo, commissione, nuovi_soldi: bool) -> dict:
    """Replica in Python dei fogli PORTAFOGLIO (rischio con il fondo) e CONFRONTO.

    posizioni: (ticker, controvalore in euro). Varianza in euro^2: sum_ij x_i s_i x_j s_j rho_ij sui titoli e sul fondo,
    con le correlazioni arrotondate a 4 decimali come nel foglio CORRELAZIONI e 0 dove non stimabili."""
    tk = stat["tickers"]
    corr = [[round(c, 4) if c is not None else 0.0 for c in riga] for riga in stat["corr"]]
    sig = {t: (ingressi[t].get("vol_3a_eur") if t in ingressi else fondo.get("vol")) for t in tk}
    x = {t: 0.0 for t in tk}
    for t, e in posizioni:
        x[t] = x.get(t, 0.0) + e
    if fondo["ticker"] in x:
        x[fondo["ticker"]] += valore_fondo
    v = [x[t] * sig[t] if sig[t] is not None else 0.0 for t in tk]
    cv = {t: sum(corr[i][j] * v[j] for j in range(len(tk))) for i, t in enumerate(tk)}
    s2 = sum(v[i] * cv[t] for i, t in enumerate(tk))
    tot = sum(e for _, e in posizioni) + liquidita + valore_fondo
    out = {"totale": tot, "s2": s2, "vol": (max(0.0, s2) ** 0.5 / tot) if tot > 0 else None, "righe": {}}
    ok = isinstance(importo, (int, float)) and importo > 0
    tn = tot + (importo if (nuovi_soldi and ok) else 0.0)
    sf = fondo.get("vol")

    def vol_dopo(s, c):
        return (max(0.0, s2 + 2 * importo * s * c + importo ** 2 * s ** 2) ** 0.5) / tn if ok and tn > 0 else None
    out["vol_fondo_dopo"] = vol_dopo(sf, cv.get(fondo["ticker"], 0.0)) if sf is not None and fondo["ticker"] in cv else None
    for t, i in ingressi.items():
        diretto = sum(e for tt, e in posizioni if tt == t)
        eff = diretto + valore_fondo * (i.get("peso_etf") or 0.0)
        s = i.get("vol_3a_eur")
        vd = vol_dopo(s, cv.get(t, 0.0)) if s is not None else None
        r = {"diretto": diretto, "eff": eff, "eff_pct": eff / tot if tot > 0 else None,
             "eff_dopo": (eff + importo) / tn if ok and tn > 0 else None, "vol_dopo": vd,
             "diff": vd - out["vol_fondo_dopo"] if vd is not None and out["vol_fondo_dopo"] is not None else None,
             "comm": commissione / importo if ok and isinstance(commissione, (int, float)) else None}
        out["righe"][t] = r
    return out
