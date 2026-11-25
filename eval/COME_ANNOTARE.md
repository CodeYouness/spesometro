# Come annotare il golden set

Il **golden set** è l'insieme congelato di annotazioni fatte a mano (scontrini e pagine di volantino) contro cui si misura l'estrazione. Va annotato prima di implementarla, altrimenti l'eval misurerebbe il modello contro se stesso. Questa pagina basta per annotare senza leggere il codice.

## Dove stanno i file

```text
eval/golden/
  testata.json          versione e data del golden set
  scontrini/<nome>.json un file per scontrino
  volantini/<nome>.json un file per pagina di volantino
data/                   le immagini: fuori da git
```

- Nel repo ci sono **solo le annotazioni**. Le immagini (scontrini veri e pagine di volantino) stanno in `data/`, ignorata da git, e non vanno mai committate (ADR 0007 e 0011). Nei file l'immagine è un percorso relativo dentro `data/`, per esempio `scontrini/a.jpg`.
- `testata.json` contiene `{"versione": "1", "data": "2026-11-25"}`. Ogni report cita questi due valori, quindi si cambia la versione quando il golden set cambia.
- Le due annotazioni qui sotto sono **sintetiche** (nessun dato reale) e vivono in `eval/esempi/`, separate dal golden set reale.

## Creare lo scheletro

```sh
uv run spesometro-eval scheletro scontrini/a.jpg                    # scontrino
uv run spesometro-eval scheletro raw/volantini/lidl/2026-11-01_2026-12-31_abc/page_001.webp --tipo pagina   # pagina di volantino
```

Il percorso dell'immagine è quello dentro `data/`; va bene anche copiato con `data/` davanti (o assoluto), il comando lo riporta dentro `data/`. Il comando scrive il file vuoto in `eval/golden/scontrini/` o `eval/golden/volantini/` e non sovrascrive un file esistente. Nome del file: per uno scontrino il nome dell'immagine (`a.json`); per una pagina catena, cartella del volantino e pagina (`lidl_2026-11-01_2026-12-31_abc_page_001.json`), perché `page_001.webp` c'è in ogni volantino. Per una pagina calcola anche lo `sha256`, dall'immagine in `data/` o, se manca, da `manifest.json`. Poi si completa a mano. Opzioni: `--golden` e `--data` per cambiare le cartelle.

## Esempio: scontrino

```json esempi/scontrino.json
{
  "immagine": "esempi/scontrino-sintetico.jpg",
  "contenuto": {
    "catena": "lidl",
    "data": "2026-11-02",
    "ora": "18:45",
    "totale": "10.09",
    "righe": [
      {"testo_grezzo": "LATTE PS UHT 1L", "quantita": "2", "prezzo": "2.58"},
      {"testo_grezzo": "BANANE", "quantita": "1.250", "prezzo": "2.31", "sconto": "0.31"},
      {"testo_grezzo": "PASTA SPAGHETTI 500G", "quantita": "3", "prezzo": "2.97"},
      {"testo_grezzo": "VUOTO A RENDERE", "quantita": "1", "prezzo": "-0.50"},
      {"testo_grezzo": "YOGURT BIANCO 2X125G", "quantita": "1", "prezzo": "3.54"}
    ],
    "sconti_scontrino": [
      {"descrizione": "BUONO SCONTO ESEMPIO", "importo": "0.50"}
    ]
  }
}
```

Gli importi sono stringhe decimali con il punto. `prezzo` è il totale della riga prima dello sconto; `quantita` è in pezzi o in kg. La somma deve tornare: Σ(`prezzo` − `sconto`) − Σ `sconti_scontrino` = `totale` (qui 2,58 + 2,00 + 2,97 − 0,50 + 3,54 − 0,50 = 10,09).

## Esempio: pagina di volantino

