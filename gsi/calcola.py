"""Dall'archivio agli ingressi dei punteggi (i dati che finiranno nel foglio DATI) e ai risultati."""
from __future__ import annotations
import csv
from datetime import date

from . import bilanci, config, db, indicatori, punteggi
from .controlli import valuta_unita
from .parametri import predefiniti
from .universo import INDICI, UNIVERSO, VALUTA_BILANCIO_VERIFICATA


def cambio(con, valuta: str, giorno: str | None = None):
    """Unita' di valuta per 1 euro all'ultima data disponibile (<= giorno)."""
    if valuta == "EUR":
        return 1.0
    r = con.execute("SELECT tasso FROM cambi WHERE valuta=? AND data<=? ORDER BY data DESC LIMIT 1",
                    (valuta, giorno or "9999")).fetchone()
    return r[0] if r else None


N_RESISTENZE = 12
ORIZZONTI = (("1m", 21), ("3m", 63), ("6m", 126), ("1a", 252), ("5a", 1260), ("10a", 2520))


def fq_serie(con, valuta: str):
    if valuta == "EUR":
        return None
    r = con.execute("SELECT data, tasso FROM cambi WHERE valuta=? ORDER BY data", (valuta,)).fetchall()
    return [x[0] for x in r], [x[1] for x in r]


def performance(con, pr: dict, fx) -> dict:
    """Rendimenti a 1, 3, 6 mesi, 1, 5, 10 anni (in sedute): prezzo, total return, total return in euro."""
    o = {}
    d, c, tr = pr["data"], pr["chius"], pr["rett"]
    for nome, s in ORIZZONTI:
        ok = len(c) > s
        o[f"pp_{nome}"] = c[-1] / c[-1 - s] - 1 if ok and c[-1 - s] > 0 else None
        o[f"pt_{nome}"] = tr[-1] / tr[-1 - s] - 1 if ok and tr[-1 - s] > 0 else None
        if not ok or o[f"pt_{nome}"] is None:
            o[f"pe_{nome}"] = None
        elif fx is None:
            o[f"pe_{nome}"] = o[f"pt_{nome}"]
        else:
            a, b = indicatori.valore_al(fx[0], fx[1], d[-1 - s]), indicatori.valore_al(fx[0], fx[1], d[-1])
            o[f"pe_{nome}"] = (1 + o[f"pt_{nome}"]) * a / b - 1 if a and b else None
    return o


def serie_prezzi(con, ticker: str) -> dict:
    r = con.execute("SELECT data, massimo, minimo, chiusura, chiusura_rett, volume FROM prezzi "
                    "WHERE ticker=? ORDER BY data", (ticker,)).fetchall()
    return {"data": [x[0] for x in r], "max": [x[1] for x in r], "min": [x[2] for x in r],
            "chius": [x[3] for x in r], "rett": [x[4] for x in r], "vol": [x[5] for x in r]}


