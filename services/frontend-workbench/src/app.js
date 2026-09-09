function formatPrice(value) {
  return Number(value).toFixed(2);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderApp(state = {}) {
  const instruments = Array.isArray(state.instruments) ? state.instruments : [];
  const rows = instruments
    .map(
      (instrument) =>
        `<li data-symbol="${escapeHtml(instrument.symbol)}">${escapeHtml(
          instrument.symbol
        )}: $${formatPrice(instrument.price)}</li>`
    )
    .join("");

  return `<main class="workbench"><h1>Instrument workbench</h1><ul>${rows}</ul></main>`;
}

module.exports = { formatPrice, renderApp };
