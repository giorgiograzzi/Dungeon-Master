import { api } from "./api.js";
import { showDiceOverlay } from "./dice.js";

const SETTINGS = ["fantasy classico", "noir", "fantascienza", "horror comico"];
const DURATIONS = [
  { id: "breve", label: "Breve (~1 ora)" },
  { id: "media", label: "Media (~2 ore)" },
  { id: "lunga", label: "Lunga (~3 ore)" },
];

function newTurnId() {
  return window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

export async function renderGame(container) {
  const state = await api.gameState();
  if (!state.has_campaign) {
    renderCampaignSetup(container);
    return;
  }
  if (state.ended) {
    await renderFinaleScreen(container);
    return;
  }
  if (state.mode === "combat") {
    await renderCombatScreen(container);
    return;
  }
  const crossroad = await api.crossroads();
  if (crossroad.at_crossroads) {
    renderCrossroadsScreen(container, crossroad);
    return;
  }
  renderTurnScreen(container, state);
}

function renderCampaignSetup(container) {
  container.innerHTML = `
    <h2>La tua avventura</h2>
    <div class="field">
      <label>Ambientazione</label>
      <select id="setting">${SETTINGS.map((s) => `<option value="${s}">${s}</option>`).join("")}</select>
    </div>
    <div class="field">
      <label>Durata</label>
      <select id="duration">${DURATIONS.map((d) => `<option value="${d.id}">${d.label}</option>`).join("")}</select>
    </div>
    <button id="start">Inizia l'avventura</button>
    <div id="setup-error"></div>
  `;
  document.getElementById("start").addEventListener("click", async () => {
    const button = document.getElementById("start");
    button.disabled = true;
    button.textContent = "Genero il piano della campagna…";
    try {
      await api.startCampaign({
        setting: document.getElementById("setting").value,
        duration: document.getElementById("duration").value,
      });
      await renderGame(container);
    } catch (err) {
      document.getElementById("setup-error").innerHTML = `<p class="error">${err.message}</p>`;
      button.disabled = false;
      button.textContent = "Inizia l'avventura";
    }
  });
}

function _actsBar(currentAct) {
  return `
    <div class="acts-bar">
      ${[1, 2, 3].map((n) => `<span class="act-dot ${n <= currentAct ? "done" : ""}">Atto ${n}</span>`).join("")}
    </div>
  `;
}

function renderTurnScreen(container, state) {
  container.innerHTML = `
    <h2>${state.title ?? "La tua avventura"}</h2>
    ${_actsBar(state.current_act ?? 1)}
    <p class="hint">Obiettivo attuale: ${state.current_objective}</p>
    <button id="diary-btn" class="secondary" type="button">📖 Diario</button>
    <div id="diary-panel"></div>
    <div id="journal">
      ${state.recent_turns
        .map((t) => `<p><strong>Tu:</strong> ${t.action}</p><p>${t.narration}</p>`)
        .join("<hr>")}
    </div>
    <div id="options"></div>
    <div class="field"><label>Cosa fai?</label><textarea id="action" rows="2"></textarea></div>
    <button id="submit-action">Agisci</button>
    <div id="turn-error"></div>
  `;
  const lastTurn = state.recent_turns[state.recent_turns.length - 1];
  if (lastTurn && lastTurn.options?.length) {
    document.getElementById("options").innerHTML = lastTurn.options
      .map((o) => `<button class="secondary option-btn" type="button">${o.label}</button>`)
      .join("");
    document.querySelectorAll(".option-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.getElementById("action").value = btn.textContent;
      });
    });
  }

  document.getElementById("diary-btn").addEventListener("click", () => toggleDiaryPanel());
  document.getElementById("submit-action").addEventListener("click", () => {
    const actionText = document.getElementById("action").value;
    submitAction(container, actionText);
  });
}

async function toggleDiaryPanel() {
  const panel = document.getElementById("diary-panel");
  if (panel.dataset.open === "true") {
    panel.innerHTML = "";
    panel.dataset.open = "false";
    return;
  }
  const diary = await api.diary();
  panel.dataset.open = "true";
  panel.innerHTML = `
    <div class="card">
      <h3>Quest principale</h3>
      <p>${diary.main_quest.objective}</p>
      ${
        diary.side_quests.length
          ? `<h3>Quest secondarie</h3>${diary.side_quests
              .map((q) => `<p><strong>${q.hook}</strong> — ${q.status}<br><span class="hint">${q.hint}</span></p>`)
              .join("")}`
          : ""
      }
      ${diary.notes.length ? `<h3>Note</h3>${diary.notes.map((n) => `<p class="hint">${n}</p>`).join("")}` : ""}
    </div>
  `;
}

