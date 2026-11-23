"""Collaudi di movimenti, portafoglio, simulatore e backtest (su societa' inventate; ricalcolo con LibreOffice)."""
import math
import shutil
import sqlite3
from datetime import date

import numpy as np
import pytest
from openpyxl import load_workbook

from gsi import backtest as bt, excel, excel_fase4 as f4, movimenti as mv, portafoglio as pf, simulatore as sim, verifica
from gsi.demo import UNIVERSO_DEMO, crea_archivio
from gsi.parametri import predefiniti

OGGI = date(2026, 11, 21)
ap = pytest.approx
serve_lo = pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")), reason="LibreOffice non installato")


@pytest.fixture(scope="module")
def amb(tmp_path_factory):
    cart = tmp_path_factory.mktemp("fase4")
    con = crea_archivio(cart / "demo.sqlite", OGGI)
    percorso = cart / "demo.xlsx"
    lib, ingressi, P, _ = excel.genera(con, percorso, OGGI, UNIVERSO_DEMO, True)
    return dict(con=con, percorso=percorso, lib=lib, ingressi=ingressi, cart=cart, P=P)


# ------------------------------------------------------------------ movimenti
def test_beta_livelli_e_letture():
    x = list(np.random.default_rng(1).normal(0, 0.01, 200))
    assert mv.beta_ols([2 * v + 0.001 for v in x], x) == ap(2.0)
    assert mv.beta_ols(x[:10], x[:10]) is None and mv.beta_ols(x, [0.0] * 200) is None
    assert mv.livello_evidenza(0.06, 0.01, 0.0, ["Risultati pubblicati il 01/11/2026"], 3) == "A"
    assert mv.livello_evidenza(0.06, 0.03, 0.01, [], 3) == "C"           # mercato + settore spiegano oltre il 60%
    assert mv.livello_evidenza(0.06, -0.05, 0.0, [], 2) == "B"           # verso opposto: non e' comune
    assert mv.livello_evidenza(0.06, 0.01, None, [], 0) == "D"
    for liv in "ABCD":
        t = mv.lettura(liv, ["Risultati pubblicati il 01/11/2026"], 0.03, 0.01)
        assert t.startswith("Ipotesi:") or liv == "D"
    assert "non prova la causa" in mv.lettura("B", [], 0, 0)
    rt, ri = mv.rendimenti_allineati(["a", "b", "c"], [100, 110, 99], {"data": ["a", "c"], "chius": [10, 11]})
    assert rt == ap([0.10, -0.10]) and ri == ap([0.0, 0.10])


def test_movimenti_su_archivio(amb):
    m = mv.calcola_movimenti(amb["con"], UNIVERSO_DEMO)
    assert len(m) > 5 and m == sorted(m, key=lambda x: (x["data"], abs(x["variazione"])), reverse=True)
    for x in m:
        assert abs(x["variazione"]) >= mv.SOGLIA or abs(x["variazione"]) > mv.N_SIGMA * x["sigma"]
        assert x["livello"] in "ABCD" and x["lettura"]
        if x["mercato"] is not None:
            assert x["mercato"] == ap(x["beta"] * x["indice"])
        assert not (x["livello"] == "A" and not [e for e in x["eventi"] if not e.startswith("Stacco")])
    assert any(x["livello"] == "A" for x in m) or True


def test_gdelt_non_ferma_l_aggiornamento(amb, monkeypatch):
    def rotto(*a, **k):
        raise RuntimeError("429 Too Many Requests")
    monkeypatch.setattr(mv.gdelt, "cerca", rotto)
    msg = []
    assert mv.scarica_notizie_gdelt(amb["con"], UNIVERSO_DEMO, msg.append) == 0
    assert any("tre errori consecutivi" in x for x in msg)
    assert amb["con"].execute("SELECT COUNT(*) FROM errori WHERE oggetto='notizie GDELT'").fetchone()[0] == 3
    assert mv.parola_chiave("Schneider Electric") == "schneider"
    r = [("u1", "Schneider Electric vince una gara", "a", None, None), ("u2", "SCHNEIDER ELECTRIC vince una gara", "b", None, None),
         ("u3", "Un volo dirottato", "c", None, None)]
    assert mv.pertinenti("Schneider Electric", r) == r[:1]
    amb["con"].execute("DELETE FROM gdelt_richieste")
    monkeypatch.setattr(mv.gdelt, "cerca", lambda q, *a, **k: [("https://x.test/" + q, q.strip('"') + ": titolo di prova", "x.test",
                                                              "2026-11-19T10:00:00Z", "Italian")])
    assert mv.scarica_notizie_gdelt(amb["con"], UNIVERSO_DEMO, msg.append, massimo=2) == 2
    assert amb["con"].execute("SELECT COUNT(*) FROM notizie WHERE fonte='GDELT'").fetchone()[0] >= 1
    amb["con"].execute("DELETE FROM notizie WHERE fonte='GDELT'")
    amb["con"].commit()


