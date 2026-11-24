"""Controllo incrociato: i punteggi e i valori calcolati dalle formule del cruscotto (ricalcolato con
LibreOffice in modalita' headless) devono coincidere con quelli calcolati in Python, titolo per titolo.
Verifica anche che nel file ricalcolato non ci sia alcun errore di formula."""
from __future__ import annotations
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from .excel import R0, SIGLE_SCENARI, giudizi_da_gialle, leggi_gialle, parametri_da_gialle
from .parametri import predefiniti
from . import motivazioni, punteggi

ERRORI = ("#VALUE!", "#DIV/0!", "#REF!", "#NAME?", "#N/A", "#NUM!", "#NULL!", "Err:")


def ricalcola(percorso, cartella=None) -> Path:
    """Copia ricalcolata del file (l'originale non viene toccato). Richiede LibreOffice (soffice)."""
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise RuntimeError("LibreOffice non trovato: impossibile ricalcolare il cruscotto")
    cartella = Path(cartella or tempfile.mkdtemp(prefix="gsi_ricalcolo_"))
    profilo = cartella / "profilo"
    r = subprocess.run([exe, "--headless", "--norestore", f"-env:UserInstallation={profilo.as_uri()}",
                        "--convert-to", "xlsx", "--outdir", str(cartella), str(percorso)],
                       capture_output=True, text=True, timeout=600)
    out = cartella / Path(percorso).name
    if not out.exists():
        raise RuntimeError(f"Ricalcolo non riuscito: {r.stdout} {r.stderr}")
    return out


def errori_di_formula(wb) -> list[str]:
    out = []
    for ws in wb.worksheets:
        for riga in ws.iter_rows():
            for c in riga:
                if isinstance(c.value, str) and c.value.startswith(ERRORI):
                    out.append(f"{ws.title}!{c.coordinate}: {c.value}")
    return out


def conta_formule(percorso) -> int:
    from openpyxl.worksheet.formula import ArrayFormula
    wb = load_workbook(percorso)
    return sum(1 for ws in wb.worksheets for riga in ws.iter_rows() for c in riga
               if (isinstance(c.value, str) and c.value.startswith("=")) or isinstance(c.value, ArrayFormula))


def leggi_foglio(wb_val, wb_for, nome: str, chiavi: dict[str, str]) -> dict:
    """-> {ticker: {chiave: valore}} leggendo le colonne per lettera."""
    ws = wb_val[nome]
    out = {}
    for r in range(R0, ws.max_row + 1):
        tk = ws.cell(r, 1).value
        if tk:
            out[tk] = {k: ws[f"{L}{r}"].value for k, L in chiavi.items()}
    return out


