"""I due punteggi e il valore intrinseco: replica in Python di cio' che il cruscotto calcola con le formule.

Tutte le funzioni sono pure: ingressi (dati importati) + parametri -> risultati. Nessun accesso a rete o archivio.
None significa "n.d." e non vale mai punti. Le due strategie non vengono mai fuse.
"""
from __future__ import annotations
import math
import statistics

from .parametri import FINANZIARI, METRICHE_A, PILASTRI_B

INSUFF = "Dati insufficienti"


def punti(x, s0, s100):
    """Punteggio lineare tra la soglia che vale 0 (s0) e quella che vale 100 (s100); funziona anche se s100 < s0."""
    if x is None or s100 == s0:
        return None
    return 100.0 * max(0.0, min(1.0, (x - s0) / (s100 - s0)))


def arrotonda(x, cifre=1):
    """Arrotondamento come ROUND di Excel (meta' lontano da zero)."""
    if x is None:
        return None
    k = 10 ** cifre
    return math.floor(abs(x) * k + 0.5 + 1e-9) / k * (1 if x >= 0 else -1)


# ====================================================================== Strategia A
def tassi(ing: dict, P: dict, scenario: str) -> tuple[float, float]:
    r0, g0 = P["tassi"].get(ing["valuta_bil"], P["tassi"]["ALTRO"])
    r = r0 + (P["extra_emergenti"] if ing["area"] == "Emergenti" else 0.0) + P["scenari"][scenario][2]
    return r, min(g0, r - P["distanza_terminale"])


def crescita_storica(ing: dict, P: dict):
    if ing["modello"] == "UTL":
        v = [x for x in (ing.get("cagr_ricavi"), ing.get("G2")) if x is not None]
        c = sum(v) / len(v) if v else None
    else:
        c = ing.get("cagr_ricavi")
    if c is None:
        return None
    return max(P["crescita_minima"], min(P["tetto_crescita"][ing["modello"]], c))


def fattore_prevedibilita(livello, P: dict) -> float:
    """Quota della crescita futura riconosciuta secondo la prevedibilita' a 10 anni."""
    return {"Media": P["prev_crescita_media"], "Bassa": P["prev_crescita_bassa"]}.get(livello, 1.0)


def valore_intrinseco(ing: dict, P: dict, scenario: str = "Base", livello=None) -> dict:
    """Ogni passaggio e' una voce del risultato (= una colonna del foglio VALUTAZIONE).
    'valore' e' un numero, oppure 'n.s.' (flusso di partenza negativo), oppure None (dati mancanti)."""
    mod = ing["modello"]
    quota, fattore, _ = P["scenari"][scenario]
    r, gT = tassi(ing, P, scenario)
    o = {"scenario": scenario, "r": r, "gT": gT, "valore": None}
    n = P["anni_fase"]
    if mod in FINANZIARI:
        b0, roe0 = ing.get("tbv_ps"), ing.get("roe_norm")
        if b0 is None or roe0 is None:
            return o
        roe = roe0 * fattore
        pay = ing.get("F4")
        pay = P["payout_predefinito"] if pay is None else max(0.0, min(1.0, pay))
        gB = min(P["tetto_crescita"][mod], roe * (1 - pay))
        if gB > 0:
            gB *= fattore_prevedibilita(livello, P)
        q = (1 + gB) / (1 + r)
        somma = 2 * n if abs(q - 1) < 1e-12 else (1 - q ** (2 * n)) / (1 - q)
        extra = (roe - r) * b0 / (1 + r) * somma
        o.update(patrimonio_tangibile=b0, roe=roe, payout=pay, g_patrimonio=gB, extra_rendimento=extra,
                 valore=max(0.0, b0 + extra))
        return o
    c = crescita_storica(ing, P)
    f = ing.get("flusso_ps")
    if c is None or f is None:
        return o
    g1 = c * quota * fattore_prevedibilita(livello, P) if c > 0 else c * (2 - quota)
    g2 = (g1 + gT) / 2
    f0 = f * P["quota_flusso"][mod] * fattore
    o.update(crescita_storica=c, g1=g1, g2=g2, flusso_partenza=f0)
    if f0 <= 0:
        o["valore"] = "n.s."
        return o

    def serie(q):
        return n if abs(q - 1) < 1e-12 else q * (1 - q ** n) / (1 - q)
    a, b = (1 + g1) / (1 + r), (1 + g2) / (1 + r)
    va1 = f0 * serie(a)
    va2 = f0 * a ** n * serie(b)
    f10 = f0 * (1 + g1) ** n * (1 + g2) ** n
    vt = f10 * (1 + gT) / (r - gT)
    va_t = vt / (1 + r) ** (2 * n)
    cassa = P["quota_cassa_netta"] * max(0.0, ing.get("cassa_netta_ps") or 0.0)
    o.update(va_fase1=va1, va_fase2=va2, flusso_anno10=f10, valore_terminale=vt, va_terminale=va_t,
             cassa_riconosciuta=cassa, valore=va1 + va2 + va_t + cassa)
    return o


