# Decisioni prese senza chiedere conferma

Come richiesto dalla regola d'oro §0.3: qui annoto i default scelti quando la specifica lasciava un margine, con il motivo.

## Fase 0

- **Pillow solo in build/sviluppo**: `requirements.txt` (runtime) non include Pillow. `tools/generate_assets.py` e `tools/npc_portraits.py` girano in uno stage separato del `Dockerfile` (che installa `requirements-dev.txt`) e i soli PNG risultanti vengono copiati nell'immagine finale. In locale vanno lanciati a mano una volta (vedi README). Questo rispetta alla lettera "Richiedono Pillow: aggiungilo ai requisiti di sviluppo" (§0) senza portarsi dietro Pillow in produzione.
- **`DATABASE_URL` di default**: `sqlite+aiosqlite:///./dungeon_master.db` per lo sviluppo locale; in produzione va sempre valorizzato con un URL Postgres (`postgresql+asyncpg://...`, Neon). Non c'è validazione che vieti SQLite in produzione: è responsabilità di chi fa il deploy.
- **Migrazioni**: per la Fase 0 le tabelle si creano con `Base.metadata.create_all` all'avvio (schema minimo, un'unica tabella `users`). Quando lo schema dei salvataggi si stabilizzerà (Fase 3+) valuteremo Alembic, per non perdere dati in produzione durante un update.
- **`ALLOWED_USER_IDS` vuoto = tutti ammessi.** Se valorizzato (lista di ID separati da virgola), sia il bot sia `/api/auth/verify` rifiutano gli utenti non in lista.
- **Scadenza di `initData`**: 24 ore (`DEFAULT_MAX_AGE_SECONDS` in `app/security/telegram_auth.py`). Nessun requisito esplicito nel PROMPT su quanto sia "recente" `auth_date`; 24h è un compromesso ragionevole tra sicurezza e comodità (l'utente riapre la Mini App più volte al giorno senza dover rifare `/start`).
- **Rate limit AI e `DAILY_TURN_CAP`**: la variabile è già dichiarata in `app/config.py` ma non ancora applicata, perché non esiste ancora nessuna chiamata AI da limitare. Verrà applicata a partire dalla Fase 3, quando arriva `request_check`/`narrate_outcome`.
- **`WEBHOOK_SECRET` vuoto disattiva il controllo del secret** sul webhook (utile solo per prove locali senza un vero deploy pubblico). In produzione va sempre impostato.
- **`WEBAPP_URL` fa doppio uso**: è sia l'URL del pulsante Web App del bot, sia la base per calcolare l'URL del webhook (`<WEBAPP_URL>/telegram/webhook`) in `tools/set_webhook.py`. Evita di dover configurare due URL quando in pratica coincidono sempre.
- **`python-telegram-bot` in webhook puro** (`Application.builder().updater(None)`): nessun polling, gli update arrivano solo da `/telegram/webhook` e vengono passati con `application.process_update`.
- **Bot disabilitato se `BOT_TOKEN` è vuoto**: l'app FastAPI parte comunque (utile per test e per l'healthcheck di Render prima di aver configurato le variabili), ma il webhook risponde 503 finché il token non c'è.
- **Comando `/gioca` aggiunto già in Fase 0** oltre a `/start`/`/aiuto`/`/galleria` esplicitamente richiesti, come alias che apre subito la Mini App: allinea l'elenco comandi a quello finale del §14 senza introdurre logica di gioco (per ora fa solo da collegamento).
- **`manifest.json` degli asset (§11) non ancora creato**: gli script esistenti generano già i PNG con nomi coerenti alla convenzione descritta nel PROMPT; il file di manifest vero e proprio (utile quando il frontend dovrà scegliere varianti/param) arriverà quando servirà davvero, per non introdurre un file che nessun codice legge ancora.
