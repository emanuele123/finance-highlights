#!/usr/bin/env python3
"""Global Stock Intelligence - comandi:

  python avvia.py aggiorna                scarica prezzi, bilanci, cambi e rigenera il cruscotto
  python avvia.py aggiorna --solo-prezzi  scarica solo prezzi e cambi
  python avvia.py punteggi                calcola i punteggi dall'archivio (tabella in dati/punteggi.csv)
  python avvia.py excel                   rigenera il cruscotto senza scaricare
  python avvia.py backtest                backtest della strategia B (Trading Score)
  python avvia.py demo                    versione dimostrativa con societa' inventate
"""
import argparse
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="Global Stock Intelligence (uso personale, non e' consulenza finanziaria)")
    s = p.add_subparsers(dest="comando", required=True)
    a = s.add_parser("aggiorna", help="scarica i dati e rigenera il cruscotto")
    a.add_argument("--solo-prezzi", action="store_true", help="scarica solo prezzi e cambi")
    a.add_argument("--forza-bilanci", action="store_true", help="riscarica i bilanci anche se recenti")
    a.add_argument("--titoli", default="", help="elenco di ticker separati da virgola (per prove)")
    s.add_parser("punteggi", help="calcola i due punteggi dall'archivio e li scrive in dati/punteggi.csv")
    a.add_argument("--senza-excel", action="store_true", help="non rigenerare il cruscotto alla fine")
    for nome in ("excel", "backtest", "demo"):
        s.add_parser(nome)
    arg = p.parse_args()
    if arg.comando == "aggiorna":
        from gsi import aggiorna
        esito = aggiorna.esegui(solo_prezzi=arg.solo_prezzi, forza_bilanci=arg.forza_bilanci,
                                tickers=[x.strip() for x in arg.titoli.split(",") if x.strip()] or None)
        if esito == 0 and not arg.senza_excel:
            from gsi import comandi
            return comandi.excel_da_archivio()
        return esito
    if arg.comando == "excel":
        from gsi import comandi
        return comandi.excel_da_archivio()
    if arg.comando == "backtest":
        from gsi import comandi
        return comandi.backtest()
    if arg.comando == "demo":
        from gsi import comandi
        return comandi.demo()
    if arg.comando == "punteggi":
        from gsi import calcola
        return calcola.esegui()
    print(f"Comando '{arg.comando}' non ancora implementato (fasi successive del progetto).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