def metriche_valutazione(ing: dict, P: dict, valore_base) -> dict:
    mod, prezzo = ing["modello"], ing.get("prezzo")
    v = {"V1": None, "V2": None, "V3": None, "V4": None}
    if not prezzo or prezzo <= 0:
        return v
    if isinstance(valore_base, (int, float)) and valore_base > 0:
        v["V1"] = 1 - prezzo / valore_base
    if ing.get("flusso_ps") is not None:
        v["V2"] = ing["flusso_ps"] * P["quota_flusso"][mod] / prezzo
    if mod in FINANZIARI:
        if ing.get("tbv_ps") and ing["tbv_ps"] > 0:
            v["V3"] = prezzo / ing["tbv_ps"]
    elif ing.get("ebitda_q") is not None and ing.get("debito_netto_q") is not None and ing.get("azioni"):
        v["V3"] = (ing["azioni"] * prezzo + ing["debito_netto_q"]) / ing["ebitda_q"] if ing["ebitda_q"] > 0 else 999.0
    if ing.get("eps_atteso") and ing["eps_atteso"] > 0:
        v["V4"] = prezzo / ing["eps_atteso"]
    return v


def pilastro(valori: dict, soglie: dict, lettera: str, copertura_minima: float):
    """Media pesata delle metriche disponibili. -> (punteggio|None, copertura, {metrica: punti})"""
    tot = disp = somma = 0.0
    det = {}
    for m in METRICHE_A:
        if m[0] != lettera:
            continue
        peso, s0, s100 = soglie[m]
        if peso <= 0:
            continue
        tot += peso
        p = punti(valori.get(m), s0, s100)
        det[m] = p
        if p is not None:
            disp += peso
            somma += peso * p
    cop = disp / tot if tot else 0.0
    return (somma / disp if disp and cop >= copertura_minima - 1e-9 else None), cop, det


def segnali_rischio(ing: dict, val: dict, P: dict) -> list[str]:
    mod, s = ing["modello"], []
    sog = P["metriche"][mod]
    fin = mod in FINANZIARI
    f1 = val.get("F1")
    if f1 is not None and sog["F1"][0] > 0 and punti(f1, sog["F1"][1], sog["F1"][2]) == 0:
        s.append("Patrimonio sottile rispetto all'attivo" if fin else "Leva finanziaria alta")
    if ing.get("margine_ultimo") is not None and ing.get("margine_medio_prec") is not None and \
            ing["margine_ultimo"] < ing["margine_medio_prec"] - P["rischio_calo_margine"]:
        s.append("Margini in calo")
    if ing.get("var_ricavi_ultimo") is not None and ing["var_ricavi_ultimo"] < 0:
        s.append("Ricavi in calo")
    if not fin and ing.get("fcf_ultimo") is not None and ing["fcf_ultimo"] < 0:
        s.append("Free cash flow negativo")
    if val.get("F4") is not None and val["F4"] > P["rischio_payout"]:
        s.append("Dividendi non coperti")
    if val.get("G3") is not None and val["G3"] > P["rischio_diluizione"]:
        s.append("Diluizione degli azionisti")
    if ing.get("avviamento_su_patr") is not None and ing["avviamento_su_patr"] > P["rischio_avviamento"]:
        s.append("Avviamento elevato")
    if not fin and val.get("F2") is not None and val["F2"] < P["rischio_copertura"]:
        s.append("Copertura degli interessi bassa")
    return s


