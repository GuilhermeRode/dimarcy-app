// Only orders placed in the app make a customer "Pedido realizado". Run from frontend/:  node test_contact_state.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// format.js is plain ESM with a .js name, so load it as a module whatever the package type
const source = readFileSync(new URL("./src/format.js", import.meta.url));
const { contactState } = await import(`data:text/javascript;base64,${source.toString("base64")}`);

const today = "2026-10-31";
const appOrder = { date: "2026-10-15", id: 1, pieces: 1, total: 10 };
const state = (c) => contactState({ recent_orders: [], last_order_date: null, ...c }, today).key;

assert.equal(state({}), "missing");
assert.equal(state({ last_order_date: "2026-05-12" }), "missing"); // imported past purchase only
assert.equal(state({ last_order_date: "2026-10-15", recent_orders: [appOrder] }), "ordered");

const contacted = { last_contact_at: "2026-10-20T12:00:00" };
assert.equal(state({ ...contacted, last_order_date: "2026-10-25" }), "contacted"); // past purchase after the contact
assert.equal(state({ ...contacted, recent_orders: [{ ...appOrder, date: "2026-10-25" }] }), "ordered");
assert.equal(state({ ...contacted, recent_orders: [appOrder] }), "contacted"); // order before the contact

console.log("ok");
