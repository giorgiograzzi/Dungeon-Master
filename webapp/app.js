const tg = window.Telegram?.WebApp;
const statusEl = document.getElementById("status");

async function verify() {
  if (!tg) {
    statusEl.textContent = "Apri questa pagina dal bot Telegram per accedere.";
    return;
  }
  tg.ready();
  tg.expand();

  try {
    const res = await fetch("/api/auth/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: tg.initData }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      statusEl.textContent = `Accesso negato: ${err.detail ?? res.status}`;
      return;
    }
    const data = await res.json();
    statusEl.textContent = `Ciao ${data.first_name ?? "avventuriero"}! Sei autenticato.`;
  } catch (err) {
    statusEl.textContent = "Impossibile contattare il server. Riprova.";
  }
}

verify();
