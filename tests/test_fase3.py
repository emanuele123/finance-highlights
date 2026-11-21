"""Collaudi del cruscotto Excel sulla versione dimostrativa (societa' inventate): formule senza errori,
coincidenza con il calcolo Python, conservazione delle celle gialle. Il ricalcolo richiede LibreOffice."""
import json
import shutil
from datetime import date

import pytest
from openpyxl import load_workbook

from gsi import excel, verifica
from gsi.demo import UNIVERSO_DEMO, crea_archivio
from gsi.parametri import predefiniti

OGGI = date(2026, 11, 21)
serve_lo = pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")),
                              reason="LibreOffice non installato")


@pytest.fixture(scope="module")
def ambiente(tmp_path_factory):
    cart = tmp_path_factory.mktemp("demo")
    con = crea_archivio(cart / "demo.sqlite", OGGI)
    percorso = cart / "demo.xlsx"
    lib, ingressi, P, giudizi = excel.genera(con, percorso, OGGI, UNIVERSO_DEMO, True)
    return dict(con=con, percorso=percorso, lib=lib, ingressi=ingressi, cart=cart)


def _mappa(wb):
    return {r[0]: (r[1], r[2]) for r in wb["_MAPPA"].iter_rows(min_row=2, values_only=True)}


def test_struttura_e_convenzioni(ambiente):
    wb = load_workbook(ambiente["percorso"])
    assert wb.sheetnames[0] == "CRUSCOTTO" and wb["_MAPPA"].sheet_state == "hidden"
    for nome in ("SCREENER", "SCHEDA", "BUFFETT", "VALUTAZIONE", "TRADING", "PERFORMANCE", "GIUDIZI", "PARAMETRI",
                 "UNIVERSO", "DATI", "QUALITA_DATI"):
        assert nome in wb.sheetnames
    assert "DIMOSTRATIVA" in wb["CRUSCOTTO"]["B1"].value
    # DATI: solo valori importati (nessuna formula), in blu; tutti i caratteri sono Arial
    for riga in wb["DATI"].iter_rows(min_row=3):
        for c in riga:
            assert not (isinstance(c.value, str) and c.value.startswith("="))
            if c.value is not None:
                assert c.font.color.rgb.endswith("0000FF")
    for ws in wb.worksheets:
        for riga in ws.iter_rows(max_row=8):
            for c in riga:
                if c.value is not None and ws.title != "_MAPPA":
                    assert c.font.name == "Arial", (ws.title, c.coordinate)
    # celle gialle: tutte e sole quelle della mappa, mai formule
    m = _mappa(wb)
    assert len(m) > 400
    for chiave, (foglio, cella) in m.items():
        c = wb[foglio][cella]
        assert c.fill.fgColor.rgb.endswith("FFFF00"), chiave
        assert not (isinstance(c.value, str) and c.value.startswith("="))
    # nessuna funzione disponibile solo in Excel 365
    vietate = ("XLOOKUP", "FILTER(", "SORT(", "UNIQUE(", "SEQUENCE(", "LET(", "TEXTJOIN", "IFS(", "XMATCH")
    for ws in wb.worksheets:
        for riga in ws.iter_rows():
            for c in riga:
                if isinstance(c.value, str) and c.value.startswith("="):
                    assert not any(v in c.value for v in vietate), (ws.title, c.coordinate)
    # i collegamenti tra fogli passano dal ticker
    f = wb["BUFFETT"]["F3"].value
    assert "MATCH($A3,DATI!$A$3:" in f and f.startswith("=INDEX(DATI!")


@serve_lo
def test_zero_errori_e_coincidenza_con_python(ambiente):
    r = verifica.verifica_file(ambiente["percorso"], ambiente["ingressi"], ambiente["lib"])
    assert r["formule"] > 5000 and r["errori"] == []
    assert r["confronti"] > 1000 and r["differenze"] == []
    wb = load_workbook(r["ricalcolato"], data_only=True)
    tb = ambiente["lib"].tab["BUFFETT"].cols
    verdetti = {wb["BUFFETT"][f"{tb['verdetto']}{x}"].value for x in range(3, 3 + len(UNIVERSO_DEMO))}
    assert len(verdetti) >= 3                       # la demo esercita piu' rami del verdetto
    assert wb["CRUSCOTTO"]["D5"].value == len(UNIVERSO_DEMO)
    assert wb["SCHEDA"]["B5"].value == UNIVERSO_DEMO[0].nome
    assert isinstance(wb["SCHEDA"]["M4"].value, (int, float))        # serie del grafico


