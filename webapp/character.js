import { api } from "./api.js";

const ABILITY_LABELS = { for: "Forza", des: "Destrezza", cos: "Costituzione", int: "Intelligenza", sag: "Saggezza", car: "Carisma" };
const ABILITY_IDS = Object.keys(ABILITY_LABELS);
const STEP_ORDER = ["species", "class", "background", "ability_scores", "skills", "details", "summary"];

function skillIdByName(skills, name) {
  const found = skills.find((s) => s.name_it.toLowerCase() === name.toLowerCase());
  if (!found) throw new Error(`Abilità sconosciuta: ${name}`);
  return found.id;
}

function stepsBar(current) {
  const idx = STEP_ORDER.indexOf(current);
  return `<div class="steps">${STEP_ORDER.map((_, i) => `<span class="${i <= idx ? "done" : ""}"></span>`).join("")}</div>`;
}

function errorBox(message) {
  return message ? `<p class="error">${message}</p>` : "";
}

export async function renderStep(root, ctx) {
  const { character } = ctx;
  const renderers = {
    species: renderSpecies,
    class: renderClass,
    background: renderBackground,
    ability_scores: renderAbilityScores,
    skills: renderBackgroundBonus, // "skills" = assegna il bonus del background (§4.3)
    details: renderDetails,
    summary: renderSummary,
  };
  const renderFn = renderers[character.step] || renderSpecies;
  root.innerHTML = `${stepsBar(character.step)}<div id="step"></div>`;
  await renderFn(document.getElementById("step"), ctx);
}

async function withErrorHandling(container, ctx, fn) {
  try {
    await fn();
  } catch (err) {
    const errEl = document.createElement("div");
    errEl.innerHTML = errorBox(err.message);
    container.appendChild(errEl);
  }
}

function renderSpecies(container, ctx) {
  const { options } = ctx;
  container.innerHTML = `
    <h2>1. Scegli la specie</h2>
    ${options.species
      .map(
        (s) => `<div class="card" data-id="${s.id}"><h3>${s.name_it}</h3><p>${s.size} · velocità ${s.speed}</p></div>`
      )
      .join("")}
  `;
  container.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", () =>
      withErrorHandling(container, ctx, async () => {
        await api.setSpecies(card.dataset.id);
        await ctx.reload();
      })
    );
  });
}

function renderClass(container, ctx) {
  const { options } = ctx;
  container.innerHTML = `
    <h2>2. Scegli la classe</h2>
    ${options.classes
      .map(
        (c) =>
          `<div class="card" data-id="${c.id}"><h3>${c.name_it}</h3><p>${c.hit_die} · ${c.primary_abilities}</p></div>`
      )
      .join("")}
    <div id="class-detail"></div>
  `;
  container.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", () => {
      container.querySelectorAll(".card").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
      renderClassDetail(document.getElementById("class-detail"), ctx, card.dataset.id);
    });
  });
}

function renderClassDetail(container, ctx, classId) {
  const { options } = ctx;
  const cls = options.classes.find((c) => c.id === classId);
  const equipmentLetters = [...new Set([...cls.starting_equipment.matchAll(/\(([A-C])\)/g)].map((m) => m[1]))];
  const skillOptions = cls.skill_choice_options || options.skills.map((s) => s.name_it);

  container.innerHTML = `
    <p><strong>Competenze nelle armi:</strong> scegli ${cls.skill_choice_count} abilità</p>
    ${skillOptions
      .map(
        (name) =>
          `<div class="checkbox-row"><input type="checkbox" id="sk-${name}" value="${name}"><label for="sk-${name}">${name}</label></div>`
      )
      .join("")}
    <div class="field">
      <label>Equipaggiamento iniziale</label>
      <p>${cls.starting_equipment}</p>
      <select id="equipment-choice">
        ${equipmentLetters.map((l) => `<option value="${l}">Opzione ${l}</option>`).join("")}
      </select>
    </div>
    <button id="confirm-class">Continua</button>
    <div id="class-error"></div>
  `;

  document.getElementById("confirm-class").addEventListener("click", () =>
    withErrorHandling(document.getElementById("class-error"), ctx, async () => {
      const checked = [...container.querySelectorAll("input[type=checkbox]:checked")].map((i) => i.value);
      if (checked.length !== cls.skill_choice_count) {
        throw new Error(`Scegli esattamente ${cls.skill_choice_count} abilità.`);
      }
      const skill_choices = checked.map((name) => skillIdByName(options.skills, name));
      const equipment_choice = document.getElementById("equipment-choice").value;
      await api.setClass({ class_id: classId, skill_choices, equipment_choice });
      await ctx.reload();
    })
  );
}

