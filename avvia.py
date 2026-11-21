#!/usr/bin/env python3
"""Global Stock Intelligence - comandi:

  python avvia.py aggiorna                scarica prezzi, bilanci, cambi e rigenera il cruscotto
  python avvia.py aggiorna --solo-prezzi  scarica solo prezzi e cambi
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
    for nome in ("excel", "backtest", "demo"):
        s.add_parser(nome)
    arg = p.parse_args()
    if arg.comando == "aggiorna":
        from gsi import aggiorna
        return aggiorna.esegui(solo_prezzi=arg.solo_prezzi, forza_bilanci=arg.forza_bilanci,
                               tickers=[x.strip() for x in arg.titoli.split(",") if x.strip()] or None)
    print(f"Comando '{arg.comando}' non ancora implementato (fasi successive del progetto).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
