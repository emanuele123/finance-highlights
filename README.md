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
| 4 | Movimenti, portafoglio, simulatore, backtest, manuale | fatta |

`aggiorna` scarica i dati e crea il cruscotto `Global_Stock_Intelligence.xlsx`. Il manuale è nel foglio LEGGIMI del
cruscotto; criteri e pesi nel foglio METODOLOGIA; che cosa funziona e che cosa no nel foglio STATO.

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
    python avvia.py backtest                 backtest della strategia B (meno di un minuto), poi rigenera il cruscotto
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

## Come funziona un aggiornamento

1. Scarica prezzi a 11 anni (sempre per intero), bilanci (se hanno più di 7 giorni), cambi BCE, stime, notizie.
   Ogni errore è registrato per titolo senza fermare gli altri.
2. Controlla ogni titolo (prezzi recenti, valuta e nome attesi, salti anomali, età dei bilanci) e stampa chi è "DA VERIFICARE".
3. Calcola indicatori e metriche e li scrive nel foglio DATI.
4. Ricrea il cruscotto rimettendo le celle gialle lette dal file precedente.
5. Se LibreOffice è installato, ricalcola le formule e le confronta con il calcolo Python.

## Manutenzione

- **A ogni aggiornamento**: le ultime righe devono dire "errori di formula: 0" e "differenze: 0".
  Guardare i titoli "DA VERIFICARE" (anche nel foglio QUALITA_DATI). Chiudere Excel prima di lanciare il comando.
- **Ogni trimestre**: dati manuali di banche e assicurazioni in GIUDIZI; `python avvia.py backtest`;
  `pip install -U yfinance` (Yahoo cambia spesso e la libreria si adegua).
- **Ogni anno**: rendimenti richiesti per valuta in PARAMETRI; descrizioni di società e settori.

| Sintomo | Causa probabile | Cosa fare |
|---|---|---|
| Molti titoli senza prezzo | Yahoo ha cambiato qualcosa o blocca le richieste | aggiornare yfinance, riprovare dopo qualche ora |
| Un titolo "nessun prezzo scaricato" | delisting, OPA, cambio di simbolo | correggere `gsi/universo.py` e rilanciare `python -m pytest -q tests` |
| "Ultimo esercizio vecchio" | bilancio non ancora caricato da Yahoo | aspettare |
| Differenze nel controllo incrociato | errore nel programma | non usare il file, far correggere |
| Il file non si salva | Excel aperto | chiudere Excel |

**Cosa conservare**: il file Excel è l'unica copia delle proprie modifiche (l'archivio si ricrea): farne copie di sicurezza.
Non spostare, rinominare o inserire colonne nei fogli. `configurazione.ini` non è su GitHub: va ricreato su un nuovo computer.

### Limiti principali

- Verificato con LibreOffice, non con Microsoft Excel.
- Indicatori tecnici e metriche di bilancio grezze sono calcolati in Python e scritti nel foglio DATI.
- GDELT rifiuta spesso le richieste: i titoli di stampa da questa fonte sono pochi.
- Per banche e assicurazioni cost/income, combined ratio, CET1 e Solvency II vanno inseriti a mano.
- Il backtest riguarda solo la strategia B e ha distorsione da sopravvivenza.

## Collaudi

    python -m pytest -q tests