function renderCrossroadsScreen(container, crossroad) {
  container.innerHTML = `
    <h2>Un bivio nel tuo cammino</h2>
    <p class="hint">Scegli come proseguire: la scelta cambia davvero la storia.</p>
    <div id="routes">
      ${crossroad.routes
        .map(
          (r) => `
        <div class="card route-card" data-id="${r.id}">
          <h3>${r.title}</h3>
          <p>${r.promise}</p>
          <p class="hint">Rischio: ${r.risk} · Stile: ${r.style}</p>
        </div>`
        )
        .join("")}
    </div>
    <div id="crossroads-error"></div>
  `;
  container.querySelectorAll(".route-card").forEach((card) => {
    card.addEventListener("click", async () => {
      try {
        const result = await api.chooseRoute(card.dataset.id);
        if (result.level_up) {
          await showDiceOverlay({
            die: `d${result.level_up.hit_die_sides}`,
            finalValue: result.level_up.roll,
            label: `Livello ${result.level_up.new_level}! +${result.level_up.hp_gain} PF massimi`,
          });
        }
        await renderGame(container);
      } catch (err) {
        document.getElementById("crossroads-error").innerHTML = `<p class="error">${err.message}</p>`;
      }
    });
  });
}

async function renderFinaleScreen(container) {
  const finale = await api.finale();
  const s = finale.stats;
  container.innerHTML = `
    <h2>${finale.ending?.title ?? "Fine dell'avventura"}</h2>
    <p>${finale.epilogue}</p>
    <div class="sheet-grid">
      <div class="stat-tile"><div class="value">${s.turns}</div><div class="label">Turni</div></div>
      <div class="stat-tile"><div class="value">${s.rolls}</div><div class="label">Tiri</div></div>
      <div class="stat-tile"><div class="value">${s.natural_20}</div><div class="label">20 naturali</div></div>
      <div class="stat-tile"><div class="value">${s.natural_1}</div><div class="label">1 naturali</div></div>
      <div class="stat-tile"><div class="value">${s.hp_lost}</div><div class="label">PF persi</div></div>
      <div class="stat-tile"><div class="value">${s.items_used}</div><div class="label">Oggetti usati</div></div>
    </div>
    ${
      finale.rewards_obtained.length
        ? `<h3>Ricompense ottenute</h3>${finale.rewards_obtained
            .map((r) => `<p class="hint">${r.reward?.effect ?? r.quest_id}</p>`)
            .join("")}`
        : ""
    }
    <button id="export-story-btn" class="secondary" type="button">Esporta come racconto</button>
    <div id="story-export"></div>
    <h3>Rigioca da un bivio</h3>
    <p class="hint">Riparti da prima di una scelta per provare un percorso diverso.</p>
    <button class="secondary rewind-btn" type="button" data-index="0">Rigioca dal 1° bivio</button>
    <button class="secondary rewind-btn" type="button" data-index="1">Rigioca dal 2° bivio</button>
    <div id="finale-error"></div>
  `;
  document.getElementById("export-story-btn").addEventListener("click", async (event) => {
    event.target.disabled = true;
    event.target.textContent = "Scrivo il racconto…";
    try {
      const { story_text } = await api.storyExport();
      document.getElementById("story-export").innerHTML = `<p>${story_text}</p>`;
    } catch (err) {
      document.getElementById("finale-error").innerHTML = `<p class="error">${err.message}</p>`;
    } finally {
      event.target.disabled = false;
      event.target.textContent = "Esporta come racconto";
    }
  });
  container.querySelectorAll(".rewind-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api.rewind(Number(btn.dataset.index));
        await renderGame(container);
      } catch (err) {
        document.getElementById("finale-error").innerHTML = `<p class="error">${err.message}</p>`;
      }
    });
  });
}

function _hpBar(hp) {
  const pct = Math.max(0, Math.round((hp.current / hp.maximum) * 100));
  const tempLabel = hp.temp ? ` (+${hp.temp} temp)` : "";
  return `
    <div class="hp-bar"><div class="hp-bar-fill" style="width:${pct}%"></div></div>
    <span class="hp-label">${hp.current}/${hp.maximum}${tempLabel} PF</span>
  `;
}

