"""Backtest della sola strategia B (Trading Score), senza sguardo al futuro.

A ogni data di rilevazione (una ogni 21 sedute) il punteggio di ogni titolo e' ricalcolato usando solo i
prezzi fino a quella data; poi si misura che cosa e' successo nelle 21 e 63 sedute successive.

Limiti dichiarati:
- distorsione da sopravvivenza: l'universo e' quello di oggi (societa' fallite, delistate o uscite non ci sono);
- il pilastro Catalizzatori non e' ricostruibile nel passato (revisioni e date degli utili storiche non
  disponibili): il punteggio storico usa gli altri sei pilastri (95% del peso);
- nessun costo di negoziazione, nessuna imposta, nessuno slittamento oltre alle regole indicate;
- le finestre a 63 sedute rilevate ogni 21 si sovrappongono: le osservazioni non sono indipendenti.
Per la strategia A il backtest non viene fatto: mancano i bilanci "come erano noti allora".
"""
from __future__ import annotations
import bisect
import json
import statistics
from datetime import date

from . import db, indicatori, punteggi

PASSO = 21
FINESTRA = 520                 # sedute di storico usate per gli indicatori a ogni data
ORIZZONTI = (21, 63)
FASCE = [(None, 40, "sotto 40"), (40, 55, "40 - 55"), (55, 65, "55 - 65"), (65, 75, "65 - 75"), (75, None, "75 e oltre")]
ATTESA_ROTTURA = 5             # sedute entro cui la rottura deve scattare
DURATA_MASSIMA = 63            # sedute dopo le quali la posizione si chiude al prezzo di chiusura
MIN_OSSERVAZIONI = 100         # sotto questa numerosita' la frequenza storica non viene mostrata


def carica_serie(con, ticker: str) -> dict:
    r = con.execute("SELECT data, apertura, massimo, minimo, chiusura, chiusura_rett, volume FROM prezzi "
                    "WHERE ticker=? ORDER BY data", (ticker,)).fetchall()
    return {"data": [x[0] for x in r], "ap": [x[1] for x in r], "max": [x[2] for x in r], "min": [x[3] for x in r],
            "chius": [x[4] for x in r], "rett": [x[5] for x in r], "vol": [x[6] for x in r]}


def simula_setup(s: dict, i: int, setup: dict) -> dict | None:
    """Esito di un setup rilevato alla chiusura della seduta i (dati successivi usati solo per l'esito).
    Rottura: ordine di acquisto al livello d'ingresso, valido 5 sedute (se l'apertura e' gia' sopra, si
    entra all'apertura). Ritracciamento: ingresso all'apertura successiva. Se nella stessa seduta sono
    toccati sia lo stop sia l'obiettivo si assume lo stop. Stop in apertura sotto il livello: esce all'apertura."""
    n = len(s["chius"])
    rischio = setup["ingresso"] - setup["stop"]
    if rischio <= 0 or i + 1 >= n:
        return None
    if setup["tipo"] == "Rottura":
        j = next((k for k in range(i + 1, min(i + 1 + ATTESA_ROTTURA, n)) if s["max"][k] >= setup["ingresso"]), None)
        if j is None:
            return {"esito": "non eseguito"}
        ingresso = max(setup["ingresso"], s["ap"][j])
    else:
        j, ingresso = i + 1, s["ap"][i + 1]
    stop, obiettivo = setup["stop"], setup["obiettivo"]
    if ingresso <= stop or ingresso >= obiettivo:
        return {"esito": "non eseguito"}
    fine = min(j + DURATA_MASSIMA, n - 1)
    for k in range(j, fine + 1):
        if s["min"][k] <= stop:
            uscita, esito = (min(stop, s["ap"][k]) if k > j else stop), "stop"
            break
        if s["max"][k] >= obiettivo:
            uscita, esito = obiettivo, "obiettivo"
            break
    else:
        if fine - j < DURATA_MASSIMA and fine == n - 1:
            return {"esito": "in corso"}                 # storico finito prima dell'esito: non contato
        uscita, esito = s["chius"][fine], "tempo"
    return {"esito": esito, "r": (uscita - ingresso) / rischio, "rendimento": uscita / ingresso - 1, "sedute": k - j if esito != "tempo" else fine - j}


def _fascia(p: float) -> str:
    for lo, hi, nome in FASCE:
        if (lo is None or p >= lo) and (hi is None or p < hi):
            return nome
    return FASCE[-1][2]


def _sintesi(v: list[float]) -> dict:
    if not v:
        return {"n": 0}
    return {"n": len(v), "media": statistics.fmean(v), "mediana": statistics.median(v),
            "positivi": sum(1 for x in v if x > 0) / len(v)}


