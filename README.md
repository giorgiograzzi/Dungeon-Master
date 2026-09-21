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
python tools/extract_srd.py        # estrae i dati SRD (classi, specie, incantesimi...) in data/srd/

uvicorn app.main:app --reload
```

L'app risponde su `http://localhost:8000/` (Mini App), `/healthz` (stato) e `/telegram/webhook` (bot).

Per provare il narratore senza una chiave Anthropic (o senza consumarne il credito), imposta `DEV_FAKE_AI=true` nel `.env`: le chiamate AI restituiscono risposte finte ma strutturalmente valide (piano di campagna incluso), sufficienti a giocare un turno completo con dadi e bivi.

Per collegare davvero il bot Telegram, dopo aver esposto l'app pubblicamente (tunnel o deploy):

```bash
python tools/set_webhook.py
```

## Test

```bash
pytest
```

Copertura attuale: validazione `initData` (firma, scadenza, manomissioni), endpoint `/healthz` e `/api/auth/verify` (creazione/riuso utente, filtro `ALLOWED_USER_IDS`), comando `/galleria` (album e messaggi di fallback), fumo sugli script di generazione asset e ritratti PNG (stesso seed → stesso volto), estrazione dei dati SRD (`tools/extract_srd.py`, con valori noti verificati), motore di regole (`rules/`): dadi con `secrets`, vantaggio/svantaggio e annullamento, tabella CD, modificatori e bonus di competenza, economia delle azioni, PF temporanei, costo d'uso oggetti, cambio arma, condizioni SRD, riposo; creazione del personaggio (`app/character/`): tutti gli step della procedura guidata validati contro i dati SRD, calcolo della scheda, **le 432 combinazioni specie×classe×background** create e verificate end-to-end, flusso completo via API, avvio robusto anche se il bot Telegram non risponde; narratore AI (`app/ai/`, `app/game/`): validazione del piano di campagna a grafo (percorsi, vicoli ciechi, gate, quest secondarie, indizi ridondanti), client AI finto (`DEV_FAKE_AI=1`), effetti di gioco, ciclo di turno idempotente, bivi, salvataggi — flusso completo verificato anche dal vivo in un browser (Playwright), non solo via API.

## Creazione del personaggio e scheda (`app/character/`)

Procedura guidata a 7 step (§4) esposta via `/api/character/*` e giocabile nella Mini App: specie, classe (competenze ed equipaggiamento iniziale A/B/C), background (talento d'origine e competenze), punteggi di caratteristica (array standard, point buy 27 punti, 4d6 scarta il più basso — tirati dal server), bonus del background, dettagli personali, riepilogo. La scheda calcolata (`/api/character/sheet`) include CA, PF, iniziativa, bonus di competenza, tiri salvezza, le 18 abilità con bonus, percezione passiva, velocità, equipaggiamento e oro. Ogni chiamata valida `initData` (header `X-Telegram-Init-Data`).

## Narratore AI, campagna e turni (`app/ai/`, `app/game/`)

- `app/ai/client.py`: chiamate AI con tool use e schema forzato (`app/ai/tools.py`), prompt caching sul system prompt (`prompts/narrator_system_it.md`). Con `DEV_FAKE_AI=1` le risposte sono finte ma strutturalmente valide: è la modalità usata per sviluppare e testare senza consumare credito (nessuna chiave Anthropic era disponibile in questa sessione di sviluppo).
- `rules/campaign.py`: valida il Piano di Campagna a grafo generato dall'AI — ogni percorso raggiunge il finale senza vicoli ciechi, ogni gate ha almeno 3 soluzioni, ogni scena è collegata a un beat o a una quest, le durate dei percorsi sono bilanciate, gli indizi sono ridondanti. Se il piano non è valido, viene rigenerato (fino a 3 tentativi).
- `app/game/turn.py`: un turno = al massimo 2 chiamate AI (`request_check` poi `narrate_outcome`), con il codice che tira i dadi e confronta con la CD. Idempotente per `turn_id`: un refresh non ritira.
- `app/game/effects.py`: applica gli effetti proposti dall'AI (PF, oggetti, condizioni, oro, quest, PNG...) riusando il motore di regole della Fase 1 — l'AI propone, il codice valida e applica.
- Bivi (`/api/game/crossroads`) presentati senza spoiler; salvataggi (`/api/game/saves*`) come documento JSON, autosave + 5 slot manuali.
- Nella Mini App: tab **Scheda/Gioca** dopo la creazione, form di avvio campagna (ambientazione e durata), schermata di turno con dado animato (§7: il client non genera mai il numero che conta, solo l'animazione) e opzioni rapide.

## Dati SRD (`data/srd/`)

Estratti da `docs/srd/IT_SRD_CC_v5.2.1.pdf` (SRD 5.2.1, già in italiano) con `tools/extract_srd.py`, script ripetibile: si può rilanciare ogni volta che il PDF cambia, sovrascrive solo i JSON. Copre: specie (9), background (4), classi (12, con tabella dei privilegi e sottoclasse), talenti (17), condizioni (15), armi (37), armature (13), incantesimi (339, tutti i livelli — il motore di regole ne usa 0–2 in questa fase), mostri (273 schede con CA/PF/caratteristiche/attacchi). Limiti noti e scelte di scope in [`DECISIONS.md`](DECISIONS.md).

## Motore di regole (`rules/`)

Modulo Python deterministico e testato (§0.1: "il codice decide, l'AI racconta"): `dice.py` (tiri con `secrets`, vantaggio/svantaggio), `difficulty.py` (tabella CD), `ability.py` (modificatori, bonus di competenza), `action_economy.py` (Azione/Bonus/Reazione/Movimento/Interazione libera), `hit_points.py` (PF e PF temporanei), `items.py` (costo d'uso oggetti), `weapon.py` (cambio arma), `conditions.py` (le 15 condizioni SRD), `rest.py` (riposo breve/lungo). Le capacità di classe non ancora implementate sono elencate in [`TODO_FEATURES.md`](TODO_FEATURES.md).

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
rules/             motore di regole deterministico (dadi, CD, azioni, PF, condizioni...)
webapp/            Mini App (HTML/CSS/JS) + assets/ generati (non versionati)
tools/             generazione asset, ritratti PNG, estrazione SRD, impostazione webhook
data/srd/          dati SRD estratti in JSON (classi, specie, incantesimi, mostri...)
docs/srd/          PDF dell'SRD 5.2.1 (italiano)
docs/riferimenti/  esempi dello stile grafico atteso
tests/             pytest
```

## Fasi di lavoro

0. ✅ Scaffold, config, DB, auth `initData`, bot `/start`/`/gioca`/`/aiuto`, deploy "hello", asset e `/galleria`
1. ✅ Dati SRD + rules engine
2. ✅ Creazione personaggio
3. ✅ Narratore AI, piano di campagna, turni, dadi animati, salvataggi
4. ⏳ Combattimento
5. ⏳ Ritmo, bivi, finale
6. ⏳ Asset definitivi, traduzioni, rifiniture

## Licenza e crediti

Basato sul **System Reference Document 5.2.1**, distribuito da Wizards of the Coast sotto licenza **Creative Commons Attribution 4.0 International (CC-BY-4.0)**. Questo è un adattamento non ufficiale: Wizards of the Coast non avalla né sponsorizza il progetto. La schermata "Crediti" con l'attribuzione ufficiale completa arriva nella Fase 6.
