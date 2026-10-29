export const money = (v) =>
  Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const dateBR = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString("pt-BR") : "");

export const orderNumber = (id) => String(id).padStart(5, "0");

export const STATUS = {
  quote: "Orçamento",
  confirmed: "Confirmado",
  in_production: "Em produção",
  shipped: "Enviado",
  delivered: "Entregue",
  canceled: "Cancelado",
};

export const DEFAULT_SIZES = ["U", "P", "M", "G", "GG"];
// Same order everywhere sizes are listed (product form, order grid, prints). Same list as SIZE_ORDER in backend/app/models.py.
const SIZE_ORDER = ["U", "PP", "P", "M", "G", "GG", "XG", "XGG", "EG", "EGG"];
const sizeRank = (s) => {
  const i = SIZE_ORDER.indexOf(s);
  return i >= 0 ? [0, i, ""] : /^\d+$/.test(s) ? [1, Number(s), ""] : [2, 0, s];
};
// known sizes in SIZE_ORDER, then numbers (36, 38...), then anything else alphabetically
export const sortSizes = (sizes) => [...sizes].sort((a, b) => {
  const [x, y] = [sizeRank(a), sizeRank(b)];
  return x[0] - y[0] || x[1] - y[1] || x[2].localeCompare(y[2]);
});

// Calendar dates in the user's local timezone. Never toISOString() — that's UTC and
// returns tomorrow's date after 21:00 in Brazil.
// A server timestamp (naive UTC, as the API sends created_at) as a pt-BR date.
export const utcDateBR = (iso) => new Date(`${iso}Z`).toLocaleDateString("pt-BR");

export const localDate = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

// Integer cents, half up — same as the server's retail_price; the server prices the order again on save.
export const tablePrice = (price, table, markup) =>
  table === "retail" ? Math.round(Math.round(price * 100) * Math.round((100 + Number(markup)) * 100) / 10000) / 100 : price;

// Goals run October -> September (backend: clock.goal_year_start): the 2026/27 goal starts on 2026-10-01.
export const goalYearStart = (d = new Date()) => `${d.getMonth() >= 9 ? d.getFullYear() : d.getFullYear() - 1}-10-01`;

export const addDays = (iso, days) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return localDate(d);
};

export const compactMoney = (v) => {
  const n = Number(v || 0);
  if (n >= 1e6) return `R$ ${(n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} mi`;
  if (n >= 1e3) return `R$ ${(n / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
  return money(n);
};

export const plural = (n, one, many) => `${n.toLocaleString("pt-BR")} ${n === 1 ? one : many}`;

export function initials(name) {
  const words = (name || "?").trim().split(/\s+/);
  return words.length > 1 ? (words[0][0] + words[1][0]).toUpperCase() : words[0].slice(0, 2).toUpperCase();
}

// Lowercase without accents, for search ("Itaiópolis" matches "itaiopolis").
export const normalize = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// CPF/CNPJ share one field: it formats as a CPF (000.000.000-00) up to 11 digits and switches to a
// CNPJ (00.000.000/0000-00) when the 12th digit is typed.
const digits = (s) => (s || "").replace(/\D/g, "");
export function maskDocument(v) {
  const d = digits(v).slice(0, 14);
  if (d.length > 11) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}${d.length > 12 ? "-" + d.slice(12) : ""}`;
  return [d.slice(0, 3), d.slice(3, 6), d.slice(6, 9)].filter(Boolean).join(".") + (d.length > 9 ? "-" + d.slice(9) : "");
}
// (00) 0000-0000 up to 10 digits, (00) 00000-0000 with 11; a pasted country code 55 and trunk 0
// ("047 ...", "0xx47 ...") are dropped. The server adds the 9th digit to old 8-digit mobiles (format_phone).
export function maskPhone(v) {
  let d = digits(v).replace(/^0+/, "");
  if (d.length > 11 && d.startsWith("55")) d = d.slice(2);
  d = d.slice(0, 11);
  if (!d) return "";
  const k = d.length > 10 ? 5 : 4;
  return `(${d.slice(0, 2)}` + (d.length > 2 ? `) ${d.slice(2, 2 + k)}` : "") + (d.length > 2 + k ? `-${d.slice(2 + k)}` : "");
}
// Inscrição estadual mask per state; each 0 is a digit, some states have two lengths.
// Keep in sync with IE_MASKS in backend/app/br_format.py.
export const IE_MASKS = {
  AC: ["00.000.000/000-00"], AL: ["000000000"], AM: ["00.000.000-0"], AP: ["000000000"],
  BA: ["000000-00", "0000000-00"], CE: ["00000000-0"], DF: ["00000000000-00"], ES: ["000.000.00-0"],
  GO: ["00.000.000-0"], MA: ["000000000"], MG: ["000.000.000/0000"], MS: ["00.000.000-0"],
  MT: ["0000000000-0"], PA: ["00-000000-0"], PB: ["00000000-0"], PE: ["0000000-00", "00.0.000.0000000-0"],
  PI: ["000000000"], PR: ["00000000-00"], RJ: ["00.000.00-0"], RN: ["00.000.000-0", "00.0.000.000-0"],
  RO: ["0000000000000-0"], RR: ["00000000-0"], RS: ["000/0000000"], SC: ["000.000.000"],
  SE: ["00000000-0"], SP: ["000.000.000.000"], TO: ["000000000", "00000000000"],
};
const ieMasks = (uf) => IE_MASKS[(uf || "").toUpperCase()] || [];
const zeros = (m) => m.replace(/[^0]/g, "").length;
// Formats as it's typed, capped at the state's longest IE; the shorter mask is used until a digit overflows it.
// Without a known UF: digits only, up to 14.
export function maskStateRegistration(v, uf) {
  const masks = ieMasks(uf);
  if (!masks.length) return digits(v).slice(0, 14);
  const d = digits(v).slice(0, Math.max(...masks.map(zeros)));
  const mask = masks.find((m) => zeros(m) >= d.length);
  let out = "", i = 0;
  for (const ch of mask) {
    if (i === d.length) break;
    out += ch === "0" ? d[i++] : ch;
  }
  return out;
}
export const stateRegistrationHint = (uf) => ieMasks(uf).join(" ou ");

