import { api, setInitData } from "./api.js";
import { renderStep } from "./character.js";

const tg = window.Telegram?.WebApp;
const root = document.getElementById("app");

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
    await renderStep(root, { options, character: characterResponse.data, reload: loadAndRender });
  } catch (err) {
    root.innerHTML = `<p id="status">Errore: ${err.message}</p>`;
  }
}

boot();