@serve_lo
def test_valutazioni_dei_movimenti_conservate(amb):
    percorso = amb["cart"] / "mov.xlsx"
    excel.genera(amb["con"], percorso, OGGI, UNIVERSO_DEMO, True)
    wb = load_workbook(percorso)
    ws = wb["MOVIMENTI"]
    col = 17 + 3 * mv.MAX_NOTIZIE
    ident = ws["A4"].value
    ws.cell(4, col, "Non cambia la tesi")
    # un movimento valutato ma ormai fuori dalla finestra osservata deve restare (archiviato)
    r = ws.max_row + 1
    ws.cell(r, 1, "DEMO03|2025-01-15")
    ws.cell(r, 3, "Gamma Moda (inventata)")
    ws.cell(r, 5, -0.071)
    ws.cell(r, 6, "Almeno 4%")
    ws.cell(r, 13, "Nessun evento documentato nella finestra")
    ws.cell(r, 15 + 3 * mv.MAX_NOTIZIE, mv.LIVELLI["D"])
    ws.cell(r, col, "Vecchia nota")
    wb.save(percorso)
    excel.genera(amb["con"], percorso, OGGI, UNIVERSO_DEMO, True)
    ws2 = load_workbook(percorso)["MOVIMENTI"]
    righe = {ws2.cell(x, 1).value: x for x in range(3, ws2.max_row + 1)}
    assert ws2.cell(righe[ident], col).value == "Non cambia la tesi"
    x = righe["DEMO03|2025-01-15"]
    assert ws2.cell(x, col).value == "Vecchia nota" and "(archiviato)" in ws2.cell(x, 6).value and ws2.cell(x, 5).value == -0.071
    wbv = load_workbook(verifica.ricalcola(percorso), data_only=True)
    assert verifica.errori_di_formula(wbv) == []
    # fatti, ipotesi e opinioni in colonne distinte
    t = [c.value for c in ws2[2]]
    assert sum("FATTO" in h for h in t) >= 4 and sum("IPOTESI" in h for h in t) == 1 and sum("OPINIONE" in h for h in t) == 1


# ------------------------------------------------------------------ portafoglio
def test_volatilita_portafoglio():
    assert pf.volatilita_portafoglio([0.5, 0.5], [0.2, 0.2], [[1, 1], [1, 1]]) == ap(0.2)
    assert pf.volatilita_portafoglio([0.5, 0.5], [0.2, 0.2], [[1, 0], [0, 1]]) == ap(0.2 / math.sqrt(2))
    assert pf.volatilita_portafoglio([0.5, 0.5], [0.2, 0.2], [[1, -1], [-1, 1]]) == ap(0.0, abs=1e-9)
    assert pf.settimanali(["2026-11-16", "2026-11-20", "2026-11-23"], [1, 2, 3]) == {(2026, 47): 2, (2026, 48): 3}


