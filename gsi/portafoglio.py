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


def statistiche(con, universo: list, mercato: str | None, valuta_mercato: str = "EUR", anni: int = ANNI) -> dict:
    """-> {"tickers", "vol": {tk: volatilita' annua}, "beta": {tk: beta}, "corr": matrice (None dove non stimabile)}"""
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
