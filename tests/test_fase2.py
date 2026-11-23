"""Collaudi senza rete: indicatori tecnici, metriche di bilancio, valore intrinseco e punteggi."""
import math

import numpy as np
import pytest

from gsi import bilanci, indicatori as ind, punteggi as pt
from gsi.parametri import predefiniti

P = predefiniti()
ap = pytest.approx


# ------------------------------------------------------------------ regole comuni
def test_punti_lineare_nei_due_versi():
    assert pt.punti(0.13, 0.06, 0.20) == ap(50.0)
    assert pt.punti(0.50, 0.06, 0.20) == 100 and pt.punti(-1, 0.06, 0.20) == 0
    assert pt.punti(2.25, 4, 0.5) == ap(50.0)             # soglia a 100 piu' bassa di quella a 0
    assert pt.punti(5, 4, 0.5) == 0 and pt.punti(0, 4, 0.5) == 100
    assert pt.punti(None, 0, 1) is None                   # n.d. non vale mai punti
    assert pt.arrotonda(57.25) == 57.3 and pt.arrotonda(57.24) == 57.2 and pt.arrotonda(-0.25) == -0.3


def test_pesi_delle_metriche():
    for mod, sog in P["metriche"].items():
        for L in "QFGV":
            assert sum(v[0] for k, v in sog.items() if k[0] == L) == 100, (mod, L)
        assert sum(P["pesi_pilastri"][mod].values()) == 100
    assert P["metriche"]["STD"]["V3"] == [10, 22, 8] and P["metriche"]["REIT"]["V4"][0] == 0
    assert sum(P["pesi_b"].values()) == 100


def test_pilastro_copertura():
    sog = P["metriche"]["BAN"]
    v = {"F1": 0.07, "F4": 0.65, "F5": None}               # 65% del peso disponibile
    p, cop, det = pt.pilastro(v, sog, "F", 0.6)
    assert cop == ap(0.65) and p == ap((40 * 50 + 25 * 50) / 65) and det["F5"] is None
    p, cop, _ = pt.pilastro({"F1": 0.07}, sog, "F", 0.6)   # 40%: dati insufficienti
    assert p is None and cop == ap(0.40)


# ------------------------------------------------------------------ indicatori
def test_medie_rsi_macd_atr():
    x = list(range(1, 301))
    assert ind.media_mobile(x, 20) == ap(290.5) and ind.media_mobile(x, 200, 280) == ap(180.5)
    assert ind.media_mobile(x[:10], 20) is None
    assert ind.rsi(x) == 100.0 and ind.rsi([5.0] * 50) == 50.0 and ind.rsi([1, 2]) is None
    # RSI a 14 con guadagni e perdite alternati uguali -> 50 circa
    alt = [100 + (i % 2) for i in range(200)]
    assert 45 < ind.rsi(alt) < 55
    m = ind.macd([10.0] * 100)
    assert m == (0.0, 0.0, 0.0, 0.0)
    m = ind.macd(x)
    assert m[0] > 0 and m[0] == ap(m[1], abs=1e-6)         # serie lineare: MACD costante = segnale
    c = [100.0] * 60
    assert ind.atr([101.0] * 60, [99.0] * 60, c) == ap(2.0)
    e = ind.ema([1, 2, 3], 3)
    assert list(e) == ap([1, 1.5, 2.25])


