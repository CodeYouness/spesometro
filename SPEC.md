# Spesometro — Specifica di progetto

**Versione:** 1.4 — 9 novembre 2026
**Autore:** Youness (GitHub: CodeYouness)
**Contesto:** esame finale, Master part-time AI Engineering (Boolean). Consegna **12 dicembre 2026**; finestra di valutazione 5–12 dicembre.
**Storia:** grill (Q1–Q46) → revisione ostile (R1–R15) → analisi hosting (v1.1) → verifica fornitori con fonti del 7/11 (v1.2) → **revisione critica finale su 10 punti: modellazione, forecasting, equivalenze, scadenze, provenienza, hosting, backup, NiceGUI, privacy, sostenibilità (v1.3)** → **revisione indipendente del 9/11: modello a gruppi, prezzo di riferimento dagli scontrini, minimizzazione, auth, ricalcolo notturno, calendario (v1.4)**. L'appendice A registra cosa è stato smentito; l'appendice B le decisioni prese per raccomandazione e ancora ribaltabili; l'appendice C le modifiche della v1.4 con il motivo.
**Volantini passati recuperabili (conteggio dell'8/11):** 14 (Lidl 8, Eurospin 1, Coop 5), sotto la soglia di 20 → ADR 0004, niente backfill.

> Frase guida da ripetere nel README: **l'LLM serve per il linguaggio (estrarre, matchare, spiegare); il codice deterministico prende le decisioni.** Ogni numero mostrato all'utente porta una confidenza e una fonte.

---

## 0. Vincoli non negoziabili

| Vincolo | Valore |
|---|---|
| Scadenza | 12 dic 2026 (5 settimane); app raggiungibile senza interruzioni 5–12 dic |
| Persone | 1, ~20 ore/settimana |
| Budget | ~10 € LLM + ≤ 8 € hosting al mese |
| Valutazione | codice su GitHub pubblico + app online con account demo + documentazione in 8 sezioni |
| Dati reali disponibili | piccolo storico di scontrini cartacei + ciò che si raccoglie in 5 settimane |
| Nome | **Spesometro** (omonimo di un vecchio adempimento fiscale: spiegarlo in una riga nel README) |

---

## 1. Idea e problema che risolve

Assistente per la spesa alimentare che, da **foto di scontrini** e **volantini** (PDF o immagini di pagina) (Lidl, Eurospin, Coop), costruisce uno storico prezzi e acquisti, stima cosa sta per finire in casa e propone una **lista spesa ottimizzata per catena**, che l'utente approva prima dell'uso. Risolve tre problemi: non sapere se un'offerta è davvero conveniente (serve un prezzo di riferimento), non ricordare cosa manca, e dover confrontare a mano più volantini.

**Perimetro verificato:** 3 catene (Lidl, Eurospin, Coop). Ingestione generica (il modello deduce la catena, con fallback a scelta manuale); catalogo, golden set e demo coprono solo le 3. **Coop non è una catena unica:** si ingeriscono solo i volantini dell'insegna di riferimento dell'utente (da indicare — appendice B); per Lidl solo i volantini alimentari settimanali (§2.5).

**Flusso fondamentale da preservare (MVP d'esame, chiuso entro fine S3):**
scontrino → riconoscimento prodotti → storico acquisti → magazzino → volantini → confronto offerte → lista ottimizzata → approvazione umana.

**Ordine di taglio se si va lunghi** (dal primo che salta):
1. esperimenti di forecasting (notebook: statsforecast / Chronos-2 / Timestral)
2. bot Telegram (resta upload web) — si fa solo se tutto il resto è chiuso entro il 2/12
3. embedding nel matching (restano alias + trigrammi + LLM)
4. confronto modelli oltre le 3 colonne base
5. chat minimale con tool calling e RAG — ultima a saltare: è l'unico punto del progetto con RAG e tool calling (da confermare sulla griglia d'esame — appendice B)

**Tagliato in v1.3:** pagina costi/stato nella web app → sostituita da un link a LangSmith e da una tabella nel README.

**Tagliato o rimandato in v1.4:** verifica JWKS, job notturno su GitHub Actions, statsforecast in produzione, indice HNSW, backup di `auth` e Storage, VPS d'apprendimento prima della consegna (appendice C).

**Lavoro futuro (dichiarato nel README):** agente che compila il carrello online (solo account proprio, mai pagamento), download automatico dei volantini, lettura della scadenza reale dalla foto della confezione, misura dello spreco, indice di inflazione personale, deploy self-hosted su VPS (§8, dopo la consegna), import della cronologia degli scontrini digitali dalle app delle catene, minimo storico e ritorno delle promozioni quando lo storico basta, Hermes Agent come runtime sempre acceso.

---

## 2. Regole di funzionamento e casi limite

### 2.1 Entità (schema dati)
- `User` — account; `user_id` su ogni tabella, filtro in ogni query (testato). Registrazione **disabilitata**: solo account personale + account demo. **Preferenze:** esclusioni alimentari (ciascuna di tipo `allergia` | `dieta`), carte fedeltà possedute, catena abituale, insegna Coop di riferimento, soglia di viaggio (§2.3).
- **`ProductGroup`** — il *bisogno* ("latte parzialmente scremato UHT 1 L"): nome, categoria, `unità_base` (kg | L | pezzo), formato normalizzato di riferimento, **`tipo_durata` ∈ {scadenza_reale, durata_stimata, non_deperibile}**, durata tipica (giorni, solo per `durata_stimata`). È l'unità su cui lavorano magazzino, lista e confronto prezzi (ADR 0005).
- `Product` — articolo concreto, indipendente dalla catena: nome, marca, **`group_id`** (nullable finché non assegnato), `unità_di_vendita` (pezzo | peso variabile), dimensione (quantità + unità; multipack `n × q` normalizzato al totale; conservata anche normalizzata, `dimensione_base` nella `unità_base` del prodotto — ADR 0014), **`attributi`** (insieme chiuso di tag per le esclusioni: `maiale`, `carne`, `pesce`, `alcol`, `glutine`, `lattosio`, `frutta_a_guscio`, …) e `attributi_verificati` (bool). Due prodotti dello stesso gruppo sono **equivalenti**: sostituibili senza chiedere. Assegnazione al gruppo e attributi con provenienza (§2.4).
- `ProductAlias` — stringa grezza → `Product`, per catena. Con provenienza (§2.4).
- **`GroupAlternative`** — `group_a`, `group_b`: un gruppo diverso che soddisfa lo stesso bisogno (**alternativa**: proposta, mai sostituita in automatico); nasce solo da conferma umana. Con provenienza. Sostituisce `ProductEquivalence`: `identico` era già coperto da `ProductAlias`, `equivalente` è l'appartenenza allo stesso gruppo.
- **`Flyer`** — volantino: catena, `insegna` (es. Coop Alleanza 3.0, Ipercoop), zona opzionale, `validità_da/a`, `tipo` ∈ {settimanale, catalogo}, numero di pagine, URL di origine, **`sha256`** del file (unico: lo stesso volantino non si ingerisce due volte), `incluso` (bool: entra nell'estrazione).
- `Offer` — `flyer_id` e pagina, `testo_grezzo` (il nome come appare sul volantino), product (nullable se non mappato), `prezzo_confezione`, `prezzo_unitario`, `unità`, `prezzo_barrato`, `sconto_dichiarato`, `validità_da/a` (per offerta), **`condizione`** ∈ {nessuna, carta_fedeltà, multi_acquisto}, `quantità_minima` (per `multi_acquisto`: il `prezzo_unitario` è quello effettivo a quella quantità), `limite_pezzi` opzionale. Con provenienza.
- `Receipt` + `ReceiptLine` — data e ora, catena, totale, **`impronta`** (sha256 del file) e vincolo di unicità su (`user_id`, catena, data-ora, totale): il doppio caricamento è respinto; **`estrazione_grezza`** (JSON del modello prima di ogni correzione, redatto, con modello e versione del prompt: resta dopo l'eliminazione dell'originale). Riga: testo grezzo, quantità, prezzo, sconto riga, product. `ReceiptLine` con provenienza.
- `InventoryItem` — **group**, data ultimo acquisto, quantità ultimo acquisto (in `unità_base`), **`tasso_consumo`** (`unità_base`/giorno, nullable), durata stimata, scadenza reale opzionale (inserita a mano), stato `probabilmente_finito` (bool), **`livello_confidenza`** ∈ {bassa, media, alta}, **`livello`** ∈ {0, 1, 2}.
- **`PriceObservation`** — **vista SQL**, non tabella: unione dei prezzi pagati (`ReceiptLine`) e dei prezzi da volantino (`Offer`) → gruppo, product, catena, data, `prezzo_unitario`, `fonte` ∈ {scontrino, volantino}, `promo` (bool). Unica sorgente per prezzo di riferimento, verdetto sulle offerte e grafici.
- `Job` — coda in Postgres (tipo, payload, stato, tentativi, lease).

Prezzi normalizzati a €/kg, €/L, €/pezzo. Per i prodotti a peso variabile il confronto usa sempre €/kg. I multipack (`6 × 1,5 L`) si normalizzano al totale; formati diversi dello stesso gruppo si sommano in `unità_base`.

### 2.2 Magazzino a tre livelli (si sbloccano da soli con i dati)
| Livello | Condizione | Stima | `livello_confidenza` | UI |
|---|---|---|---|---|
| 0 | 0–1 acquisti del gruppo | stato da durata tipica della categoria | bassa | "stima provvisoria" |
| 1 | 2–3 acquisti | tasso di consumo = quantità acquistata / intervallo medio di riacquisto → stato + quantità residua stimata | media | quantità mostrata con "≈" |
| 2 | ≥ 4 acquisti **o** ≥ 2 feedback | media mobile esponenziale del tasso di consumo | alta | quantità mostrata |

Feedback dalla lista: "ne ho ancora" / "è finito prima" corregge il **tasso**, non la durata; tolto 2 volte di seguito → chiedi "non ti serve o non lo vuoi più?". Funzione pura in `packages/core`, testata. Gli acquisti si contano per gruppo, in `unità_base`: marche e formati diversi dello stesso bisogno alimentano la stessa stima.

### 2.3 Regole deterministiche
- **Quantità in lista** = fabbisogno su 2 settimane del gruppo (dal tasso di consumo o dalla durata tipica) − scorta stimata.
- **Prezzo di riferimento personale** del gruppo = mediana dei `prezzo_unitario` pagati negli ultimi 6 acquisti (da `PriceObservation`, fonte scontrino, righe senza sconto). La mediana dei soli prezzi da volantino **non** è un prezzo normale: i volantini contengono solo promozioni (ADR 0006).
- **Verdetto sull'offerta ("davvero conveniente")**: il `prezzo_unitario` dell'offerta si confronta con (a) il prezzo di riferimento personale ("−18% rispetto a quanto lo paghi di solito") e (b) il miglior prezzo unitario dello stesso gruppo nei volantini validi nella stessa settimana ("il più basso tra le catene questa settimana"). Il confronto (b) non richiede storico. In home: "le offerte che ti riguardano", cioè le offerte sui gruppi che l'utente compra, ordinate per risparmio.
- **Scorta extra** solo se sconto ≥ X% rispetto al prezzo di riferimento personale **e** tetto di budget rispettato **e**: `non_deperibile` → sempre ammessa; `durata_stimata` → solo se la stima copre il consumo **con margine del 50%** e `livello_confidenza` ≥ media; `scadenza_reale` → solo se la scadenza inserita copre il consumo.
- **Offerte condizionate**: `carta_fedeltà` vale solo se l'utente ha dichiarato la carta di quella catena; `multi_acquisto` entra in lista solo se la quantità in lista è ≥ `quantità_minima`; `limite_pezzi` limita la scorta extra.
- **Esclusioni alimentari** (allergie, dieta, motivi religiosi): filtro duro, prima dell'ottimizzazione, sugli `attributi` del `Product`. Esclusione di tipo `allergia` → *fail-closed*: un prodotto con attributi non verificati è escluso e mostrato come "da verificare". Esclusione di tipo `dieta` → filtro sui tag proposti, con badge "non verificato" finché manca la conferma. Limite dichiarato: i tag derivano dal nome del prodotto, non dalla lista ingredienti, e non sostituiscono la lettura dell'etichetta.
- **Confronto prezzi tra catene**: dentro lo stesso `ProductGroup`; l'*alternativa* (`GroupAlternative`) appare solo come suggerimento "risparmieresti X scegliendo Y".
- **Soglia di viaggio**: una catena in più entra nella lista solo se il risparmio che porta è ≥ `risparmio_minimo_per_negozio` (default 5 €) e il numero di catene resta ≤ `max_negozi` (default 2); sotto soglia tutto resta nella catena abituale. Rende la divisione per catena una decisione spiegabile, non un'assegnazione riga per riga.
- **Prezzo anomalo** (es. −80% vs prezzo di riferimento) → coda di revisione, mai in lista.
- **Prodotto non trovato** in nessun volantino → "senza offerta", mai inventato.
- **Soglie minime di dati per ogni previsione** (tabella `soglie_dati` nel codice, badge di confidenza nell'UI):

| Previsione | Dati minimi | Sotto soglia |
|---|---|---|
| Consumo / fabbisogno | ≥ 3 acquisti del gruppo (fallback categoria) | "stima provvisoria" da durata tipica |
| Verdetto "davvero conveniente" | ≥ 2 acquisti del gruppo sugli scontrini (prezzo di riferimento) | si mostrano solo il confronto tra catene della settimana e lo sconto dichiarato, con etichetta "storico insufficiente" |
| Minimo storico dai volantini | ≥ 8 osservazioni del prezzo del gruppo | non mostrato; lavoro futuro (non entro dicembre) |
| Ritorno promozione | ≥ 3 cicli osservati | non mostrato; lavoro futuro (non entro dicembre) |

### 2.4 Provenienza (mixin di 4 colonne, su `Offer`, `ReceiptLine`, `ProductAlias`, `Product` e `GroupAlternative`)
`fonte` (volantino_id | scontrino_id | umano | regola; nello schema sono due colonne, tipo e riferimento — ADR 0014), `acquisito_il`, `confidenza` (0–1), `stato` ∈ {auto, rivisto, rifiutato}. La revisione umana è lo stato, non una riga separata. Nessun audit log per campo. Dà alla UI il filtro "solo dati rivisti" e all'eval la curva precision/confidenza. Su `Product` la provenienza riguarda l'assegnazione al gruppo e gli attributi.

### 2.5 Casi limite noti
- Scontrini con sconti riga, coupon, 2×1, resi, vuoti a rendere → somma righe ≠ totale: retry con discrepanza (§3.2).
- Volantini con validità diverse per pagina → validità per offerta.
- Pagine a bassa risoluzione → se precision < 70% la pagina va in "inserimento assistito".
- Data, ora e numero documento stampati sotto il totale e il pagamento (frequente sugli scontrini italiani): l'estrazione legge lo scontrino intero, senza taglio automatico (§3.1); se la data manca viene chiesta alla conferma, mai dedotta.
- Stesso scontrino o stesso volantino caricato due volte → respinto (`impronta` e `sha256`, §2.1).
- Più volantini per catena e settimana (Lidl: circa 6 per circa 150 pagine, molti non alimentari) → il flag `incluso` del `Flyer` decide cosa entra nell'estrazione; per Coop solo l'insegna di riferimento.
- Volantini di tipo `catalogo` (validità di mesi) → prezzi di listino: `promo` falso in `PriceObservation`.
- Offerte con carta fedeltà, per soci o multi-acquisto (3×2, secondo pezzo a metà prezzo) → `condizione` e `quantità_minima`, mai confrontate come prezzo pieno.
- Cold start dichiarato ovunque (livello 0, soglie, badge).

---

## 3. Architettura AI

### 3.1 Pipeline
```
[foto, PDF o screenshot di scontrino · PDF o immagini di volantino] → Storage (ridimensionato ≤1540 px)
  → Deduplica (sha256 del file; chiave naturale dello scontrino dopo l'estrazione)
  → Ritaglio manuale facoltativo nell'upload (l'utente può escludere la zona pagamento)
  → Job → Estrazione (VLM, structured output JSON-schema → Pydantic; lo schema non chiede campi di pagamento, carta o fidelity)
  → Redazione regex sul JSON estratto (PAN parziali, CF, codici fidelity) prima di persistenza e tracce
  → Validazione (coerenza somme/prezzi, range-check) → conferma utente → originale eliminato (resta `estrazione_grezza`)
  → Matching (normalizzazione regex → alias → trigrammi `pg_trgm` → LLM su top-10 → revisione umana) + assegnazione al gruppo
  → Catalogo / Gruppi / Offerte / Righe scontrino (con provenienza)
  → Ricalcolo notturno nel processo dell'app: magazzino a livelli + prezzi di riferimento
  → LangGraph: stima_fabbisogno → genera_lista → confronta_offerte → ottimizza_carrello
      → [interrupt: approvazione umana, checkpoint persistito] → esporta
  → Chat sui dati (tool calling + RAG sui volantini) — minimale, S4
```

**Minimizzazione (ADR 0007).** Nessun taglio automatico "sotto la riga TOTALE": per localizzarla servirebbe un OCR locale, e sugli scontrini italiani data, ora e numero documento stanno di norma sotto totale e pagamento (da verificare su 3 scontrini reali in S1). Se l'utente non ritaglia, la zona pagamento raggiunge il provider vision: è dichiarato in `/privacy`; con `VISION_PROVIDER=mistral` il dato resta in UE.

### 3.2 Estrazione (multi-provider, scelto con l'eval)
- **Scontrini (default, da confermare — appendice B):** immagine ridimensionata (ed eventualmente ritagliata dall'utente, §3.1) → **Claude Haiku 5.5** ($0,10 in / $0,50 out per M token, vision solida, structured output; dati solo US, trasferimento dichiarato via SCC). Guardrail: somma righe ≈ totale; il retry riceve la discrepanza ("somma 23,10, totale 21,60: cerca righe sconto"). **Flag di configurazione `VISION_PROVIDER`**: con `mistral` il default diventa Mistral Small 4 (EU, Svezia) senza altre modifiche. Gli scontrini digitali (PDF o screenshot dall'app della catena) passano per la stessa pipeline; verifica di 30 minuti in S1 sulla cronologia scontrini di Lidl Plus: se copre mesi, riduce il cold start dei consumi.
- **Confronto nell'eval** (3 colonne base: Haiku 5.5, Mistral Small 4 `mistral-small-2603`, un modello Qwen via OpenRouter con `data_collection:"deny"` + `zdr:true`; altre colonne — Ministral 3 8B, DeepSeek V4.1 Flash, Gemini Flash-Lite, modelli locali sul Mac — solo se avanza tempo). Metriche: accuratezza campo per campo, tasso di cifre errate, costo reale per foto, tempo. **Il prezzo per token non è il criterio** (~0,0004 $ a foto con qualsiasi modello): contano accuratezza, affidabilità del provider e residenza dei dati. Se un modello batte il default sul golden set diventa il default, con motivazione nel README.
- **Volantini:** pagina (immagine già pronta o rasterizzata da PDF) → stesso VLM con schema a campi separati (inclusa la `condizione` dell'offerta) + validatore (prezzo_unitario × quantità ≈ prezzo_confezione). **Mistral OCR 4.1** (`mistral-ocr-4-1`, $4/1000 pagine, $5 con annotazioni, −50% batch) come layer opzionale (bbox e annotazioni con schema per la griglia nuovo/barrato/€-kg). **Gate in S1:** 3 volantini reali, 50 prodotti annotati, precision ≥ 70% altrimenti "inserimento assistito".
- **Regole tecniche:** solo `json_schema` o tool calling, mai `json_object`; immagini ≤ 1540 px / ≤ 400 KB; versioni dei modelli pinnate esplicitamente, mai `-latest`; retry con backoff su 429; **nessun modello uscito da meno di 30 giorni in produzione d'esame: va nell'eval** (ADR). **Una pagina o uno scontrino per richiesta:** sopra 100k token di prompt Haiku 5.5 applica la tariffa 5× all'intera richiesta (verificato il 9/11).
- Modelli ritirati da non citare come scelta: Pixtral 12B, Pixtral Large, Mistral Small 3.2, Mistral OCR 4.0.

### 3.3 Matching (entity resolution)
1. **Normalizzazione regex** della riga grezza (quantità, unità, marca, abbreviazioni note per catena).
2. Match esatto su alias confermati.
3. **Similarità a trigrammi (`pg_trgm`)** sul nome normalizzato, per catena: il full-text di Postgres non è BM25 e rende poco sulle righe abbreviate degli scontrini ("LATTE PS UHT 1L"). Embedding (`text-embedding-3-small`, pgvector a scansione esatta: **nessun indice HNSW** con poche centinaia di righe) **solo se** l'F1 sul golden set con alias + trigrammi + LLM resta sotto l'obiettivo (ADR 0010). `multilingual-e5-large` locale solo come colonna di eval se avanza tempo.
4. Sopra soglia alta → auto-accetta; zona grigia → **Mistral Small 4** sceglie tra top-10 o "nuovo prodotto"; sotto soglia bassa → coda di revisione umana. Ogni conferma umana diventa alias (stato `rivisto`).
5. **Gruppi**: alla creazione di un `Product` la regola deterministica (stessa categoria + stesso formato normalizzato) propone il `ProductGroup`; con più candidati o nessuno l'LLM sceglie tra i candidati o "nuovo gruppo"; conferma umana dalla coda. Nella stessa coda si confermano gli `attributi` proposti dall'LLM. Le `GroupAlternative` nascono solo da conferma umana.
6. **Scope:** matching automatico solo per i gruppi presenti negli scontrini dell'utente (~100–150); le altre offerte restano "non mappate" ma cercabili dalla chat (RAG, §3.6).
7. **Soglie calibrate a posteriori** sulla curva di precision del golden set (auto-accept a precision ≥ 0,95). Golden set annotato **prima** di implementare.
8. **Apprendimento misurabile:** tasso di auto-accettazione del matching nel tempo (le conferme diventano alias): grafico nel README.

### 3.4 Forecasting
- **Produzione = regole del magazzino (§2.2) e prezzi di riferimento (§2.3)**: funzioni pure in `packages/core`, ricalcolate ogni notte nel processo dell'app (§8). Nessuna libreria di forecasting in produzione: statsforecast e la media mobile del magazzino stimerebbero la stessa quantità con gli stessi pochi dati (ADR 0009).
- **Esperimenti documentati** (notebook, dopo il 28 novembre, solo se c'è tempo): **statsforecast** (Croston / SeasonalNaive) come baseline classica, **Chronos-2** (Amazon, Apache 2.0) e **Timestral-123M** (Mistral, pesi aperti) su dataset pubblico proxy + dati propri, a confronto con la media mobile di produzione. Dipendenze in un gruppo `notebook` separato, mai nell'immagine di produzione. Fuori programma del corso.

### 3.5 Agente
Un solo grafo **LangGraph 1.2.x**, `interrupt()` + `Command(resume=)`, checkpoint su Postgres (`langgraph-checkpoint-postgres`) **via session pooler 5432** con `prepare_threshold=None`, `supports_pipeline=False`, `setup()` come migrazione. Nessun side-effect prima dell'interrupt. Output = lista strutturata per catena, nel rispetto della soglia di viaggio (§2.3). È un workflow con approvazione umana, non un agente autonomo: nel README va chiamato così. Nessun multi-agente.

### 3.6 Chat sui dati (minimale, S4; ultima voce dell'ordine di taglio)
3–4 tool: SQL parametriche su acquisti e prezzi, offerte della settimana, magazzino, RAG sui volantini (qui gli embedding servono: provider deciso con una riga di ADR tra `text-embedding-3-small` e `mistral-embed`, per non aggiungere un fornitore solo per questo). LLM: Mistral Small 4 (`reasoning_effort="none"`). Memoria di sessione persistita.

### 3.7 Provider
Interfaccia `Provider` propria (~40 righe) con implementazioni Anthropic e Mistral; OpenAI-compatible (copre OpenRouter) solo per la colonna dell'eval. Niente LiteLLM, niente `init_chat_model`: una sola strada (ADR 0012); tracce LangSmith con `@traceable` sulle chiamate del Provider. **Due client HTTP coesistono:** `httpx2` (SDK Anthropic, SDK Mistral, NiceGUI 4) e `httpx` (python-telegram-bot): dichiarare entrambi, non mockare quello sbagliato.

---

## 4. Guardrail

1. **Prompt injection via immagini/PDF:** l'LLM produce solo JSON validato con Pydantic; nessuna tool call con effetti decisa dal contenuto estratto; range-check su ogni campo numerico.
2. **Costi:** tetti in console configurati l'8/11 (Anthropic 5 $/mese sul workspace `spesometro`, Mistral 10 €/mese oltre gli 8,5 € inclusi — minimo accettato —, OpenAI 2 $ rigido, Cloudflare avviso a 1 $), ma sono mensili e per organizzazione → resta il **tetto applicativo** giornaliero per utente e globale con kill switch, su tutti i provider; quota demo in **job LLM/giorno** (es. 30) verificata prima dell'enqueue; `make eval` mai in CI automatica. Mistral **pay-as-you-go con opt-out dal training attivato in Admin Console → Privacy**; mai il tier gratuito (usa i dati per training).
3. **Abuso:** max 5 MB per foto scontrino e 25 MB per PDF volantino (imposti anche sui bucket privati `receipts` e `flyers`), 10 upload/ora per utente, rate limiting, registrazione disabilitata.
4. **Dati personali:** minimizzazione secondo §3.1 (ridimensionamento, ritaglio manuale facoltativo, schema senza campi di pagamento, redazione regex sul JSON prima di persistenza e tracce; la zona pagamento può raggiungere il provider vision se l'utente non la ritaglia, ed è dichiarato); originali conservati **al massimo 7 giorni** (eliminati alla conferma dell'utente; si tengono solo il JSON strutturato, l'`estrazione_grezza` redatta e, se serve, una thumbnail ritagliata); cancellazione account completa inclusi file su Storage; LangSmith **EU** con `hide_inputs` e `hide_outputs` (anche il JSON estratto può contenere un CF); OpenRouter solo con `data_collection:"deny"` + `zdr:true`; pagina `/privacy` con titolare, finalità (art. 6(1)(b)), retention, diritti, **tabella dei sub-processor con link ai DPA** (Supabase EU, Railway Amsterdam/US, Mistral SE, Anthropic US, OpenAI US (solo se si attivano gli embedding), OpenRouter US, LangSmith EU, Telegram NL, Cloudflare R2) e trasferimenti extra-UE con SCC. Timebox della pagina: 1 ora. **Eccessivo e non previsto:** DPIA, DPO, ZDR contrattuale.
5. **Decisioni:** regole in codice deterministico e testate.
6. **Segreti:** solo variabili d'ambiente; `.env.example`; `gitleaks` pre-commit **e** push protection del repo. **Repo pubblico:** nessuna foto reale di scontrino e nessuna immagine di volantino di terzi nel repo, nemmeno dentro le cassette vcrpy (che registrano l'immagine in base64 nel corpo della richiesta): cassette registrate su immagini sintetiche; credenziali demo nel documento di consegna, non nel README.

---

## 5. Valutazione (`make eval`)

Golden set congelato, con versione e data (nel repo pubblico **solo le annotazioni**; scontrini reali in `data/`, fuori da git; volantini referenziati per URL + `sha256` in `manifest.json`; 2–3 scontrini sintetici nel repo per provare la pipeline senza dati privati), annotato **prima** dell'implementazione: 30 scontrini (≥ 5 con sconti/coupon/2×1) + 10 pagine volantino; 200 righe per il matching (con etichetta "stesso gruppo sì/no" su 50 coppie); 20 prodotti "finito sì/no"; 20 domande chat con risposta attesa.

| Modulo | Metrica |
|---|---|
| Estrazione scontrini | accuratezza campo per campo; tabella modelli (3 colonne base) con costo e tempo |
| Estrazione volantini | precision/recall su offerte |
| Matching | precision/recall/F1; curva precision–soglia; accuracy sull'assegnazione al gruppo; tasso di auto-accettazione nel tempo |
| Magazzino | accuracy su 20 prodotti "finito sì/no", per `livello_confidenza` |
| Forecasting (notebook, se c'è tempo) | media mobile di produzione vs statsforecast / Chronos-2 / Timestral: MAE/MASE sul proxy |
| Verdetto offerte | quota di offerte sui gruppi acquistati con prezzo di riferimento disponibile; controllo a mano di 20 verdetti |
| Carrello | € risparmiati vs "tutto nella catena abituale", con e senza soglia di viaggio; tasso di accettazione righe |
| Chat | exact-match / tolleranza numerica (SQL); RAGAS solo sulle domande sui volantini |

Report markdown versionato in `eval/reports/`. Eseguito a mano o su tag. Costo < 1 $ per run.

---

## 6. Stima dei costi (mensili, IVA inclusa dove si applica; S = stima)

| Voce | Costo |
|---|---|
| Claude Haiku 5.5 (estrazione) | 1–2 $ (S) |
| Mistral Small 4 (matching, chat) + OCR 4.1 opzionale | 1–2 $ (S) |
| Embedding (solo se attivati: matching o RAG della chat) | centesimi |
| Eval completo (manuale) | < 1 $ per run |
| **Railway Hobby** (1 servizio always-on) | **~5–8 € (S)**: 5 $ di abbonamento con 5 $ di consumo inclusi; tariffe a consumo di 10 $/GB di RAM e 20 $/vCPU al mese (verificato il 9/11): un'app quasi sempre inattiva resta vicina ai 5 $ |
| Supabase Free, LangSmith Developer, GitHub Actions (repo pubblico), Cloudflare R2 | 0 |
| **Totale** | **≈ 8–11 €/mese** |
| VPS d'apprendimento | dopo la consegna, fuori dal budget d'esame |

Nel README: tabella "costi stimati vs costi reali misurati" a fine progetto, per provider.

---

## 7. Stack tecnologico (versioni esatte bloccate in `pyproject.toml` / `uv.lock`)

- **Python 3.13** (immagine `python:3.13-slim`; evitare 3.15 per i wheel). `uv` workspaces, un solo lock. Pydantic v2, async.
- **NiceGUI 4.0.0 — versione di riferimento.** Requisiti verificati: Python ≥ 3.11, **FastAPI ≥ 0.143.1**, **Starlette ≥ 1.3.1**, Chrome 121+/Safari 17.2+; usa `httpx2` (non installa più `httpx`). Nessuna 3.x come fallback, salvo problema concreto e documentato in ADR. **Regole di codice per la 4.0** (dalle release note, da mettere in `docs/adr/` e nel `CLAUDE.md` del repo):
  - `.props()` non converte più snake_case/camelCase in kebab-case: scrivere i prop Quasar esattamente come li vuole Quasar.
  - Input di testo svuotato → `''`, non `None`: nessun check `is None` su `ui.input`, `ui.textarea`, `ui.date_input`, `ui.time_input`, `ui.color_input`.
  - `run.cpu_bound` usa `spawn`: funzioni importabili a livello di modulo; non usarlo per OCR/LLM (quello va nel worker).
  - `run.io_bound/cpu_bound` e i timer propagano `CancelledError`: rilanciarla, mai `except Exception` nudo.
  - ID DOM `ng-<n>` (per i test Playwright usare selettori propri, non gli ID).
  - `ui.table`: `pagination_controls=False` dove i controlli non servono.
  - Oggetti scene/leaflet richiedono `with` (non usati).
  - Rimossi: `sanitize=None`, `coroutine=` in `background_tasks`, `ui.add_scss/add_sass`, `Props.add_rename`: non usarli.
  - Quasar 2.35 / AG Grid 36 / Tailwind 4.3: i dialog si chiudono su mousedown fuori; le classi CSS interne di AG Grid sono cambiate: nessuno stile basato su classi interne.
  - `WEB_CONCURRENCY>1` solleva `ValueError`: **1 replica, 1 worker uvicorn** (Railway non ha sticky session).
  - Auth: `BaseHTTPMiddleware` + `app.storage.user` + `storage_secret` (esempio ufficiale `examples/authentication`, già compatibile 4.0); montaggio con `ui.run_with(app, mount_path=..., storage_secret=...)`.
  - Issue aperte al 7/11 sul 4.0: nessuna su `run_with`, auth, proxy, Tailwind o `httpx2`; se compare un bug bloccante: ADR + pin a `3.19.0` (costo ~mezza giornata), non prima. Al 9/11 la 4.0.0 è ancora l'unica 4.x pubblicata: prima del freeze controllare se esiste una 4.0.x correttiva.
- **Monorepo:** `apps/api` (FastAPI), `apps/web` (NiceGUI via `ui.run_with`), `apps/bot` (webhook nello stesso processo, lifecycle in `lifespan`), `apps/worker` (task asyncio leggero + ricalcolo notturno, nello stesso processo), `packages/core` (dominio, regole, schemi, provider, minimizzazione; senza dipendenze da web/DB), `eval/`, `docs/`, `docker/`, `.github/workflows/`.
- **AI:** Claude Haiku 5.5 (vision, da confermare), Mistral Small 4 (testo), Mistral OCR 4.1 (opzionale), embedding solo se attivati (§3.3, §3.6); LangChain 1.x / LangGraph 1.2.x; statsforecast, Chronos-2 e Timestral solo nei notebook.
- **Dati:** Supabase Free (Postgres + pgvector + Auth + Storage, regione **Central EU (Frankfurt)**, scelta esplicita: la voce generica "Europe" può assegnare Londra; Data API disattivata e RLS automatica attiva). **SQLAlchemy 2.x** (`Mapped`/`mapped_column`, asyncpg) + **Alembic async**; non SQLModel. `pgvector.sqlalchemy` importato in `script.py.mako`. Estensione `pg_trgm` per il matching; pgvector senza indice HNSW (scansione esatta) finché le righe sono poche centinaia.
- **Connessioni Supabase:** **tutto sul session pooler porta 5432** (utente `postgres.<ref>`, host `aws-1-eu-central-1.pooler.supabase.com`: il prefisso `aws-N` varia per progetto, va copiato dal pannello Connect): app, Alembic, pg_dump, checkpointer LangGraph, workflow di backup su GitHub Actions. La direct connection è IPv6-only su Free e i runner GitHub non hanno IPv6 (Railway lo ha come toggle, ma non serve); mai il transaction pooler 6543. Pool `pool_size ≤ 5`, chiuso nel cron.
- **Auth:** Supabase Auth email/password con **login lato server** dalla pagina NiceGUI (`sign_in_with_password`), poi `user_id` in `app.storage.user`. Nessuna verifica JWKS: NiceGUI è renderizzato dal server e nessun client presenta token all'API; `/health` e il webhook non usano token utente (ADR 0008). Se nascerà un client esterno: verifica via JWKS (chiavi asimmetriche).
- **Coda:** tabella `job` in Postgres, `FOR UPDATE SKIP LOCKED`, lease con timeout.
- **Design:** `/impeccable init` → `DESIGN.md`; comandi `critique`/`audit`/`typeset`/`colorize` e detector via URL del dev server (live mode e regole su `.py` non funzionano) + skill `frontend-design` di Anthropic.
- **Input:** **python-telegram-bot 22.8** in webhook (`updater(None)`, esempio `customwebhookbot`), `secret_token`, 200 immediato e processing in background task; polling in dev, webhook in prod; pairing codice 6 cifre, 10 min, monouso; `httpx` dichiarato esplicitamente. In **S4**.
- **Test:** pytest; **vcrpy + pytest-recording** (cassette `httpx2`, `filter_headers=["Authorization"]`, `--block-network`; cassette registrate su immagini sintetiche, mai su scontrini reali); **httpx2-pytest** per i mock unitari. Playwright MCP per i test end-to-end della UI.
- **Qualità:** ruff; mypy con override permissive su `apps/web` e `apps/bot`; non `ty`.
- **Osservabilità:** LangSmith Developer **EU** (`eu.smith.langchain.com`, 5k tracce/mese, retention 14 gg) con `LANGSMITH_HIDE_INPUTS/OUTPUTS`; log JSON; `/health` con `PORT` da env; alert Telegram; UptimeRobot (gratis) sull'URL pubblico dal 1° dicembre.

---

## 8. Deploy in produzione e monitoraggio

- **Produzione d'esame: Railway Hobby** (da confermare — appendice B). Regione **EU West (Amsterdam)**. **Un solo servizio** Docker multi-stage (uv: `uv sync --frozen --no-install-workspace` come layer cache, poi `--package`, stage finale solo `.venv`): API + web + webhook + worker leggero. Serverless/app sleeping **spento**, `replicas: 1`, healthcheck `/health`, tutto in **`.railway/railway.ts`** nel repo (Infrastructure as Code: `railway.json` è deprecato e smette di funzionare il 1/12/2026 — ADR 0013). Deploy automatico da push su `main` **fino al 2 dicembre**; dal 3 dicembre deploy automatico **disattivato** (i commit di documentazione durante la valutazione non devono ridistribuire l'app) e hotfix solo con deploy manuale. Immagine su **GHCR** (multi-arch). **Ultimo deploy di funzionalità: 2 dicembre sera.**
- **Ricalcolo notturno** (magazzino a livelli, prezzi di riferimento): task pianificato **nel processo dell'app** (avviato nel `lifespan`, registrato come `Job`), più un pulsante "ricalcola ora" nella UI per la demo. Nessun workflow schedulato per la logica applicativa: niente segreti del database per il calcolo, niente ritardi del cron, niente disattivazione dopo 60 giorni (ADR 0009).
- **Backup Supabase Free (ridotto, ADR 0011):** workflow GitHub Actions **settimanale** (`schedule` + `workflow_dispatch`) e un run manuale prima del freeze: `supabase db dump --db-url <session pooler, percent-encoded> --schema public` in due file (schema; dati con `--data-only --use-copy`), cifratura con `age`, upload su **Cloudflare R2** (10 GB free). **Non** negli artifact del repo pubblico (leggibili da chiunque). Fuori dal backup: `auth` (due utenti creati a mano, ricreabili), Storage (gli originali vivono al massimo 7 giorni), roles. Retention 30 gg. **Test di ripristino entro il 25/11** (30 minuti) su un secondo progetto Free (`psql --single-transaction --variable ON_ERROR_STOP=1 --file schema.sql --command 'SET session_replication_role = replica' --file data.sql`), poi cancellarlo. **Keep-alive:** non serve finché l'app è accesa (il polling della coda interroga il database ogni giorno); il Free pausa dopo 1 settimana di bassa attività, finestra di ripristino 1 anno. Egress 5 GB/mese: foto servite con signed URL.
- **CI (S1):** ruff + pytest unit con cassette; mypy e integration con Postgres in container solo dopo il 1° dicembre; gitleaks + push protection.
- **Monitoraggio:** LangSmith EU (mascherato), alert Telegram (budget 80%, job fallito 3 volte), UptimeRobot.
- **Account demo:** `demo` con 2–6 mesi di storico sintetico generato da script e dichiarato, scrittura consentita, quota propria, ripristino da snapshot; credenziali nel documento di consegna, non nel README pubblico (chiunque potrebbe esaurire la quota prima dei docenti).
- **Piano B hosting:** Dockerfile + immagine GHCR + Supabase esterno → Render Starter/Fly/Koyeb in 60–90 minuti. **Prova generale di migrazione a fine novembre** (1 ora).
- **VPS d'apprendimento, solo dopo la consegna del 12/12 (nessun ordine prima), documentato in `docs/deploy-vps.md`:** **OVH VPS-1** (2 vCore / 4 GB / 40 GB NVMe, backup giornaliero incluso, traffico illimitato; l'eventuale verifica documenti può richiedere giorni) al posto di Hetzner (CX/CAX non ordinabile al 7/11). Con 4 GB il job torch può girare sullo stesso host (container `run --rm` notturno). Mai come URL dato ai docenti finché non regge 2 settimane stabili. Provider low-cost: CrownCloud Amsterdam (6 GB, 5 $, 12 anni di storia) è l'unica offerta LowEndSpirit a rischio basso-medio; solo dopo l'esame.
  - Checklist VPS: utente non-root + chiavi SSH, `PasswordAuthentication no`, ufw deny + 22/80/443, fail2ban, unattended-upgrades, firewall del provider; **mai `ports: "8000:8000"`** (Docker bypassa ufw): `127.0.0.1:` o rete interna con **Caddy 2.11** (volume `caddy_data`; `acme_ca` staging in test; Let's Encrypt 5 duplicati/settimana); dominio proprio; `mem_limit` e swap 2 GB; cache HF su volume; `docker system prune` settimanale; `restart: unless-stopped`.

---

## 9. Timebox (20 ore/settimana)

| Settimana | Obiettivo | Gate |
|---|---|---|
| **S1** 9–15 nov | Repo e deploy "hello" su Railway EU; schema v1.4 (gruppi, `Flyer`, provenienza) + Alembic; login lato server; funzioni di minimizzazione; schemi di estrazione, golden set (sottoinsieme S1) e scorer; estrazione scontrini e volantini; CI minima. **Fuori dal codice:** fotografare gli scontrini (in ritardo sull'8/11); verificare dove sta la data su 3 scontrini; guardare la cronologia Lidl Plus; indicare l'insegna Coop di riferimento. | Precision volantini ≥ 70% su 3 volantini reali. |
| **S2** 16–22 nov | Salvataggio scontrino (upload → `Job` → DB con deduplica); normalizzazione regex, catalogo e gruppi, matching (alias + trigrammi + LLM), coda di revisione, UI NiceGUI minima, magazzino ai livelli 0–1, lista per catena senza grafo; backup ridotto su R2. | **Fetta verticale online entro il 22/11:** uno scontrino reale → DB → matching → magazzino → lista, nell'app su Railway, anche brutta. F1 matching sul golden set; soglie calibrate. |
| **S3** 23–29 nov | Magazzino completo e `tipo_durata`, prezzo di riferimento, verdetto sulle offerte, soglia di viaggio, LangGraph con approvazione, ricalcolo notturno, seed demo, `DESIGN.md` e UI. **Test di ripristino backup entro il 25. Prova di migrazione hosting (1 h).** | **MVP d'esame end-to-end online.** |
| **S4** 30 nov–6 dic | **Fino al 2/12 (ultimo deploy di funzionalità):** guardrail, quote, LangSmith, alert, UptimeRobot, pagina privacy (1 h), chat minimale. **Dal 3/12 (deploy automatico spento):** solo lavoro che non richiede deploy: eval a 3 colonne, report, notebook di forecasting se c'è tempo. Bot Telegram solo se tutto il resto è chiuso entro il 2/12. | `make eval` completo. |
| **S5** 7–12 dic | README, 8 sezioni, report eval, percorso demo di 5 minuti, margine. Nessun ritocco alla UI che richieda deploy (solo hotfix manuali). Verifica backup recente e app raggiungibile. | Consegna. |

Ogni ticket ha una stima in ore; la somma settimanale non supera le 20. Le ore utili per codice distribuibile sono circa 70 (dal 9/11 al 2/12); le restanti circa 30 vanno a eval, documentazione e demo.

**Percorso demo per i docenti (5 minuti):** foto scontrino → ritaglio e redazione → traccia LangSmith → matching con confidenza e gruppo → revisione umana → magazzino con livello e confidenza → offerte che ti riguardano, con verdetto rispetto al prezzo pagato → grafo con checkpoint → lista approvata con spiegazione, soglia di viaggio e badge "storico insufficiente" dove vero → pulsante "ricalcola ora".

---

## 10. Metodo di lavoro

- grill (fatto) → questa spec → ticket settimanali → implementazione in sessioni Claude Code separate → retro.
- **Fonte di verità:** markdown nel repo (`BACKLOG.md`, `WORK_LOG.md`, `docs/adr/`, `GLOSSARY.md`); `.scratch/` fuori da git. GitHub Projects con 5 card-milestone.
- **Regola decisionale:** decisione irreversibile = 30 minuti max; tutto il resto = default più semplice + ADR di 3 righe. **ADR già decise:** nessun modello < 30 giorni in produzione; NiceGUI 4.0 adottato con accettazione del rischio; pooler 5432 ovunque; niente backfill dei volantini (0004); le otto della v1.4 (0005–0012, appendice C).
- Un solo assistente per il codice. `docs/ai-workflow.md`.
- MCP in Claude Code: Supabase, documentazione live, Playwright. Niente Notion.
- Dati: fotografare lo storico di scontrini e scaricare i volantini correnti **questa settimana**.

---

## 11. Registro dei rischi

| # | Rischio | P | Mitigazione |
|---|---|---|---|
| 1 | Scope troppo ampio per 100 ore | Alta | MVP + ordine di taglio; pagina costi tagliata; bot in S4 |
| 2 | Volantini storici non esistono | Alta | Verdetto basato sul prezzo pagato (scontrini) e sul confronto tra catene della settimana; soglie dati e badge "storico insufficiente" |
| 3 | Cold start | Alta | Magazzino a livelli, soglie, baseline onesta |
| 4 | Estrazione volantini < 70% | Media-alta | Gate S1; OCR 4.1 con bbox; inserimento assistito |
| 5 | Coda di revisione diventa il lavoro | Alta | Scope sugli scontrini; regex; soglie calibrate |
| 6 | Demo "vuota" / CRUD | Media-alta | Seed; percorso demo sui moduli del corso |
| 7 | Supabase in pausa all'esame | Media | App sempre accesa (interroga il database ogni giorno); verifica in S5 |
| 8 | Abuso demo → costi (nessun hard cap Mistral) | Media | Tetto applicativo; quota job/giorno; registrazione chiusa |
| 9 | Chiave su repo pubblico | Media | gitleaks + push protection |
| 10 | Perfezionismo | Media | Regola 30 minuti; un tracker |
| 11 | VPS: ore e IP esposto | Bassa | Rimandato a dopo la consegna |
| 12 | Dipendenze pesanti in produzione (torch, statsforecast) | Bassa | Solo nel gruppo `notebook`; ricalcolo notturno in puro Python |
| **13** | **NiceGUI 4.0 a 3 giorni dal rilascio** | **Media** | Versioni esatte pinnate; regole 4.0 in `CLAUDE.md`; test Playwright sulle pagine critiche (revisione, approvazione) in S2; ADR + pin 3.19 solo su bug bloccante documentato |
| 14 | Connessione DB sbagliata | Alta se ignorata | Pooler 5432 in `.env.example` con motivazione |
| 15 | Vision che inventa cifre | Media | Haiku default; guardrail somma/totale; eval |
| 16 | Backup che non si sa ripristinare | Media | Test di ripristino entro il 25/11 |
| 17 | Dato personale inviato a provider US | Media (orale) | Ritaglio manuale, schema senza campi di pagamento, redazione sul JSON; flag `VISION_PROVIDER=mistral`; sub-processor e SCC dichiarati |
| 18 | Flusso completo online troppo tardi | Alta | Fetta verticale entro il 22/11; ultimo deploy di funzionalità il 2/12 |
| 19 | Demo esaurita o sporcata prima dei docenti | Media | Credenziali nel documento di consegna; quota propria; ripristino da snapshot |
| 20 | Dati personali o di terzi nel repo pubblico (golden set, cassette) | Media | Solo annotazioni nel repo; cassette su immagini sintetiche |
| 21 | Offerta della cooperativa o del volantino sbagliato | Media | `Flyer.insegna` e flag `incluso`; insegna Coop di riferimento nelle preferenze |
| 22 | Esclusione alimentare non applicata (attributi mancanti) | Media | Attributi con conferma umana; allergie fail-closed; limite dichiarato |

---

## 12. Decisioni fuori programma del corso (da motivare nel README)
Multi-provider scelto con l'eval · statsforecast/Chronos-2/Timestral (solo notebook) · pgvector al posto di Chroma/Pinecone · trigrammi prima degli embedding · Supabase · provider abstraction propria · Impeccable + frontend-design · NiceGUI 4.0 adottato al rilascio (rischio accettato, mitigato).

---

## Appendice A — Verifiche con fonti del 7/11/2026: smentito e sostituito

*Alcune righe sono superate dalla v1.4 (appendice C): JWKS, baseline statsforecast in produzione, backup completo, ordine del VPS.*

| Voce | Esito | Motivo |
|---|---|---|
| Mistral Small 4 per la vision | Default → Claude Haiku 5.5 (Small 4 resta per testo e nell'eval; flag per EU-only) | Benchmark OCR deboli, cifre inventate su foto reali |
| `mistral-embed` | → `text-embedding-3-small` | Modello del 2023, 5× il prezzo |
| Pixtral 12B / Large, Mistral OCR 4.0 | Ritirati | 31/12/2025, 31/5/2026, 30/9/2026 |
| Tetto di spesa Mistral in console | **Esiste** (verificato l'8/11): "Tetto di spesa mensile per il superamento del limite", minimo 10 € | Tetto console a 10 € + tetto applicativo |
| Tier gratuito Mistral | Escluso | Usa le richieste per training |
| Timestral come forecaster di produzione | → esperimento; baseline statsforecast | Repo immaturo; nessuna evidenza su serie corte |
| SQLModel | → SQLAlchemy 2.x | Pin incoerente |
| respx | → vcrpy + pytest-recording, httpx2-pytest | Non supporta httpx2 |
| aiogram | → python-telegram-bot | Pin `pydantic<2.14` |
| Supabase direct connection | → session pooler 5432 ovunque | IPv6-only su Free; runner GitHub senza IPv6 |
| JWT HS256 | → JWKS | Chiavi asimmetriche nei nuovi progetti |
| Hetzner CX22/CAX11 | Rimosso → OVH VPS-1 | Linea CX/CAX non ordinabile; ~9,5 € IVA incl. |
| Railway "5 $" | → ~8 € reali a 0,5 GB/0,2 vCPU | Usage oltre i 5 $ inclusi |
| Railway "senza IPv6" (v1.2) | Corretto: toggle disponibile | Changelog 3/7/2026; il pooler resta la regola |
| Backup su artifact GitHub | → Cloudflare R2 cifrato | Artifact leggibili su repo pubblico, quota 500 MB |
| Originali 30 giorni | → ≤ 7 giorni + minimizzazione | Minimizzazione GDPR; CF e PAN sugli scontrini |
| Supabase pausa "90 giorni" | Finestra di ripristino 1 anno | Docs aggiornate |
| NiceGUI 4.0 come riferimento | **Confermato per scelta dell'autore** | Rischio accettato: pin esatto, regole 4.0, test UI; 3.19 solo su bug bloccante |

## Appendice B — Decisioni prese per raccomandazione, ribaltabili con una riga
1. **Hosting d'esame = Railway Hobby (~5–8 €)**; il VPS d'apprendimento è rimandato a dopo la consegna (v1.4).
2. **Default vision = Claude Haiku 5.5 con minimizzazione** e trasferimento US dichiarato. Alternativa: `VISION_PROVIDER=mistral` per EU-only, con accuratezza inferiore misurata nell'eval.
3. Tagli adottati: pagina costi → LangSmith + README; bot Telegram in S4; eval a 3 colonne base.
4. **Ordine di taglio (v1.4):** la chat minimale è l'ultima a saltare perché è l'unico punto con RAG e tool calling. Ribaltabile se la griglia d'esame non li valuta: in quel caso torna prima nell'ordine.
5. **Insegna Coop di riferimento:** da indicare (quella dove si fa la spesa); finché manca, i volantini Coop non entrano nell'estrazione.
6. **`Provider` proprio** invece di `init_chat_model` (ADR 0012): scelto perché il ticket 08 era già scritto così.
7. **Soglia di viaggio:** default 5 € e 2 catene, impostabili dall'utente.

## Appendice C — Revisione indipendente del 9/11/2026: modifiche della v1.4

| Modifica | Sezioni | Motivo | ADR |
|---|---|---|---|
| `ProductGroup` come unità di magazzino, lista e confronto; `GroupAlternative`; rimossa `ProductEquivalence` | §2.1–2.4, §3.3 | Con il consumo per prodotto, lo stesso bisogno comprato in due catene restava a livello 0 in due righe; le equivalenze a coppie non sono transitive; `identico` duplicava `ProductAlias` | 0005 |
| Prezzo di riferimento dagli scontrini; verdetto anche per confronto tra catene; soglia a 2 acquisti | §2.3 | I volantini contengono solo promozioni e in 5 settimane non danno 8 osservazioni | 0006 |
| `Flyer`, `condizione` dell'offerta, deduplica, attributi per le esclusioni, `estrazione_grezza`, `PriceObservation` | §2.1, §2.5 | Campi che i dati raccolti mostrano già (insegne Coop diverse, sei volantini Lidl a settimana) o senza i quali una regola non ha su cosa lavorare | 0005, 0006 |
| Soglia di viaggio e "offerte che ti riguardano" | §2.3, §9 | Rendono la lista una decisione spiegabile e il verdetto dimostrabile sui dati reali | 0006 |
| Minimizzazione senza taglio automatico; redazione sul JSON | §3.1, §4 | Le regex agiscono su un testo che esiste solo dopo il modello; la data sta di norma sotto il totale | 0007 |
| Login lato server, niente JWKS | §7 | Nessun client presenta token all'API | 0008 |
| Ricalcolo notturno nel processo; forecasting solo nei notebook | §3.4, §8 | Due stimatori della stessa quantità; workflow schedulato fragile e con segreti | 0009 |
| Trigrammi prima degli embedding; niente HNSW | §3.3, §7 | Righe abbreviate; catalogo di poche centinaia di righe | 0010 |
| Backup ridotto; VPS dopo la consegna; deploy automatico spento dal 3/12; credenziali demo e dati reali fuori dal repo pubblico | §4, §5, §8 | Proporzione rispetto a due utenti; rischio demo e dati personali | 0011 |
| `Provider` proprio, una sola strada | §3.7 | La v1.3 lasciava un "oppure" | 0012 |
| Calendario a fette verticali; ordine di taglio | §1, §9 | Primo flusso completo previsto il 29/11 con freeze il 3/12: circa 70 ore utili, non 100 | — |

**Verifiche del 9/11:** Haiku 5.5 a 0,10 $/0,50 $ per M token sotto i 100k di prompt, 5× oltre; tariffe Railway a consumo; SDK Anthropic e Mistral su `httpx2`; vcrpy con supporto `httpx2` dalla 8.2; NiceGUI 4.0.0 ancora unica 4.x; pausa Supabase dopo 7 giorni di bassa attività. Non verificati: prezzi OVH e Hetzner, limiti LangSmith, esportazione dalla cronologia Lidl Plus.