def _uguali(a, b, tol=1e-6) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        a, b = (1 if a is True else 0 if a is False else a), (1 if b is True else 0 if b is False else b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    return a == b


def _py(x, vuoto="n.d."):
    return vuoto if x is None else x


def confronta(ingressi: dict, lib, percorso_ricalcolato, P: dict, giudizi: dict) -> tuple[int, list[str]]:
    """Confronta Python e formule per ogni titolo. -> (numero di confronti, elenco delle differenze)"""
    from .calcola import applica_eta
    applica_eta(ingressi, P)                      # le soglie di eta' dei dati sono parametri
    wb = load_workbook(percorso_ricalcolato, data_only=True)
    A = {k: punteggi.buffett(i, P, giudizi.get(k)) for k, i in ingressi.items()}
    B = punteggi.trading_universo(ingressi, P)
    tb, tv, tt = lib.tab["BUFFETT"], lib.tab["VALUTAZIONE"], lib.tab["TRADING"]
    xb = leggi_foglio(wb, None, "BUFFETT", tb.cols)
    xv = leggi_foglio(wb, None, "VALUTAZIONE", tv.cols)
    xt = leggi_foglio(wb, None, "TRADING", tt.cols)
    diff, n = [], 0

    def chk(tk, cosa, py, xl):
        nonlocal n
        n += 1
        if not _uguali(py, xl):
            diff.append(f"{tk} {cosa}: Python={py!r} Excel={xl!r}")

    for tk, i in ingressi.items():
        a, b, eb, ev, et = A[tk], B[tk], xb[tk], xv[tk], xt[tk]
        # --- valore intrinseco, tre scenari, passaggio per passaggio
        for scen, s in SIGLE_SCENARI.items():
            v = a["scenari"][scen]
            chk(tk, f"valore {scen}", _py(v["valore"]), ev[f"valore_{s}"])
            chk(tk, f"r {scen}", v["r"], ev[f"r_{s}"])
            chk(tk, f"gT {scen}", v["gT"], ev[f"gT_{s}"])
            if isinstance(v["valore"], (int, float)) and "va_fase1" in v:
                for kp, kx in (("g1", "g1"), ("g2", "g2"), ("flusso_partenza", "f0"), ("va_fase1", "va1"), ("va_fase2", "va2"),
                               ("valore_terminale", "vt"), ("va_terminale", "vavt"), ("cassa_riconosciuta", "cassa")):
                    chk(tk, f"{kp} {scen}", v[kp], ev[f"{kx}_{s}"])
            if "extra_rendimento" in v:
                for kp, kx in (("roe", "roe"), ("g_patrimonio", "gB"), ("extra_rendimento", "extra")):
                    chk(tk, f"{kp} {scen}", v[kp], ev[f"{kx}_{s}"])
        # --- Buffett Score
        for m, val in a["valori"].items():
            chk(tk, f"valore {m}", _py(val), eb["v_" + m])
            if m in a["punti"]:
                chk(tk, f"punti {m}", _py(a["punti"][m]), eb["p_" + m])
        for L in "QFGV":
            chk(tk, f"pilastro {L}", _py(a["pilastri"][L]), eb["pil_" + L])
            chk(tk, f"copertura {L}", a["copertura"][L], eb["cop_" + L])
        chk(tk, "qualità composita", _py(a["qualita_composita"]), eb["qc"])
        chk(tk, "classe", _py(a["classe"]), eb["classe"])
        chk(tk, "valutazione usata", _py(a["valutazione_usata"]), eb["v_usata"])
        chk(tk, "Buffett Score", _py(a["punteggio"], punteggi.INSUFF), eb["punteggio"])
        chk(tk, "prezzo d'acquisto", _py(a["prezzo_acquisto"]), eb["prezzo_acq"])
        chk(tk, "verdetto", a["verdetto"], eb["verdetto"])
        chk(tk, "segnali di rischio", "; ".join(a["rischi"]) or "Nessun segnale", eb["rischi"])
        mot = motivazioni.motivazione(i, a, P, giudizi.get(tk))
        xl = lambda v: re.sub(r"(?<=\d),(?=\d)", ".", v) if isinstance(v, str) else v   # virgola decimale  # noqa: E731
        chk(tk, "punti di forza", mot["forti"], xl(eb["forti"]) or "")
        chk(tk, "punti deboli", mot["deboli"], xl(eb["deboli"]) or "")
        chk(tk, "perché questo verdetto", mot["testo"], xl(eb["motivazione"]))
        # --- Trading Score
        for kx, nome in (("trend", "Trend"), ("mom", "Momentum"), ("forza", "Forza relativa"), ("osc", "Oscillatori"),
                         ("vol", "Volumi"), ("ass", "Assetto e rischio"), ("cat", "Catalizzatori")):
            chk(tk, f"pilastro {nome}", _py(b["pilastri"][nome]), et[kx])
        chk(tk, "stato trend", _py(b["stato_trend"]), et["stato_trend"])
        chk(tk, "Trading Score", _py(b["punteggio"], punteggi.INSUFF), et["punteggio"])
        chk(tk, "segnale", b["segnale"], et["segnale"])
        st = b["setup"]
        chk(tk, "setup", st["tipo"] or "-", et["setup"])
        chk(tk, "setup valido", 1 if st["valido"] else 0, et["valido"])
        for kp, kx in (("ingresso", "s_in"), ("stop", "s_stop"), ("obiettivo", "s_ob"), ("rr", "s_rr")):
            chk(tk, f"setup {kp}", _py(st[kp]), et[kx])
        chk(tk, "numero di azioni", _py(b["n_azioni"]), et["n_azioni"])
        chk(tk, "avviso trimestrale", 1 if b["avviso_trimestrale"] else 0, et["avviso"])
    # --- indicatori principali (SCREENER) e mediane di settore (SETTORI)
    from .excel_viste import COL_MEDIANE, CONFRONTABILI, INDICATORI
    import statistics
    if "SCREENER" in lib.tab and "SETTORI" in wb.sheetnames:
        xs = leggi_foglio(wb, None, "SCREENER", lib.tab["SCREENER"].cols)
        py = {}
        for tk, i in ingressi.items():
            a = A[tk]["valori"]
            p_, e_, d_ = i.get("prezzo"), i.get("utile_ttm_ps"), i.get("div_12m")
            py[tk] = {"pe_ttm": p_ / e_ if p_ and e_ and p_ > 0 and e_ > 0 else None,
                      "div_yield": d_ / p_ if d_ is not None and p_ and p_ > 0 else None,
                      "pe_fwd": a["V4"], "multiplo": a["V3"], "rend_cap": a["Q1"], "margine_op": a["Q3"],
                      "leva": a["F1"], "crescita": a["G1"]}
            for k, *_ in INDICATORI:
                chk(tk, f"indicatore {k}", _py(py[tk][k]), xs[tk][k])
        fin = {tk: i["modello"] in ("BAN", "ASS") for tk, i in ingressi.items()}
        for tk, i in ingressi.items():
            pari = [x for x, j in ingressi.items() if j["settore"] == i["settore"] and fin[x] == fin[tk]]
            chk(tk, "titoli confrontabili", len(pari), xs[tk]["n_pari"])
            for k, _h, _f, _fmt, lim in INDICATORI:
                v = [py[x][k] for x in pari if py[x][k] is not None and (lim is None or py[x][k] < lim)]
                chk(tk, f"mediana dei confrontabili {k}", statistics.median(v) if v else "n.d.", xs[tk]["med_" + k])
        ws = wb["SETTORI"]
        for r in range(R0, ws.max_row + 1):
            sett = ws.cell(r, 1).value
            if not sett:
                continue
            for j, (k, _h, _f, _fmt, lim) in enumerate(x for x in INDICATORI if x[0] in CONFRONTABILI):
                v = [py[tk][k] for tk, i in ingressi.items() if i["settore"] == sett and py[tk][k] is not None
                     and (lim is None or py[tk][k] < lim)]
                chk(sett, f"mediana {k}", statistics.median(v) if v else "n.d.", ws.cell(r, COL_MEDIANE + j).value)
    # --- catene del valore: numero di titoli e mediane di ogni anello
    if "CATENE" in lib.tab:
        from . import catene as cat
        xc = leggi_foglio(wb, None, "CATENE", lib.tab["CATENE"].cols)
        aid = {tk: cat.profilo(tk).get("anello_id") for tk in ingressi}
        for tk in ingressi:
            if not aid[tk]:
                continue
            pari = [x for x in ingressi if aid[x] == aid[tk]]
            chk(tk, "titoli nell'anello", len(pari), xc[tk]["n_anello"])
            for k, campo in (("med_marg", "Q3"), ("med_rend", "Q1")):
                v = [ingressi[x][campo] for x in pari if ingressi[x].get(campo) is not None]
                chk(tk, f"mediana dell'anello {campo}", statistics.median(v) if v else "n.d.", xc[tk][k])
    return n, diff


def verifica_file(percorso, ingressi: dict, lib, P: dict | None = None, giudizi: dict | None = None) -> dict:
    """Ricalcola il file, conta gli errori di formula e confronta con Python usando i parametri e i
    giudizi presenti nel file stesso (celle gialle)."""
    gialle = leggi_gialle(percorso)
    P = P or parametri_da_gialle(predefiniti(), gialle)
    giudizi = giudizi if giudizi is not None else giudizi_da_gialle(gialle)
    ric = ricalcola(percorso)
    wb = load_workbook(ric, data_only=True)
    err = errori_di_formula(wb)
    n, diff = confronta(ingressi, lib, ric, P, giudizi)
    return {"formule": conta_formule(percorso), "errori": err, "confronti": n, "differenze": diff, "ricalcolato": ric}