async function renderCombatScreen(container, log = "") {
  const state = await api.combatState();
  if (!state.in_combat) {
    await renderGame(container);
    return;
  }

  const player = state.combatants.find((c) => c.is_player);
  const isPlayerTurn = state.current_turn_id === "player";
  const playerDown = player.hp.current <= 0;
  const combatantsHtml = state.combatants
    .map((c) => {
      const current = c.id === state.current_turn_id ? " combatant-current" : "";
      const down = c.hp.current <= 0 ? " combatant-down" : "";
      return `
        <div class="combatant${current}${down}">
          <div class="combatant-name">${c.name}${c.id === state.current_turn_id ? " ⚔️" : ""}</div>
          ${_hpBar(c.hp)}
          <span class="hint">CA ${c.ac}</span>
        </div>
      `;
    })
    .join("");

  const deathSaveHtml = state.death_save
    ? `<p class="hint">A terra: tiri salvezza contro la morte — ${state.death_save.successes} success${state.death_save.successes === 1 ? "o" : "i"}, ${state.death_save.failures} fallim${state.death_save.failures === 1 ? "ento" : "enti"}${state.death_save.stable ? " · stabilizzato" : ""}</p>`
    : "";

  let actionsHtml = "";
  if (state.pending_reaction) {
    actionsHtml = `
      <div class="reaction-prompt">
        <p>${state.pending_reaction.description}</p>
        <button id="reaction-accept">Attacca (Reazione)</button>
        <button id="reaction-decline" class="secondary">Ignora</button>
      </div>
    `;
  } else if (isPlayerTurn && playerDown) {
    actionsHtml = `<button id="advance-btn" class="secondary" type="button">Termina il turno</button>`;
  } else if (isPlayerTurn) {
    const targets = state.combatants.filter((c) => !c.is_player && c.hp.current > 0);
    const weaponOptions = state.available_weapons
      .map((w) => `<option value="${w.id}" ${w.name_it === state.active_weapon ? "selected" : ""}>${w.name_it}</option>`)
      .join("");
    actionsHtml = `
      <div class="field">
        <label>Arma impugnata: ${state.active_weapon}</label>
        ${state.available_weapons.length > 1 ? `<select id="weapon-select">${weaponOptions}</select><button id="weapon-swap-btn" class="secondary" type="button">Cambia arma</button>` : ""}
      </div>
      <div id="targets">
        ${targets.map((t) => `<button class="target-btn" type="button" data-target="${t.id}">Attacca ${t.name}</button>`).join("")}
      </div>
      ${
        state.inventory.length
          ? `<div class="field"><label>Usa oggetto</label>
             <select id="item-select">${state.inventory.map((i) => `<option value="${i}">${i}</option>`).join("")}</select>
             <button id="item-use-btn" class="secondary" type="button">Usa</button></div>`
          : ""
      }
      <button id="advance-btn" class="secondary" type="button">Termina il turno</button>
    `;
  } else {
    actionsHtml = `<p class="hint">Il combattimento procede...</p>`;
  }

  container.innerHTML = `
    <h2>Combattimento — Round ${state.round}</h2>
    <div id="combatants">${combatantsHtml}</div>
    ${deathSaveHtml}
    ${log ? `<div id="combat-log"><p>${log}</p></div>` : ""}
    ${actionsHtml}
    <div id="combat-error"></div>
  `;

  document.querySelectorAll(".target-btn").forEach((btn) => {
    btn.addEventListener("click", () => runCombatAction(container, () => api.combatAttack(btn.dataset.target)));
  });
  document.getElementById("advance-btn")?.addEventListener("click", () => runCombatAction(container, () => api.combatAdvance()));
  document.getElementById("reaction-accept")?.addEventListener("click", () => runCombatAction(container, () => api.combatReaction(true)));
  document.getElementById("reaction-decline")?.addEventListener("click", () => runCombatAction(container, () => api.combatReaction(false)));
  document.getElementById("weapon-swap-btn")?.addEventListener("click", () => {
    const weaponId = document.getElementById("weapon-select").value;
    runCombatAction(container, () => api.combatWeaponSwap(weaponId));
  });
  document.getElementById("item-use-btn")?.addEventListener("click", () => {
    const item = document.getElementById("item-select").value;
    runCombatAction(container, () => api.combatItemUse(item));
  });
}

async function runCombatAction(container, action) {
  try {
    await action();
    await renderCombatScreen(container);
  } catch (err) {
    const errorBox = document.getElementById("combat-error");
    if (errorBox) errorBox.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

async function submitAction(container, actionText) {
  if (!actionText || !actionText.trim()) return;
  const button = document.getElementById("submit-action");
  button.disabled = true;
  try {
    const turn = await api.playTurn({ turn_id: newTurnId(), action: actionText });
    if (turn.roll) {
      await showDiceOverlay({
        die: "d20",
        finalValue: turn.roll.d20,
        label: `${turn.roll.total} vs CD ${turn.roll.dc} — ${turn.roll.success ? "Successo" : "Fallimento"}`,
      });
    }
    await renderGame(container);
  } catch (err) {
    document.getElementById("turn-error").innerHTML = `<p class="error">${err.message}</p>`;
    button.disabled = false;
  }
}
