"""Yahoo Finance tramite yfinance (solo uso personale; richieste lente e ripetute con attese crescenti).

Le funzioni `normalizza_*` sono pure (DataFrame/dict -> righe) e collaudate senza rete.
"""
from __future__ import annotations
import json
import math
import time
from datetime import date, timedelta

import pandas as pd

from .. import config

PROSPETTI = {"CE": "get_income_stmt", "SP": "get_balance_sheet", "RF": "get_cash_flow"}
FREQUENZE = {"A": "yearly", "T": "quarterly", "U": "trailing"}   # U non esiste per lo stato patrimoniale

_ultima = 0.0


def _pausa():
    global _ultima
    att = config.PAUSA_YAHOO - (time.monotonic() - _ultima)
    if att > 0:
        time.sleep(att)
    _ultima = time.monotonic()


def con_tentativi(funzione, *a, **k):
    """Esegue una chiamata con pausa, ripetendo con attese crescenti. Solleva l'ultimo errore."""
    ultimo = None
    for i in range(config.TENTATIVI):
        _pausa()
        try:
            return funzione(*a, **k)
        except Exception as e:  # noqa: BLE001 - ogni errore di rete/fonte va ritentato e poi registrato
            ultimo = e
            if i < config.TENTATIVI - 1:
                time.sleep(config.ATTESA_BASE * (3 ** i))
    raise ultimo


def _num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


# ---------------------------------------------------------------- prezzi
def normalizza_storico(df: pd.DataFrame, in_centesimi: bool, meta: dict | None = None) -> list[tuple]:
    """Storico yfinance (auto_adjust=False, actions=True) -> righe per la tabella prezzi.

    Scarta le sedute senza chiusura. Le quotazioni in centesimi (GBp) sono divise per 100,
    dividendi compresi. `Close` di Yahoo e' gia' rettificato per i frazionamenti;
    `Adj Close` anche per i dividendi (total return).

    Per l'ultima seduta di alcune borse europee Yahoo lascia vuota la chiusura finche' non
    consolida l'asta finale: in quel caso (e solo per l'ultima riga) si usa l'ultimo prezzo
    della stessa seduta dichiarato dalla fonte (`regularMarketPrice`), se la data coincide.
    """
    if df is None or len(df) == 0:
        return []
    k = 0.01 if in_centesimi else 1.0
    righe = []
    ultima = df.index[-1]
    for ts, r in df.iterrows():
        ch = _num(r.get("Close"))
        adj = _num(r.get("Adj Close"))
        if ch is None and ts == ultima and meta and _num(r.get("High")) and _num(r.get("Low")):
            pm, tm = _num(meta.get("regularMarketPrice")), meta.get("regularMarketTime")
            try:
                stessa = pd.Timestamp(tm).strftime("%Y-%m-%d") == pd.Timestamp(ts).strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                stessa = False
            if pm and stessa and _num(r["Low"]) * 0.999 <= pm <= _num(r["High"]) * 1.001:
                ch = adj = pm
        if ch is None or ch <= 0:
            continue
        righe.append((
            pd.Timestamp(ts).strftime("%Y-%m-%d"),
            (_num(r.get("Open")) or ch) * k, (_num(r.get("High")) or ch) * k,
            (_num(r.get("Low")) or ch) * k, ch * k, (adj if adj is not None else ch) * k,
            _num(r.get("Volume")) or 0.0,
            (_num(r.get("Dividends")) or 0.0) * k, _num(r.get("Stock Splits")) or 0.0))
    return righe


def scarica_storico(tk, inizio: date | None = None):
    inizio = inizio or (date.today() - timedelta(days=int(365.25 * config.ANNI_STORICO) + 5))
    df = con_tentativi(tk.history, start=inizio.isoformat(), interval="1d",
                       auto_adjust=False, actions=True, raise_errors=True)
    meta = {}
    try:
        meta = tk.get_history_metadata() or {}
    except Exception:  # noqa: BLE001
        pass
    return df, meta


# ---------------------------------------------------------------- bilanci
def normalizza_prospetto(df: pd.DataFrame) -> list[tuple]:
    """Prospetto yfinance (righe = voci, colonne = date di chiusura) -> (data, voce, valore)."""
    if df is None or len(df) == 0:
        return []
    righe = []
    for col in df.columns:
        d = pd.Timestamp(col).strftime("%Y-%m-%d")
        for voce, v in df[col].items():
            f = _num(v)
            if f is not None:
                righe.append((d, str(voce), f))
    return righe


def scarica_prospetto(tk, prospetto: str, frequenza: str) -> list[tuple]:
    df = con_tentativi(getattr(tk, PROSPETTI[prospetto]), freq=FREQUENZE[frequenza])
    return normalizza_prospetto(df)