def buffett(ing: dict, P: dict, giudizi: dict | None = None) -> dict:
    """Buffett Score (metodologia ispirata ai principi del value investing; nessun giudizio attribuito a Buffett)."""
    from .prevedibilita import livello_usato
    g = giudizi or {}
    mod = ing["modello"]
    sog = P["metriche"][mod]
    livello, fonte = livello_usato(ing.get("ticker", ""), g, ing.get("prev_claude"))
    scen = {s: valore_intrinseco(ing, P, s, livello) for s in P["scenari"]}
    base = scen["Base"]["valore"]
    val = {m: ing.get(m) for m in METRICHE_A}
    if mod in FINANZIARI:
        val["Q3"] = g.get("Q3")
    val["F5"] = g.get("F5")
    val.update(metriche_valutazione(ing, P, base))
    o = {"modello": mod, "valori": val, "scenari": scen, "valore_base": base, "punti": {}, "copertura": {},
         "prevedibilita": livello, "fonte_prev": fonte}
    pil = {}
    for L in "QFGV":
        pil[L], o["copertura"][L], det = pilastro(val, sog, L, P["copertura_minima"])
        o["punti"].update(det)
    o["pilastri"] = pil
    w = P["pesi_pilastri"][mod]
    vecchio = bool(ing.get("prezzo_vecchio") or ing.get("esercizio_vecchio"))
    qc = None
    if all(pil[L] is not None for L in "QFG"):
        qc = sum(w[L] * pil[L] for L in "QFG") / sum(w[L] for L in "QFG")
    o["qualita_composita"] = qc
    o["classe"] = None if qc is None else ("A" if qc >= P["classe_a"] else "B" if qc >= P["classe_b"] else "C")
    corr = max(-P["correzione_massima"], min(P["correzione_massima"], float(g.get("correzione") or 0.0)))
    o["correzione"] = corr
    if qc is None or pil["V"] is None or vecchio:
        o["valutazione_usata"], o["punteggio"] = None, None
    else:
        vu = min(pil["V"], qc + P["tetto_valutazione"])
        grezzo = (sum(w[L] for L in "QFG") * qc + w["V"] * vu) / sum(w.values()) + corr
        o["valutazione_usata"] = vu
        o["punteggio"] = arrotonda(max(0.0, min(100.0, grezzo)), 1)
    prezzo = ing.get("prezzo")
    o["margine_sicurezza"] = val["V1"]
    o["richiesto"] = None
    o["prezzo_acquisto"] = None
    if vecchio or qc is None:
        o["verdetto"] = INSUFF
    elif o["classe"] == "C":
        o["verdetto"] = "Non comprerei: qualità insufficiente"
    elif livello == "Bassa":
        o["verdetto"] = "Non comprerei: troppo difficile da prevedere"
    elif base == "n.s.":
        o["verdetto"] = "Non comprerei: valore non stimabile"
    elif not isinstance(base, (int, float)) or not prezzo:
        o["verdetto"] = INSUFF
    else:
        richiesto = (P["margine_a"] if o["classe"] == "A" else P["margine_b"]) + (P["prev_margine_media"] if livello == "Media" else 0.0)
        o["prezzo_acquisto"] = base * (1 - richiesto)
        o["richiesto"] = richiesto
        o["verdetto"] = "Comprerei" if prezzo < o["prezzo_acquisto"] else "Aspetterei"
    o["rischi"] = segnali_rischio(ing, val, P)
    return o


# ====================================================================== Strategia B
def _rsi_punti(x, fasce):
    if x is None:
        return None
    for limite, p in fasce:
        if x < limite:
            return float(p)
    return float(fasce[-1][1])