```json esempi/pagina_volantino.json
{
  "immagine": "esempio/pagina_sintetica.webp",
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "contenuto": {
    "offerte": [
      {
        "testo_grezzo": "Latte UHT parzialmente scremato 1 L",
        "prezzo_confezione": "1.09",
        "condizione": "nessuna",
        "marca": "Esempio",
        "confezione_quantita": "1",
        "confezione_unita": "L",
        "prezzo_unitario": "1.09",
        "unita": "L",
        "prezzo_barrato": "1.29",
        "sconto_dichiarato": null,
        "validita_da": "2026-11-02",
        "validita_a": "2026-11-08",
        "quantita_minima": null,
        "limite_pezzi": 6
      },
      {
        "testo_grezzo": "Pasta di semola 500 g, con carta fedeltà, 3 pezzi",
        "prezzo_confezione": "0.79",
        "condizione": "multi_acquisto",
        "marca": null,
        "confezione_quantita": "0.5",
        "confezione_unita": "kg",
        "prezzo_unitario": null,
        "unita": null,
        "prezzo_barrato": null,
        "sconto_dichiarato": "20",
        "validita_da": null,
        "validita_a": null,
        "quantita_minima": 3,
        "limite_pezzi": null
      }
    ]
  }
}
```

Obbligatori per ogni offerta: `testo_grezzo`, `prezzo_confezione`, `condizione`. Tutto il resto è facoltativo.

## Regole di annotazione

1. **La pagina si annota per intero.** Ogni offerta stampata sulla pagina entra nell'annotazione, anche se illeggibile o poco interessante: la recall e la precision (ADR 0015) hanno senso solo se l'elenco è completo.
2. **Un campo non stampato resta vuoto (`null`) e non si calcola mai.** Niente prezzo al kg ricavato a mente, niente validità dedotta dalla copertina: se la pagina non lo mostra, resta vuoto. La validità mancante sull'offerta viene ereditata dal volantino al salvataggio, non qui.
3. **Lo sconto di riga va sulla riga a cui si riferisce** (`sconto` di quella riga, come `BANANE` nell'esempio), così il prezzo pagato per quel prodotto è ricostruibile.
4. **Un buono non legato a una riga è uno sconto di scontrino**: va in `sconti_scontrino`, non come riga.
5. **Resi e vuoti a rendere sono righe con `prezzo` negativo** (come `VUOTO A RENDERE`).
6. **Uno scontrino senza data o senza ora resta nel golden set**: `data` o `ora` a `null`. Resta obbligatorio il `totale`.
7. Nessun dato di pagamento, carta o fidelity: lo schema non ha i campi e non vanno scritti da nessuna parte.

Se un valore esce dai limiti dello schema (prezzo di riga tra −100 e 500 €, totale tra 0 e 2.000 €, data non futura, ecc.) il file viene rifiutato: un valore fuori limite quasi sempre è un errore di battitura.

## Controllare le annotazioni

```sh
uv run spesometro-eval valida
```

Controlla la testata e valida ogni file; se un file è sbagliato il messaggio nomina il file e il campo (`ERRORE`, uscita con codice 1). Su una macchina senza `data/` la validazione funziona lo stesso: gli avvisi (`AVVISO`, su stderr) non fermano nulla.

## Produrre il report

```sh
uv run spesometro-eval report --predizioni <cartella> [--soglia 0.6] [--out eval/reports]
```

Legge il golden set e le predizioni salvate in `<cartella>` (stessa forma delle annotazioni, più modello, versione del prompt, costo e tempo), scrive `report-golden-<versione>-<data>.md` e ne stampa il percorso. Non chiama nessun modello. Il report riporta versione e data del golden set, criteri e soglia di somiglianza; per le pagine mostra precision e recall con il criterio che decide il gate (prodotto e `prezzo_confezione` identico al centesimo, ADR 0015) accanto al criterio severo (accoppiamento massimo a parte, solo coppie con tutti i campi uguali, `testo_grezzo` carattere per carattere compreso). Una pagina o uno scontrino annotato senza predizione per un modello conta come estrazione vuota: pesa su recall, accuratezza e cifre errate, e il report dice «valutate n su m». Negli scontrini un refuso nel testo di una riga la conta come mancante più inventata.

Gli avvisi compaiono su stderr e in fondo al report, sezione "Avvisi":

- **immagine mancante**: l'immagine non è in `data/` (normale su una macchina senza dati privati); l'annotazione è comunque valutata.
- **`manifest.json` assente, o pagina non presente nel manifest**: lo `sha256` non è stato verificato.
- **`sha256` diverso**: l'annotazione dichiara un'impronta diversa da quella del manifest. La pagina in `data/` è cambiata o l'annotazione è associata alla pagina sbagliata: controllare l'immagine prima di fidarsi delle metriche.
- **predizione senza annotazione**: esiste una predizione per un'immagine che nel golden set non c'è.
