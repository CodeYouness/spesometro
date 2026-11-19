# 0009 — Ricalcolo notturno nel processo, forecasting solo nei notebook

**Contesto:** la v1.3 metteva in produzione una baseline statsforecast in un workflow schedulato di GitHub Actions. Quella baseline e la media mobile del magazzino stimano la stessa quantità con gli stessi pochi dati; il workflow richiede i segreti del database, può ritardare e si disattiva dopo 60 giorni senza commit.
**Decisione:** magazzino a livelli e prezzi di riferimento sono funzioni pure in `packages/core`, ricalcolate ogni notte da un task pianificato nel processo dell'app (registrato come `Job`), con un pulsante "ricalcola ora" nella UI. statsforecast, Chronos-2 e Timestral restano nei notebook di confronto, in un gruppo di dipendenze `notebook`.
**Conseguenze:** nessuna dipendenza di forecasting né torch nell'immagine di produzione; GitHub Actions resta solo per CI e backup; la demo mostra il pulsante al posto del `workflow_dispatch`.