def ingressi_titolo(con, t, oggi: date, indice: dict | None) -> dict:
    """Tutti i dati importati/derivati di un titolo, indipendenti dai parametri."""
    ana = con.execute("SELECT * FROM anagrafica WHERE ticker=?", (t.ticker,)).fetchone()
    q = con.execute("SELECT stato, motivi FROM qualita WHERE ticker=?", (t.ticker,)).fetchone()
    ing: dict = {"ticker": t.ticker, "nome": t.nome, "area": t.area, "settore": t.settore, "modello": t.modello,
                 "valuta": t.valuta, "indice": t.indice, "stato_dati": q["stato"] if q else "ERRORE",
                 "motivi_dati": q["motivi"] if q else "nessun dato", "note": []}
    # valuta di bilancio: quella della fonte, salvo correzione verificata
    vb = (ana["valuta_bilancio_fonte"] if ana else None) or t.valuta_bilancio
    if t.ticker in VALUTA_BILANCIO_VERIFICATA:
        vb = VALUTA_BILANCIO_VERIFICATA[t.ticker][0]
    ing["valuta_bil"] = vb
    fq, fb = cambio(con, t.valuta), cambio(con, vb)
    ing["cambio_eur"], ing["cambio_bil_eur"] = fq, fb
    k = fq / fb if fq and fb else None             # da valuta di bilancio a valuta di quotazione
    ing["k_bil_quot"] = k

    # ---- prezzi e indicatori tecnici
    pr = serie_prezzi(con, t.ticker)
    ing.update(indicatori.calcola_tecnici(pr, indice))
    prezzo = ing.get("prezzo")
    ing["eta_prezzo"] = (oggi - date.fromisoformat(ing["data_prezzo"])).days if ing.get("data_prezzo") else None
    # resistenze: al piu' 12 livelli sopra il prezzo, in ordine crescente (sono quelle scritte nel foglio DATI)
    if prezzo is not None:
        ing["resistenze"] = [x for x in ing.get("resistenze") or [] if x > prezzo][:N_RESISTENZE]
    ing.update(performance(con, pr, fq_serie(con, t.valuta)))
    du = con.execute("SELECT data, eps_reale FROM date_utili WHERE ticker=? ORDER BY data", (t.ticker,)).fetchall()
    oggi_s = oggi.isoformat()
    ing["reazione_utili"], ing["data_utili"], ing["giorni_da_utili"] = indicatori.reazione_utili(
        pr, indice, [x[0] for x in du if x[1] is not None], oggi_s)
    future = [x[0] for x in du if x[0] >= oggi_s]
    ing["prossimi_utili"] = min(future) if future else None
    ing["giorni_a_utili"] = (date.fromisoformat(min(future)) - oggi).days if future else None
    rv = con.execute("SELECT su_30g, giu_30g FROM revisioni WHERE ticker=? AND periodo='0y'", (t.ticker,)).fetchone()
    ing["rev_su30"], ing["rev_giu30"] = (rv[0], rv[1]) if rv else (None, None)

    # ---- azioni = capitalizzazione / prezzo della fonte (cosi' ADR e classi multiple tornano)
    azioni = None
    if ana and ana["capitalizzazione"] and ana["prezzo_fonte"]:
        _, cent = valuta_unita(ana["valuta_fonte"])
        azioni = ana["capitalizzazione"] / (ana["prezzo_fonte"] / (100.0 if cent else 1.0))
    ing["azioni"] = azioni
    ing["capitalizzazione"] = azioni * prezzo if azioni and prezzo else None
    ing["capitalizzazione_eur"] = ing["capitalizzazione"] / fq if ing["capitalizzazione"] and fq else None
    ing["controvalore_eur"] = ing["controvalore_20"] / fq if ing.get("controvalore_20") and fq else None
    ing["beta_fonte"] = ana["beta"] if ana else None

    # ---- bilanci
    anni, note = bilanci.carica_esercizi(con, t.ticker)
    ing["note"] += note
    if k:
        bilanci.dividendi_da_prezzi(con, t.ticker, anni, 1.0 / k)
        if any(a.get("dividendi_stimati") for a in anni):
            ing["note"].append("dividendi pagati stimati dai dividendi per azione (assenti nel rendiconto della fonte)")
    fraz = [(r[0], r[1]) for r in con.execute(
        "SELECT data, frazionamento FROM prezzi WHERE ticker=? AND frazionamento<>0 ORDER BY data", (t.ticker,))]
    f = bilanci.calcola_fondamentali(anni, t.modello, fraz)
    ing["note"] += f.pop("note", [])
    ing.update(f)
    ue = ing.get("ultimo_esercizio")
    ing["eta_esercizio"] = (oggi - date.fromisoformat(ue)).days if ue else None
    if t.modello in ("STD", "CIC") and not ing.get("sbc_disponibile"):
        ing["note"].append("compensi in azioni non riportati dalla fonte: non dedotti dal flusso")

    def per_azione(x):
        return x * k / azioni if x is not None and k and azioni else None
    ing["flusso_ps"] = per_azione(ing.get("flusso_norm"))
    ing["cassa_netta_ps"] = per_azione(ing.get("cassa_netta"))
    ing["tbv_ps"] = per_azione(ing.get("tbv"))
    ing["debito_netto_q"] = ing["debito_netto"] * k if ing.get("debito_netto") is not None and k else None
    ing["ebitda_q"] = ing["ebitda"] * k if ing.get("ebitda") is not None and k else None

    # ---- utile per azione atteso dal consenso, riportato alla valuta di quotazione e alle azioni di oggi
    stime = {r["periodo"]: dict(r) for r in con.execute("SELECT * FROM stime_utili WHERE ticker=?", (t.ticker,))}
    ing["_cambi"] = {v: cambio(con, v) for v in {valuta_unita(r["valuta"])[0] for r in stime.values()} if v}
    ing["eps_atteso"] = eps_atteso(t, ing, stime, fraz, oggi)
    del ing["_cambi"]
    return ing


def eps_atteso(t, ing: dict, stime: dict, fraz: list, oggi: date):
    """EPS atteso dal consenso (esercizio successivo, altrimenti quello in corso), riportato alla valuta
    di quotazione con la valuta dichiarata dalla fonte. Se negli ultimi 12 mesi c'e' stato un
    frazionamento e l'EPS dell'anno prima riportato nelle stime e' fuori scala proprio di quel fattore
    rispetto all'utile per azione corrente, la stima si divide per il fattore (nota)."""
    riga = stime.get("+1y") or stime.get("0y")
    if not riga or not riga["media"] or riga["media"] <= 0:
        return None
    ing["eps_atteso_periodo"] = riga["periodo"]
    val, cent = valuta_unita(riga["valuta"] or t.valuta)
    fe = riga["media"] / (100.0 if cent else 1.0)
    fx_s, fx_q = ing.get("_cambi", {}).get(val), ing.get("cambio_eur")
    if val != t.valuta:
        if not fx_s or not fx_q:
            return None
        fe *= fx_q / fx_s
    k, az = ing.get("k_bil_quot"), ing.get("azioni")
    base = ing["utile_ultimo"] * k / az if ing.get("utile_ultimo") and k and az else None
    prima = (stime.get("0y") or {}).get("eps_anno_prima")
    if base and base > 0 and prima and prima > 0:
        rapporto = prima / (100.0 if cent else 1.0) * (fx_q / fx_s if val != t.valuta else 1.0) / base
        for d, f in fraz:
            if abs(f - 1) > 0.3 and (oggi - date.fromisoformat(d)).days <= 365 \
                    and not 0.6 <= rapporto <= 1.6 and 0.6 <= rapporto / f <= 1.6:
                fe /= f
                ing["note"].append(f"EPS atteso diviso per {f:g}: stima non rettificata per il frazionamento del {d}")
                break
    return fe