// Only checks fields the user changed, so an old record with a free-text value can still be edited.
export function customerFieldError(form, before = {}) {
  const changed = (k) => (form[k] || "") !== (before[k] || "");
  if (changed("document") && form.document && ![11, 14].includes(digits(form.document).length)) return "CPF/CNPJ incompleto: informe 11 dígitos (CPF) ou 14 (CNPJ).";
  if (changed("phone") && form.phone && ![10, 11].includes(digits(form.phone).length)) return "Telefone incompleto: informe o DDD e o número.";
  const ie = form.state_registration, masks = ieMasks(form.state);
  if ((changed("state_registration") || changed("state")) && ie && ie !== "ISENTO" && masks.length
      && !masks.map(zeros).includes(digits(ie).length))
    return `Inscrição estadual incompleta para ${form.state.toUpperCase()}: use o formato ${stateRegistrationHint(form.state)}.`;
  return "";
}

// Only digits ever reach the URL. Brazilian numbers: 10-11 digits (DDD + number) after an
// optional country code 55 and an optional trunk 0 ("047 ...", "0xx47 ..."). `text` pre-fills the message.
export function whatsappUrl(phone, text) {
  let digits = (phone || "").replace(/\D/g, "");
  if (digits.length >= 12 && digits.startsWith("55")) digits = digits.slice(2); // DDD 55 alone is 10-11 digits
  if (digits.startsWith("0")) digits = digits.slice(1);
  if (digits.length !== 10 && digits.length !== 11) return null;
  return `https://wa.me/55${digits}${text ? `?text=${encodeURIComponent(text)}` : ""}`;
}

// 14 characters (digits, or letters since 2026) -> 12.ABC.345/0001-99
export const formatCnpj = (c) =>
  c && c.length === 14 ? `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}` : c || "";

export const LEAD_SIZES = { mei: "MEI", me: "ME", epp: "EPP", large: "Grande" };

// Keys match the backend's customer_status(); tone picks the CSS color (.cstatus-<tone>).
export const CUSTOMER_STATUS = {
  active: { label: "Ativo", tone: "active" },
  at_risk: { label: "Em risco", tone: "risk" },
  inactive: { label: "Inativo", tone: "inactive" },
  never_ordered: { label: "A conquistar", tone: "never" },  // history before the app (older collections) is unknown
};