def esegui(con, universo: list, P: dict, registra=print, salva: bool = True) -> dict:
    serie = {t.ticker: carica_serie(con, t.ticker) for t in universo}
    indici = {}
    for k in {t.indice for t in universo}:
        s = carica_serie(con, k)
        indici[k] = {"data": s["data"], "chius": s["chius"]}
    calendario = max((s["data"] for s in indici.values()), key=len, default=[])
    if len(calendario) < 400:
        raise RuntimeError("storico insufficiente per il backtest")
    date_ril = calendario[300:len(calendario) - PASSO:PASSO]
    oss = []                       # (data, ticker, punteggio, {orizzonte: rendimento})
    operazioni = []
    for n_d, D in enumerate(date_ril):
        tec, pos = {}, {}
        for t in universo:
            s = serie[t.ticker]
            i = bisect.bisect_right(s["data"], D) - 1
            if i < 260 or (date.fromisoformat(D) - date.fromisoformat(s["data"][i])).days > 7:
                continue
            a = max(0, i + 1 - FINESTRA)
            pr = {k: s[k][a:i + 1] for k in ("data", "max", "min", "chius", "rett", "vol")}
            x = indicatori.calcola_tecnici(pr, indici.get(t.indice))
            x["resistenze"] = [v for v in x.get("resistenze") or [] if v > x["prezzo"]][:12]
            x.update(settore=t.settore, cambio_eur=1.0)
            tec[t.ticker], pos[t.ticker] = x, i
        ris = punteggi.trading_universo(tec, P)
        for tk, b in ris.items():
            if b["punteggio"] is None:
                continue
            s, i = serie[tk], pos[tk]
            fwd = {h: (s["rett"][i + h] / s["rett"][i] - 1 if i + h < len(s["rett"]) else None) for h in ORIZZONTI}
            oss.append((D, tk, b["punteggio"], fwd))
            if b["segnale"] == "Setup attivo":
                e = simula_setup(s, i, b["setup"])
                if e:
                    e.update(data=D, ticker=tk, tipo=b["setup"]["tipo"])
                    operazioni.append(e)
        if n_d % 20 == 0:
            registra(f"  backtest: {D} ({n_d + 1}/{len(date_ril)})")
    # --- rendimenti per fascia di punteggio, assoluti e rispetto alla media dell'universo alla stessa data
    out = {"eseguito": db.adesso(), "dal": date_ril[0], "al": date_ril[-1], "rilevazioni": len(date_ril),
           "titoli": len(universo), "osservazioni": len(oss), "fasce": {}, "min_osservazioni": MIN_OSSERVAZIONI}
    for h in ORIZZONTI:
        medie: dict[str, list] = {}
        for D, _, _, f in oss:
            if f[h] is not None:
                medie.setdefault(D, []).append(f[h])
        medie_d = {D: statistics.fmean(v) for D, v in medie.items()}
        per: dict[str, list] = {n: [] for _, _, n in FASCE}
        extra: dict[str, list] = {n: [] for _, _, n in FASCE}
        for D, _, p, f in oss:
            if f[h] is not None:
                per[_fascia(p)].append(f[h])
                extra[_fascia(p)].append(f[h] - medie_d[D])
        out["fasce"][str(h)] = {n: {**_sintesi(per[n]), "extra_media": statistics.fmean(extra[n]) if extra[n] else None}
                                for _, _, n in FASCE}
        tutti = [f[h] for _, _, _, f in oss if f[h] is not None]
        out["fasce"][str(h)]["tutti"] = _sintesi(tutti)
    chiuse = [o for o in operazioni if o["esito"] in ("stop", "obiettivo", "tempo")]
    out["setup"] = {"segnali": len(operazioni), "non_eseguiti": sum(1 for o in operazioni if o["esito"] == "non eseguito"),
                    "in_corso": sum(1 for o in operazioni if o["esito"] == "in corso"), "chiuse": len(chiuse), "per_tipo": {}}
    for tipo in ("Tutti", "Rottura", "Ritracciamento"):
        v = [o for o in chiuse if tipo == "Tutti" or o["tipo"] == tipo]
        if not v:
            out["setup"]["per_tipo"][tipo] = {"n": 0}
            continue
        out["setup"]["per_tipo"][tipo] = {
            "n": len(v), "obiettivo": sum(1 for o in v if o["esito"] == "obiettivo") / len(v),
            "stop": sum(1 for o in v if o["esito"] == "stop") / len(v),
            "tempo": sum(1 for o in v if o["esito"] == "tempo") / len(v),
            "r_medio": statistics.fmean(o["r"] for o in v), "rendimento_medio": statistics.fmean(o["rendimento"] for o in v),
            "sedute_medie": statistics.fmean(o["sedute"] for o in v)}
    if salva:
        con.execute("INSERT OR REPLACE INTO meta VALUES('backtest', ?)", (json.dumps(out),))
        con.commit()
    return out


def leggi(con) -> dict | None:
    r = con.execute("SELECT valore FROM meta WHERE chiave='backtest'").fetchone()
    return json.loads(r[0]) if r else None


def stampa(b: dict) -> None:
    print(f"Backtest della strategia B dal {b['dal']} al {b['al']}: {b['rilevazioni']} rilevazioni, "
          f"{b['titoli']} titoli, {b['osservazioni']} osservazioni.")
    for h, fasce in b["fasce"].items():
        print(f"  Rendimento nelle {h} sedute successive, per fascia di Trading Score:")
        for nome, s in fasce.items():
            if s.get("n"):
                ex = f"  extra sulla media {100 * s['extra_media']:+.2f}%" if s.get("extra_media") is not None else ""
                print(f"    {nome:11s} n={s['n']:5d}  media {100 * s['media']:+.2f}%  mediana {100 * s['mediana']:+.2f}%  "
                      f"positivi {100 * s['positivi']:.0f}%{ex}")
    st = b["setup"]
    print(f"  Setup: {st['segnali']} segnali, {st['non_eseguiti']} non eseguiti, {st['chiuse']} operazioni chiuse.")
    for tipo, s in st["per_tipo"].items():
        if s.get("n"):
            freq = (f"obiettivo {100 * s['obiettivo']:.0f}%, stop {100 * s['stop']:.0f}%, a tempo {100 * s['tempo']:.0f}%"
                    if s["n"] >= MIN_OSSERVAZIONI else f"frequenze non mostrate (meno di {MIN_OSSERVAZIONI} osservazioni)")
            print(f"    {tipo:15s} n={s['n']:4d}  {freq}  R medio {s['r_medio']:+.2f}")
    print("  Distorsione da sopravvivenza: l'universo è quello di oggi. Risultati passati, non previsioni.")