function renderBackground(container, ctx) {
  const { options } = ctx;
  container.innerHTML = `
    <h2>3. Scegli il background</h2>
    ${options.backgrounds
      .map(
        (b) =>
          `<div class="card" data-id="${b.id}"><h3>${b.name_it}</h3><p>${b.ability_scores}</p><p>Talento: ${b.feat}</p></div>`
      )
      .join("")}
  `;
  container.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", () =>
      withErrorHandling(container, ctx, async () => {
        await api.setBackground(card.dataset.id);
        await ctx.reload();
      })
    );
  });
}

function renderAbilityScores(container, ctx) {
  const { options } = ctx;
  container.innerHTML = `
    <h2>4. Punteggi di caratteristica</h2>
    <div class="card" data-method="standard_array"><h3>Array standard</h3><p>${options.standard_array.join(", ")}</p></div>
    <div class="card" data-method="point_buy"><h3>Point buy</h3><p>27 punti da spendere (8-15)</p></div>
    <div class="card" data-method="4d6"><h3>4d6, scarta il più basso</h3><p>Tira 6 volte, il server decide i dadi</p></div>
    <div id="method-detail"></div>
  `;
  container.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", () => {
      container.querySelectorAll(".card").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
      renderMethodDetail(document.getElementById("method-detail"), ctx, card.dataset.method);
    });
  });
}

function abilityAssignFields(values) {
  // Ogni caratteristica parte con un valore diverso già assegnato (ruotando
  // l'elenco), così una conferma senza modifiche invia comunque 6 valori
  // distinti invece di ripetere il primo su tutti i menu.
  return ABILITY_IDS.map(
    (a, i) => `
    <div class="field">
      <label>${ABILITY_LABELS[a]}</label>
      <select data-ability="${a}">
        ${values.map((v, j) => `<option value="${v}" ${i === j ? "selected" : ""}>${v}</option>`).join("")}
      </select>
    </div>`
  ).join("");
}

function renderMethodDetail(container, ctx, method) {
  if (method === "standard_array") {
    container.innerHTML = `${abilityAssignFields(ctx.options.standard_array)}<button id="confirm-scores">Continua</button><div id="scores-error"></div>`;
    bindAssignConfirm(container, ctx, method);
  } else if (method === "point_buy") {
    container.innerHTML = `
      ${ABILITY_IDS.map(
        (a) => `<div class="field"><label>${ABILITY_LABELS[a]}</label>
        <input type="number" min="8" max="15" value="8" data-ability="${a}"></div>`
      ).join("")}
      <p id="pb-cost">Costo: 0 / 27</p>
      <button id="confirm-scores">Continua</button>
      <div id="scores-error"></div>
    `;
    const cost = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 };
    const updateCost = () => {
      const total = [...container.querySelectorAll("input[data-ability]")].reduce(
        (sum, el) => sum + (cost[Number(el.value)] ?? 0),
        0
      );
      document.getElementById("pb-cost").textContent = `Costo: ${total} / 27`;
    };
    container.querySelectorAll("input[data-ability]").forEach((el) => el.addEventListener("input", updateCost));
    document.getElementById("confirm-scores").addEventListener("click", () =>
      withErrorHandling(document.getElementById("scores-error"), ctx, async () => {
        const scores = {};
        container.querySelectorAll("input[data-ability]").forEach((el) => (scores[el.dataset.ability] = Number(el.value)));
        await api.setAbilityScores({ method, scores });
        await ctx.reload();
      })
    );
  } else {
    container.innerHTML = `<button id="roll">Tira i dadi</button><div id="roll-result"></div>`;
    document.getElementById("roll").addEventListener("click", () =>
      withErrorHandling(container, ctx, async () => {
        const { rolled_scores } = await api.rollAbilityScores();
        document.getElementById("roll-result").innerHTML = `
          <p>Valori tirati: ${rolled_scores.join(", ")}</p>
          ${abilityAssignFields(rolled_scores)}
          <button id="confirm-scores">Continua</button>
          <div id="scores-error"></div>
        `;
        bindAssignConfirm(container, ctx, "4d6");
      })
    );
  }
}

function bindAssignConfirm(container, ctx, method) {
  document.getElementById("confirm-scores").addEventListener("click", () =>
    withErrorHandling(document.getElementById("scores-error"), ctx, async () => {
      const scores = {};
      const used = new Set();
      container.querySelectorAll("select[data-ability]").forEach((el) => {
        scores[el.dataset.ability] = Number(el.value);
        used.add(el);
      });
      await api.setAbilityScores({ method, scores });
      await ctx.reload();
    })
  );
}

