# Spesometro — Specifica di progetto

**Versione:** 1.3 — 7 novembre 2026
**Autore:** Youness (GitHub: CodeYouness)
**Contesto:** esame finale, Master part-time AI Engineering (Boolean). Consegna **12 dicembre 2026**; finestra di valutazione 5–12 dicembre.
**Storia:** grill (Q1–Q46) → revisione ostile (R1–R15) → analisi hosting (v1.1) → verifica fornitori con fonti del 7/11 (v1.2) → **revisione critica finale su 10 punti: modellazione, forecasting, equivalenze, scadenze, provenienza, hosting, backup, NiceGUI, privacy, sostenibilità (v1.3)**. L'appendice A registra cosa è stato smentito; l'appendice B le decisioni prese per raccomandazione e ancora ribaltabili.

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

Assistente per la spesa alimentare che, da **foto di scontrini** e **PDF di volantini** (Lidl, Eurospin, Coop), costruisce uno storico prezzi e acquisti, stima cosa sta per finire in casa e propone una **lista spesa ottimizzata per catena**, che l'utente approva prima dell'uso. Risolve tre problemi: non sapere se un'offerta è davvero conveniente (serve lo storico), non ricordare cosa manca, e dover confrontare a mano più volantini.

**Perimetro verificato:** 3 catene (Lidl, Eurospin, Coop). Ingestione generica (il modello deduce la catena, con fallback a scelta manuale); catalogo, golden set e demo coprono solo le 3.

