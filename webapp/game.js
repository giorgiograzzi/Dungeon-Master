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

function renderTurnScreen(container, state) {
  container.innerHTML = `
    <h2>${state.title ?? "La tua avventura"}</h2>
    <p class="hint">Obiettivo attuale: ${state.current_objective}</p>
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

  document.getElementById("submit-action").addEventListener("click", () => {
    const actionText = document.getElementById("action").value;
    submitAction(container, actionText);
  });
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
