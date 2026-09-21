import { api, setInitData } from "./api.js";
import { renderStep } from "./character.js";
import { renderGame } from "./game.js";

const tg = window.Telegram?.WebApp;
const root = document.getElementById("app");
let view = "sheet"; // "sheet" | "game", rilevante solo a creazione completata

async function boot() {
  if (!tg) {
    root.innerHTML = `<p id="status">Apri questa pagina dal bot Telegram per accedere.</p>`;
    return;
  }
  tg.ready();
  tg.expand();
  setInitData(tg.initData);

  try {
    await api.verify(tg.initData);
  } catch (err) {
    root.innerHTML = `<p id="status">Accesso negato: ${err.message}</p>`;
    return;
  }

  await loadAndRender();
}

async function loadAndRender() {
  root.innerHTML = `<p id="status">Carico il personaggio…</p>`;
  try {
    const [options, characterResponse] = await Promise.all([api.options(), api.character()]);
    const character = characterResponse.data;
    if (character.step !== "summary") {
      await renderStep(root, { options, character, reload: loadAndRender });
      return;
    }
    await renderCompletedCharacterView(options, character);
  } catch (err) {
    root.innerHTML = `<p id="status">Errore: ${err.message}</p>`;
  }
}

async function renderCompletedCharacterView(options, character) {
  const gameState = await api.gameState();
  if (gameState.has_campaign) view = "game";

  root.innerHTML = `
    <nav class="tabbar">
      <button class="tab ${view === "sheet" ? "active" : ""}" data-view="sheet">Scheda</button>
      <button class="tab ${view === "game" ? "active" : ""}" data-view="game">Gioca</button>
    </nav>
    <div id="content"></div>
  `;
  root.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", async () => {
      view = btn.dataset.view;
      await renderCompletedCharacterView(options, character);
    });
  });

  const content = document.getElementById("content");
  if (view === "game") {
    await renderGame(content);
  } else {
    await renderStep(content, { options, character, reload: loadAndRender });
  }
}

boot();
