const DIE_FACES = { d4: 4, d6: 6, d8: 8, d10: 10, d12: 12, d20: 20, d100: 100 };

function randomFace(sides) {
  return 1 + Math.floor(Math.random() * sides);
}

/**
 * Mostra un overlay con un dado che "rotola" (valori casuali solo per
 * l'animazione) e poi si ferma sul valore deciso dal server (§7): il
 * client non genera mai il numero che conta, solo il movimento.
 */
export function showDiceOverlay({ die = "d20", finalValue, label = "" }) {
  return new Promise((resolve) => {
    const sides = DIE_FACES[die] || 20;
    const overlay = document.createElement("div");
    overlay.className = "dice-overlay";
    overlay.innerHTML = `
      <div class="dice-tray">
        <div class="die-face">?</div>
        <div class="die-label">${label}</div>
      </div>
    `;
    document.body.appendChild(overlay);
    const face = overlay.querySelector(".die-face");

    let elapsed = 0;
    const stepMs = 60;
    const durationMs = 1200;
    const interval = setInterval(() => {
      face.textContent = randomFace(sides);
      elapsed += stepMs;
      if (elapsed >= durationMs) {
        clearInterval(interval);
        face.textContent = finalValue;
        face.classList.add("settled");
        setTimeout(() => {
          overlay.remove();
          resolve();
        }, 500);
      }
    }, stepMs);
  });
}