def applica_eta(ingressi: dict, P: dict) -> None:
    """Prezzo piu' vecchio di N giorni o ultimo esercizio piu' vecchio di M giorni: dati insufficienti."""
    for i in ingressi.values():
        i["prezzo_vecchio"] = i.get("eta_prezzo") is None or i["eta_prezzo"] > P["giorni_prezzo"]
        i["esercizio_vecchio"] = i.get("eta_esercizio") is None or i["eta_esercizio"] > P["giorni_esercizio"]


def calcola_tutto(con, oggi: date | None = None, P: dict | None = None, giudizi: dict | None = None,
                  universo: list | None = None):
    """-> (ingressi per ticker, risultati Buffett per ticker, risultati Trading per ticker)"""
    oggi = oggi or date.today()
    P = P or predefiniti()
    giudizi = giudizi or {}
    universo = universo or UNIVERSO
    indici = {}
    for k in {t.indice for t in universo} | (set(INDICI) if universo is UNIVERSO else set()):
        s = serie_prezzi(con, k)
        indici[k] = {"data": s["data"], "chius": s["chius"]}
    ingressi = {t.ticker: ingressi_titolo(con, t, oggi, indici.get(t.indice)) for t in universo}
    applica_eta(ingressi, P)
    A = {k: punteggi.buffett(i, P, giudizi.get(k)) for k, i in ingressi.items()}
    B = punteggi.trading_universo(ingressi, P)
    return ingressi, A, B


def _f(x, n=1, pct=False):
    if x is None:
        return "n.d."
    if isinstance(x, str):
        return x
    return f"{x * 100:.{n}f}%" if pct else f"{x:.{n}f}"


def esporta_csv(ingressi, A, B, percorso) -> None:
    with open(percorso, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Ticker", "Società", "Modello", "Prezzo", "Valuta", "Buffett Score", "Classe", "Q", "F", "G", "V",
                    "Qualità composita", "Valore prudente", "Valore base", "Valore ottimistico", "Margine di sicurezza",
                    "Prezzo d'acquisto", "Verdetto", "Rischi", "Trading Score", "Trend", "Segnale", "Setup",
                    "Ingresso", "Stop", "Obiettivo", "R/R", "Stato dati", "Note"])
        for k, i in ingressi.items():
            a, b = A[k], B[k]
            s = b["setup"]
            w.writerow([k, i["nome"], i["modello"], _f(i.get("prezzo"), 2), i["valuta"], _f(a["punteggio"]),
                        a["classe"] or "n.d."] + [_f(a["pilastri"][L]) for L in "QFGV"] +
                       [_f(a["qualita_composita"])] +
                       [_f(a["scenari"][x]["valore"], 2) for x in ("Prudente", "Base", "Ottimistico")] +
                       [_f(a["margine_sicurezza"], 1, True), _f(a["prezzo_acquisto"], 2), a["verdetto"],
                        ", ".join(a["rischi"]), _f(b["punteggio"]), b["stato_trend"] or "n.d.", b["segnale"],
                        s["tipo"] if s["valido"] else "-"] +
                       [_f(s[x], 2) if s["valido"] else "-" for x in ("ingresso", "stop", "obiettivo", "rr")] +
                       [i["stato_dati"], " | ".join(i["note"])])


def esegui(percorso_db=None) -> int:
    con = db.apri(percorso_db or config.FILE_DB)
    ingressi, A, B = calcola_tutto(con)
    con.close()
    out = config.CARTELLA_DATI / "punteggi.csv"
    esporta_csv(ingressi, A, B, out)
    print("STRATEGIA A - Buffett Score: primi 10")
    ord_a = sorted((k for k in A if A[k]["punteggio"] is not None), key=lambda k: -A[k]["punteggio"])
    for k in ord_a[:10]:
        a = A[k]
        print(f"  {k:12s} {a['punteggio']:5.1f}  classe {a['classe']}  margine {_f(a['margine_sicurezza'], 0, True):>6s}  {a['verdetto']}")
    print("STRATEGIA B - Trading Score: primi 10")
    ord_b = sorted((k for k in B if B[k]["punteggio"] is not None), key=lambda k: -B[k]["punteggio"])
    for k in ord_b[:10]:
        b = B[k]
        print(f"  {k:12s} {b['punteggio']:5.1f}  {b['stato_trend']:10s} {b['segnale']}")
    print(f"Buffett Score calcolato per {len(ord_a)} titoli su {len(A)}; Trading Score per {len(ord_b)} su {len(B)}.")
    print(f"Tabella completa: {out}")
    print("I punteggi ordinano i titoli secondo criteri dichiarati: non sono previsioni né consulenza.")
    return 0