function renderBackgroundBonus(container, ctx) {
  container.innerHTML = `
    <h2>Bonus del background</h2>
    <p>Aumenta una caratteristica di 2 e un'altra di 1, oppure tre caratteristiche di 1 ciascuna.</p>
    <div class="field">
      <label>Modalità</label>
      <select id="bonus-mode">
        <option value="2-1">+2 / +1</option>
        <option value="1-1-1">+1 / +1 / +1</option>
      </select>
    </div>
    <div id="bonus-fields"></div>
    <button id="confirm-bonus">Continua</button>
    <div id="bonus-error"></div>
  `;
  const renderFields = () => {
    const mode = document.getElementById("bonus-mode").value;
    const count = mode === "2-1" ? 2 : 3;
    document.getElementById("bonus-fields").innerHTML = Array.from(
      { length: count },
      (_, i) => `
      <div class="field">
        <label>Caratteristica ${i + 1}</label>
        <select data-slot="${i}">${ABILITY_IDS.map(
          (a, j) => `<option value="${a}" ${i === j ? "selected" : ""}>${ABILITY_LABELS[a]}</option>`
        ).join("")}</select>
      </div>`
    ).join("");
  };
  document.getElementById("bonus-mode").addEventListener("change", renderFields);
  renderFields();

  document.getElementById("confirm-bonus").addEventListener("click", () =>
    withErrorHandling(document.getElementById("bonus-error"), ctx, async () => {
      const mode = document.getElementById("bonus-mode").value;
      const increments = mode === "2-1" ? [2, 1] : [1, 1, 1];
      const bonus = {};
      document.querySelectorAll("#bonus-fields select").forEach((el, i) => {
        bonus[el.value] = (bonus[el.value] || 0) + increments[i];
      });
      await api.setBackgroundBonus(bonus);
      await ctx.reload();
    })
  );
}

function renderDetails(container, ctx) {
  container.innerHTML = `
    <h2>5. Chi è il tuo personaggio?</h2>
    <div class="field"><label>Nome</label><input type="text" id="name"></div>
    <div class="field"><label>Aspetto</label><textarea id="appearance"></textarea></div>
    <div class="field"><label>Tratti caratteriali</label><textarea id="traits"></textarea></div>
    <div class="field"><label>Ideali</label><textarea id="ideals"></textarea></div>
    <div class="field"><label>Legami</label><textarea id="bonds"></textarea></div>
    <div class="field"><label>Difetti</label><textarea id="flaws"></textarea></div>
    <div class="field"><label>Breve storia</label><textarea id="backstory"></textarea></div>
    <button id="confirm-details">Crea il personaggio</button>
    <div id="details-error"></div>
  `;
  document.getElementById("confirm-details").addEventListener("click", () =>
    withErrorHandling(document.getElementById("details-error"), ctx, async () => {
      const name = document.getElementById("name").value;
      const details = {};
      ["appearance", "traits", "ideals", "bonds", "flaws", "backstory"].forEach((k) => {
        details[k] = document.getElementById(k).value;
      });
      await api.setDetails({ name, details });
      await ctx.reload();
    })
  );
}

async function renderSummary(container, ctx) {
  container.innerHTML = "<p>Genero la scheda…</p>";
  const sheet = await api.sheet();
  const mod = (n) => (n >= 0 ? `+${n}` : `${n}`);
  container.innerHTML = `
    <h2>${sheet.name}</h2>
    <p>${sheet.species} · ${sheet.class_} · ${sheet.background} · Livello ${sheet.level}</p>
    <div class="sheet-grid">
      <div class="stat-tile"><div class="value">${sheet.armor_class}</div><div class="label">CA</div></div>
      <div class="stat-tile"><div class="value">${sheet.hit_points.current}/${sheet.hit_points.maximum}</div><div class="label">PF</div></div>
      <div class="stat-tile"><div class="value">${mod(sheet.initiative)}</div><div class="label">Iniziativa</div></div>
      <div class="stat-tile"><div class="value">${mod(sheet.proficiency_bonus)}</div><div class="label">Competenza</div></div>
      <div class="stat-tile"><div class="value">${sheet.speed_m} m</div><div class="label">Velocità</div></div>
      <div class="stat-tile"><div class="value">${sheet.passive_perception}</div><div class="label">Percezione passiva</div></div>
    </div>
    <h3>Caratteristiche</h3>
    ${Object.entries(sheet.ability_scores)
      .map(([a, v]) => `<span class="tag">${ABILITY_LABELS[a]} ${v} (${mod(sheet.ability_modifiers[a])})</span>`)
      .join("")}
    <h3>Tiri salvezza</h3>
    ${Object.entries(sheet.saving_throws)
      .map(([a, v]) => `<span class="tag">${ABILITY_LABELS[a]} ${mod(v)}</span>`)
      .join("")}
    <h3>Abilità</h3>
    ${Object.values(sheet.skills)
      .map(
        (s) => `<div class="skill-row ${s.proficient ? "proficient" : ""}"><span>${s.name_it}</span><span>${mod(s.bonus)}</span></div>`
      )
      .join("")}
    <h3>Equipaggiamento</h3>
    <p>${sheet.equipment}</p>
    <p>${sheet.gold} mo</p>
    ${sheet.feat ? `<h3>Talento d'origine</h3><p>${sheet.feat}</p>` : ""}
    <p class="hint">Sottoclasse al livello ${sheet.subclass_at_level}${sheet.spellcasting ? " · classe incantatrice" : ""}</p>
  `;
}
