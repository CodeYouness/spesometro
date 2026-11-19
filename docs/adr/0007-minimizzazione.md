# 0007 — Minimizzazione senza taglio automatico

**Contesto:** la v1.3 prevedeva il taglio "sotto la riga TOTALE" e regex prima dell'invio al modello. Le regex agiscono su un testo che esiste solo dopo l'estrazione; localizzare la riga richiede un OCR locale; sugli scontrini italiani data, ora e numero documento stanno di norma sotto totale e pagamento, quindi il taglio toglierebbe la data.
**Decisione:** ridimensionamento a ≤ 1540 px e ≤ 400 KB; ritaglio manuale facoltativo nell'upload; schema di estrazione senza campi di pagamento, carta o fidelity; redazione regex (PAN parziali, CF, codici fidelity) sul JSON estratto prima di persistenza e tracce. Nessun OCR locale.
**Conseguenze:** se l'utente non ritaglia, la zona pagamento raggiunge il provider vision: va dichiarato in `/privacy`; `VISION_PROVIDER=mistral` tiene il dato in UE. Da verificare su 3 scontrini reali dove sta la data; se manca, la si chiede alla conferma.
