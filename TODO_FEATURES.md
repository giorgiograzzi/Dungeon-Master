# Capacità di classe non ancora codificate

Per la regola §8: finché una capacità non ha un handler nel codice, va
mostrata come testo (dalla scheda) e **mai** applicata a bluff. Questo file
tiene traccia di cosa manca ancora, aggiornato a mano a mano che `rules/`
cresce nelle prossime fasi (creazione personaggio, combattimento).

I dati grezzi (nome, testo, livello) sono già estratti in
`data/srd/classes.json` (`level1_features`, `levels`); qui sotto solo le
capacità che richiedono un handler meccanico dedicato (usi limitati e
ricarica, effetti su tiri/PF/economia delle azioni), citate esplicitamente
dal PROMPT (§8):

- [ ] Ira (Barbaro) — usi limitati, danno bonus, resistenza ai danni fisici
- [ ] Recupero energie (Guerriero) — recupero PF/risorse 1/riposo breve
- [ ] Ispirazione bardica (Bardo) — dado di ispirazione, usi per riposo
- [ ] Incanalare Divinità (Chierico/Paladino) — opzioni ed usi per riposo
- [ ] Forma selvatica (Druido) — trasformazione, PF temporanei, azioni disponibili
- [ ] Attacco furtivo (Ladro) — dado extra 1/turno, condizioni di attivazione
- [ ] Imposizione delle mani (Paladino) — riserva di PF di cura
- [ ] Punti ki / punti focus (Monaco/Warlock) — pool di risorsa e usi

Man mano che una capacità viene implementata, spostarla in `rules/features/`
(o modulo equivalente) con test dedicati e segnarla qui come fatta.
