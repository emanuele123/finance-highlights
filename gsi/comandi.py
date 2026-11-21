"""Comandi `excel` e `demo`: rigenerano il cruscotto e, se LibreOffice e' installato, lo verificano."""
from __future__ import annotations
from datetime import date
from pathlib import Path

from . import config, db


def genera_e_verifica(con, percorso: Path, oggi: date | None = None, universo=None, demo: bool = False,
                      verifica: bool = True) -> int:
    from . import excel
    try:
        lib, ingressi, P, giudizi = excel.genera(con, percorso, oggi, universo, demo)
    except PermissionError:
        print(f"Impossibile scrivere {percorso}: chiudere il file in Excel e riprovare.")
        return 2
    conservate = len(excel.leggi_gialle(percorso))
    print(f"Cruscotto scritto: {percorso}  ({len(ingressi)} titoli, {len(lib.wb.sheetnames) - 1} fogli)")
    if conservate:
        print(f"  Celle gialle conservate dal file precedente: {conservate}")
    if not verifica:
        return 0
    from . import verifica as ver
    try:
        r = ver.verifica_file(percorso, ingressi, lib, P, giudizi)
    except RuntimeError as e:
        print(f"  Controllo incrociato NON eseguito: {e}")
        print("  (il file e' comunque utilizzabile: Excel calcola le formule all'apertura)")
        return 0
    print(f"  Controllo incrociato (formule ricalcolate con LibreOffice contro il calcolo Python):")
    print(f"    formule nel file: {r['formule']}   errori di formula: {len(r['errori'])}")
    print(f"    confronti eseguiti: {r['confronti']}   differenze: {len(r['differenze'])}")
    for x in (r["errori"] + r["differenze"])[:20]:
        print("      " + x)
    return 0 if not r["errori"] and not r["differenze"] else 3


def excel_da_archivio() -> int:
    if not config.FILE_DB.exists():
        print("Archivio assente: eseguire prima  python avvia.py aggiorna")
        return 2
    con = db.apri(config.FILE_DB)
    return genera_e_verifica(con, config.FILE_EXCEL)


def demo() -> int:
    from .demo import UNIVERSO_DEMO, crea_archivio
    percorso_db = config.CARTELLA_DATI / "demo.sqlite"
    if percorso_db.exists():
        percorso_db.unlink()
    con = crea_archivio(percorso_db)
    print("VERSIONE DIMOSTRATIVA: società e dati sono INVENTATI, non riguardano alcuna società reale.")
    return genera_e_verifica(con, config.RADICE / "Global_Stock_Intelligence_DEMO.xlsx", universo=UNIVERSO_DEMO, demo=True)