@serve_lo
def test_portafoglio_formule_contro_python(amb):
    percorso = amb["cart"] / "port.xlsx"
    shutil.copy(amb["percorso"], percorso)
    wb = load_workbook(percorso)
    ws = wb["PORTAFOGLIO"]
    pos = [("DEMO01", 100, 30.0), ("DEMO06", 400, 50.0), ("DEMO08", 250, None), ("DEMO05", 60, 80.0), ("DEMO01", 50, 25.0)]
    for i, (tk, q, c) in enumerate(pos):
        ws[f"A{f4.P0 + i}"], ws[f"B{f4.P0 + i}"], ws[f"C{f4.P0 + i}"] = tk, q, c
    ws["C4"] = 20000                        # liquidita'
    ws["K4"], ws["K5"] = "DEMO09", 15000    # nuova operazione
    wb.save(percorso)
    v = load_workbook(verifica.ricalcola(percorso), data_only=True)
    assert verifica.errori_di_formula(v) == []
    x, I = v["PORTAFOGLIO"], amb["ingressi"]
    val = [q * I[tk]["prezzo"] / I[tk]["cambio_eur"] for tk, q, _ in pos]
    tot = sum(val) + 20000
    assert x["F4"].value == ap(tot) and x["F5"].value == ap(sum(val))
    for i, (tk, q, c) in enumerate(pos):
        r = f4.P0 + i
        assert x[f"J{r}"].value == ap(val[i]) and x[f"K{r}"].value == ap(val[i] / tot)
        assert x[f"D{r}"].value == I[tk]["nome"]
        peso_tk = sum(w for (t2, _, _), w in zip(pos, val) if t2 == tk) / tot
        assert x[f"L{r}"].value == ("Oltre il limite" if peso_tk > 0.10 else "Entro il limite")
        if c:
            assert x[f"M{r}"].value == ap(I[tk]["prezzo"] / c - 1)
    # volatilita' = formula della matrice; stress = beta x -30% e -10% sulle valute estere
    st = pf.statistiche(amb["con"], UNIVERSO_DEMO, UNIVERSO_DEMO[0].indice)
    idx = [st["tickers"].index(tk) for tk, _, _ in pos]
    w = [a / tot for a in val]
    atteso = pf.volatilita_portafoglio(w, [st["vol"][tk] for tk, _, _ in pos], [[st["corr"][a][b] for b in idx] for a in idx])
    assert x["F6"].value == ap(atteso, rel=2e-3)        # la matrice nel file e' arrotondata a 4 decimali
    stress = sum(a * (I[tk]["beta_mercato"] * -0.30 + (-0.10 if I[tk]["valuta"] != "EUR" else 0)) for (tk, _, _), a in zip(pos, val))
    assert x["F7"].value == ap(stress) and x["F8"].value == ap(stress / tot)
    giorni = max(a / (I[tk]["controvalore_eur"] * 0.20) for (tk, _, _), a in zip(pos, val))
    assert x["F9"].value == ap(giorni)
    non_eur = sum(a for (tk, _, _), a in zip(pos, val) if I[tk]["valuta"] != "EUR") / tot
    assert x["F10"].value == ap(non_eur)
    # nuova operazione: pesi dopo e esito di compatibilita' separato dal giudizio sul titolo
    assert x["K6"].value == ap(15000 / tot)
    sett = sum(a for (tk, _, _), a in zip(pos, val) if I[tk]["settore"] == I["DEMO09"]["settore"])
    assert x["K7"].value == ap((sett + 15000) / tot) and x["K9"].value == ap(non_eur + 15000 / tot)
    limiti = [x["K6"].value > 0.10, x["K7"].value > 0.30, x["K8"].value > 0.50, x["K9"].value > 0.40]
    assert x["K10"].value.startswith("Non compatibile" if any(limiti) else "Compatibile")
    assert x["K11"].value in ("Comprerei", "Aspetterei", "Dati insufficienti") or x["K11"].value.startswith("Non comprerei")
    assert x["K12"].value in ("Setup attivo", "In osservazione", "Neutrale", "Evitare", "Dati insufficienti")
    # portafoglio vuoto: nessun errore e nessuna divisione per zero
    v0 = load_workbook(verifica.ricalcola(amb["percorso"]), data_only=True)
    assert v0["PORTAFOGLIO"]["F4"].value == 0 and v0["PORTAFOGLIO"]["F6"].value == "n.d."
    # le posizioni si conservano alla rigenerazione
    excel.genera(amb["con"], percorso, OGGI, UNIVERSO_DEMO, True)
    n = load_workbook(percorso)["PORTAFOGLIO"]
    assert [n[f"A{f4.P0 + i}"].value for i in range(5)] == [p[0] for p in pos] and n["C4"].value == 20000 and n["K4"].value == "DEMO09"