**Flusso fondamentale da preservare (MVP d'esame, chiuso entro fine S3):**
scontrino → riconoscimento prodotti → storico acquisti → magazzino → volantini → confronto offerte → lista ottimizzata → approvazione umana.

**Ordine di taglio se si va lunghi** (dal primo che salta):
1. chat con tool calling
2. esperimenti di forecasting (Chronos-2/Timestral; resta la baseline statsforecast)
3. matching con embedding (resta BM25 + regole)
4. bot Telegram (resta upload web) — già spostato in S4
5. confronto modelli oltre le 3 colonne base

**Tagliato in v1.3:** pagina costi/stato nella web app → sostituita da un link a LangSmith e da una tabella nel README.

**Lavoro futuro (dichiarato nel README):** agente che compila il carrello online (solo account proprio, mai pagamento), download automatico dei volantini, lettura della scadenza reale dalla foto della confezione, misura dello spreco, indice di inflazione personale, deploy self-hosted su VPS (§8), Hermes Agent come runtime sempre acceso.

---

## 2. Regole di funzionamento e casi limite

### 2.1 Entità (schema dati)
- `User` — account; `user_id` su ogni tabella, filtro in ogni query (testato). Registrazione **disabilitata**: solo account personale + account demo.
- `Product` — canonico: nome, marca, categoria, `unità_di_vendita` (pezzo | peso variabile), dimensione, **`tipo_durata` ∈ {scadenza_reale, durata_stimata, non_deperibile}**, durata tipica (giorni, solo per `durata_stimata`), scadenza reale opzionale (inserita a mano).
- `ProductAlias` — stringa grezza → `Product` **identico**, per catena. Con provenienza (§2.4).
- **`ProductEquivalence`** — `product_a`, `product_b`, `tipo` ∈ {**identico** (stesso prodotto, stessa marca/formato, alias diversi tra catene), **equivalente** (stessa categoria e formato normalizzato, marca diversa: sostituibile senza chiedere), **alternativa** (prodotto diverso che soddisfa lo stesso bisogno: proposto, mai sostituito in automatico)}, origine (regola | umano). Con provenienza.
- `Offer` — catena, product (nullable se non mappato), `prezzo_confezione`, `prezzo_unitario`, `unità`, `prezzo_barrato`, `sconto_dichiarato`, `validità_da/a`, pagina/volantino di origine. Con provenienza.
- `Receipt` + `ReceiptLine` — data, catena, totale; riga grezza, quantità, prezzo, sconto riga, product. `ReceiptLine` con provenienza.
- `InventoryItem` — product, data ultimo acquisto, quantità ultimo acquisto, **`tasso_consumo`** (unità/giorno, nullable), durata stimata, stato `probabilmente_finito` (bool), **`livello_confidenza`** ∈ {bassa, media, alta}, **`livello`** ∈ {0, 1, 2}.
- `Job` — coda in Postgres (tipo, payload, stato, tentativi, lease).

Prezzi normalizzati a €/kg, €/L, €/pezzo. Per i prodotti a peso variabile il confronto usa sempre €/kg.

### 2.2 Magazzino a tre livelli (si sbloccano da soli con i dati)
| Livello | Condizione | Stima | `livello_confidenza` | UI |
|---|---|---|---|---|
| 0 | 0–1 acquisti del prodotto | stato da durata tipica della categoria | bassa | "stima provvisoria" |
| 1 | 2–3 acquisti | tasso di consumo = quantità acquistata / intervallo medio di riacquisto → stato + quantità residua stimata | media | quantità mostrata con "≈" |
| 2 | ≥ 4 acquisti **o** ≥ 2 feedback | media mobile esponenziale del tasso di consumo | alta | quantità mostrata |

Feedback dalla lista: "ne ho ancora" / "è finito prima" corregge il **tasso**, non la durata; tolto 2 volte di seguito → chiedi "non ti serve o non lo vuoi più?". Funzione pura in `packages/core`, testata.

### 2.3 Regole deterministiche
- **Quantità in lista** = fabbisogno su 2 settimane (dal tasso di consumo o dalla durata tipica) − scorta stimata.
- **Scorta extra** solo se sconto ≥ X% rispetto alla mediana storica **e** tetto di budget rispettato **e**: `non_deperibile` → sempre ammessa; `durata_stimata` → solo se la stima copre il consumo **con margine del 50%** e `livello_confidenza` ≥ media; `scadenza_reale` → solo se la scadenza inserita copre il consumo.
- **Esclusioni alimentari** (allergie, dieta, motivi religiosi): filtro duro, prima dell'ottimizzazione.
- **Confronto prezzi tra catene**: sul gruppo *identico + equivalente*; l'*alternativa* appare solo come suggerimento "risparmieresti X scegliendo Y".
- **Prezzo anomalo** (es. −80% vs mediana) → coda di revisione, mai in lista.
- **Prodotto non trovato** in nessun volantino → "senza offerta", mai inventato.
- **Soglie minime di dati per ogni previsione** (tabella `soglie_dati` nel codice, badge di confidenza nell'UI):

| Previsione | Dati minimi | Sotto soglia |
|---|---|---|
| Consumo / fabbisogno | ≥ 3 acquisti del prodotto (fallback categoria) | "stima provvisoria" da durata tipica |
| Prezzo "davvero conveniente" | ≥ 8 osservazioni del prezzo dai volantini | si mostra solo lo sconto dichiarato con etichetta "storico insufficiente" |
| Ritorno promozione | ≥ 3 cicli osservati | feature presente nel codice, si attiva da sola quando i dati bastano (non entro dicembre) |

### 2.4 Provenienza (mixin di 4 colonne, su `Offer`, `ReceiptLine`, `ProductAlias`, `ProductEquivalence`)
`fonte` (volantino_id | scontrino_id | umano | regola), `acquisito_il`, `confidenza` (0–1), `stato` ∈ {auto, rivisto, rifiutato}. La revisione umana è lo stato, non una riga separata. Nessun audit log per campo. Dà alla UI il filtro "solo dati rivisti" e all'eval la curva precision/confidenza.

### 2.5 Casi limite noti
- Scontrini con sconti riga, coupon, 2×1, resi, vuoti a rendere → somma righe ≠ totale: retry con discrepanza (§3.2).
- Volantini con validità diverse per pagina → validità per offerta.
- PDF a bassa risoluzione → se precision < 70% la pagina va in "inserimento assistito".
- Cold start dichiarato ovunque (livello 0, soglie, badge).

---

## 3. Architettura AI

### 3.1 Pipeline
```
[foto scontrino / PDF volantino] → Storage (ridimensionato ≤1540 px)
  → Minimizzazione (crop sotto la riga TOTALE; regex su PAN parziali, CF, codici fidelity)
  → Job → Estrazione (VLM, structured output JSON-schema → Pydantic)
  → Validazione (coerenza somme/prezzi, range-check) → conferma utente → originale eliminato
  → Matching (normalizzazione regex → alias → ibrido BM25+embed → LLM su top-5 → revisione umana)
  → Catalogo / Equivalenze / Offerte / Righe scontrino (con provenienza)
  → Job notturno: baseline statsforecast + magazzino a livelli
  → LangGraph: stima_fabbisogno → genera_lista → confronta_offerte → ottimizza_carrello
      → [interrupt: approvazione umana, checkpoint persistito] → esporta
  → Chat sui dati (tool calling) — opzionale, S4
```

### 3.2 Estrazione (multi-provider, scelto con l'eval)
- **Scontrini (default, da confermare — appendice B):** immagine minimizzata → **Claude Haiku 5.5** ($0,10 in / $0,50 out per M token, vision solida, structured output; dati solo US, trasferimento dichiarato via SCC). Guardrail: somma righe ≈ totale; il retry riceve la discrepanza ("somma 23,10, totale 21,60: cerca righe sconto"). **Flag di configurazione `VISION_PROVIDER`**: con `mistral` il default diventa Mistral Small 4 (EU, Svezia) senza altre modifiche.
- **Confronto nell'eval** (3 colonne base: Haiku 5.5, Mistral Small 4 `mistral-small-2603`, un modello Qwen via OpenRouter con `data_collection:"deny"` + `zdr:true`; altre colonne — Ministral 3 8B, DeepSeek V4.1 Flash, Gemini Flash-Lite, modelli locali sul Mac — solo se avanza tempo). Metriche: accuratezza campo per campo, tasso di cifre errate, costo reale per foto, tempo. **Il prezzo per token non è il criterio** (~0,0004 $ a foto con qualsiasi modello): contano accuratezza, affidabilità del provider e residenza dei dati. Se un modello batte il default sul golden set diventa il default, con motivazione nel README.
- **Volantini:** pagina rasterizzata → stesso VLM con schema a campi separati + validatore (prezzo_unitario × quantità ≈ prezzo_confezione). **Mistral OCR 4.1** (`mistral-ocr-4-1`, $4/1000 pagine, $5 con annotazioni, −50% batch) come layer opzionale (bbox e annotazioni con schema per la griglia nuovo/barrato/€-kg). **Gate in S1:** 3 PDF reali, 50 prodotti annotati, precision ≥ 70% altrimenti "inserimento assistito".
- **Regole tecniche:** solo `json_schema` o tool calling, mai `json_object`; immagini ≤ 1540 px / ≤ 400 KB; versioni dei modelli pinnate esplicitamente, mai `-latest`; retry con backoff su 429; **nessun modello uscito da meno di 30 giorni in produzione d'esame: va nell'eval** (ADR).
- Modelli ritirati da non citare come scelta: Pixtral 12B, Pixtral Large, Mistral Small 3.2, Mistral OCR 4.0.

### 3.3 Matching (entity resolution)
1. **Normalizzazione regex** della riga grezza (quantità, unità, marca, abbreviazioni note per catena).
2. Match esatto su alias confermati.
3. Ricerca ibrida BM25 (Postgres full-text) + embedding **`text-embedding-3-small`** (OpenAI, $0,02/M, dimensioni ridotte a ≤ 1024 per HNSW) su pgvector. `multilingual-e5-large` locale solo come colonna di eval se avanza tempo.
4. Sopra soglia alta → auto-accetta; zona grigia → **Mistral Small 4** sceglie tra top-5 o "nuovo prodotto"; sotto soglia bassa → coda di revisione umana. Ogni conferma umana diventa alias (stato `rivisto`).
5. **Equivalenze**: regola deterministica (stessa categoria + stesso formato normalizzato → `equivalente`) + conferma umana dalla coda; le `alternative` solo da conferma umana.
6. **Scope:** matching automatico solo per i prodotti presenti negli scontrini dell'utente (~100–150); le altre offerte restano "non mappate" ma cercabili via RAG.
7. **Soglie calibrate a posteriori** sulla curva di precision del golden set (auto-accept a precision ≥ 0,95). Golden set annotato **prima** di implementare.

### 3.4 Forecasting
- **Produzione = baseline statsforecast** per prodotto (Croston / SeasonalNaive per domanda intermittente; mediana prezzo; periodo medio tra offerte), con le soglie di §2.3. Job notturno.
- **Esperimenti documentati** (notebook, dopo il 28 novembre, solo se c'è tempo): **Chronos-2** (Amazon, Apache 2.0, libreria matura) e **Timestral-123M** (Mistral; repo immaturo: un commit, nessuna release) su dataset pubblico proxy + dati propri, confrontati con la baseline. Fuori programma del corso.

### 3.5 Agente
Un solo grafo **LangGraph 1.2.x**, `interrupt()` + `Command(resume=)`, checkpoint su Postgres (`langgraph-checkpoint-postgres`) **via session pooler 5432** con `prepare_threshold=None`, `supports_pipeline=False`, `setup()` come migrazione. Nessun side-effect prima dell'interrupt. Output = lista strutturata per catena. Nessun multi-agente.

### 3.6 Chat sui dati (opzionale, S4)
5–6 tool: SQL parametriche, catalogo, offerte, magazzino, RAG sui volantini. LLM: Mistral Small 4 (`reasoning_effort="none"`). Memoria di sessione persistita.

### 3.7 Provider
Interfaccia `Provider` propria (~40 righe) con implementazioni Anthropic, Mistral, OpenAI-compatible (copre anche OpenRouter), oppure `init_chat_model`. Niente LiteLLM. **Due client HTTP coesistono:** `httpx2` (SDK Mistral, NiceGUI 4) e `httpx` (python-telegram-bot): dichiarare entrambi, non mockare quello sbagliato.

---

## 4. Guardrail

1. **Prompt injection via immagini/PDF:** l'LLM produce solo JSON validato con Pydantic; nessuna tool call con effetti decisa dal contenuto estratto; range-check su ogni campo numerico.
2. **Costi:** Mistral non offre un hard cap in console → **tetto applicativo** giornaliero per utente e globale con kill switch, su tutti i provider; quota demo in **job LLM/giorno** (es. 30) verificata prima dell'enqueue; `make eval` mai in CI automatica. Mistral **pay-as-you-go con opt-out dal training attivato in Admin Console → Privacy**; mai il tier gratuito (usa i dati per training).
3. **Abuso:** max 5 MB per file, 10 upload/ora per utente, rate limiting, registrazione disabilitata.
4. **Dati personali:** minimizzazione **prima** dell'invio ai modelli (§3.1); originali conservati **al massimo 7 giorni** (eliminati alla conferma dell'utente; si tiene solo il JSON strutturato e, se serve, una thumbnail ritagliata); cancellazione account completa inclusi file su Storage; LangSmith **EU** con `hide_inputs` e `hide_outputs` (anche il JSON estratto può contenere un CF); OpenRouter solo con `data_collection:"deny"` + `zdr:true`; pagina `/privacy` con titolare, finalità (art. 6(1)(b)), retention, diritti, **tabella dei sub-processor con link ai DPA** (Supabase EU, Railway Amsterdam/US, Mistral SE, Anthropic US, OpenAI US, OpenRouter US, LangSmith EU, Telegram NL, Cloudflare R2) e trasferimenti extra-UE con SCC. **Eccessivo e non previsto:** DPIA, DPO, ZDR contrattuale.
5. **Decisioni:** regole in codice deterministico e testate.
6. **Segreti:** solo variabili d'ambiente; `.env.example`; `gitleaks` pre-commit **e** push protection del repo.

---

## 5. Valutazione (`make eval`)

Golden set congelato nel repo con versione e data, annotato **prima** dell'implementazione: 30 scontrini (≥ 5 con sconti/coupon/2×1) + 10 pagine volantino; 200 righe per il matching (con etichetta identico/equivalente/alternativa su 50 coppie); 20 prodotti "finito sì/no"; 20 domande chat con risposta attesa.

| Modulo | Metrica |
|---|---|
| Estrazione scontrini | accuratezza campo per campo; tabella modelli (3 colonne base) con costo e tempo |
| Estrazione volantini | precision/recall su offerte |
| Matching | precision/recall/F1; curva precision–soglia; accuracy sul tipo di equivalenza |
| Magazzino | accuracy su 20 prodotti "finito sì/no", per `livello_confidenza` |
| Forecasting | baseline vs esperimenti: MAE/MASE sul proxy; precision/recall su "torna in offerta" (se i dati bastano) |
| Carrello | € risparmiati vs "tutto nella catena abituale"; tasso di accettazione righe |
| Chat | exact-match / tolleranza numerica (SQL); RAGAS solo sulle domande sui volantini |

Report markdown versionato in `eval/reports/`. Eseguito a mano o su tag. Costo < 1 $ per run.

---

## 6. Stima dei costi (mensili, IVA inclusa dove si applica; S = stima)

| Voce | Costo |
|---|---|
| Claude Haiku 5.5 (estrazione) | 1–2 $ (S) |
| Mistral Small 4 (matching, chat) + OCR 4.1 opzionale | 1–2 $ (S) |
| OpenAI `text-embedding-3-small` | centesimi |
| Eval completo (manuale) | < 1 $ per run |
| **Railway Hobby** (1 servizio always-on a ~0,5 GB / 0,2 vCPU) | **~8 € (S)**; ~5,5 € a 0,4 GB / 0,1 vCPU |
| Supabase Free, LangSmith Developer, GitHub Actions (repo pubblico), Cloudflare R2 | 0 |
| **Totale** | **≈ 10–11 €/mese** |
| OVH VPS-1 (VPS d'apprendimento post-MVP, opzionale) | 4,65 € con impegno 12–24 mesi (V), 6–7 € senza (S) |

Nel README: tabella "costi stimati vs costi reali misurati" a fine progetto, per provider.

---

## 7. Stack tecnologico (versioni esatte bloccate in `pyproject.toml` / `uv.lock`)

- **Python 3.13** (immagine `python:3.13-slim`; evitare 3.15 per i wheel). `uv` workspaces, un solo lock. Pydantic v2, async.
- **NiceGUI 4.0.0 — versione di riferimento.** Requisiti verificati: Python ≥ 3.11, **FastAPI ≥ 0.143.1**, **Starlette ≥ 1.3.1**, Chrome 121+/Safari 17.2+; usa `httpx2` (non installa più `httpx`). Nessuna 3.x come fallback, salvo problema concreto e documentato in ADR. **Regole di codice per la 4.0** (dalle release note, da mettere in `docs/adr/` e nel `CLAUDE.md` del repo):
  - `.props()` non converte più snake_case/camelCase in kebab-case: scrivere i prop Quasar esattamente come li vuole Quasar.
  - Input di testo svuotato → `''`, non `None`: nessun check `is None` su `ui.input`, `ui.textarea`, `ui.date_input`.
  - `run.cpu_bound` usa `spawn`: funzioni importabili a livello di modulo; non usarlo per OCR/LLM (quello va nel worker).
  - `run.io_bound/cpu_bound` e i timer propagano `CancelledError`: rilanciarla, mai `except Exception` nudo.
  - ID DOM `ng-<n>` (per i test Playwright usare selettori propri, non gli ID).
  - `ui.table`: `pagination_controls=False` dove i controlli non servono.
  - Oggetti scene/leaflet richiedono `with` (non usati).
  - Rimossi: `sanitize=None`, `coroutine=` in `background_tasks`, `ui.add_scss/add_sass`, `Props.add_rename`: non usarli.
  - Quasar 2.35 / AG Grid 36 / Tailwind 4.3: i dialog si chiudono su mousedown fuori; le classi CSS interne di AG Grid sono cambiate: nessuno stile basato su classi interne.
  - `WEB_CONCURRENCY>1` solleva `ValueError`: **1 replica, 1 worker uvicorn** (Railway non ha sticky session).
  - Auth: `BaseHTTPMiddleware` + `app.storage.user` + `storage_secret` (esempio ufficiale `examples/authentication`, già compatibile 4.0); montaggio con `ui.run_with(app, mount_path=..., storage_secret=...)`.
  - Issue aperte al 7/11 sul 4.0: nessuna su `run_with`, auth, proxy, Tailwind o `httpx2`; se compare un bug bloccante: ADR + pin a `3.19.0` (costo ~mezza giornata), non prima.
- **Monorepo:** `apps/api` (FastAPI), `apps/web` (NiceGUI via `ui.run_with`), `apps/bot` (webhook nello stesso processo, lifecycle in `lifespan`), `apps/worker` (task asyncio leggero + job notturno separato), `packages/core` (dominio, regole, schemi, provider, minimizzazione; senza dipendenze da web/DB), `eval/`, `docs/`, `docker/`, `.github/workflows/`.
- **AI:** Claude Haiku 5.5 (vision, da confermare), Mistral Small 4 (testo), Mistral OCR 4.1 (opzionale), OpenAI `text-embedding-3-small`; LangChain 1.x / LangGraph 1.2.x; statsforecast; Chronos-2 e Timestral (notebook).
- **Dati:** Supabase Free (Postgres + pgvector + Auth + Storage, regione EU). **SQLAlchemy 2.x** (`Mapped`/`mapped_column`, asyncpg) + **Alembic async**; non SQLModel. `pgvector.sqlalchemy` importato in `script.py.mako`. HNSW ≤ 1024 dimensioni, `maintenance_work_mem` basso.
- **Connessioni Supabase:** **tutto sul session pooler porta 5432** (utente `postgres.<ref>`): app, Alembic, pg_dump, checkpointer LangGraph, job su GitHub Actions. La direct connection è IPv6-only su Free e i runner GitHub non hanno IPv6 (Railway lo ha come toggle, ma non serve); mai il transaction pooler 6543. Pool `pool_size ≤ 5`, chiuso nel cron.
- **Auth:** Supabase Auth email/password; token verificati in FastAPI via **JWKS** (chiavi asimmetriche nei nuovi progetti).
- **Coda:** tabella `jobs` in Postgres, `FOR UPDATE SKIP LOCKED`, lease con timeout.
- **Design:** `/impeccable init` → `DESIGN.md`; comandi `critique`/`audit`/`typeset`/`colorize` e detector via URL del dev server (live mode e regole su `.py` non funzionano) + skill `frontend-design` di Anthropic.
- **Input:** **python-telegram-bot 22.8** in webhook (`updater(None)`, esempio `customwebhookbot`), `secret_token`, 200 immediato e processing in background task; polling in dev, webhook in prod; pairing codice 6 cifre, 10 min, monouso; `httpx` dichiarato esplicitamente. In **S4**.
- **Test:** pytest; **vcrpy + pytest-recording** (cassette `httpx2`, `filter_headers=["Authorization"]`, `--block-network`); **httpx2-pytest** per i mock unitari. Playwright MCP per i test end-to-end della UI.
- **Qualità:** ruff; mypy con override permissive su `apps/web` e `apps/bot`; non `ty`.
- **Osservabilità:** LangSmith Developer **EU** (`eu.smith.langchain.com`, 5k tracce/mese, retention 14 gg) con `LANGSMITH_HIDE_INPUTS/OUTPUTS`; log JSON; `/health` con `PORT` da env; alert Telegram; UptimeRobot (gratis) sull'URL pubblico dal 1° dicembre.

---

## 8. Deploy in produzione e monitoraggio

- **Produzione d'esame: Railway Hobby** (da confermare — appendice B). Regione **EU West (Amsterdam)**. **Un solo servizio** Docker multi-stage (uv: `uv sync --frozen --no-install-workspace` come layer cache, poi `--package`, stage finale solo `.venv`): API + web + webhook + worker leggero. Serverless/app sleeping **spento**, `replicas: 1`. Deploy automatico da push su `main`. Immagine su **GHCR** (multi-arch). **Freeze dei deploy dal 3 dicembre**, salvo hotfix.
- **Job notturno** (baseline statsforecast, magazzino): **GitHub Actions scheduled workflow** (runner 4 vCPU / 16 GB) + `workflow_dispatch` per lanciarlo davanti ai docenti; cron in **UTC**; può ritardare 5–30 min; **si disattiva dopo 60 giorni senza commit**; wheel torch CPU in cache. Alternative: Railway cron o Modal.
- **Backup Supabase Free (strategia completa):** workflow GitHub Actions giornaliero (`schedule` + `workflow_dispatch`): `supabase db dump --db-url <session pooler, percent-encoded>` in tre file (roles, schema, data con `--use-copy`), + dump **solo dati** di `auth.users`/`auth.identities` (mai lo schema `auth`/`storage`, gestito dalla piattaforma), + export dei file Storage via API; cifratura con `age`; upload su **Cloudflare R2** (10 GB free). **Non** negli artifact del repo pubblico (leggibili da chiunque, quota 500 MB). Retention 30 gg fino all'esame, poi settimanale. **Test di ripristino entro il 25/11** sul secondo progetto Free (`psql --single-transaction --variable ON_ERROR_STOP=1 --file roles.sql --file schema.sql --command 'SET session_replication_role = replica' --file data.sql`), poi cancellarlo. **Keep-alive:** il Free pausa dopo 1 settimana di bassa attività; una `SELECT 1` giornaliera dal workflow basta; finestra di ripristino 1 anno. Egress 5 GB/mese: foto servite con signed URL.
- **CI (S1):** ruff + pytest unit con cassette; mypy e integration con Postgres in container solo dopo il 1° dicembre; gitleaks + push protection.
- **Monitoraggio:** LangSmith EU (mascherato), alert Telegram (budget 80%, job fallito 3 volte), UptimeRobot.
- **Account demo:** `demo` con 2–6 mesi di storico sintetico generato da script e dichiarato, scrittura consentita, quota propria, ripristino da snapshot; credenziali nel README.
- **Piano B hosting:** Dockerfile + immagine GHCR + Supabase esterno → Render Starter/Fly/Koyeb in 60–90 minuti. **Prova generale di migrazione a fine novembre** (1 ora).
- **VPS d'apprendimento, dopo l'MVP di S3, documentato in `docs/deploy-vps.md`:** **OVH VPS-1** (2 vCore / 4 GB / 40 GB NVMe, backup giornaliero incluso, traffico illimitato; ordinare entro il 15/11 per l'eventuale verifica documenti) al posto di Hetzner (CX/CAX non ordinabile al 7/11). Con 4 GB il job torch può girare sullo stesso host (container `run --rm` notturno). Mai come URL dato ai docenti finché non regge 2 settimane stabili. Provider low-cost: CrownCloud Amsterdam (6 GB, 5 $, 12 anni di storia) è l'unica offerta LowEndSpirit a rischio basso-medio; solo dopo l'esame.
  - Checklist VPS: utente non-root + chiavi SSH, `PasswordAuthentication no`, ufw deny + 22/80/443, fail2ban, unattended-upgrades, firewall del provider; **mai `ports: "8000:8000"`** (Docker bypassa ufw): `127.0.0.1:` o rete interna con **Caddy 2.11** (volume `caddy_data`; `acme_ca` staging in test; Let's Encrypt 5 duplicati/settimana); dominio proprio; `mem_limit` e swap 2 GB; cache HF su volume; `docker system prune` settimanale; `restart: unless-stopped`.

---

## 9. Timebox (20 ore/settimana)

| Settimana | Obiettivo | Gate |
|---|---|---|
| **S1** 9–15 nov | Repo (uv, Python 3.13, NiceGUI 4.0.0 e dipendenze pinnate, `CLAUDE.md` con le regole 4.0), schema + Alembic + mixin provenienza, Supabase (pooler, JWKS), minimizzazione immagini, estrazione scontrini e volantini, golden set annotato, CI minima, deploy "hello" su Railway EU, backup su R2. **Dom 8:** contare i volantini storici. Ordine OVH entro il 15. | Precision volantini ≥ 70% su 3 PDF; archivi < 20 PDF → niente backfill. |
| **S2** 16–22 nov | Normalizzazione regex, catalogo, equivalenze (regola + conferma), matching ibrido, coda di revisione, UI NiceGUI minima, `DESIGN.md`. | F1 matching sul golden set; soglie calibrate. **Test di ripristino backup entro il 25.** |
| **S3** 23–29 nov | Magazzino a 3 livelli, `tipo_durata`, baseline statsforecast + soglie dati, LangGraph con approvazione, lista per catena, seed demo. **Prova di migrazione hosting (1 h).** | **MVP d'esame end-to-end online.** |
| **S4** 30 nov–6 dic | Guardrail, quote, LangSmith, alert, UptimeRobot, pagina privacy; bot Telegram; eval a 3 colonne; chat e notebook forecasting solo se c'è tempo. **Freeze deploy dal 3/12.** | `make eval` completo. |
| **S5** 7–12 dic | README, 8 sezioni, report eval, percorso demo di 5 minuti, polish UI, margine. Verifica keep-alive, cron attivo, backup recente. | Consegna. |

Ogni ticket ha una stima in ore; la somma settimanale non supera le 20.

**Percorso demo per i docenti (5 minuti):** foto scontrino → minimizzazione → traccia LangSmith → matching con confidenza e tipo di equivalenza → revisione umana → magazzino con livello e `livello_confidenza` → grafo con checkpoint → lista approvata con spiegazione e badge "storico insufficiente" dove vero → `workflow_dispatch` del job notturno.

---

## 10. Metodo di lavoro

- grill (fatto) → questa spec → ticket settimanali → implementazione in sessioni Claude Code separate → retro.
- **Fonte di verità:** markdown nel repo (`BACKLOG.md`, `WORK_LOG.md`, `docs/adr/`, `GLOSSARY.md`); `.scratch/` fuori da git. GitHub Projects con 5 card-milestone.
- **Regola decisionale:** decisione irreversibile = 30 minuti max; tutto il resto = default più semplice + ADR di 3 righe. **ADR già decise:** nessun modello < 30 giorni in produzione; NiceGUI 4.0 adottato con accettazione del rischio; pooler 5432 ovunque.
- Un solo assistente per il codice. `docs/ai-workflow.md`.
- MCP in Claude Code: Supabase, documentazione live, Playwright. Niente Notion.
- Dati: fotografare lo storico di scontrini e scaricare i volantini correnti **questa settimana**.

---

## 11. Registro dei rischi

| # | Rischio | P | Mitigazione |
|---|---|---|---|
| 1 | Scope troppo ampio per 100 ore | Alta | MVP + ordine di taglio; pagina costi tagliata; bot in S4 |
| 2 | Volantini storici non esistono | Alta | Verifica dom 8; soglie dati e badge "storico insufficiente" |
| 3 | Cold start | Alta | Magazzino a livelli, soglie, baseline onesta |
| 4 | Estrazione volantini < 70% | Media-alta | Gate S1; OCR 4.1 con bbox; inserimento assistito |
| 5 | Coda di revisione diventa il lavoro | Alta | Scope sugli scontrini; regex; soglie calibrate |
| 6 | Demo "vuota" / CRUD | Media-alta | Seed; percorso demo sui moduli del corso |
| 7 | Supabase in pausa / cron disattivato all'esame | Alta | Keep-alive; commit regolari; `workflow_dispatch`; verifica S5 |
| 8 | Abuso demo → costi (nessun hard cap Mistral) | Media | Tetto applicativo; quota job/giorno; registrazione chiusa |
| 9 | Chiave su repo pubblico | Media | gitleaks + push protection |
| 10 | Perfezionismo | Media | Regola 30 minuti; un tracker |
| 11 | VPS: ore e IP esposto | Media | Solo post-MVP; checklist; OVH non LES |
| 12 | Worker torch in OOM | Media | Job su GitHub Actions (16 GB) |
| **13** | **NiceGUI 4.0 a 3 giorni dal rilascio** | **Media** | Versioni esatte pinnate; regole 4.0 in `CLAUDE.md`; test Playwright sulle pagine critiche (revisione, approvazione) in S2; ADR + pin 3.19 solo su bug bloccante documentato |
| 14 | Connessione DB sbagliata | Alta se ignorata | Pooler 5432 in `.env.example` con motivazione |
| 15 | Vision che inventa cifre | Media | Haiku default; guardrail somma/totale; eval |
| 16 | Backup che non si sa ripristinare | Media | Test di ripristino entro il 25/11 |
| 17 | Dato personale inviato a provider US | Media (orale) | Minimizzazione; flag `VISION_PROVIDER=mistral`; sub-processor e SCC dichiarati |

---

## 12. Decisioni fuori programma del corso (da motivare nel README)
Multi-provider scelto con l'eval · statsforecast/Chronos-2/Timestral · pgvector al posto di Chroma/Pinecone · Supabase · job notturno su GitHub Actions · provider abstraction propria · Impeccable + frontend-design · NiceGUI 4.0 adottato al rilascio (rischio accettato, mitigato).

---

## Appendice A — Verifiche con fonti del 7/11/2026: smentito e sostituito

| Voce | Esito | Motivo |
|---|---|---|
| Mistral Small 4 per la vision | Default → Claude Haiku 5.5 (Small 4 resta per testo e nell'eval; flag per EU-only) | Benchmark OCR deboli, cifre inventate su foto reali |
| `mistral-embed` | → `text-embedding-3-small` | Modello del 2023, 5× il prezzo |
| Pixtral 12B / Large, Mistral OCR 4.0 | Ritirati | 31/12/2025, 31/5/2026, 30/9/2026 |
| Tetto di spesa Mistral in console | Non esiste | Solo tracking: tetto applicativo |
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
1. **Hosting d'esame = Railway Hobby (~8 €)**, OVH VPS-1 come VPS d'apprendimento post-MVP. Alternativa: OVH in produzione subito (−3 €/mese, +10–15 h di setup da assorbire tagliando bot e chat).
2. **Default vision = Claude Haiku 5.5 con minimizzazione** e trasferimento US dichiarato. Alternativa: `VISION_PROVIDER=mistral` per EU-only, con accuratezza inferiore misurata nell'eval.
3. Tagli adottati: pagina costi → LangSmith + README; bot Telegram in S4; eval a 3 colonne base.
