# Spesometro

Assistente per la spesa alimentare: da scontrini e volantini di Lidl, Eurospin e Coop costruisce lo storico di prezzi e acquisti, stima cosa sta finendo in casa e propone una lista spesa per catena da approvare. I termini sono scritti con il nome esatto usato nel codice.

## Linguaggio

### Catalogo

**`ProductGroup`**:
Il bisogno che un prodotto soddisfa (es. "latte parzialmente scremato UHT 1 L"), con categoria, `unità_base`, formato normalizzato e `tipo_durata`; è l'unità su cui lavorano magazzino, lista e confronto prezzi.
_Avoid_: famiglia, categoria (è più larga), equivalenza

**`Product`**:
Articolo concreto del catalogo, indipendente dalla catena, descritto da nome, marca, `unità_di_vendita` (pezzo | peso variabile), dimensione, `attributi` e dal `ProductGroup` a cui appartiene.
_Avoid_: articolo, referenza

**`ProductAlias`**:
Stringa grezza con cui una catena indica un `Product` su scontrino o volantino; porta la provenienza.
_Avoid_: sinonimo, nome catena

**`equivalente`**:
Due `Product` dello stesso `ProductGroup`: sostituibili senza chiedere e confrontati insieme nel confronto prezzi tra catene. Non è una tabella: è l'appartenenza allo stesso gruppo.

**`GroupAlternative`**:
Relazione orientata tra due `ProductGroup` (`group_a`, `group_b`) in cui il secondo soddisfa lo stesso bisogno del primo, non il contrario; nasce solo da conferma umana e porta la provenienza.
_Avoid_: `ProductEquivalence` (rimossa in v1.4), sostituto

**`alternativa`**:
Il gruppo collegato da una `GroupAlternative`: viene solo proposto come suggerimento di risparmio, mai sostituito in automatico.
_Avoid_: sostituto

**`attributi`**:
Insieme chiuso di tag di un `Product` (es. `maiale`, `alcol`, `glutine`) su cui lavorano le esclusioni alimentari; proposti dal modello a partire dal nome, confermati da una persona (`attributi_verificati`).
_Avoid_: ingredienti (la lista ingredienti non viene letta)

**`Exclusion`**:
Esclusione alimentare di un utente su un attributo, di tipo `allergia` (un prodotto con attributi non verificati è escluso) o `dieta` (filtro sui tag proposti, con avviso finché manca la conferma).
_Avoid_: preferenza, filtro, intolleranza

**`tipo_durata`**:
Modo in cui un `ProductGroup` si deteriora, con tre valori: `scadenza_reale` (data di scadenza inserita a mano), `durata_stimata` (durata tipica in giorni) e `non_deperibile`.
_Avoid_: shelf life, conservabilità

### Prezzi e acquisti

**`catena`**:
Azienda della grande distribuzione a cui appartiene un negozio: `lidl`, `eurospin`, `coop` oppure `altra` (scontrini di catene fuori dal perimetro, salvati senza catalogo né volantini).
_Avoid_: negozio, supermercato, `insegna` (è il marchio o la cooperativa dentro la catena)