def setup_operativo(t: dict, P: dict) -> dict:
    """Setup solo se prezzo > media 200 e media 50 > media 200. Prima la rottura, poi il ritracciamento."""
    o = {"tipo": None, "ingresso": None, "stop": None, "obiettivo": None, "rr": None, "valido": False}
    pr, a = t.get("prezzo"), t.get("atr")
    if None in (pr, a, t.get("mm20"), t.get("mm50"), t.get("mm200"), t.get("rsi")) or a <= 0:
        return o
    if not (pr > t["mm200"] and t["mm50"] > t["mm200"]):
        return o
    candidati = []
    if t["max20"] - pr <= P["setup_rottura_atr"] * a:
        candidati.append(("Rottura", t["max20"] + P["setup_ingresso_atr"] * a))
    f = P["setup_fascia_atr"] * a
    if t["mm50"] - f <= pr <= t["mm20"] + f and P["setup_rsi"][0] <= t["rsi"] <= P["setup_rsi"][1]:
        candidati.append(("Ritracciamento", pr))
    for tipo, ingresso in candidati:
        rischio = P["setup_stop_atr"] * a
        obiettivo = ingresso + P["setup_obiettivo_r"] * rischio
        livelli = [x for x in list(t.get("resistenze") or []) + [t.get("max52")] if x is not None and x > ingresso]
        if livelli and min(livelli) < obiettivo:
            obiettivo = min(livelli)
        rr = (obiettivo - ingresso) / rischio
        cand = {"tipo": tipo, "ingresso": ingresso, "stop": ingresso - rischio, "obiettivo": obiettivo, "rr": rr,
                "valido": rr >= P["setup_rr_min"] - 1e-12}
        if cand["valido"]:
            return cand
        if o["tipo"] is None:
            o = cand
    return o