def test_rendimenti_resistenze_tecnici():
    x = [100.0] * 300
    x[-1], x[-22], x[-64] = 110.0, 105.0, 88.0
    assert ind.rendimento(x, 21) == ap(110 / 105 - 1) and ind.rendimento(x, 63) == ap(110 / 88 - 1)
    assert ind.rendimento(x, 252, 21) == ap(0.05) and ind.rendimento(x[:10], 21) is None
    h = [10.0] * 100
    h[50], h[70] = 15.0, 12.0
    assert ind.massimi_locali(h) == [12.0, 15.0]
    n = 300
    d = [f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
    c = [100 + 0.1 * i for i in range(n)]
    pr = {"data": d, "max": [v + 1 for v in c], "min": [v - 1 for v in c], "chius": c, "rett": c,
          "vol": [1000.0] * n}
    t = ind.calcola_tecnici(pr, {"data": d, "chius": [50.0] * n})
    assert t["prezzo"] == ap(129.9) and t["mm20"] == ap(np.mean(c[-20:])) and t["max20"] == ap(130.9)
    assert t["idx_r3m"] == 0.0 and t["r3m"] == ap(c[-1] / c[-64] - 1)
    assert t["vol_su_giu"] is None and t["vol_20_60"] == ap(1.0)       # nessuna seduta al ribasso
    assert t["atr"] == ap(2.0) and t["rsi"] == 100.0
    assert ind.valore_al(["2026-01-01", "2026-01-05"], [1, 2], "2026-01-04") == 1


def test_reazione_utili():
    d = ["2026-11-0%d" % i for i in range(1, 8)]
    pr = {"data": d, "rett": [100, 100, 100, 106, 110, 110, 110]}
    idx = {"data": d, "chius": [10, 10, 10, 10.1, 10.2, 10.2, 10.2]}
    r, quando, giorni = ind.reazione_utili(pr, idx, ["2026-11-04", "2027-02-01"], "2026-11-21")
    assert quando == "2026-11-04" and giorni == 17 and r == ap(0.10 - 0.02)
    assert ind.reazione_utili(pr, idx, ["2027-02-01"], "2026-11-21") == (None, None, None)


# ------------------------------------------------------------------ metriche di bilancio
def _anno(data, ricavi, ebit, utile, **k):
    a = dict(data=data, ricavi=ricavi, ebit=ebit, utile=utile, lordo=ricavi * 0.5, tasse=ebit * 0.2, ante=ebit,
             interessi=10.0, da=20.0, ebitda=ebit + 20, eps=utile / 100, az_dil=100.0, debito=200.0, patr=300.0,
             patr_tot=300.0, attivo=1000.0, cassa=50.0, pass_corr=100.0, deb_corr=20.0, avviamento=60.0,
             tbv=240.0, az_fine=100.0, fcf=utile * 0.9, dividendi=-utile * 0.4, sbc=5.0)
    a.update(k)
    return a


ANNI = [_anno("2022-12-31", 1000.0, 100.0, 80.0), _anno("2023-12-31", 1100.0, 121.0, 90.0),
        _anno("2024-12-31", 1050.0, 105.0, 85.0), _anno("2025-12-31", 1210.0, 145.2, 110.0, debito=260.0)]


def test_fondamentali_standard():
    f = bilanci.calcola_fondamentali(ANNI, "STD")
    nopat = [e * 0.8 for e in (100.0, 121.0, 105.0, 145.2)]
    roic = [nopat[0] / 500, nopat[1] / 500, nopat[2] / 500, nopat[3] / ((500 + 560) / 2)]
    assert f["n_anni"] == 4 and f["ultimo_esercizio"] == "2025-12-31"
    assert f["Q1"] == ap(sum(roic) / 4) and f["Q2"] == ap(min(roic))
    assert f["Q3"] == ap(np.mean([0.10, 0.11, 0.10, 0.12])) and f["Q4"] == ap(np.std([0.10, 0.11, 0.10, 0.12], ddof=1))
    assert f["Q5"] == ap(2 / 3) and f["Q6"] == ap(0.5)
    assert f["F1"] == ap((260 - 50) / 165.2) and f["F2"] == ap(14.52)
    assert f["F3"] == ap(0.9) and f["F4"] == ap(0.4 / 0.9) and f["F5"] is None
    assert f["G1"] == ap(1.21 ** (1 / 3) - 1) and f["G2"] == ap((110 / 80) ** (1 / 3) - 1) and f["G3"] == ap(0.0)
    assert f["G4"] == ap((nopat[3] - nopat[0]) / 60)
    marg = np.mean([(a["fcf"] - 5) / a["ricavi"] for a in ANNI[1:]])     # ultimi 3 esercizi
    assert f["flusso_norm"] == ap(marg * 1210) and f["flusso_anni"] == 3
    assert f["cassa_netta"] == ap(-210) and f["tbv"] == 240 and f["var_ricavi_ultimo"] == ap(1210 / 1050 - 1)
    c = bilanci.calcola_fondamentali(ANNI, "CIC")                        # ciclici: tutti gli esercizi
    assert c["flusso_anni"] == 4 and c["Q6"] is None


def test_fondamentali_casi_particolari():
    # EBITDA negativo -> leva 99; cassa netta -> copertura 99; niente dividendi -> payout vuoto
    a = [dict(x) for x in ANNI]
    a[-1].update(ebitda=-5.0, dividendi=None)
    for x in a[:-1]:
        x["dividendi"] = None
    f = bilanci.calcola_fondamentali(a, "STD")
    assert f["F1"] == 99.0 and f["F4"] is None
    a[-1].update(cassa=500.0)
    assert bilanci.calcola_fondamentali(a, "STD")["F2"] == 99.0
    # dividendi non coperti da flussi negativi -> payout 9,99; EPS negativo -> crescita EPS vuota
    b = [dict(x, fcf=-10.0) for x in ANNI]
    b[-1]["eps"] = -1.0
    f = bilanci.calcola_fondamentali(b, "STD")
    assert f["F4"] == 9.99 and f["G2"] is None and f["F3"] == ap(-40 / 365)
    # patrimonio quasi azzerato dai riacquisti -> capitale = attivo - cassa - passivita' correnti non finanziarie
    z = [dict(x, patr_tot=50.0) for x in ANNI]
    f = bilanci.calcola_fondamentali(z, "STD")
    assert f["capitale_alternativo"] and f["Q1"] == ap(np.mean([e * 0.8 / 870 for e in (100.0, 121.0, 105.0, 145.2)]))
    # aliquota fuori scala limitata al 35%, mancante 25%
    t = [dict(ANNI[-1], tasse=None)]
    assert bilanci.calcola_fondamentali(t, "STD")["Q1"] == ap(145.2 * 0.75 / 560)
    t = [dict(ANNI[-1], tasse=100.0)]
    assert bilanci.calcola_fondamentali(t, "STD")["Q1"] == ap(145.2 * 0.65 / 560)
    assert bilanci.calcola_fondamentali([], "STD")["n_anni"] == 0
    # componenti straordinarie tolte dall'EBITDA; debito assente in ogni esercizio -> zero con nota
    s = [dict(ANNI[-1], straord=-100.0)]
    assert bilanci.calcola_fondamentali(s, "STD")["ebitda"] == ap(265.2)
    n = [dict(ANNI[-1], debito=None, deb_corr=None)]
    f = bilanci.calcola_fondamentali(n, "STD")
    assert f["debito_netto"] == -50.0 and any("assunto pari a zero" in x for x in f["note"])


def test_fondamentali_banca():
    a = [dict(data=f"{y}-12-31", ricavi=100.0 + i, utile=u, patr=p, attivo=p * 12, az_fine=10.0, az_dil=10.0,
              eps=u / 10, dividendi=-u * 0.5, fcf=1.0, tbv=p - 10)
         for i, (y, u, p) in enumerate([(2022, 10.0, 100.0), (2023, 12.0, 106.0), (2024, 11.0, 111.0), (2025, 13.0, 118.0)])]
    f = bilanci.calcola_fondamentali(a, "BAN")
    roe = [10 / 100, 12 / 103, 11 / 108.5, 13 / 114.5]
    assert f["Q1"] == ap(np.mean(roe)) and f["Q2"] == ap(min(roe)) and f["Q3"] is None
    assert f["Q4"] == ap(np.std(roe, ddof=1)) and f["roe_norm"] == ap(np.mean(roe))
    assert f["F1"] == ap(1 / 12) and f["F2"] is None and f["F3"] is None and f["F4"] == ap(0.5)
    assert f["G1"] == ap(((11.8 + (6 + 5.5 + 6.5) / 10) / 10.0) ** (1 / 3) - 1)
    assert f["flusso_norm"] == ap(np.mean(roe) * 118)


def test_rettifica_frazionamenti():
    d = ["2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]
    v, note = bilanci.rettifica_frazionamenti(d, [100, 101, 204, 205], [("2024-06-10", 2.0)], False)
    assert v == [200, 202, 204, 205] and len(note) == 1
    v, _ = bilanci.rettifica_frazionamenti(d, [8.0, 4.1, 4.2, 4.3], [("2025-08-26", 2.0)], True)
    assert v == [4.0, 4.1, 4.2, 4.3]
    # nessuna correzione: il salto non coincide col fattore, o il frazionamento e' precedente
    assert bilanci.rettifica_frazionamenti(d, [100, 150, 151, 152], [("2023-06-01", 2.0)], False)[0] == [100, 150, 151, 152]
    assert bilanci.rettifica_frazionamenti(d, [100, 200, 201, 202], [("2021-06-01", 2.0)], False)[0] == [100, 200, 201, 202]
    assert bilanci.cagr(100, 121, 2) == ap(0.10) and bilanci.cagr(-1, 5, 2) is None
    assert bilanci.anni_tra("2022-09-30", "2025-09-30") == 3


# ------------------------------------------------------------------ valore intrinseco
def _ing(**k):
    d = dict(modello="STD", area="USA", valuta_bil="USD", prezzo=100.0, cagr_ricavi=0.08, flusso_ps=6.0,
             cassa_netta_ps=10.0, azioni=1000.0, debito_netto_q=-10000.0, ebitda_q=9000.0, eps_atteso=5.0,
             Q1=0.25, Q2=0.2, Q3=0.3, Q4=0.01, Q5=1.0, Q6=0.6, F1=-1.0, F2=30.0, F3=1.0, F4=0.4,
             G1=0.08, G2=0.10, G3=-0.01, G4=0.2)
    d.update(k)
    return d


def _dcf_esplicito(f0, g1, g2, gT, r):
    tot, f = 0.0, f0
    for t in range(1, 11):
        f *= 1 + (g1 if t <= 5 else g2)
        tot += f / (1 + r) ** t
    return tot + f * (1 + gT) / (r - gT) / (1 + r) ** 10


def test_valore_intrinseco_industriale():
    v = pt.valore_intrinseco(_ing(), P, "Base")
    g1 = 0.08 * 0.6
    assert v["r"] == ap(0.09) and v["gT"] == ap(0.025) and v["g1"] == ap(g1) and v["g2"] == ap((g1 + 0.025) / 2)
    assert v["valore"] == ap(_dcf_esplicito(6.0, g1, (g1 + 0.025) / 2, 0.025, 0.09) + 5.0)
    assert v["va_fase1"] + v["va_fase2"] + v["va_terminale"] + v["cassa_riconosciuta"] == ap(v["valore"])
    p = pt.valore_intrinseco(_ing(), P, "Prudente")
    assert p["r"] == ap(0.10) and p["flusso_partenza"] == ap(6 * 0.85) and p["g1"] == ap(0.02)
    o = pt.valore_intrinseco(_ing(), P, "Ottimistico")
    assert p["valore"] < v["valore"] < o["valore"]
    # crescita limitata dal tetto del modello e dal minimo; crescita negativa pesata con (2 - quota)
    assert pt.valore_intrinseco(_ing(cagr_ricavi=0.30), P)["g1"] == ap(0.10 * 0.6)
    assert pt.valore_intrinseco(_ing(cagr_ricavi=-0.10), P)["g1"] == ap(-0.02 * 1.4)
    # emergenti +2 punti; crescita terminale mai oltre r - 3 punti; valuta sconosciuta -> ALTRO
    e = pt.valore_intrinseco(_ing(area="Emergenti", valuta_bil="INR"), P)
    assert e["r"] == ap(0.14) and e["gT"] == ap(0.05)
    assert pt.valore_intrinseco(_ing(valuta_bil="CHF"), P, "Ottimistico")["gT"] == ap(0.01)
    assert pt.tassi(_ing(valuta_bil="INR"), P, "Ottimistico") == ap((0.115, 0.05))
    assert pt.tassi(_ing(valuta_bil="XXX"), P, "Base") == ap((0.10, 0.025))
    # flusso negativo -> n.s.; dati mancanti -> None; cassa netta negativa non aggiunta
    assert pt.valore_intrinseco(_ing(flusso_ps=-1.0), P)["valore"] == "n.s."
    assert pt.valore_intrinseco(_ing(flusso_ps=None), P)["valore"] is None
    assert pt.valore_intrinseco(_ing(cassa_netta_ps=-50.0), P)["cassa_riconosciuta"] == 0
    # reti regolate: quota distribuibile 75% e crescita = media tra ricavi ed EPS, tetto 4%
    u = pt.valore_intrinseco(_ing(modello="UTL", cagr_ricavi=0.02, G2=0.04), P)
    assert u["flusso_partenza"] == ap(4.5) and u["crescita_storica"] == ap(0.03)


def test_valore_intrinseco_banca():
    i = _ing(modello="BAN", valuta_bil="EUR", tbv_ps=50.0, roe_norm=0.12, F4=0.5)
    v = pt.valore_intrinseco(i, P, "Base")
    r, g = 0.085, min(0.06, 0.12 * 0.5)
    b, tot = 50.0, 0.0
    for t in range(1, 11):
        tot += (0.12 - r) * b / (1 + r) ** t
        b *= 1 + g
    assert v["valore"] == ap(50 + tot) and v["g_patrimonio"] == ap(0.06)
    assert pt.valore_intrinseco(dict(i, F4=None), P)["payout"] == 0.5
    assert pt.valore_intrinseco(dict(i, roe_norm=-0.5), P)["valore"] == 0.0        # mai sotto zero
    assert pt.valore_intrinseco(dict(i, tbv_ps=None), P)["valore"] is None


# ------------------------------------------------------------------ Buffett Score
def test_buffett_composizione_e_verdetti():
    b = pt.buffett(_ing(), P)
    assert b["pilastri"]["Q"] == 100 and b["qualita_composita"] is not None and b["classe"] == "A"
    v = b["valori"]
    assert v["V1"] == ap(1 - 100 / b["valore_base"]) and v["V2"] == ap(0.06) and v["V4"] == ap(20.0)
    assert v["V3"] == ap((1000 * 100 - 10000) / 9000)
    w, pil = P["pesi_pilastri"]["STD"], b["pilastri"]
    qc = (30 * pil["Q"] + 15 * pil["F"] + 15 * pil["G"]) / 60
    atteso = (60 * qc + 40 * min(pil["V"], qc + 20)) / 100
    assert b["punteggio"] == pt.arrotonda(atteso, 1)
    assert b["prezzo_acquisto"] == ap(b["valore_base"] * 0.75)
    assert b["verdetto"] == ("Comprerei" if 100 < b["prezzo_acquisto"] else "Aspetterei")
    assert pt.buffett(_ing(prezzo=10.0), P)["verdetto"] == "Comprerei"
    # azienda mediocre che costa poco: la valutazione usata e' limitata a qualita' + 20
    m = pt.buffett(_ing(Q1=0.06, Q2=0.0, Q3=0.05, Q4=0.06, Q5=0.5, Q6=0.2, F1=4.0, F2=2.0, F3=0.4, F4=1.0,
                        G1=0.0, G2=0.0, G3=0.03, G4=0.05, prezzo=5.0), P)
    assert m["qualita_composita"] == 0 and m["pilastri"]["V"] == 100 and m["valutazione_usata"] == 20
    assert m["punteggio"] == 8.0 and m["classe"] == "C" and m["verdetto"] == "Non comprerei: qualità insufficiente"
    # classe B: margine richiesto 40%
    q = pt.buffett(_ing(Q1=0.13, F1=2.25, F2=7.0, F3=0.7, F4=0.75, G1=0.05, G2=0.06, G3=0.005, G4=0.125), P)
    assert q["qualita_composita"] == ap((30 * 85 + 15 * 50 + 15 * 50) / 60)
    assert q["classe"] == "B" and q["prezzo_acquisto"] == ap(q["valore_base"] * 0.60)
    # flussi negativi -> valore non stimabile, punteggio insufficiente
    n = pt.buffett(_ing(flusso_ps=-2.0), P)
    assert n["verdetto"] == "Non comprerei: valore non stimabile" and n["punteggio"] is None
    # correzione qualitativa limitata a +-10
    c = pt.buffett(_ing(), P, {"correzione": 25})
    assert c["correzione"] == 10 and c["punteggio"] == min(100.0, pt.arrotonda(atteso + 10, 1))
    # dati vecchi -> insufficienti; pilastro scoperto -> insufficienti
    assert pt.buffett(_ing(prezzo_vecchio=True), P)["verdetto"] == pt.INSUFF
    assert pt.buffett(_ing(esercizio_vecchio=True), P)["punteggio"] is None
    s = pt.buffett(_ing(G1=None, G2=None), P)
    assert s["pilastri"]["G"] is None and s["punteggio"] is None and s["verdetto"] == pt.INSUFF


def test_buffett_finanziari_e_rischi():
    i = _ing(modello="ASS", valuta_bil="EUR", tbv_ps=50.0, roe_norm=0.12, flusso_ps=7.0, Q1=0.12, Q2=0.08,
             Q3=None, Q4=0.02, Q5=1.0, F1=0.10, F2=None, F3=None, F4=0.5, G1=0.08, G2=0.08, G3=0.0, G4=None)
    b = pt.buffett(i, P)
    assert b["valori"]["Q3"] is None and b["copertura"]["Q"] == ap(0.85) and b["copertura"]["F"] == ap(0.60)
    assert b["valori"]["V3"] == ap(2.0) and b["punteggio"] is not None
    m = pt.buffett(i, P, {"Q3": 0.96, "F5": 1.85})                      # dati manuali dal foglio GIUDIZI
    assert m["copertura"]["Q"] == 1 and m["punti"]["F5"] == ap(50.0) and m["punti"]["Q3"] == ap(50.0)
    r = pt.buffett(_ing(F1=5.0, F2=1.0, F4=1.4, G3=0.05, margine_ultimo=0.05, margine_medio_prec=0.10,
                        var_ricavi_ultimo=-0.02, fcf_ultimo=-1.0, avviamento_su_patr=0.9), P)["rischi"]
    assert len(r) == 8 and "Leva finanziaria alta" in r and "Dividendi non coperti" in r
    assert pt.buffett(_ing(), P)["rischi"] == []


# ------------------------------------------------------------------ Trading Score
def _tec(**k):
    d = dict(settore="X", cambio_eur=1.0, prezzo=100.0, mm20=98.0, mm50=95.0, mm200=90.0, mm200_20fa=89.0,
             rsi=58.0, macd=1.0, macd_segnale=0.5, macd_isto=0.5, macd_isto_5fa=0.3, atr=2.0, max20=101.0,
             max52=101.0, resistenze=[], r1m=0.03, r3m=0.10, r6m=0.15, r12m_1=0.25, idx_r3m=0.05, idx_r6m=0.0,
             vol_su_giu=1.1, vol_20_60=1.0, rev_su30=6, rev_giu30=2, reazione_utili=0.025, giorni_da_utili=20,
             giorni_a_utili=40)
    d.update(k)
    return d


def test_trading_pilastri():
    u = {"A": _tec(), "B": _tec(r3m=-0.05, r6m=-0.10, r12m_1=-0.2, prezzo=80.0, mm50=85.0),
         "C": _tec(r3m=0.0, r6m=0.0, r12m_1=0.0), "D": _tec(), "E": _tec(r12m_1=None)}
    r = pt.trading_universo(u, P)
    a = r["A"]["pilastri"]
    assert a["Trend"] == 100 and r["A"]["stato_trend"] == "Rialzista"
    comp = 0.4 * 0.25 + 0.3 * 0.15 + 0.3 * 0.10
    assert r["A"]["mom_composito"] == ap(comp) and r["A"]["mom_rango"] == ap(2 / 3)      # 4 titoli col dato
    assert a["Momentum"] == ap(50 * 2 / 3 + 0.5 * 100 * (comp + 0.15) / 0.5)
    med = 0.10                                                                            # mediana di 5 titoli
    assert r["A"]["mediana_settore_3m"] == ap(med)
    assert a["Forza relativa"] == ap((75 + 100 + 50) / 3)
    assert a["Oscillatori"] == ap(0.6 * 100 + 0.4 * 100)
    assert a["Volumi"] == ap(0.7 * 50 + 0.3 * 50)
    assert a["Catalizzatori"] == ap((75 + 75) / 2)
    st = r["A"]["setup"]                                   # rottura: massimo a 20 sedute entro 1 ATR
    assert st["tipo"] == "Rottura" and st["ingresso"] == ap(101.2) and st["stop"] == ap(97.2)
    assert st["obiettivo"] == ap(109.2) and st["rr"] == ap(2.0) and st["valido"]
    assert a["Assetto e rischio"] == ap(0.5 * 100 + 0.25 * 100 + 0.25 * 50)   # 1% dal massimo, ATR 2%, R/R 2
    tot = sum(P["pesi_b"][n] * a[n] for n in a) / 100
    assert r["A"]["punteggio"] == pt.arrotonda(tot, 1) and r["A"]["segnale"] == "Setup attivo"
    assert r["A"]["n_azioni"] == math.floor(min(500 / 4.0, 5000 / 101.2))
    # B: sotto tutte le medie -> ribassista, nessun setup, "Evitare"
    assert r["B"]["pilastri"]["Trend"] == 15 and r["B"]["stato_trend"] == "Ribassista"
    assert r["B"]["setup"]["tipo"] is None and r["B"]["segnale"] == "Evitare" and r["B"]["mom_rango"] == 0
    # E: momentum mancante -> punteggio insufficiente
    assert r["E"]["punteggio"] is None and r["E"]["segnale"] == pt.INSUFF


def test_trading_setup_e_regole():
    # ritracciamento: prezzo tra mm50 - 0,5 ATR e mm20 + 0,5 ATR, RSI 40-60; obiettivo ridotto alla resistenza
    t = _tec(prezzo=97.0, max20=104.0, max52=120.0, rsi=50.0, resistenze=[99.0, 103.5, 110.0])
    s = pt.setup_operativo(t, P)
    assert s["tipo"] == "Ritracciamento" and s["ingresso"] == 97.0 and s["stop"] == 93.0
    assert s["obiettivo"] == 99.0 and s["rr"] == ap(0.5) and not s["valido"]            # sotto 1,5: non valido
    s = pt.setup_operativo(dict(t, resistenze=[103.5]), P)
    assert s["obiettivo"] == 103.5 and s["rr"] == ap(1.625) and s["valido"]
    assert pt.setup_operativo(dict(t, rsi=65.0), P)["tipo"] is None                     # RSI fuori fascia
    assert pt.setup_operativo(dict(t, mm50=80.0, mm200=90.0), P)["tipo"] is None        # media 50 < media 200
    # fasce RSI
    f = P["rsi_fasce"]
    assert [pt._rsi_punti(x, f) for x in (20, 30, 44.9, 45, 55, 69, 70, 79, 80, 95)] == \
           [10, 35, 35, 65, 100, 100, 60, 60, 25, 25]
    # punteggio alto senza setup -> in osservazione; volume relativo invertito se il mese e' negativo
    r = pt.trading_universo({"A": _tec(max20=110.0, max52=110.0, rsi=65.0), "B": _tec(r3m=0.0), "C": _tec(r3m=0.2),
                             "D": _tec()}, P)
    assert r["A"]["setup"]["tipo"] is None and r["A"]["segnale"] == "In osservazione"
    r = pt.trading_universo({"A": _tec(r1m=-0.01, vol_20_60=1.3)}, P)
    assert r["A"]["pilastri"]["Volumi"] == ap(0.7 * 50 + 0.3 * 0)
    assert r["A"]["pilastri"]["Momentum"] == ap(25 + 0.5 * pt.punti(0.175, -0.15, 0.35))  # un solo titolo: rango 0,5
    assert r["A"]["mediana_settore_3m"] is None                                           # meno di 4 nel settore
    # catalizzatori: reazione vecchia di oltre 60 giorni non vale; trimestrale entro 7 giorni = solo avviso
    r = pt.trading_universo({"A": _tec(giorni_da_utili=90, rev_su30=0, rev_giu30=0, giorni_a_utili=3)}, P)
    assert r["A"]["pilastri"]["Catalizzatori"] is None and r["A"]["avviso_trimestrale"]
    assert r["A"]["copertura"] == ap(0.95) and r["A"]["punteggio"] is not None
    # prezzo vecchio -> dati insufficienti
    assert pt.trading_universo({"A": _tec(prezzo_vecchio=True)}, P)["A"]["segnale"] == pt.INSUFF


# ------------------------------------------------------------------ perche' questo verdetto
def test_motivazione():
    from gsi import motivazioni as mz
    assert [mz.t(x, d) for x, d in ((30.4, 0), (8.0, 1), (8.66, 1), (261.355, 2), (125.5, 2), (-0.04, 1), (2.5, 0))] == \
           ["30", "8", "8.7", "261.36", "125.5", "0", "3"]
    assert mz.frase("Q1", 0.30, "STD") == "rendimento sul capitale medio 30%"
    assert mz.frase("Q1", 0.12, "BAN") == "ROE medio 12%"
    assert mz.frase("Q3", 0.55, "BAN") == "cost/income 55%" and mz.frase("Q3", 0.95, "ASS") == "combined ratio 95%"
    assert mz.frase("F1", 99.0, "STD") == "EBITDA negativo" and mz.frase("F1", -0.7, "STD") == "più cassa che debiti"
    assert mz.frase("F1", 1.234, "STD") == "debito netto pari a 1.2 volte l'EBITDA"
    assert mz.frase("F1", 0.013, "STD") == "debito netto quasi nullo"
    assert mz.frase("F2", 99.0, "STD") == "interessi coperti dalla cassa netta"
    assert mz.frase("F4", 9.99, "STD") == "dividendi non coperti" and mz.frase("F4", 0.6, "REIT") == "dividendi pari al 60% dell'FFO"
    assert mz.frase("G1", -0.031, "STD") == "ricavi -3.1% l'anno" and mz.frase("G1", 0.1, "STD") == "ricavi +10% l'anno"
    assert mz.frase("G3", -0.0002, "STD") == "numero di azioni stabile"
    assert mz.frase("G3", -0.024, "STD") == "azioni in calo del 2.4% l'anno (riacquisti)"
    b = pt.buffett(_ing(prezzo=10.0), P)
    m = mz.motivazione(_ing(prezzo=10.0), b, P)
    assert m["testo"].startswith("Qualità: classe A (") and "per questa strategia è un acquisto." in m["testo"]
    assert "rendimento sul capitale medio 25%" in m["forti"] and m["deboli"] == ""
    m = mz.motivazione(_ing(), pt.buffett(_ing(), P), P)
    assert "per comprare il prezzo dovrebbe scendere a" in m["testo"]
    q = _ing(Q1=0.06, Q2=0.0, Q3=0.05, Q4=0.06, Q5=0.5, Q6=0.2, F1=4.0, F2=2.0, F3=0.4, F4=1.0, G1=0.0, G2=0.0, G3=0.03, G4=0.05)
    m = mz.motivazione(q, pt.buffett(q, P), P)
    assert "non è abbastanza buona a nessun prezzo" in m["testo"] and "Punti di forza: nessuno in particolare." in m["testo"]
    n = _ing(flusso_ps=-2.0)
    assert "non è stimabile" in mz.motivazione(n, pt.buffett(n, P), P)["testo"]
    s = _ing(G1=None, G2=None)
    assert "pilastri: Crescita e allocazione del capitale." in mz.motivazione(s, pt.buffett(s, P), P)["testo"]
    c = mz.motivazione(_ing(), pt.buffett(_ing(), P, {"correzione": -4}), P, {"correzione": -4, "motivazione": "concorrenza"})
    assert "Correzione qualitativa: -4 punti (concorrenza)." in c["testo"]
    r = _ing(F1=5.0)
    assert mz.motivazione(r, pt.buffett(r, P), P)["testo"].endswith("Segnali di rischio: Leva finanziaria alta.")


# ------------------------------------------------------------------ prevedibilita' a 10 anni
def test_prevedibilita():
    from gsi import motivazioni as mz
    from gsi.prevedibilita import PREVEDIBILITA, livello_usato, normalizza
    assert len(PREVEDIBILITA) == 120 and all(v["livello"] in ("Alta", "Media", "Bassa") and v["fonti"] for v in PREVEDIBILITA.values())
    assert normalizza(" media ") == "Media" and normalizza("forse") is None and normalizza(None) is None
    assert livello_usato("ADBE", {"prevedibilita": "alta"}) == ("Alta", "tuo giudizio")
    assert livello_usato("ADBE", {}) == (PREVEDIBILITA["ADBE"]["livello"], "giudizio di Claude")
    assert livello_usato("NON_ESISTE", {}) == (None, "nessun giudizio")
    base = pt.buffett(_ing(prezzo=10.0), P)
    assert base["prevedibilita"] is None and base["verdetto"] == "Comprerei"
    m = pt.buffett(_ing(prezzo=10.0), P, {"prevedibilita": "Media"})
    g1a, g1m = base["scenari"]["Base"]["g1"], m["scenari"]["Base"]["g1"]
    assert g1m == ap(g1a * 0.5) and m["valore_base"] < base["valore_base"]
    assert m["richiesto"] == ap(0.25 + 0.15) and m["prezzo_acquisto"] == ap(m["valore_base"] * 0.60)
    b = pt.buffett(_ing(prezzo=10.0), P, {"prevedibilita": "Bassa"})
    assert b["verdetto"] == "Non comprerei: troppo difficile da prevedere" and b["prezzo_acquisto"] is None
    assert b["scenari"]["Base"]["g1"] == 0 and b["punteggio"] is not None
    # crescita negativa: la prevedibilita' non la riduce
    n = pt.buffett(_ing(cagr_ricavi=-0.05), P, {"prevedibilita": "Media"})
    assert n["scenari"]["Base"]["g1"] == ap(-0.02 * 1.4)
    # banche: crescita del patrimonio dimezzata
    i = _ing(modello="BAN", valuta_bil="EUR", tbv_ps=50.0, roe_norm=0.12, F4=0.5)
    assert pt.valore_intrinseco(i, P, "Base", "Media")["g_patrimonio"] == ap(0.03)
    t = mz.motivazione(_ing(prezzo=10.0), b, P, {"prevedibilita": "Bassa"})["testo"]
    assert "Prevedibilità a 10 anni: Bassa (tuo giudizio)." in t and "non compra a nessun prezzo" in t
    t = mz.motivazione(_ing(), m, P)["testo"]
    assert "richiesto per la classe A con prevedibilità media" in t
    assert "Prevedibilità a 10 anni: nessun giudizio." in mz.motivazione(_ing(), base, P)["testo"]
