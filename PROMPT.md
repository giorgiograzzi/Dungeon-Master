# PROMPT PER CLAUDE CODE — "Dungeon Master Tascabile" (Telegram Mini App)

Costruisci da zero, in un repo vuoto, una **Telegram Mini App + bot** per giocare in solitaria un'avventura fantasy in stile D&D. Il narratore è un'AI (API Anthropic), ma **le regole le esegue il codice**, basate sull'**SRD 5.2.1** (Creative Commons CC-BY-4.0). UI e narrazione in **italiano**. Sessione di **1–3 ore**, salvabile in qualunque momento. **Solo giocatore singolo: nessuna modalità multiplayer, gruppo o co-op** (una partita = un utente = un personaggio).

**File già presenti nel repo** (usali come base, non riscriverli da zero): `tools/generate_assets.py` (stile delle immagini), `tools/npc_portraits.py` (ritratti dei PNG, importa il primo: tienili nella stessa cartella), `tools/fonts/` (font open source incluso, così non si dipende dal sistema) e `docs/riferimenti/*.png` (esempi del risultato atteso). Richiedono Pillow: aggiungilo ai requisiti di sviluppo. **Se nel repo trovi file con `__` nel nome** (es. `tools__generate_assets.py`), esegui per prima cosa `python riordina.py`: li sposta nelle cartelle giuste (e mette eventuali PDF in `docs/srd/`). Poi committa e rimuovi lo script.

---

## 0. Regole d'oro (valgono per tutto il progetto)

1. **Il codice decide, l'AI racconta.** Dadi, CD, vantaggio/svantaggio, PF, PF temporanei, economia delle azioni, inventario e progressione sono gestiti da moduli Python deterministici e testati. L'AI non inventa mai un tiro né modifica lo stato da sola: propone, il codice valida e applica.
2. **Nessun dato di regole a memoria.** Parti dal PDF dell'SRD 5.2.1 in `docs/srd/` se è presente nel repo; altrimenti scarica quello ufficiale (pagina SRD di D&D Beyond, PDF CC; se serve, `https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf`) ed estrai classi, specie, background, talenti, equipaggiamento, incantesimi, condizioni e mostri in `data/srd/*.json` con uno script ripetibile `tools/extract_srd.py`. Verifica i dati con test. Se la rete della sessione non permette il download, fermati e chiedimi di caricare il PDF nel repo.
3. **Lavora a fasi (§15).** A fine fase: test verdi, commit, README aggiornato. Non chiedermi conferme: se hai un dubbio scegli un default ragionevole e annotalo in `DECISIONS.md`.
4. **Mai chiavi o token nel codice.** Tutto da variabili d'ambiente.
5. **Niente riempitivi.** La durata della storia si costruisce con quest secondarie pianificate che aiutano a risolvere la principale, mai con eventi casuali messi solo per allungare (vedi §5).
6. **Più strade, stessa meta.** La storia è un grafo con percorsi alternativi che convergono sull'obiettivo principale, e ogni ostacolo obbligatorio ha più modi di essere superato (vedi §5).

---

## 1. Stack

- **Backend**: Python 3.12, FastAPI + uvicorn, SQLAlchemy 2 (async), SDK ufficiale `anthropic` (async), `python-telegram-bot` v21 (pattern async) in **modalità webhook** dentro la stessa app FastAPI (`/telegram/webhook`). Versioni **pinnate** in `requirements.txt` (occhio ai conflitti tra dipendenze async).
- **DB**: `DATABASE_URL`. SQLite in locale, **Postgres in produzione** (Neon free): i filesystem dell'hosting gratuito sono effimeri, quindi il salvataggio non può stare su file locali.
- **Frontend**: HTML/CSS/JS vanilla con moduli ES, **senza build step**, servito da FastAPI. Mobile-first, usa il Telegram WebApp SDK (`themeParams`, `HapticFeedback`, `MainButton`/`BackButton`).
- **Modelli AI configurabili via env**: `MODEL_NARRATOR` (default `claude-haiku-4-5-20251001`, turni normali e riassunti) e `MODEL_CLIMAX` (default `claude-sonnet-5`, piano di campagna, colpi di scena, finale, export racconto). Controlla i nomi correnti nella documentazione Anthropic prima di fissarli. Usa **prompt caching** per system prompt e regole.
- **Variabili** (`.env.example` con **ogni riga commentata**, distinguendo campi manuali e opzionali): `BOT_TOKEN`, `ANTHROPIC_API_KEY`, `DATABASE_URL`, `WEBAPP_URL`, `WEBHOOK_SECRET`, `ALLOWED_USER_IDS` (opzionale, lista di ID Telegram), `DAILY_TURN_CAP`, `MODEL_NARRATOR`, `MODEL_CLIMAX`, `RULE_WEAPON_SWAP_COST` (default `action`, alternativa `free_interaction`).
- **Niente wizard di primo avvio**: la chiave Anthropic sta nelle variabili dell'hosting.