def trading_universo(tecnici: dict[str, dict], P: dict) -> dict[str, dict]:
    """tecnici: ticker -> ingressi tecnici (+ 'settore', 'cambio_eur'). Il rango del momentum e la mediana
    di settore si calcolano sull'universo. -> ticker -> risultati."""
    wm = P["mom_pesi"]
    comp = {}
    for k, t in tecnici.items():
        if None not in (t.get("r12m_1"), t.get("r6m"), t.get("r3m")):
            comp[k] = wm[0] * t["r12m_1"] + wm[1] * t["r6m"] + wm[2] * t["r3m"]
    per_settore: dict[str, list] = {}
    for k, t in tecnici.items():
        if t.get("r3m") is not None:
            per_settore.setdefault(t.get("settore"), []).append(t["r3m"])
    mediane = {s: statistics.median(v) for s, v in per_settore.items() if len(v) >= P["fr_min_settore"]}
    out = {}
    for k, t in tecnici.items():
        o: dict = {"pilastri": {}}
        pr = t.get("prezzo")
        # Trend
        if None in (pr, t.get("mm20"), t.get("mm50"), t.get("mm200"), t.get("mm200_20fa")):
            trend = None
        else:
            tp = P["trend_punti"]
            trend = float(tp[0] * (pr > t["mm200"]) + tp[1] * (t["mm50"] > t["mm200"]) + tp[2] * (pr > t["mm50"])
                          + tp[3] * (t["mm200"] > t["mm200_20fa"]) + tp[4] * (pr > t["mm20"]))
        o["stato_trend"] = None if trend is None else ("Rialzista" if trend >= P["trend_rialzista"] else
                                                       "Ribassista" if trend < P["trend_ribassista"] else "Laterale")
        # Momentum
        if k in comp:
            rango = sum(1 for x in comp.values() if x < comp[k]) / (len(comp) - 1) if len(comp) > 1 else 0.5
            mom = 50.0 * rango + 0.5 * punti(comp[k], P["mom_s0"], P["mom_s100"])
            o["mom_composito"], o["mom_rango"] = comp[k], rango
        else:
            mom = None
            o["mom_composito"], o["mom_rango"] = None, None
        # Forza relativa
        fr = []
        if None not in (t.get("r3m"), t.get("idx_r3m")):
            fr.append(punti(t["r3m"] - t["idx_r3m"], -P["fr_3m"], P["fr_3m"]))
        if None not in (t.get("r6m"), t.get("idx_r6m")):
            fr.append(punti(t["r6m"] - t["idx_r6m"], -P["fr_6m"], P["fr_6m"]))
        o["mediana_settore_3m"] = mediane.get(t.get("settore"))
        if t.get("r3m") is not None and o["mediana_settore_3m"] is not None:
            fr.append(punti(t["r3m"] - o["mediana_settore_3m"], -P["fr_settore"], P["fr_settore"]))
        forza = sum(fr) / len(fr) if fr else None
        # Oscillatori
        if None in (t.get("rsi"), t.get("macd"), t.get("macd_segnale"), t.get("macd_isto"), t.get("macd_isto_5fa")):
            osc = None
        else:
            pm = P["macd_sopra"] * (t["macd"] > t["macd_segnale"]) + P["macd_isto"] * (t["macd_isto"] > t["macd_isto_5fa"])
            osc = P["osc_peso_rsi"] * _rsi_punti(t["rsi"], P["rsi_fasce"]) + (1 - P["osc_peso_rsi"]) * pm
        # Volumi
        if None in (t.get("vol_su_giu"), t.get("vol_20_60"), t.get("r1m")):
            vol = None
        else:
            x = punti(t["vol_20_60"], *P["vol_rel"])
            if t["r1m"] < 0:
                x = 100 - x
            vol = P["vol_peso_ud"] * punti(t["vol_su_giu"], *P["vol_ud"]) + (1 - P["vol_peso_ud"]) * x
        # Setup, assetto e rischio
        st = setup_operativo(t, P)
        o["setup"] = st
        if None in (pr, t.get("max52"), t.get("atr")):
            ass = None
        else:
            wa = P["ass_pesi"]
            ass = (wa[0] * punti(1 - pr / t["max52"], *P["ass_dist"]) + wa[1] * punti(t["atr"] / pr, *P["ass_atr"])
                   + wa[2] * (punti(st["rr"], *P["ass_rr"]) if st["valido"] else 0.0))
        # Catalizzatori
        cat = []
        su, giu = t.get("rev_su30"), t.get("rev_giu30")
        if su is not None and giu is not None and su + giu > 0:
            cat.append(50 + 50 * (su - giu) / (su + giu))
        if t.get("reazione_utili") is not None and t.get("giorni_da_utili") is not None \
                and t["giorni_da_utili"] <= P["cat_giorni"]:
            cat.append(punti(t["reazione_utili"], -P["cat_reazione"], P["cat_reazione"]))
        catal = sum(cat) / len(cat) if cat else None
        o["avviso_trimestrale"] = (t.get("giorni_a_utili") is not None and 0 <= t["giorni_a_utili"] <= P["cat_avviso"])
        pil = dict(zip(PILASTRI_B, (trend, mom, forza, osc, vol, ass, catal)))
        o["pilastri"] = pil
        w = P["pesi_b"]
        disp = sum(w[n] for n in PILASTRI_B if pil[n] is not None)
        o["copertura"] = disp / sum(w.values())
        if trend is None or mom is None or o["copertura"] < P["copertura_b"] - 1e-9 or t.get("prezzo_vecchio"):
            o["punteggio"] = None
        else:
            o["punteggio"] = arrotonda(sum(w[n] * pil[n] for n in PILASTRI_B if pil[n] is not None) / disp, 1)
        p = o["punteggio"]
        if p is None:
            o["segnale"] = INSUFF
        elif p >= P["soglia_segnale"] and st["valido"]:
            o["segnale"] = "Setup attivo"
        elif p >= P["soglia_segnale"]:
            o["segnale"] = "In osservazione"
        elif o["stato_trend"] == "Ribassista":
            o["segnale"] = "Evitare"
        else:
            o["segnale"] = "Neutrale"
        # dimensione della posizione (capitale di esempio, in euro)
        o["n_azioni"] = None
        if st["valido"] and t.get("cambio_eur"):
            rischio_eur = (st["ingresso"] - st["stop"]) / t["cambio_eur"]
            ingresso_eur = st["ingresso"] / t["cambio_eur"]
            o["n_azioni"] = math.floor(min(P["capitale"] * P["rischio_operazione"] / rischio_eur,
                                           P["capitale"] * P["peso_massimo"] / ingresso_eur))
        out[k] = o
    return out
