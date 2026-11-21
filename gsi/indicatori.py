"""Indicatori tecnici sui prezzi rettificati per i frazionamenti; rendimenti sul total return.

Funzioni pure su liste/array, collaudate senza rete. Finestre in sedute: 21, 63, 126, 252.
"""
from __future__ import annotations
import bisect
from datetime import date

import numpy as np

S1M, S3M, S6M, S12M = 21, 63, 126, 252


def media_mobile(x, n: int, fine: int | None = None):
    """Media semplice delle n chiusure che terminano all'indice `fine` (escluso; None = ultima)."""
    x = np.asarray(x, float)
    fine = len(x) if fine is None else fine
    if fine < n or fine > len(x):
        return None
    return float(x[fine - n:fine].mean())


def ema(x, n: int) -> np.ndarray:
    x = np.asarray(x, float)
    k = 2.0 / (n + 1)
    out = np.empty(len(x))
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(chiusure, n: int = 14):
    """RSI di Wilder. None se lo storico e' insufficiente."""
    c = np.asarray(chiusure, float)
    if len(c) < n + 1:
        return None
    d = np.diff(c)
    su, giu = np.clip(d, 0, None), np.clip(-d, 0, None)
    ms, mg = su[:n].mean(), giu[:n].mean()
    for i in range(n, len(d)):
        ms = (ms * (n - 1) + su[i]) / n
        mg = (mg * (n - 1) + giu[i]) / n
    if mg == 0:
        return 100.0 if ms > 0 else 50.0
    return float(100 - 100 / (1 + ms / mg))


def macd(chiusure, veloce=12, lenta=26, segnale=9):
    """-> (macd, segnale, istogramma, istogramma di 5 sedute fa) oppure None."""
    c = np.asarray(chiusure, float)
    if len(c) < lenta + segnale + 5:
        return None
    linea = ema(c, veloce) - ema(c, lenta)
    seg = ema(linea, segnale)
    isto = linea - seg
    return float(linea[-1]), float(seg[-1]), float(isto[-1]), float(isto[-6])


def atr(massimi, minimi, chiusure, n: int = 14):
    """Average True Range di Wilder."""
    h, l, c = (np.asarray(v, float) for v in (massimi, minimi, chiusure))
    if len(c) < n + 1:
        return None
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    a = tr[:n].mean()
    for i in range(n, len(tr)):
        a = (a * (n - 1) + tr[i]) / n
    return float(a)


def rendimento(x, sedute: int, salta: int = 0):
    """Rendimento tra `sedute` sedute fa e `salta` sedute fa (0 = ultima)."""
    if len(x) < sedute + 1:
        return None
    a, b = x[-1 - sedute], x[-1 - salta]
    return float(b / a - 1) if a and a > 0 else None


def massimi_locali(massimi, ampiezza: int = 5, finestra: int = S12M) -> list[float]:
    """Livelli di resistenza: massimi piu' alti delle `ampiezza` sedute precedenti e successive,
    nelle ultime `finestra` sedute."""
    h = np.asarray(massimi, float)[-finestra:]
    out = []
    for i in range(ampiezza, len(h) - ampiezza):
        if h[i] == h[i - ampiezza:i + ampiezza + 1].max() and h[i] > h[i - ampiezza:i].max():
            out.append(float(h[i]))
    return sorted(set(out))


def valore_al(date_ord: list[str], valori, giorno: str):
    """Ultimo valore con data <= giorno (per allineare indici e cambi alle date del titolo)."""
    i = bisect.bisect_right(date_ord, giorno) - 1
    return valori[i] if i >= 0 else None


def calcola_tecnici(pr: dict, indice: dict | None = None) -> dict:
    """pr: {"data": [...], "max": [...], "min": [...], "chius": [...], "rett": [...], "vol": [...]}
    (serie in ordine di data). indice: {"data": [...], "chius": [...]} dell'indice di riferimento."""
    d, c, tr = pr["data"], np.asarray(pr["chius"], float), np.asarray(pr["rett"], float)
    h, l, v = np.asarray(pr["max"], float), np.asarray(pr["min"], float), np.asarray(pr["vol"], float)
    n = len(c)
    o: dict = {"n_sedute": n, "data_prezzo": d[-1] if n else None, "prezzo": float(c[-1]) if n else None}
    if n < 30:
        return o
    o["mm20"], o["mm50"], o["mm200"] = media_mobile(c, 20), media_mobile(c, 50), media_mobile(c, 200)
    o["mm200_20fa"] = media_mobile(c, 200, n - 20)
    o["rsi"] = rsi(c)
    m = macd(c)
    o["macd"], o["macd_segnale"], o["macd_isto"], o["macd_isto_5fa"] = m if m else (None,) * 4
    o["atr"] = atr(h, l, c)
    o["max20"] = float(h[-20:].max())
    o["max52"] = float(h[-S12M:].max()) if n >= S12M else None
    o["resistenze"] = massimi_locali(h)
    o["r1m"], o["r3m"], o["r6m"] = rendimento(tr, S1M), rendimento(tr, S3M), rendimento(tr, S6M)
    o["r12m_1"] = rendimento(tr, S12M, S1M)
    o["r12m"] = rendimento(tr, S12M)
    # volumi: sedute al rialzo e al ribasso nelle ultime 20
    var = np.diff(c[-21:])
    vv = v[-20:]
    su, giu = float(vv[var > 0].sum()), float(vv[var < 0].sum())
    o["vol_su_giu"] = su / giu if giu > 0 else None
    v20, v60 = float(v[-20:].mean()), float(v[-60:].mean()) if n >= 60 else None
    o["vol_20_60"] = v20 / v60 if v60 else None
    o["controvalore_20"] = float((v[-20:] * c[-20:]).mean())
    if n >= S12M + 1:
        rg = np.diff(np.log(tr[-S12M - 1:]))
        o["volatilita"] = float(rg.std(ddof=1) * np.sqrt(252))
    else:
        o["volatilita"] = None
    # extra-rendimento sull'indice nelle stesse date
    if indice and indice["data"]:
        fine = valore_al(indice["data"], indice["chius"], d[-1])
        for nome, s in (("idx_r3m", S3M), ("idx_r6m", S6M)):
            ini = valore_al(indice["data"], indice["chius"], d[-1 - s]) if n > s else None
            o[nome] = float(fine / ini - 1) if ini and fine else None
    return o


def reazione_utili(pr: dict, indice: dict | None, date_utili: list[str], oggi: str):
    """Reazione anomala all'ultima trimestrale: rendimento del titolo meno quello dell'indice tra la
    chiusura precedente la data di pubblicazione e la chiusura della seduta successiva.
    -> (reazione, data, giorni trascorsi) oppure (None, None, None)."""
    d, tr = pr["data"], pr["rett"]
    passate = sorted(x for x in date_utili if x <= oggi)
    if not passate or not d:
        return None, None, None
    u = passate[-1]
    i = bisect.bisect_left(d, u)             # prima seduta >= data di pubblicazione
    giorni = (date.fromisoformat(oggi) - date.fromisoformat(u)).days
    if i < 1 or i + 1 >= len(d):
        return None, u, giorni
    r = tr[i + 1] / tr[i - 1] - 1
    if indice and indice["data"]:
        a = valore_al(indice["data"], indice["chius"], d[i - 1])
        b = valore_al(indice["data"], indice["chius"], d[i + 1])
        if a and b:
            r -= b / a - 1
    return float(r), u, giorni
