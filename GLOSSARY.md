# Spesometro

Assistente per la spesa alimentare: da scontrini e volantini di Lidl, Eurospin e Coop costruisce lo storico di prezzi e acquisti, stima cosa sta finendo in casa e propone una lista spesa per catena da approvare. I termini sono scritti con il nome esatto usato nel codice.

## Linguaggio

### Catalogo

**`Product`**:
Prodotto canonico del catalogo, indipendente dalla catena, descritto da nome, marca, categoria, `unità_di_vendita` (pezzo | peso variabile), dimensione e `tipo_durata`.
_Avoid_: articolo, referenza

**`ProductAlias`**:
Stringa grezza con cui una catena indica un `Product` su scontrino o volantino; punta sempre a un prodotto **identico** e porta la provenienza.
_Avoid_: sinonimo, nome catena

**`ProductEquivalence`**:
Relazione tra due prodotti (`product_a`, `product_b`) con un `tipo` e un'origine (regola | umano); porta la provenienza.
_Avoid_: somiglianza, match

**`identico`**:
`tipo` di `ProductEquivalence` per lo stesso prodotto, con stessa marca e formato, che compare con alias diversi tra catene.

**`equivalente`**:
`tipo` di `ProductEquivalence` per prodotti della stessa categoria e dello stesso formato normalizzato ma di marca diversa: sostituibili senza chiedere e confrontati insieme agli identici nel confronto prezzi tra catene.

**`alternativa`**:
`tipo` di `ProductEquivalence` per un prodotto diverso che soddisfa lo stesso bisogno: viene solo proposto come suggerimento di risparmio, mai sostituito in automatico, e nasce solo da conferma umana.
_Avoid_: sostituto

**`tipo_durata`**:
Modo in cui un `Product` si deteriora, con tre valori: `scadenza_reale` (data di scadenza inserita a mano), `durata_stimata` (durata tipica in giorni) e `non_deperibile`.
_Avoid_: shelf life, conservabilità

### Prezzi e acquisti

**`Offer`**:
Prezzo di un prodotto in un volantino di una catena, con validità propria (`validità_da/a`), prezzo a confezione e unitario, prezzo barrato e sconto dichiarato; il `product` resta vuoto finché la riga non è mappata.
_Avoid_: promozione, volantino (il volantino è la fonte, non l'offerta)

**`Receipt`**:
Scontrino d'acquisto di una catena, con data e totale.
_Avoid_: ricevuta

**`ReceiptLine`**:
Singola riga di un `Receipt`: testo grezzo, quantità, prezzo, sconto riga e `Product` riconosciuto; porta la provenienza.
_Avoid_: voce, item

### Magazzino

**`InventoryItem`**:
Stima di quanto resta in casa di un `Product`, ricavata da ultimo acquisto e `tasso_consumo` (unità/giorno), con `probabilmente_finito`, `livello` e `livello_confidenza`.
_Avoid_: dispensa

**`livello`**:
Grado di affidabilità della stima di un `InventoryItem` (0, 1, 2), che sale da solo con l'accumularsi dei dati.

**Livello 0**:
Da 0 a 1 acquisti del prodotto: stato dedotto dalla durata tipica della categoria, `livello_confidenza` bassa, mostrato come "stima provvisoria".

**Livello 1**:
Da 2 a 3 acquisti: `tasso_consumo` = quantità acquistata / intervallo medio di riacquisto, `livello_confidenza` media, quantità mostrata con "≈".

**Livello 2**:
Almeno 4 acquisti o almeno 2 feedback dalla lista: `tasso_consumo` come media mobile esponenziale, `livello_confidenza` alta, quantità mostrata.

**`livello_confidenza`**:
Etichetta qualitativa della stima di un `InventoryItem`, `bassa` | `media` | `alta`, che corrisponde al `livello`.
_Avoid_: `confidenza` (riservata alla provenienza, numero 0–1)

### Provenienza

**Provenienza**:
Insieme di quattro attributi (`fonte`, `acquisito_il`, `confidenza`, `stato`) che dice da dove viene e quanto è affidabile un dato di `Offer`, `ReceiptLine`, `ProductAlias` e `ProductEquivalence`; la revisione umana è lo `stato`, non una registrazione separata.
_Avoid_: audit, storico revisioni

**`fonte`**:
Origine del dato: `volantino_id`, `scontrino_id`, `umano` o `regola`.

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
