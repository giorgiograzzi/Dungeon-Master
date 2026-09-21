let initData = null;

export function setInitData(value) {
  initData = value;
}

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (initData) headers["X-Telegram-Init-Data"] = initData;
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* risposta senza corpo JSON */
    }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  verify: (init_data) => request("/api/auth/verify", { method: "POST", body: JSON.stringify({ init_data }) }),
  options: () => request("/api/character/options"),
  character: () => request("/api/character"),
  sheet: () => request("/api/character/sheet"),
  setSpecies: (species_id) =>
    request("/api/character/species", { method: "POST", body: JSON.stringify({ species_id }) }),
  setClass: (payload) => request("/api/character/class", { method: "POST", body: JSON.stringify(payload) }),
  setBackground: (background_id) =>
    request("/api/character/background", { method: "POST", body: JSON.stringify({ background_id }) }),
  rollAbilityScores: () => request("/api/character/ability-scores/roll", { method: "POST" }),
  setAbilityScores: (payload) =>
    request("/api/character/ability-scores", { method: "POST", body: JSON.stringify(payload) }),
  setBackgroundBonus: (bonus) =>
    request("/api/character/background-bonus", { method: "POST", body: JSON.stringify({ bonus }) }),
  setDetails: (payload) => request("/api/character/details", { method: "POST", body: JSON.stringify(payload) }),
};
