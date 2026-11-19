# 0013 — Config Railway in `.railway/railway.ts`, non in `railway.json`

**Contesto:** la SPEC §8 voleva tutta la config in `railway.json`. Al 19/11 la CLI Railway (5.71.0) lo dichiara deprecato: i file esistenti funzionano fino al 1/12/2026, cioè prima del freeze del 3/12 e della valutazione del 5–12/12. Al primo deploy la sezione `deploy` del file non è stata applicata (regione `iad`, nessun healthcheck).
**Decisione:** Infrastructure as Code di Railway in `.railway/railway.ts`, generato con `railway config migrate` e applicato con `railway config plan` / `railway config apply`. Variabili `unmanaged`: i segreti restano solo su Railway, mai nel file. SDK `railway` pinnato esatto in `package.json` (solo sviluppo, fuori dall'immagine Docker).
**Conseguenze:** nel repo entrano `package.json` e `package-lock.json` e serve Node in locale per `plan`/`apply`; regione, replica e healthcheck si cambiano dal file, non dalla dashboard né con `railway scale`.