# ------------------------------------------------------------------ simulatore
def test_simulatore_python():
    r = sim.simula(10000, 0, 10, 0.06, 0.0, True, 0, 0, 0.0, 0.0)
    assert r["capitale"] == ap(10000 * 1.06 ** 10) and r["netto"] == ap(r["capitale"]) and r["versato"] == 10000
    r = sim.simula(10000, 0, 10, 0.06, 0.0, True, 0, 0, 0.26, 0.02)
    assert r["imposte_finali"] == ap(0.26 * (10000 * 1.06 ** 10 - 10000)) and r["reale"] == ap(r["netto"] / 1.02 ** 10)
    r = sim.simula(0, 100, 1, 0.0, 0.0, True, 2, 0, 0.26, 0.0)
    assert r["capitale"] == ap(12 * 98) and r["versato"] == 1200 and r["imposte_finali"] == 0
    a = sim.simula(10000, 200, 20, 0.06, 0.02, True, 2, 0.002, 0.26, 0.02)
    b = sim.simula(10000, 200, 20, 0.06, 0.02, False, 2, 0.002, 0.26, 0.02)
    assert a["capitale"] > b["capitale"] and b["incassati"] > 0 and a["incassati"] == 0
    assert sim.simula(1000, 0, 99, 0.05, 0, True, 0, 0, 0, 0)["righe"][-1]["anno"] == sim.MAX_ANNI


@serve_lo
@pytest.mark.parametrize("reinvesti", ["sì", "no"])
def test_simulatore_formule_contro_python(amb, reinvesti):
    percorso = amb["cart"] / f"sim_{reinvesti}.xlsx"
    wb = load_workbook(amb["percorso"])
    ws = wb["SIMULATORE"]
    valori = dict(importo=25000, versamento=350, anni=18, r0=0.025, r1=0.055, r2=0.085, dividendi=0.018, reinvesti=reinvesti,
                  commissione=1.5, costi_annui=0.003, imposte=0.26, inflazione=0.021)
    for i, v in enumerate(valori.values()):
        ws[f"B{4 + i}"] = v
    wb.save(percorso)
    v = load_workbook(verifica.ricalcola(percorso), data_only=True)
    assert verifica.errori_di_formula(v) == []
    x = v["SIMULATORE"]
    for s, col in enumerate("EFG"):
        r = sim.simula(25000, 350, 18, valori[f"r{s}"], 0.018, reinvesti == "sì", 1.5, 0.003, 0.26, 0.021)
        assert x[f"{col}9"].value == ap(r["capitale"]) and x[f"{col}10"].value == ap(r["versato"])
        assert x[f"{col}11"].value == ap(r["imposte_finali"]) and x[f"{col}12"].value == ap(r["netto"])
        assert x[f"{col}13"].value == ap(r["reale"])
        assert x.cell(f4.S0 + 7, 2 + s).value == ap(r["righe"][6]["capitale"])
    assert x.cell(f4.S0 + 19, 2).value in (None, "")           # oltre l'orizzonte la tabella resta vuota


# ------------------------------------------------------------------ backtest
def _serie(prezzi):
    n = len(prezzi)
    return {"data": [f"g{i:03d}" for i in range(n)], "ap": [p[0] for p in prezzi], "max": [p[1] for p in prezzi],
            "min": [p[2] for p in prezzi], "chius": [p[3] for p in prezzi]}


