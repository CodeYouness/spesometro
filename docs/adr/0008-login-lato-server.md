# 0008 — Login lato server, niente JWKS

**Contesto:** la v1.3 verificava in FastAPI i JWT di Supabase Auth via JWKS. NiceGUI è renderizzato dal server e la sessione vive in `app.storage.user`: nessun client presenta token all'API; gli account sono due e la registrazione è chiusa.
**Decisione:** login dalla pagina NiceGUI con Supabase Auth (`sign_in_with_password`, lato server); a login riuscito `user_id` in `app.storage.user`; middleware che protegge le pagine. Nessuna verifica JWKS, nessuna gestione di refresh token.
**Conseguenze:** il ticket 03 cambia oggetto; `SUPABASE_JWKS_URL` esce da `.env.example`. Se nascerà un client esterno all'app, la verifica via JWKS si aggiunge allora.
