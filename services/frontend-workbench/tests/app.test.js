const assert = require("node:assert/strict");
const test = require("node:test");

const { formatPrice, renderApp } = require("../src/app");

test("formatPrice renders two decimal places", () => {
  assert.equal(formatPrice(12.5), "12.50");
});

test("renderApp includes the workbench heading", () => {
  assert.match(renderApp(), /Instrument workbench/);
});

test("renderApp renders instrument symbols and prices", () => {
  const html = renderApp({ instruments: [{ symbol: "CONT", price: 125.5 }] });
  assert.match(html, /CONT/);
  assert.match(html, /\$125\.50/);
});

test("renderApp escapes instrument symbols", () => {
  const html = renderApp({ instruments: [{ symbol: "<CONT>", price: 1 }] });
  assert.match(html, /&lt;CONT&gt;/);
  assert.doesNotMatch(html, /<CONT>/);
});
