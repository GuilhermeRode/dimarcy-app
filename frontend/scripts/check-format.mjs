// Self-check for pure helpers in src/format.js. Run from frontend/:  node scripts/check-format.mjs
import assert from "node:assert/strict";
import { addDays, compactMoney, initials, localDate, normalize, plural, whatsappUrl } from "../src/format.js";

// late-night local time must still be "today", not UTC tomorrow
assert.equal(localDate(new Date(2026, 9, 7, 23, 30)), "2026-10-07");
assert.equal(addDays("2026-10-07", -6), "2026-10-01");
assert.equal(addDays("2026-02-28", 1), "2026-03-01");

assert.equal(whatsappUrl("(47) 99123-4567"), "https://wa.me/5547991234567");
assert.equal(whatsappUrl("+55 (47) 99123-4567"), "https://wa.me/5547991234567");
assert.equal(whatsappUrl("47 3521-1234"), "https://wa.me/554735211234");
assert.equal(whatsappUrl("abc"), null);
assert.equal(whatsappUrl("123"), null);
assert.equal(whatsappUrl(null), null);

assert.equal(normalize("Itaiópolis"), "itaiopolis");
assert.ok(normalize("Adriana Müller").includes(normalize("adriana muller")));

assert.equal(initials("Adriana Muller de Souza"), "AM");
assert.equal(initials("Bella"), "BE");
assert.equal(plural(1, "pedido", "pedidos"), "1 pedido");
assert.equal(plural(3, "pedido", "pedidos"), "3 pedidos");
assert.equal(compactMoney(18240), "R$ 18,2 mil");
assert.equal(compactMoney(1250000), "R$ 1,25 mi");

console.log("format checks OK");
