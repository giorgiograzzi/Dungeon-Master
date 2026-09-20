# Dungeon Master Tascabile

Avventura fantasy solitaria in stile D&D, giocata come **Telegram Mini App**. Il narratore è un'AI (Anthropic Claude), ma **le regole le esegue il codice** (dadi, CD, PF, inventario, progressione), basato sull'**SRD 5.2.1** (CC-BY-4.0). Interfaccia e narrazione in italiano, sessioni da 1–3 ore, salvabili in ogni momento. Un giocatore per partita: nessuna modalità multiplayer.

> Stato: **Fase 0 — Scaffold**. Specifica completa in [`PROMPT.md`](PROMPT.md), scelte prese lungo il percorso in [`DECISIONS.md`](DECISIONS.md).

## Stack

- **Backend**: FastAPI + uvicorn, SQLAlchemy 2 (async), SDK `anthropic`, `python-telegram-bot` v21 in modalità webhook, tutto dentro un'unica app FastAPI.
- **DB**: SQLite in locale, Postgres (Neon free) in produzione.
- **Frontend**: HTML/CSS/JS vanilla, senza build step, servito da FastAPI, con il Telegram WebApp SDK.
- **Asset immagine**: generati da `tools/generate_assets.py` e `tools/npc_portraits.py` (richiedono Pillow, solo in sviluppo/build).

## Avvio in locale

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env   # poi compila almeno BOT_TOKEN e WEBAPP_URL

python tools/generate_assets.py    # genera dadi, icone, classi, scene, percorsi
python tools/npc_portraits.py      # genera i 25 ritratti dei PNG e i cataloghi

uvicorn app.main:app --reload
```

L'app risponde su `http://localhost:8000/` (Mini App), `/healthz` (stato) e `/telegram/webhook` (bot).

Per collegare davvero il bot Telegram, dopo aver esposto l'app pubblicamente (tunnel o deploy):

```bash
python tools/set_webhook.py
```

## Test

```bash
pytest
```

Copertura attuale: validazione `initData` (firma, scadenza, manomissioni), endpoint `/healthz` e `/api/auth/verify` (creazione/riuso utente, filtro `ALLOWED_USER_IDS`), comando `/galleria` (album e messaggi di fallback), fumo sugli script di generazione asset e ritratti PNG (stesso seed → stesso volto).

## Variabili d'ambiente

Vedi [`.env.example`](.env.example): ogni riga è commentata. Obbligatorie per un bot funzionante: `BOT_TOKEN`, `WEBAPP_URL`, `WEBHOOK_SECRET`. `ANTHROPIC_API_KEY` serve dalla Fase 3 in poi (narratore AI); se `WEBHOOK_SECRET` è vuoto il controllo del secret è disattivato (solo per test locali).

## Deploy

- `Dockerfile` multi-stage: genera gli asset PNG in uno stage con Pillow, poi li copia in un'immagine di runtime che **non** installa Pillow.
- `docker-compose.yml` per uso locale/casalingo.
- `render.yaml` per Render (web service Docker) + Neon (Postgres free). Healthcheck: `/healthz`.
- Il piano free di Render si addormenta con l'inattività: il `/start` del bot risveglia l'app, la Mini App gestisce l'attesa (rifinitura prevista in una fase successiva).

## Struttura

```
app/               backend FastAPI (config, DB, sicurezza, bot Telegram, API)
webapp/            Mini App (HTML/CSS/JS) + assets/ generati (non versionati)
tools/             generazione asset, ritratti PNG, impostazione webhook
docs/srd/          PDF dell'SRD 5.2.1 (da aggiungere nella Fase 1)
docs/riferimenti/  esempi dello stile grafico atteso
tests/             pytest
```

## Fasi di lavoro

0. ✅ Scaffold, config, DB, auth `initData`, bot `/start`/`/gioca`/`/aiuto`, deploy "hello", asset e `/galleria`
1. ⏳ Dati SRD + rules engine
2. ⏳ Creazione personaggio
3. ⏳ Narratore AI, piano di campagna, turni, dadi animati, salvataggi
4. ⏳ Combattimento
5. ⏳ Ritmo, bivi, finale
6. ⏳ Asset definitivi, traduzioni, rifiniture

## Licenza e crediti

Basato sul **System Reference Document 5.2.1**, distribuito da Wizards of the Coast sotto licenza **Creative Commons Attribution 4.0 International (CC-BY-4.0)**. Questo è un adattamento non ufficiale: Wizards of the Coast non avalla né sponsorizza il progetto. La schermata "Crediti" con l'attribuzione ufficiale completa arriva nella Fase 6.