**`Flyer`**:
Volantino di una catena: `insegna`, validità, `tipo` (settimanale | catalogo), `sha256` del file e flag `incluso`, che decide se entra nell'estrazione.
_Avoid_: offerta (il volantino è la fonte, non l'offerta)

**`insegna`**:
Marchio o cooperativa sotto cui esce un `Flyer` (es. Coop Alleanza 3.0, Ipercoop): "Coop" da sola non identifica i prezzi validi per un negozio.

**`Offer`**:
Prezzo di un prodotto in un `Flyer`, con il testo grezzo del volantino, validità propria (`validità_da/a`), prezzo a confezione e unitario, prezzo barrato, sconto dichiarato e `condizione`; il `product` resta vuoto finché la riga non è mappata.
_Avoid_: promozione, volantino

**`condizione`**:
Vincolo a cui vale il prezzo di una `Offer`: `nessuna`, `carta_fedelta` (anche i prezzi per soci) o `multi_acquisto` (con `quantità_minima`).

**`Receipt`**:
Scontrino d'acquisto di una catena, con data e ora, totale, `impronta` per la deduplica ed `estrazione_grezza`.
_Avoid_: ricevuta

**`ReceiptLine`**:
Singola riga di un `Receipt`: testo grezzo, quantità, prezzo, sconto riga e `Product` riconosciuto; porta la provenienza.
_Avoid_: voce, item

**`estrazione_grezza`**:
JSON prodotto dal modello per un `Receipt` prima di ogni correzione umana, redatto, con modello e versione del prompt; resta dopo l'eliminazione dell'originale.

**`PriceObservation`**:
Vista che unisce i prezzi pagati (`ReceiptLine`) e i prezzi da volantino (`Offer`) per gruppo, catena e data, con `fonte` e `promo`.
_Avoid_: storico prezzi come tabella separata

**Prezzo di riferimento**:
Mediana dei prezzi unitari pagati dall'utente per un `ProductGroup` negli ultimi acquisti (solo scontrini); è il termine di confronto del verdetto sulle offerte.
_Avoid_: mediana storica (quella dei volantini contiene solo promozioni)

**Verdetto**:
Giudizio su una `Offer` rispetto al prezzo di riferimento e al miglior prezzo dello stesso gruppo negli altri volantini della settimana.

**Soglia di viaggio**:
Risparmio minimo (`risparmio_minimo_per_negozio`) e numero massimo di catene (`max_negozi`) perché una catena in più entri nella lista.

### Magazzino

**`InventoryItem`**:
Stima di quanto resta in casa di un `ProductGroup`, ricavata da ultimo acquisto e `tasso_consumo` (unità/giorno), con `probabilmente_finito`, `livello` e `livello_confidenza`.
_Avoid_: dispensa

**`livello`**:
Grado di affidabilità della stima di un `InventoryItem` (0, 1, 2), che sale da solo con l'accumularsi dei dati.

**Livello 0**:
Da 0 a 1 acquisti del gruppo: stato dedotto dalla durata tipica della categoria, `livello_confidenza` bassa, mostrato come "stima provvisoria".

**Livello 1**:
Da 2 a 3 acquisti: `tasso_consumo` = quantità acquistata / intervallo medio di riacquisto, `livello_confidenza` media, quantità mostrata con "≈".

**Livello 2**:
Almeno 4 acquisti o almeno 2 feedback dalla lista: `tasso_consumo` come media mobile esponenziale, `livello_confidenza` alta, quantità mostrata.

**`livello_confidenza`**:
Etichetta qualitativa della stima di un `InventoryItem`, `bassa` | `media` | `alta`, che corrisponde al `livello`.
_Avoid_: `confidenza` (riservata alla provenienza, numero 0–1)

### Provenienza

**Provenienza**:
Insieme di quattro attributi (`fonte`, `acquisito_il`, `confidenza`, `stato`) che dice da dove viene e quanto è affidabile un dato di `Offer`, `ReceiptLine`, `ProductAlias`, `Product` (assegnazione al gruppo e attributi) e `GroupAlternative`; la revisione umana è lo `stato`, non una registrazione separata.
_Avoid_: audit, storico revisioni

**`fonte`**:
Origine del dato: un `volantino` o uno `scontrino` (con il riferimento a quale), `umano` o `regola`.

**`acquisito_il`**:
Momento in cui il dato è entrato nel sistema.

**`confidenza` (di provenienza)**:
Affidabilità numerica del dato, tra 0 e 1.
_Avoid_: `livello_confidenza` (è del magazzino, bassa/media/alta)

**`stato` (di provenienza)**:
Esito della revisione del dato: `auto` (non rivisto), `rivisto` o `rifiutato`.
_Avoid_: confusione con lo `stato` di un `Job`

### Previsioni

**`soglie_dati`**:
Tabella delle quantità minime di dati sotto cui una previsione (consumo/fabbisogno, prezzo "davvero conveniente", ritorno promozione) non viene data come affidabile e si mostra il ripiego con badge di confidenza.
_Avoid_: soglie di matching (quelle decidono auto-accetta/revisione, non le previsioni)

### Esecuzione

**`Job`**:
Unità di lavoro accodata ed eseguita in background, descritta da tipo, payload, stato, tentativi e lease.

**`stato` (di `Job`)**:
`pending` (in coda, nessun worker) | `running` (preso da un worker, lease attivo) | `done` (completato) | `failed` (tentativi esauriti). Insieme minimo per la coda con lease.
_Avoid_: confusione con lo `stato` della provenienza (`auto` | `rivisto` | `rifiutato`)