# ---------------------------------------------------------------- anagrafica
def normalizza_anagrafica(info: dict, meta: dict | None = None) -> dict:
    meta = meta or {}
    g = info.get
    tenute = {k: v for k, v in info.items()
              if isinstance(v, (int, float, str, bool)) and k not in ("longBusinessSummary",)}
    return {
        "tipo": g("quoteType") or meta.get("instrumentType"),
        "nome_fonte": g("longName") or g("shortName") or meta.get("longName") or meta.get("shortName"),
        "valuta_fonte": g("currency") or meta.get("currency"),
        "valuta_bilancio_fonte": g("financialCurrency"),
        "borsa": g("fullExchangeName") or meta.get("fullExchangeName") or g("exchange"),
        "paese": g("country"), "settore_fonte": g("sector"), "industria_fonte": g("industry"),
        "capitalizzazione": _num(g("marketCap")),
        "prezzo_fonte": _num(g("regularMarketPrice") or g("currentPrice")),
        "azioni_fonte": _num(g("sharesOutstanding")), "beta": _num(g("beta")),
        "eps_atteso": _num(g("forwardEps")), "eps_storico": _num(g("trailingEps")),
        "json": json.dumps(tenute, ensure_ascii=False, default=str),
    }


def scarica_anagrafica(tk, meta=None) -> dict:
    info = con_tentativi(tk.get_info) or {}
    if not info.get("quoteType") and not info.get("regularMarketPrice") and not meta:
        raise RuntimeError("anagrafica vuota")
    return normalizza_anagrafica(info, meta)


# ---------------------------------------------------------------- utili, revisioni, notizie
def normalizza_date_utili(df: pd.DataFrame) -> list[tuple]:
    if df is None or len(df) == 0:
        return []
    righe = {}
    for ts, r in df.iterrows():
        t = pd.Timestamp(ts)
        righe[t.strftime("%Y-%m-%d")] = (t.strftime("%Y-%m-%d"), t.strftime("%H:%M"),
                                          _num(r.get("EPS Estimate")), _num(r.get("Reported EPS")),
                                          _num(r.get("Surprise(%)")))
    return sorted(righe.values())


def normalizza_revisioni(df: pd.DataFrame) -> list[tuple]:
    if df is None or len(df) == 0:
        return []
    col = {c.lower(): c for c in df.columns}
    def v(r, nome):
        return _num(r.get(col.get(nome.lower())))
    return [(str(p), v(r, "upLast7days"), v(r, "upLast30days"), v(r, "downLast7days"), v(r, "downLast30days"))
            for p, r in df.iterrows()]


def normalizza_stime(df: pd.DataFrame) -> list[tuple]:
    """Stime di consenso sull'utile per azione -> (periodo, media, minimo, massimo, eps anno prima,
    numero di analisti, valuta, metodo). Periodi: 0q, +1q, 0y (esercizio in corso), +1y (successivo)."""
    if df is None or len(df) == 0:
        return []
    righe = []
    for p, r in df.iterrows():
        if _num(r.get("avg")) is None:
            continue
        righe.append((str(p), _num(r.get("avg")), _num(r.get("low")), _num(r.get("high")),
                      _num(r.get("yearAgoEps")), _num(r.get("numberOfAnalysts")),
                      r.get("currency") if isinstance(r.get("currency"), str) else None,
                      r.get("methodology") if isinstance(r.get("methodology"), str) else None))
    return righe


def scarica_stime(tk):
    return normalizza_stime(con_tentativi(tk.get_earnings_estimate))


def normalizza_notizie(lista: list) -> list[tuple]:
    """Notizie yfinance -> (url, titolo, testata, pubblicato). Solo titolo e link: nessun riassunto."""
    righe = []
    for n in lista or []:
        c = n.get("content") if isinstance(n, dict) and isinstance(n.get("content"), dict) else n
        if not isinstance(c, dict):
            continue
        url = ((c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url")
               or c.get("link"))
        titolo = c.get("title")
        if not url or not titolo:
            continue
        testata = (c.get("provider") or {}).get("displayName") or c.get("publisher")
        pub = c.get("pubDate") or c.get("displayTime")
        if pub is None and c.get("providerPublishTime"):
            pub = pd.Timestamp(c["providerPublishTime"], unit="s", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        righe.append((url, titolo.strip(), testata, pub))
    return righe


def scarica_date_utili(tk):
    return normalizza_date_utili(con_tentativi(tk.get_earnings_dates, limit=16))


def scarica_revisioni(tk):
    return normalizza_revisioni(con_tentativi(tk.get_eps_revisions))


def scarica_notizie(tk):
    return normalizza_notizie(con_tentativi(tk.get_news, count=15))
