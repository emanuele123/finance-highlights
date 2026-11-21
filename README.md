# Global Stock Intelligence

Strumento personale per scegliere azioni: un programma Python scarica i dati di 120 titoli
in un archivio locale e genera un cruscotto Excel con formule.

**Non è consulenza finanziaria.** I punteggi ordinano i titoli secondo criteri dichiarati, non sono previsioni.
I dati Yahoo sono consentiti per il solo uso personale.

## Stato del progetto

| Fase | Contenuto | Stato |
|------|-----------|-------|
| 1 | Universo e scaricamento dei dati | fatta |
| 2 | Indicatori, metriche e punteggi in Python | fatta |
| 3 | Cruscotto Excel con formule e controllo incrociato | fatta |
| 4 | Movimenti, portafoglio, simulatore, backtest, manuale | da fare |

Oggi `aggiorna` scarica i dati e crea il cruscotto `Global_Stock_Intelligence.xlsx` con questi fogli: CRUSCOTTO,
SCREENER, SCHEDA, BUFFETT, VALUTAZIONE, TRADING, PERFORMANCE, GIUDIZI, PARAMETRI, UNIVERSO, DATI, QUALITA_DATI.
Mancano ancora (fase 4): MOVIMENTI, NOTIZIE, PORTAFOGLIO, SIMULATORE, BACKTEST e i fogli di documentazione.

## Installazione (una volta sola)

1. Installare Python 3.10 o successivo da https://www.python.org/downloads/
   (su Windows spuntare "Add Python to PATH").
2. Scaricare questa cartella sul computer (pulsante verde "Code" > "Download ZIP" su GitHub, poi estrarre).
3. Aprire il terminale nella cartella (Windows: clic destro nella cartella > "Apri nel terminale") e scrivere:

       pip install -r requirements.txt

## Uso

    python avvia.py aggiorna                 scarica tutto e rigenera il cruscotto (circa 20 minuti)
    python avvia.py aggiorna --solo-prezzi   scarica solo prezzi e cambi e rigenera il cruscotto (circa 5 minuti)
    python avvia.py excel                    rigenera il cruscotto dall'archivio, senza scaricare
    python avvia.py demo                     versione dimostrativa con società inventate (non serve la rete)
    python avvia.py punteggi                 le due classifiche in dati/punteggi.csv

Su Mac scrivere `python3` al posto di `python`. Chiudere il file Excel prima di aggiornare.

### Come si usa il cruscotto

- **Colori**: blu = dato importato o inserito, nero = formula, verde = collegamento ad altro foglio,
  **fondo giallo = cella che si può modificare**.
- **PARAMETRI**: tutte le soglie e i pesi. Cambiando un numero, punteggi e valori si ricalcolano.
- **GIUDIZI**: dati manuali per banche e assicurazioni (cost/income, combined ratio, CET1, Solvency II),
  correzione qualitativa (±10 punti, con motivazione) e tesi personale.
- **SCHEDA**: scegliere il titolo dal menu nella cella gialla.
- Le celle gialle modificate vengono **conservate** a ogni aggiornamento, anche se i fogli sono stati ordinati.
- Se LibreOffice è installato, a ogni rigenerazione il programma ricalcola il file e confronta le formule
  con il calcolo Python, titolo per titolo; altrimenti lo dichiara e il file resta utilizzabile.

### SEC EDGAR (facoltativo)

Per allungare a 10 anni la storia delle società americane, creare nella cartella un file
`configurazione.ini` con il proprio nome ed e-mail (lo richiede la SEC):

    [sec]
    user_agent = Nome Cognome nome@esempio.it

Verificata in rete il 21/11/2026: dati 10-K per 36 società. Le serie SEC si usano solo se coincidono
con Yahoo sugli esercizi in comune.

## Collaudi

    python -m pytest -q tests
