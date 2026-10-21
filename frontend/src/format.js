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

// Calendar dates in the user's local timezone. Never toISOString() — that's UTC and
// returns tomorrow's date after 21:00 in Brazil.
export const localDate = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

// Integer cents, half up — same as the server's retail_price; the server prices the order again on save.
export const tablePrice = (price, table, markup) =>
  table === "retail" ? Math.round(Math.round(price * 100) * Math.round((100 + Number(markup)) * 100) / 10000) / 100 : price;

// Goals run October -> September (backend: clock.goal_year_start): the 2027 goal starts on 2026-10-01.
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
// (00) 0000-0000 up to 10 digits, (00) 00000-0000 with 11; a pasted country code 55 is dropped.
export function maskPhone(v) {
  let d = digits(v);
  if (d.length > 11 && d.startsWith("55")) d = d.slice(2);
  d = d.slice(0, 11);
  if (!d) return "";
  const k = d.length > 10 ? 5 : 4;
  return `(${d.slice(0, 2)}` + (d.length > 2 ? `) ${d.slice(2, 2 + k)}` : "") + (d.length > 2 + k ? `-${d.slice(2 + k)}` : "");
}
// Only checks fields the user changed, so an old record with a free-text value can still be edited.
export function customerFieldError(form, before = {}) {
  const changed = (k) => (form[k] || "") !== (before[k] || "");
  if (changed("document") && ![11, 14].includes(digits(form.document).length)) return "CPF/CNPJ incompleto: informe 11 dígitos (CPF) ou 14 (CNPJ).";
  if (changed("phone") && form.phone && ![10, 11].includes(digits(form.phone).length)) return "Telefone incompleto: informe o DDD e o número.";
  return "";
}

// Only digits ever reach the URL. Brazilian numbers: 10-11 digits (DDD + number) after an
// optional country code 55 and an optional trunk 0 ("047 ...", "0xx47 ...").
export function whatsappUrl(phone) {
  let digits = (phone || "").replace(/\D/g, "");
  if (digits.length >= 12 && digits.startsWith("55")) digits = digits.slice(2); // DDD 55 alone is 10-11 digits
  if (digits.startsWith("0")) digits = digits.slice(1);
  return digits.length === 10 || digits.length === 11 ? `https://wa.me/55${digits}` : null;
}

// Keys match the backend's customer_status(); tone picks the CSS color (.cstatus-<tone>).
export const CUSTOMER_STATUS = {
  active: { label: "Ativo", tone: "active" },
  at_risk: { label: "Em risco", tone: "risk" },
  inactive: { label: "Inativo", tone: "inactive" },
  never_ordered: { label: "A conquistar", tone: "never" },  // history before the app (older collections) is unknown
};
