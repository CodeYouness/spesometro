# Spesometro

Assistente per la spesa alimentare: da scontrini e volantini costruisce storico prezzi e acquisti, stima il magazzino di casa e propone una lista spesa ottimizzata per catena.

## Language

### Fiducia nei dati

**confidenza**:
Numero tra 0 e 1 che dice quanto è affidabile un singolo dato estratto o abbinato (offerta, riga scontrino, alias, equivalenza). Fa parte della provenienza.
_Avoid_: livello_confidenza, score, probabilità

**livello_confidenza**:
Giudizio qualitativo (bassa | media | alta) su quanto è affidabile la stima di un articolo del magazzino; cresce con il numero di acquisti e di feedback.
_Avoid_: confidenza (riservata alla provenienza), affidabilità

**livello**:
Stadio (0 | 1 | 2) del modello di stima di un articolo del magazzino, sbloccato dalla quantità di dati disponibili. Determina il `livello_confidenza`, ma non è la stessa cosa.
_Avoid_: livello_confidenza, tier

### Coda di lavoro

**Job**:
Un'unità di lavoro asincrono in coda (es. estrazione di uno scontrino), presa in carico da un worker con un lease a tempo.
_Avoid_: task, compito

**stato del Job**:
`pending` (in attesa di un worker) | `running` (preso in carico, lease attivo) | `done` (completato) | `failed` (tentativi esauriti). Insieme minimo per una coda con lease.
_Avoid_: queued, completed, error