@serve_lo
def test_coincidenza_con_parametri_e_giudizi_modificati(ambiente):
    altro = ambiente["cart"] / "modificato.xlsx"
    wb = load_workbook(ambiente["percorso"])
    m = _mappa(wb)

    def metti(chiave, v):
        foglio, cella = m[chiave]
        wb[foglio][cella] = v
    for percorso, v in ((["metriche", "STD", "Q1", 2], 0.35), (["tassi", "EUR", 0], 0.07), (["scenari", "Base", 0], 0.4),
                        (["pesi_b", "Trend"], 40), (["setup_rottura_atr"], 4.0), (["classe_a"], 60), (["anni_fase"], 3),
                        (["rsi_fasce", 3, 1], 70), (["giorni_esercizio"], 1500), (["quota_flusso", "UTL"], 0.6)):
        metti("P|" + json.dumps(percorso), v)
    metti("GIUDIZI|Q3|DEMO08", 0.5)
    metti("GIUDIZI|F5|DEMO08", 0.15)
    metti("GIUDIZI|correzione|DEMO02", -30)
    wb.save(altro)
    r = verifica.verifica_file(altro, ambiente["ingressi"], ambiente["lib"])
    assert r["errori"] == [] and r["differenze"] == []
    wbv = load_workbook(r["ricalcolato"], data_only=True)
    tb = ambiente["lib"].tab["BUFFETT"].cols
    assert wbv["BUFFETT"][f"{tb['corr']}4"].value == -10            # correzione limitata a +-10
    assert isinstance(wbv["BUFFETT"][f"{tb['p_F5']}10"].value, (int, float))


def test_conservazione_delle_celle_gialle(ambiente):
    con, cart = ambiente["con"], ambiente["cart"]
    percorso = cart / "conserva.xlsx"
    excel.genera(con, percorso, OGGI, UNIVERSO_DEMO, True)
    assert excel.leggi_gialle(percorso) == {} and excel.leggi_gialle(cart / "non_esiste.xlsx") == {}
    wb = load_workbook(percorso)
    m = _mappa(wb)
    wb[m['P|["classe_a"]'][0]][m['P|["classe_a"]'][1]] = 75
    wb[m['P|["metriche", "BAN", "F5", 1]'][0]][m['P|["metriche", "BAN", "F5", 1]'][1]] = 0.10
    wb["SCHEDA"]["B2"] = "DEMO05"
    g = wb["GIUDIZI"]
    # l'utente compila due righe e poi ORDINA il foglio: i dati devono restare agganciati al ticker
    g["D10"], g["F10"], g["G10"], g["H10"] = 0.52, 3, "marchio forte", "tesi di prova"
    for col in "ABCDEFGH":
        g[f"{col}3"], g[f"{col}10"] = g[f"{col}10"].value, g[f"{col}3"].value
    g["A3"], g["A10"] = "DEMO08", "DEMO01"
    wb.save(percorso)
    gialle = excel.leggi_gialle(percorso)
    assert gialle['P|["classe_a"]'] == 75 and gialle["SCHEDA|ticker"] == "DEMO05"
    assert gialle["GIUDIZI|Q3|DEMO08"] == 0.52 and gialle["GIUDIZI|tesi|DEMO08"] == "tesi di prova"
    assert not any(k.endswith("|DEMO01") for k in gialle)
    P = excel.parametri_da_gialle(predefiniti(), gialle)
    assert P["classe_a"] == 75 and P["metriche"]["BAN"]["F5"][1] == 0.10 and P["classe_b"] == 55
    assert excel.giudizi_da_gialle(gialle)["DEMO08"] == {"Q3": 0.52, "correzione": 3, "motivazione": "marchio forte",
                                                         "tesi": "tesi di prova"}
    # rigenerazione: i valori tornano nelle celle del nuovo file, al posto giusto
    excel.genera(con, percorso, OGGI, UNIVERSO_DEMO, True)
    wb2 = load_workbook(percorso)
    m2 = _mappa(wb2)
    assert wb2[m2['P|["classe_a"]'][0]][m2['P|["classe_a"]'][1]].value == 75
    assert wb2["SCHEDA"]["B2"].value == "DEMO05"
    riga = next(r for r in range(3, 30) if wb2["GIUDIZI"].cell(r, 1).value == "DEMO08")
    assert wb2["GIUDIZI"][f"D{riga}"].value == 0.52 and wb2["GIUDIZI"][f"H{riga}"].value == "tesi di prova"
    assert wb2["GIUDIZI"]["D3"].value is None                       # DEMO01 non ha dati manuali
    assert len(excel.leggi_gialle(percorso)) == len(gialle)         # e si conservano ancora al giro successivo
    # un parametro reso testo o svuotato non rompe i calcoli: resta il valore predefinito
    assert excel.parametri_da_gialle(predefiniti(), {'P|["classe_a"]': "abc", 'P|["non_esiste"]': 3})["classe_a"] == 70