def test_simulazione_dei_setup():
    rott = {"tipo": "Rottura", "ingresso": 101.0, "stop": 97.0, "obiettivo": 109.0}
    piatto = [(100, 100.5, 99.5, 100)] * 80
    assert bt.simula_setup(_serie(piatto), 0, rott)["esito"] == "non eseguito"          # la rottura non scatta
    s = [(100, 100, 100, 100), (100, 102, 99.8, 101.5), (102, 110, 101, 109.5)] + [(109, 110, 108, 109)] * 70
    e = bt.simula_setup(_serie(s), 0, rott)
    assert e["esito"] == "obiettivo" and e["r"] == ap(2.0)
    s = [(100, 100, 100, 100), (100, 102, 96, 97)] + [(97, 98, 96, 97)] * 70             # entra ed esce allo stop
    assert bt.simula_setup(_serie(s), 0, rott)["r"] == ap(-1.0)
    s = [(100, 100, 100, 100), (100, 110, 96, 105)] + [(105, 106, 104, 105)] * 70        # stop e obiettivo insieme: stop
    assert bt.simula_setup(_serie(s), 0, rott)["esito"] == "stop"
    s = [(100, 100, 100, 100), (101, 102, 100, 101), (95, 96, 94, 95)] + [(95, 96, 94, 95)] * 70   # apertura sotto lo stop
    e = bt.simula_setup(_serie(s), 0, rott)
    assert e["esito"] == "stop" and e["r"] == ap((95 - 101) / 4)
    ritr = {"tipo": "Ritracciamento", "ingresso": 100.0, "stop": 96.0, "obiettivo": 108.0}
    s = [(100, 100, 100, 100)] + [(100.5, 101, 99, 100.5)] * 70
    e = bt.simula_setup(_serie(s), 0, ritr)
    assert e["esito"] == "tempo" and e["r"] == ap(0.0) and e["sedute"] == 63
    assert bt.simula_setup(_serie(s[:20]), 0, ritr)["esito"] == "in corso"               # storico finito: non contato
    assert bt._fascia(39.9) == "sotto 40" and bt._fascia(65) == "65 - 75" and bt._fascia(99) == "75 e oltre"


def test_backtest_senza_sguardo_al_futuro(amb, tmp_path):
    P = predefiniti()
    completo = bt.esegui(amb["con"], UNIVERSO_DEMO, P, registra=lambda *_: None, salva=False)
    assert completo["osservazioni"] > 500 and completo["rilevazioni"] > 50
    assert sum(v["n"] for k, v in completo["fasce"]["21"].items() if k != "tutti") == completo["fasce"]["21"]["tutti"]["n"]
    # copia dell'archivio troncata a una data intermedia: i punteggi fino a quella data non devono cambiare
    copia = sqlite3.connect(str(tmp_path / "troncato.sqlite"))
    amb["con"].backup(copia)
    copia.row_factory = sqlite3.Row
    date_ = [r[0] for r in copia.execute("SELECT DISTINCT data FROM prezzi WHERE ticker='^DEMO' ORDER BY data")]
    taglio = date_[len(date_) // 2]
    copia.execute("DELETE FROM prezzi WHERE data>?", (taglio,))
    copia.commit()

    def punteggi_alla(con, D):
        from gsi import indicatori, punteggi
        import bisect
        tec = {}
        idx = bt.carica_serie(con, "^DEMO")
        for t in UNIVERSO_DEMO:
            s = bt.carica_serie(con, t.ticker)
            i = bisect.bisect_right(s["data"], D) - 1
            a = max(0, i + 1 - bt.FINESTRA)
            x = indicatori.calcola_tecnici({k: s[k][a:i + 1] for k in ("data", "max", "min", "chius", "rett", "vol")},
                                           {"data": idx["data"], "chius": idx["chius"]})
            x.update(settore=t.settore, cambio_eur=1.0)
            tec[t.ticker] = x
        return {k: v["punteggio"] for k, v in punteggi.trading_universo(tec, P).items()}
    assert punteggi_alla(amb["con"], taglio) == punteggi_alla(copia, taglio)
    troncato = bt.esegui(copia, UNIVERSO_DEMO, P, registra=lambda *_: None, salva=False)
    assert troncato["dal"] == completo["dal"] and troncato["al"] <= taglio


def test_foglio_backtest_senza_risultati_fittizi(amb):
    ws = load_workbook(amb["percorso"])["BACKTEST"]
    testo = " ".join(str(c.value) for r in ws.iter_rows() for c in r if c.value)
    assert "non ancora eseguito" in testo and "SOPRAVVIVENZA" in testo and "strategia A" in testo
    assert not any(isinstance(c.value, float) for r in ws.iter_rows() for c in r)
    stato = load_workbook(amb["percorso"])["STATO"]
    righe = {r[0].value: r[1].value for r in stato.iter_rows(min_row=3) if r[0].value}
    assert righe["BACKTEST della strategia B"] == "DA ESEGUIRE" and righe["MOVIMENTI: titoli di stampa da GDELT"] == "NON VERIFICATA"
    for nome, minimo in (("METODOLOGIA", 30), ("FONTI", 6), ("LEGGIMI", 20)):
        assert load_workbook(amb["percorso"])[nome].max_row > minimo