## 2. Sicurezza e costi

- Valida **`initData` di Telegram** (HMAC-SHA256 con il token del bot, controllo di `auth_date`) su **ogni** chiamata API; l'utente è identificato solo da quel dato.
- Se `ALLOWED_USER_IDS` è valorizzata, rifiuta tutti gli altri.
- Rate limit per utente sulle chiamate AI e tetto giornaliero di turni (`DAILY_TURN_CAP`).
- Log senza dati personali né chiavi.

---

## 3. Ciclo di un turno

1. Il giocatore sceglie un'azione suggerita o scrive libero.
2. **Chiamata AI #1 (`request_check`)**: l'AI dice *se* serve un tiro e quale (prova di caratteristica/abilità, tiro salvezza, attacco), il motivo, la **fascia di difficoltà** e gli eventuali fattori di vantaggio/svantaggio con motivazione. Se non serve tiro, restituisce direttamente la narrazione (1 sola chiamata).
3. Il **codice** valida e calcola la CD, applica vantaggio/svantaggio, tira con `secrets` **lato server**, persiste il tiro con `turn_id` (idempotente: un refresh non lo ritira).
4. Il client **anima i dadi** fino al valore già deciso (§7).
5. **Chiamata AI #2 (`narrate_outcome`)**: riceve l'esito e narra le conseguenze, con opzioni successive ed `effects` proposti.
6. Il codice **valida e applica** gli `effects`, aggiorna lo stato, salva (autosave).

Usa **tool use con schema JSON forzato** (`tool_choice`), non parsing di testo libero. Massimo 2 chiamate AI per turno.

### Difficoltà variabile per ogni scelta (CD)
Ogni opzione e ogni tiro ha la propria **Classe Difficoltà**, scelta dall'AI come *fascia* e convertita dal codice con la tabella SRD: Molto facile 5 · Facile 10 · Media 15 · Difficile 20 · Molto difficile 25 · Quasi impossibile 30. La fascia dipende dalla fiction (preparazione, strumenti, competenza, tempo, circostanze), non dal caso. Sui pulsanti delle opzioni mostra l'etichetta di fascia (es. "Difficile"); la CD esatta compare al momento del tiro (impostazione per mostrarla subito).

### Vantaggio e svantaggio
- Proposti dall'AI con **motivo esplicito** (es. "alto terreno", "sorpresa", "sei trattenuto") e/o derivati dal codice da condizioni e privilegi di classe.
- Regole SRD: più fonti non si sommano (si tira sempre 1 d20 in più), vantaggio e svantaggio insieme **si annullano**.
- La UI mostra sempre *perché* hai vantaggio o svantaggio.

---

## 4. Creazione del personaggio (almeno pari a D&D 2024)

Procedura guidata a step, con **anteprima live della scheda** e bozza salvata:

1. **Specie** (tutte quelle dell'SRD): tratti, velocità, taglia, sensi, lingue.
2. **Classe** (le 12 dell'SRD): dado vita, competenze, tratti di 1° livello, scelta **equipaggiamento iniziale** (opzioni A/B come nel 2024), incantesimi/trucchetti per i caster.
3. **Background** (quelli dell'SRD): aumenti di caratteristica (+2/+1 oppure +1/+1/+1), **talento d'origine**, competenze in abilità/strumenti, equipaggiamento.
4. **Punteggi di caratteristica**: 3 metodi a scelta: *Array standard*, *Point buy (27 punti)*, *4d6 scarta il più basso* (con dadi animati, tirati dal server).
5. **Abilità e competenze**: scelta tra quelle di classe; expertise dove previsto.
6. **Dettagli personali**: nome, aspetto, tratti/ideali/legami/difetti (con suggerimenti AI opzionali a richiesta), breve storia (l'AI la userà in campagna), ritratto (dagli asset).
7. **Riepilogo scheda completa**: CA, PF, iniziativa, bonus competenza, tiri salvezza, tutte le 18 abilità con bonus, percezione passiva, velocità, sensi, lingue, attacchi, equipaggiamento, monete, Ispirazione eroica.

Progressione: livello 1 → **3 a milestone** (fine Atto I → lv 2, fine Atto II → lv 3); la **sottoclasse** (una per classe nell'SRD) si sceglie al livello 3. Schermata di level-up guidata.

La scheda è consultabile **in ogni momento** (tab Scheda / Inventario / Incantesimi e capacità / Diario).

---

## 5. Campagna con un piano e un finale

- All'inizio l'utente sceglie ambientazione (fantasy classico, noir, fantascienza, horror comico) e **durata target**: Breve (~1 h), Media (~2 h), Lunga (~3 h). La durata decide quante quest secondarie entrano nel piano.
- `MODEL_CLIMAX` genera **una volta** il **Piano di Campagna** (JSON nascosto al giocatore): titolo, premessa, antagonista e movente, **3 atti**, 6–10 beat con obiettivo, **2–4 quest secondarie collegate alla principale**, luoghi e **cast di 25 PNG** (vedi §12), **indizi ridondanti** (ogni informazione essenziale raggiungibile in almeno 2 modi), 2–3 finali possibili in base alle scelte, milestone di level-up.
- **Struttura a percorsi (bivi che convergono)**: il piano è un **grafo**, non una linea. Ha **nodi cardine fissi** (incidente scatenante, rivelazione centrale, scontro finale) che tutti i percorsi attraversano, così l'**obiettivo principale resta sempre lo stesso**, e **2 bivi** (fine Atto I e fine Atto II) in cui il giocatore sceglie **1 di 3 percorsi**. Ogni percorso ha un'identità (es. *Via della Parola* = diplomazia e intrighi, *Via dell'Ombra* = furtività e indagine, *Via dell'Acciaio* = scontri e forza; adattali all'ambientazione), luoghi, PNG, beat, ostacoli, tono e ricompense propri, e **cambia davvero la storia**: chi sono gli alleati, cosa si scopre, quali risorse si hanno al finale, quali quest secondarie sono disponibili (alcune esclusive di un percorso). Nessun percorso è "il migliore": durata simile (±15%), difficoltà bilanciata su profili diversi (nessuno richiede una classe specifica, ma alcune classi ne sono avvantaggiate). Al bivio **l'AI non sceglie**: presenta i 3 percorsi con anteprima senza spoiler (titolo, promessa, rischio, stile di gioco, effetto sulla durata) e decide il giocatore.
- **Più modi per superare ogni passaggio (gate)**: ogni ostacolo obbligatorio (porta sigillata, guardia, informazione mancante, attraversamento…) ha **almeno 3 soluzioni** con approcci diversi: **combattere**, **persuadere/ingannare**, **aggirare/infiltrarsi**, **usare oggetto/incantesimo/conoscenza**, oppure una **via alternativa che passa da una quest secondaria**. Ogni soluzione ha CD, costi (PF, risorse, tempo, oggetti) e conseguenze diversi. Le soluzioni sono nel piano ma **l'input libero è sempre accettato**: se il giocatore propone un modo creativo, l'AI lo valuta in base alla fiction, assegna una fascia di difficoltà (o vantaggio se l'idea è brillante) e non lo respinge mai solo perché non previsto. Le opzioni suggerite mostrano approcci diversi, comprese soluzioni che sfruttano specie, classe, background o oggetti dell'inventario.
- **Validazione del piano (nel codice)**: dopo la generazione verifica che ogni percorso raggiunga il finale, che non ci siano vicoli ciechi, che ogni gate abbia ≥3 soluzioni, che ogni scena sia collegata a un beat o a una quest e che le durate stimate dei percorsi siano bilanciate. Se il controllo fallisce, rigenera solo la parte non valida.
- **Quest secondarie collegate (mai riempitivi)**: il piano contiene **2–4 quest secondarie opzionali**, ciascuna legata alla quest principale e con una **ricompensa concreta che aiuta a risolverla**: un indizio o una prova mancante, un alleato che compare nel finale, un oggetto o una capacità che dà vantaggio nello scontro decisivo, una scorciatoia o un'informazione sul punto debole dell'antagonista. Ogni quest ha: gancio, luogo/PNG, obiettivo, 2 modi di risolverla, `reward` (tipo + effetto sul finale) e `unlocks` (cosa sblocca nella trama principale). Il codice registra le ricompense ottenute e **il finale ne tiene conto** (l'alleato arriva, l'oggetto concede vantaggio, l'indizio apre una via più facile). Chi salta le secondarie può comunque finire la storia, ma con un finale più difficile.
- **La durata la regola il piano, non il caso**: Breve = principale + 0–1 secondarie, Media = 2, Lunga = 3–4. **Vietati incontri, PNG ed eventi casuali aggiunti solo per allungare**: ogni scena deve servire un beat principale o una quest secondaria del piano. Se le regole richiedono un nemico o un ostacolo, questo deve appartenere a una delle due linee.
- **Ritmo**: il codice tiene un orologio narrativo (turni e tempo attivo) e passa all'AI un blocco `pacing` (percorso scelto, beat corrente, quest secondarie aperte/completate, tempo stimato rimasto, in ritardo/in anticipo). Se si è **in ritardo** l'AI accorcia le scene e riporta il giocatore sulla principale; se si è **in anticipo** propone una secondaria non ancora affrontata, senza inventare contenuti nuovi. La trama non resta mai ferma.
- **Fail forward**: un fallimento cambia la situazione, non blocca la storia.
- **Indirizzamento del giocatore**: "Obiettivo attuale" sempre visibile, barra degli atti senza spoiler, **diario missione** aggiornato automaticamente con sezioni *Quest principale* e *Quest secondarie* (per ognuna: gancio, stato e, in forma vaga e senza spoiler, come potrebbe aiutare nella principale), pulsanti "Riassunto finora" e "Dammi un indizio".
- **Finale**: ultimo beat con scena climax (modello forte), epilogo, schermata finale con statistiche (turni, tiri, 20 e 1 naturali, PF persi, oggetti usati) ed **esportazione della storia come racconto** (`/diario` e pulsante). Opzione **"Rigioca da un bivio"** per provare un altro percorso.
- **Morte**: a 0 PF partono i tiri salvezza contro la morte (visibili, con dadi). Se il PG muore: epilogo e opzione "riavvolgi all'ultimo salvataggio".

---

## 6. Sessione lunga e salvataggi

- **Autosave dopo ogni turno** (transazionale) + **salvataggio manuale con nome in qualsiasi momento**; 5 slot + autosave; ripresa istantanea alla riapertura, anche dopo lo spegnimento dell'hosting.
- Stato = documento JSON con `schema_version` + log dei turni. Nessuno stato solo in memoria.
- **Memoria dell'AI**: `story_summary` progressivo (aggiornato a ogni scena dal modello economico) + ultimi 6–8 turni verbatim + `facts` canonici (PNG, luoghi, oggetti, promesse, indizi trovati, quest attive/completate, ricompense ottenute, percorsi scelti e gate risolti) sempre inclusi. Tieni il contesto entro un budget e usa caching.
- Se la chiamata AI fallisce: retry con backoff, l'azione resta in coda, **il tiro non viene ritirato**.
- Esporta/importa il salvataggio come file JSON (backup).

---

## 7. Dadi visibili sullo schermo

- Overlay `DiceTray` con dadi animati: **d4, d6, d8, d10, d12, d20, d100**. L'animazione (1,2–1,8 s) rotola e atterra sul valore **deciso dal server**: il client non genera mai numeri casuali per l'esito.
- Il giocatore **tocca il dado per lanciarlo** (più tattile); il risultato è già fissato dietro le quinte.
- **Vantaggio/svantaggio**: due d20 in vasca; quello scartato sbiadisce, quello tenuto si illumina, con etichetta e motivo.
- Dopo il tiro mostra: dado naturale + modificatori con origine ("+3 Des, +2 competenza") = totale vs CD → esito. Segui le regole SRD sul 20/1 naturale (automatici solo dove le regole lo prevedono).
- Dadi visibili anche per: danni e cure, dadi vita, iniziativa, tiri salvezza contro la morte, generazione caratteristiche.
- Impostazioni: **tiro veloce** (salta animazione), vibrazione, suoni (spenti di default). **Registro tiri** consultabile.

---

## 8. Regole nel codice (modulo `rules/`, tutto coperto da test)

- **Economia delle azioni** (SRD 5.2): Azione, Azione Bonus, Reazione (1 per round), Movimento, Interazione gratuita con un oggetto (1 per turno). Modalità di gioco `exploration | social | combat`; in `combat` c'è iniziativa, round e turni, con **tracker sempre visibile** (Azione / Bonus / Reazione / Movimento / Interazione libera, consumati vs disponibili). I nemici usano stat block SRD, con tiri fatti dal codice.
- **Inventario e uso oggetti**: ogni oggetto ha `use_cost ∈ {action, bonus_action, reaction, free, none}`, letto dall'SRD (es. pozioni) con fallback documentato. Dall'inventario, tap → dettaglio → **Usa**: mostra il costo, controlla che la risorsa sia disponibile nel turno, la scala, applica l'effetto (con dadi visibili) e blocca con messaggio chiaro se esaurita. Fuori dal combattimento non si consumano risorse.
- **Cambio arma = consuma un'Azione** (regola della casa richiesta; configurabile con `RULE_WEAPON_SWAP_COST`). Equipaggiare/rimuovere armature segue i tempi SRD.
- **Reazioni**: framework con prompt "Vuoi usare la Reazione?" quando scatta un trigger (es. privilegi di classe o incantesimi in reazione presenti nell'SRD per la classe del PG). Dove il posizionamento conta, usa il *teatro della mente* semplificato.
- **PF temporanei**: campo `temp_hp` separato; il danno consuma prima quelli; **non si sommano** (si tiene il valore più alto, a scelta del giocatore se diversi); non si curano; scadono al riposo lungo. Barra PF con segmento di colore diverso.
- **Condizioni SRD** con i loro effetti su vantaggio/svantaggio e azioni; resistenze/vulnerabilità/immunità; critici; tiri salvezza contro la morte e stabilizzazione; **riposo breve/lungo** con dadi vita; **Ispirazione eroica**; **Weapon Mastery** per le classi che la usano.
- **Incantesimi SRD livelli 0–2**: slot, trucchetti, incantesimi preparati, **concentrazione** (TS Cos).
- **Capacità di classe livelli 1–3** come registry di feature con handler (usi limitati e ricarica, es. Recupero energie, Ira, Ispirazione bardica, Incanalare Divinità, Forma selvatica, Attacco furtivo, Imposizione delle mani, Punti ki/focus). Se una feature non è ancora codificata: annotala in `TODO_FEATURES.md`, mostrala come testo e **non fingere di applicarla**.
- **Nomi in italiano** tramite glossario `data/it_glossary.json` (es. Fighter→Guerriero, Rogue→Ladro, Wizard→Mago), con il nome inglese in piccolo sulla scheda.

---

## 9. Interfaccia (mobile-first)

- Schermate: **Home** (Continua / Nuova / Carica / Impostazioni / Crediti), **Creazione PG**, **Gioco**, **Scheda-Inventario-Diario**, **Salvataggi**, **Fine avventura**, **Bivio** e **Mappa del viaggio**; in Impostazioni la **Galleria immagini**.
- **Bivio**: schermata con **3 carte percorso** (immagine, titolo, promessa, rischio, stile di gioco, effetto sulla durata), senza spoiler. **Mappa del viaggio**: il grafo dei percorsi con tratto già percorso evidenziato e alternative come sagome.
- **Gioco**: barra PF (+ PF temporanei), CA, livello, sfondo di scena, testo con effetto "scrittura" (tap per saltare), **3–4 azioni suggerite** con etichetta di costo (Azione/Bonus/Reazione/Libera), abilità e fascia di difficoltà, campo libero "Cosa fai?", barra rapida (Inventario, Scheda, Salva, Menu).
- **Inventario**: griglia con icone, quantità, equipaggiato; azioni Usa / Equipaggia / Getta.
- Se l'hosting è "addormentato": schermata "Sto svegliando il narratore…" con retry automatico.
- Testo ridimensionabile, contrasto adeguato, tema che segue Telegram.

---

## 10. Prompt di sistema del narratore (`prompts/narrator_system_it.md`)

Scrivilo in italiano, con queste istruzioni:
- Ruolo: Dungeon Master caldo e cinematografico ma **conciso** (80–150 parole a turno, più lungo solo nei momenti clou).
- **Mai** inventare tiri o esiti; **mai** cambiare PF/inventario/CD da solo: usa `effects` (validati dal codice).
- Segui il Piano di Campagna e il `pacing`: avanza di beat, niente stalli, fail forward, indizi ridondanti. **Non aggiungere mai eventi, incontri o PNG casuali per allungare la storia**: per variare il ritmo usa solo le quest secondarie del piano, che devono sempre portare un vantaggio alla risoluzione della principale.
- Ai **bivi** presenta i 3 percorsi del piano senza sceglierne uno; rispetta i nodi cardine e l'obiettivo principale qualunque sia il percorso.
- Ogni gate ha ≥3 soluzioni ma **accetta sempre l'input libero**: valuta le idee creative e premiale con vantaggio o CD più bassa se sono brillanti.
- Interpreta i **PNG** secondo personalità, motivazione, atteggiamento e segreto; **non contraddire mai il ritratto** (usa la descrizione testuale fornita dal codice) e non inventare PNG fuori dal cast, salvo comparse senza nome.
- Coerenza con `facts` e `story_summary`; non rivelare piano e CD segrete.
- Opzioni: 3 approcci diversi (combattivo / astuto / sociale) più input libero; ogni tanto un'opzione che valorizza specie, classe o background del PG.
- Difficoltà: la fascia dipende dalla fiction; varia le CD tra le scelte e spiega i fattori di vantaggio/svantaggio.
- Tono avventuroso adatto a tutti, violenza non esplicita; solo italiano; risposte solo tramite tool.
- Le **scene** si descrivono con parametri tra valori validi (ambientazione, ora del giorno, meteo, elementi di scena, atmosfera): se l'immagine non esiste il codice la **compone e la mette in cache**. Le icone oggetto si scelgono da elenchi chiusi.

Tool: `request_check`, `narrate_outcome`, `generate_campaign_plan`, `present_crossroads`, `summarize_story`, `export_story`. Definisci gli schemi JSON con enum per tipo di effetto (`hp_delta`, `temp_hp`, `item_add`, `item_remove`, `condition_add`, `condition_remove`, `gold`, `fact_add`, `quest_update`, `start_combat`, `end_combat`, `beat_progress`, `side_quest_start`, `side_quest_update`, `side_quest_complete`, `route_chosen`, `gate_solved`, `npc_attitude`, `npc_learned`, `npc_status`…).

---

## 11. Asset immagine (file .png, placeholder generati dal codice, sostituibili)

- `tools/generate_assets.py` (Pillow e/o cairosvg) genera in `webapp/assets/` placeholder coerenti e curati: **dadi** (facce d4–d20, d100), **icone** (12 classi, specie, 6 caratteristiche, condizioni, tipi di azione, categorie oggetto, PF/PF temp/CA/iniziativa), **ritratti** stilizzati per specie/classe, **sfondi di scena** (taverna, foresta, dungeon, città, montagna, mare, palude, laboratorio, astronave…).
- Convenzione nomi in `assets/manifest.json`: `class_<id>.png`, `species_<id>.png`, `item_<id>.png`, `icon_<nome>.png`, `scene_<id>.png`, `portrait_<specie>_<classe>.png`, `dice_d20.png`. Dimensioni fisse (icone 128², ritratti 512², scene 1024×576, dadi 256²), trasparenza dove serve.
- Per bivi e mappa: `route_<id>.png` (carte percorso 384×512), `map_node_*.png`, `map_bg.png`.
- **Scene infinite con compositore a strati** (`tools/scene_composer.py`, da creare partendo dalle 6 scene della bozza): ogni scena è **ambientazione** (foresta, dungeon, taverna, città, montagna, mare, più palude, deserto, grotta, tempio, castello, villaggio, campo di battaglia, nave, rovine, laboratorio, astronave…) × **ora** (alba, giorno, tramonto, notte) × **meteo** (sereno, nuvoloso, pioggia, nebbia, neve, tempesta) × **elementi** (falò, torce, ponte, statua, portale, carro, rovine, bandiere, lanterne…) × **atmosfera** (palette e luminosità). Le combinazioni sono deterministiche dai parametri: la stessa scena si ricrea identica, le nuove si generano al volo in pochi ms e restano in cache e nel salvataggio.
- **Carte percorso su misura**: ogni percorso del piano (*Parola/Ombra/Acciaio* erano solo esempi) riceve una carta composta da simbolo (libreria di circa 30 glifi), palette, titolo, sottotitolo, etichette, rischio e durata. L'AI sceglie i valori tra quelli validi e il codice disegna. Lo stesso vale per le icone oggetto, e la mappa del viaggio si ridisegna sul grafo reale della campagna.
- **Illustrazioni vere (opzionale, spento di default)**: l'API Anthropic non genera immagini. Se in futuro vuoi illustrazioni realistiche, prevedi un'interfaccia `ImageProvider` a cui collegare un servizio esterno (chiave in variabile d'ambiente, cache e limite giornaliero), con ripiego sui compositori a strati. Non implementarlo ora.
- **Le immagini devono essere visibili su Telegram**: il bot ha il comando **`/galleria`**, che invia in chat i contact sheet (`assets/contact_sheet_*.png`: tutte le immagini in griglia con etichette) e, a richiesta, gli album per categoria (`sendMediaGroup`). La Mini App ha in più una **Galleria immagini** (Impostazioni → Galleria). Nel repo trovi `tools/generate_assets.py`, una **bozza già pronta con lo stile scelto** (dadi d4–d20, 12 icone di classe, icone azione/stato/oggetti, 6 scene, 3 carte percorso, mappa del viaggio e contact sheet): parti da quella, completala (specie, altre scene e icone mancanti, d100) e falla girare già in Fase 0, così vedo subito le immagini nel bot.
- Il frontend carica per nome; se un file manca usa il fallback generato. **Per sostituire un'immagine basta copiare un file .png con lo stesso nome.**
- Crea `assets/PROMPTS.md` con un prompt-stile per categoria da usare con un generatore di immagini AI (stile coerente: illustrazione fantasy flat, palette calda) per produrre le versioni definitive.

---

## 12. Personaggi non giocanti (PNG)

- **Cast di 25 PNG per campagna**, generato insieme al Piano: alleati, antagonisti, chi assegna le quest, testimoni, mercanti, comprimari. Non tutti compaiono in una sessione breve. Ogni PNG ha: `id`, nome, **specie SRD**, ruolo, età, **personalità** (2–3 tratti), motivazione, **segreto** (nascosto), **atteggiamento iniziale** (valore numerico amichevole/neutrale/ostile), **cosa sa** (indizi legati ai gate), **cosa offre** (quest, oggetti, informazioni, servizi), dove e quando compare e `seed` del ritratto.
- **Ritratti generati dal codice, a strati**: `tools/npc_portraits.py` (bozza già pronta nel repo, da completare; se mancasse, scrivilo tu seguendo questa descrizione) compone ogni ritratto da **10 varianti per strato**: forme del viso, capelli, **barbe e pizzetti**, **piercing**, occhi, sopracciglia, nasi, bocche, segni e cicatrici, copricapi, corna (tiefling e dragonidi), abiti. Le combinazioni sono casuali ma **deterministiche dal seed**, quindi ogni PNG ha sempre lo stesso volto, salvato nel suo record.
- **Tutte le 9 specie dell'SRD**, con tratti riconoscibili: orecchie a punta, orecchie tonde, zanne d'orco, scaglie e cresta del dragonide (10 colori, cromatici e metallici), pelle grigia con marchi per i golia, corna e occhi luminosi per i tiefling, barbe abbondanti per i nani, capelli ricci per gli halfling.
- **Aspetto coerente con la storia**: l'AI può chiedere tratti precisi (es. "nano anziano, barba lunga, cicatrice sull'occhio") passando **solo valori validi** di ogni strato; il codice completa il resto col seed. `describe(traits)` restituisce la descrizione testuale del ritratto, che entra nel contesto dell'AI così narrazione e immagine coincidono.
- **Libro dei PNG** nel diario: griglia con i ritratti dei PNG incontrati (sagome per quelli sconosciuti); tocca un ritratto per vedere scheda, atteggiamento e cosa hai scoperto su di lui. Nei dialoghi il ritratto compare in grande sopra il testo.
- **Interazioni sociali giocabili**: persuadere, ingannare, intimidire e capire le intenzioni usano prove d'abilità con CD influenzata dall'atteggiamento del PNG; gli esiti aggiornano atteggiamento, cose apprese e stato (`npc_attitude`, `npc_learned`, `npc_status`). Lo stato dei PNG è nel salvataggio.
- **Espressioni (miglioria)**: `render(traits, mood=...)` sostituisce bocca e sopracciglia per mostrare emozioni (neutro, felice, arrabbiato, spaventato) durante i dialoghi.
- I **mostri non umanoidi** non usano questo sistema: immagini placeholder per tipo (bestia, non morto, drago, melma...), da sostituire con arte definitiva.
- **`/galleria`** invia anche i ritratti: 25 esempi, catalogo degli strati (con ingrandimenti) e le 9 specie.

---

## 13. Crediti e licenza

- Schermata **Crediti** e sezione nel README con l'**attribuzione ufficiale CC-BY-4.0** (testo esatto nella prima pagina del PDF SRD), link alla licenza, indicazione che il materiale è stato **tradotto e adattato** e che Wizards of the Coast non avalla il progetto.
- Non usare loghi o marchi di Wizards of the Coast. Puoi dire "basato sull'SRD 5.2.1".

---

## 14. Deploy (hosting gratuito) e test

- **Render** (web service) + **Neon** (Postgres free). Fornisci `render.yaml`, endpoint `/healthz`, `Dockerfile` e `docker-compose.yml` (porta da env `PORT`) per spostare tutto sul server di casa in seguito.
- Nota: il piano free si addormenta con l'inattività. Il `/start` del bot fa "ping" all'app; la Mini App gestisce il risveglio.
- `tools/set_webhook.py` per il webhook; il bot risponde a `/start`, `/gioca`, `/aiuto` (con un pulsante **Web App**) e `/galleria` e imposta il Menu Button.
- **README passo-passo lineare** (BotFather → Neon → Render → variabili → webhook → prima partita): passaggi numerati in ordine, ogni blocco di comandi eseguibile dall'alto in basso **senza pause a metà**.
- **Test `pytest`**: vantaggio/svantaggio e annullamento, tabella CD, PF temporanei, economia azioni, cambio arma, uso oggetti (incl. costo e risorse esaurite), validazione `initData`, salvataggio/ripresa, idempotenza dei tiri, schemi tool AI (Anthropic mockato), creazione personaggio per tutte le combinazioni specie×classe×background, ricompense delle quest secondarie applicate nel finale, piano generato senza scene prive di collegamento a un beat o a una quest, grafo del piano valido (ogni percorso arriva al finale, nessun vicolo cieco, ogni gate con ≥3 soluzioni), ritratti dei PNG (stesso seed = stesso volto, fuzz su 500 seed × tutte le specie senza errori, nessuna combinazione incoerente come un dragonide con barba o capelli). Modalità `DEV_FAKE_AI=1` per provare tutto senza chiamare l'API.

---

## 15. Fasi di lavoro (a ogni checkpoint: test, commit, README)

0. **Scaffold**: repo, config, DB, auth `initData`, bot `/start` con pulsante Web App, deploy "hello" su Render (deve girare presto), `tools/generate_assets.py` e comando `/galleria` per vedere subito su Telegram immagini e ritratti dei PNG.
1. **Dati SRD + rules engine** + test.
2. **Creazione personaggio** (UI + API) e scheda.
3. **Narratore AI**: piano di campagna a grafo (percorsi, gate, quest secondarie, cast di 25 PNG) con validazione, turno con check, **dadi animati**, salvataggi e ripresa.
4. **Combattimento**: economia delle azioni, inventario e uso oggetti, reazioni, PF temporanei, condizioni.
5. **Ritmo e finale**: bivi e percorsi, pacing, quest secondarie con ricompense che influenzano il finale, milestone/level-up, epilogo, statistiche, export del racconto.
6. **Asset immagine, compositore di scene e ritratti dei PNG**, traduzione delle descrizioni (`tools/translate_srd.py` con cache, una tantum), rifiniture UI, Crediti.

Inizia dalla **Fase 0** e procedi in ordine. Alla fine di ogni fase dimmi in 3–5 righe cosa funziona e come provarlo.
