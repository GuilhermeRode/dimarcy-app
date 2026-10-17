# Prospecção + mini-CRM — Plano 3 de 3: telas

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The screens: Prospecção (`/leads`) with a lead panel, contact history in both panels, Retornos (`/follow-ups`) with a Painel alert, region cities in Usuários and the CNAE list in Configurações.

**Architecture:** Plain React components in the existing style (axios `api`, `Modal`/`Field`/`ErrorBox` from `components/ui.jsx`, the Clientes list/panel CSS). Contacts UI lives in one file `components/Contacts.jsx` (`ContactHistory` + `ContactModal`) reused by the lead and customer panels and the Retornos page.

**Tech Stack:** React 18, react-router-dom (HashRouter), axios, Vite. No frontend test framework in this repo: each task is verified with `npm run build` plus a short manual check against the running backend.

**Spec:** `docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md` (section "Telas")

**Depends on:** Plano 1 (`2026-10-16-prospeccao-1-backend.md`) API: `GET /leads` → `{items, total, cities}`, `GET /leads/{id}`, `POST /leads/{id}/convert`, `POST /leads/{id}/discard`, `GET/POST /contacts`, `GET /contacts/due`, `GET/PUT /users/{id}/cities`, `GET /users/{id}/cities/suggestions`, `GET /users/cities/options`, `/settings.lead_cnaes`, `dashboard.alerts.follow_ups_due`. Lead item keys: `id, cnpj, name, phone, email, address, city, state, opened_at, status, seller_id, seller_name`.

## Global Constraints

- Code in English; every visible string in pt-BR (`CLAUDE.md`).
- No new dependencies.
- Calendar dates: `localDate()` / `addDays()` / `dateBR()` from `format.js`; never `toISOString()` for a date.
- `created_at` from the server is UTC without a zone (SQLite `CURRENT_TIMESTAMP`): parse as `new Date(value + "Z")`.
- Reuse the Clientes CSS (`customers-layout`, `customers-table`, `customers-row`, `customer-panel*`, `pill-select`, `filters-*`); new CSS goes at the end of `styles.css` in one `/* ---------- prospecção / contatos ---------- */` block.
- Run commands from `frontend/` unless noted. Manual checks: backend `uvicorn app.main:app --reload` in `backend/`, frontend `npm run dev`; log in as admin and as a seller.

## Review Focus

- Phone width (≤ 860 px): the lead list and the lead panel must behave like Clientes (panel full screen with ×, rows collapse to name + last column).
- "Virar cliente" pressed twice quickly must not show two success flows (the API answers 409 to the second; show its message, don't crash).
- Saving a seller in Usuários whose region has a city of another seller: the 409 text must show in the modal and the user (already saved) must not be duplicated on the next "Salvar".
- A lead without phone: WhatsApp button disabled with the same tooltip as Clientes.
- A seller with no region yet: Prospecção shows an explanatory empty state, not an empty table.

---

### Task 1: Contacts UI + WhatsApp text + contact history in the customer panel

**Files:**
- Modify: `frontend/src/format.js` (`whatsappUrl(phone, text)`, `formatCnpj`)
- Create: `frontend/src/components/Contacts.jsx`
- Modify: `frontend/src/components/CustomerPanel.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Produces: `whatsappUrl(phone, text?) -> string | null`; `formatCnpj(cnpj) -> string`; `CHANNELS` (`{whatsapp: "WhatsApp", call: "Ligação", visit: "Visita", email: "E-mail"}`); `<ContactModal target={{lead_id}|{customer_id}} onClose onSaved />`; `<ContactHistory target={{lead_id}|{customer_id}} />`.

- [ ] **Step 1: `format.js`** — replace `whatsappUrl` and add `formatCnpj` below it:

```js
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
```

- [ ] **Step 2: Create `frontend/src/components/Contacts.jsx`**

```jsx
import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { addDays, dateBR, localDate } from "../format";
import { ErrorBox, Field, Modal } from "./ui";

// Keys match the backend's CONTACT_CHANNELS
export const CHANNELS = { whatsapp: "WhatsApp", call: "Ligação", visit: "Visita", email: "E-mail" };

// created_at is UTC without a zone (SQLite CURRENT_TIMESTAMP); "Z" makes the browser convert it to local time
const contactDate = (iso) => new Date(`${iso}Z`).toLocaleDateString("pt-BR");

export function ContactModal({ target, onClose, onSaved }) {
  const [form, setForm] = useState({ channel: "whatsapp", notes: "", next_action_date: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const today = localDate();

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/contacts", { ...target, channel: form.channel, notes: form.notes.trim() || null,
                                    next_action_date: form.next_action_date || null });
      onSaved();
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }

  return (
    <Modal title="Registrar contato" onClose={onClose}>
      <form onSubmit={save} className="form-grid">
        <Field label="Canal" span={2}>
          <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}>
            {Object.entries(CHANNELS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </Field>
        <Field label="Anotação" span={2}>
          <textarea rows={3} maxLength={2000} placeholder="Ex.: pediu o catálogo, falar com a dona na segunda"
            value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </Field>
        <Field label="Retornar em (opcional)" span={2}>
          <div className="contact-next">
            <input type="date" min={today} value={form.next_action_date}
              onChange={(e) => setForm({ ...form, next_action_date: e.target.value })} />
            {[3, 7, 30].map((d) => (
              <button type="button" key={d} className="btn"
                onClick={() => setForm({ ...form, next_action_date: addDays(today, d) })}>+{d} dias</button>
            ))}
          </div>
        </Field>
        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2"><button className="btn btn-primary" disabled={busy}>Salvar contato</button></div>
      </form>
    </Modal>
  );
}

export function ContactHistory({ target }) {
  const query = target.lead_id ? `lead_id=${target.lead_id}` : `customer_id=${target.customer_id}`;
  const [list, setList] = useState(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  const load = () => api.get(`/contacts?${query}`)
    .then((r) => { setList(r.data); setError(""); })
    .catch((e) => setError(errorMessage(e)));
  useEffect(() => { setList(null); load(); }, [query]);

  return (
    <div>
      <div className="contacts-head">
        <h3>Contatos</h3>
        <button type="button" className="btn" onClick={() => setAdding(true)}>Registrar contato</button>
      </div>
      <ErrorBox msg={error} />
      {list && (list.length ? list.map((ct) => (
        <div key={ct.id} className="contact-item">
          <small>{contactDate(ct.created_at)} · {CHANNELS[ct.channel]} · {ct.user_name}</small>
          {ct.notes && <p>{ct.notes}</p>}
          {ct.next_action_date && <small className="contact-due">Retornar em {dateBR(ct.next_action_date)}</small>}
        </div>
      )) : <p className="customer-panel-empty">Nenhum contato registrado ainda.</p>)}
      {adding && <ContactModal target={target} onClose={() => setAdding(false)}
        onSaved={() => { setAdding(false); load(); }} />}
    </div>
  );
}
```

- [ ] **Step 3: Customer panel** — in `frontend/src/components/CustomerPanel.jsx`, add `import { ContactHistory } from "./Contacts";` and, right after the closing `</div>` of the "Últimos pedidos" block (before `</aside>`):

```jsx
      <ContactHistory target={{ customer_id: c.id }} />
```

- [ ] **Step 4: CSS** — append to `frontend/src/styles.css`:

```css
/* ---------- prospecção / contatos ---------- */
.contacts-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 6px; }
.contacts-head h3 { margin: 0; }
.contact-item { display: flex; flex-direction: column; gap: 2px; padding: 8px 0; border-top: 1px solid var(--line); font-size: 13px; }
.contact-item p { margin: 0; white-space: pre-wrap; }
.contact-item small { color: var(--muted); }
.contact-item .contact-due { color: var(--accent-strong); font-weight: 600; }
.contact-next { display: flex; gap: 8px; flex-wrap: wrap; }
.contact-next input { flex: 1 1 150px; }
```

- [ ] **Step 5: Build**

Run: `npm run build`
Expected: `✓ built in …` with no errors.

- [ ] **Step 6: Manual check** — Clientes → open a customer: the panel shows "Contatos" with "Nenhum contato registrado ainda."; "Registrar contato" → choose Ligação, type a note, click "+7 dias", save → the item appears with today's date, "Ligação · <your name>" and "Retornar em <date>". Customer with phone: WhatsApp still opens `wa.me/55…` (no text).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/format.js frontend/src/components/Contacts.jsx frontend/src/components/CustomerPanel.jsx frontend/src/styles.css
git commit -m "Contacts: history and register-contact modal in the customer panel"
```

---

### Task 2: Prospecção screen (`/leads`) with lead panel, convert and discard

**Files:**
- Create: `frontend/src/components/LeadPanel.jsx`
- Create: `frontend/src/pages/Leads.jsx`
- Modify: `frontend/src/components/CustomerFormModal.jsx` (prop `submitUrl`)
- Modify: `frontend/src/components/icons.jsx` (`LeadsIcon`)
- Modify: `frontend/src/components/Layout.jsx` (menu link, both lists)
- Modify: `frontend/src/App.jsx` (route)
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `ContactHistory`, `whatsappUrl(phone, text)`, `formatCnpj`, `CustomerFormModal` + `EMPTY_CUSTOMER`.
- Produces: `<CustomerFormModal submitUrl="/leads/{id}/convert" … />` (POST to that URL instead of `/customers` when the form has no `id`); `LeadsIcon`; route `/leads`.

- [ ] **Step 1: `CustomerFormModal` submit URL** — in `frontend/src/components/CustomerFormModal.jsx`, change the signature and the save line:

```jsx
export default function CustomerFormModal({ initial, isAdmin, onClose, onSaved, submitUrl = "/customers" }) {
```

```jsx
      form.id ? await api.put(`/customers/${form.id}`, body) : await api.post(submitUrl, body);
```

- [ ] **Step 2: Icon** — append to `frontend/src/components/icons.jsx`:

```jsx
export const LeadsIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" r="4" />
    <circle cx="12" cy="12" r="0.8" />
  </svg>
);
```

- [ ] **Step 3: Create `frontend/src/components/LeadPanel.jsx`**

```jsx
import { useAuth } from "../auth";
import { dateBR, formatCnpj, initials, whatsappUrl } from "../format";
import { ContactHistory } from "./Contacts";

export const isNewStore = (openedAt) =>
  !!openedAt && (Date.now() - new Date(`${openedAt}T00:00:00`)) / 86400000 <= 730; // backend NEW_STORE_DAYS

export default function LeadPanel({ lead, isAdmin, onClose, onConvert, onDiscard }) {
  const { user } = useAuth();
  const firstName = (user?.name || "").split(" ")[0];
  const wa = whatsappUrl(lead.phone, `Olá, tudo bem? Sou ${firstName} da Di Marcy. Gostaria de apresentar nossa `
    + `coleção para a ${lead.name}. Posso te enviar o catálogo?`);
  return (
    <aside className="customer-panel" aria-label={`Lead ${lead.name}`}>
      <button type="button" className="customer-panel-close" onClick={onClose} aria-label="Fechar">×</button>
      <div className="customer-panel-head">
        <span className="customer-avatar lg">{initials(lead.name)}</span>
        <div>
          <strong>{lead.name}</strong>
          <span className="muted">{[`${lead.city}/${lead.state}`, lead.phone].filter(Boolean).join(" · ")}</span>
          {isNewStore(lead.opened_at) && <span className="cstatus cstatus-active">Loja nova</span>}
        </div>
      </div>
      <div className="customer-panel-actions">
        {wa
          ? <a className="btn" href={wa} target="_blank" rel="noopener noreferrer">WhatsApp</a>
          : <button type="button" className="btn" disabled title="Telefone não cadastrado ou inválido">WhatsApp</button>}
        <button type="button" className="btn btn-primary" onClick={onConvert}>Virar cliente</button>
        <button type="button" className="btn" onClick={onDiscard}>Descartar</button>
      </div>
      <dl className="customer-panel-info">
        <dt>CNPJ</dt><dd>{formatCnpj(lead.cnpj)}</dd>
        <dt>Aberta em</dt><dd>{lead.opened_at ? dateBR(lead.opened_at) : "—"}</dd>
        <dt>E-mail</dt><dd>{lead.email || "—"}</dd>
        <dt>Endereço</dt><dd>{lead.address || "—"}</dd>
        {isAdmin && <><dt>Vendedor</dt><dd>{lead.seller_name || "Sem vendedor"}</dd></>}
      </dl>
      <ContactHistory target={{ lead_id: lead.id }} />
    </aside>
  );
}
```

- [ ] **Step 4: Create `frontend/src/pages/Leads.jsx`**

```jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { formatCnpj, initials } from "../format";
import { ErrorBox, Field, Modal } from "../components/ui";
import LeadPanel, { isNewStore } from "../components/LeadPanel";
import CustomerFormModal, { EMPTY_CUSTOMER } from "../components/CustomerFormModal";

const PAGE_SIZE = 50;
// Keys match the backend's DISCARD_REASONS
const DISCARD_REASONS = { closed: "Loja fechou", not_target: "Não é o nosso público", competitor: "Já compra de concorrente", other: "Outro" };

function openedText(openedAt) {
  if (!openedAt) return "—";
  const months = Math.floor((Date.now() - new Date(`${openedAt}T00:00:00`)) / (86400000 * 30.44));
  if (months < 1) return "abriu este mês";
  if (months < 24) return `abriu há ${months} ${months === 1 ? "mês" : "meses"}`;
  return `abriu há ${Math.floor(months / 12)} anos`;
}

export default function Leads() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const nav = useNavigate();
  const [filters, setFilters] = useState({ search: "", city: "", seller: "" });
  const [searchText, setSearchText] = useState("");
  const [data, setData] = useState(null); // {items, total, cities}
  const [allCities, setAllCities] = useState([]);
  const [sellers, setSellers] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [converting, setConverting] = useState(null);
  const [discarding, setDiscarding] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (isAdmin) api.get("/users").then((r) => setSellers(r.data.filter((u) => u.role === "seller")));
  }, [isAdmin]);

  async function load(offset = 0) {
    const params = { limit: PAGE_SIZE, offset, search: filters.search, city: filters.city };
    if (isAdmin && filters.seller !== "") params.seller_id = filters.seller;
    try {
      const { data: d } = await api.get("/leads", { params });
      setData((prev) => (offset && prev ? { ...d, items: [...prev.items, ...d.items] } : d));
      if (!filters.city) setAllCities(d.cities); // keep the full list while a city is picked
      setError("");
    } catch (e) { setError(errorMessage(e)); }
  }
  useEffect(() => { load(0); }, [filters]);

  const items = data?.items || [];
  const selected = items.find((l) => l.id === selectedId);
  const drop = (id) => {
    setData((d) => ({ ...d, items: d.items.filter((l) => l.id !== id), total: d.total - 1 }));
    setSelectedId(null);
  };

  async function discard(e) {
    e.preventDefault();
    try {
      await api.post(`/leads/${discarding.id}/discard`, { reason: discarding.reason });
      drop(discarding.id);
      setDiscarding(null);
      setNotice("Lead descartado. Ele não volta nas próximas importações.");
    } catch (err) { setDiscarding({ ...discarding, error: errorMessage(err) }); }
  }

  const pill = (label, value, onChange, opts) => (
    <label className={`pill-select ${value !== "" ? "on" : ""}`}>
      <span>{label}:</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>{opts}</select>
    </label>
  );

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Prospecção</h1>
          <p className="muted">Lojas de roupa da sua região que ainda não compram da Di Marcy.</p>
        </div>
        <div className="header-actions">
          <button className="btn" onClick={() => nav("/follow-ups")}>Retornos</button>
        </div>
      </header>

      <section className="filters-bar">
        <form className="filters-row" onSubmit={(e) => { e.preventDefault(); setFilters({ ...filters, search: searchText.trim() }); }}>
          <input className="filters-search" placeholder="Buscar por nome ou CNPJ" aria-label="Buscar por nome ou CNPJ"
            value={searchText} onChange={(e) => setSearchText(e.target.value)}
            onBlur={() => searchText.trim() !== filters.search && setFilters({ ...filters, search: searchText.trim() })} />
          {pill("Cidade", filters.city, (v) => setFilters({ ...filters, city: v }), <>
            <option value="">Todas</option>{allCities.map((c) => <option key={c}>{c}</option>)}
          </>)}
          {isAdmin && pill("Vendedor", filters.seller, (v) => setFilters({ ...filters, seller: v }), <>
            <option value="">Todos</option><option value="0">Sem vendedor</option>
            {sellers.map((s) => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
          </>)}
        </form>
      </section>

      <ErrorBox msg={error} />
      {notice && <p className="muted">{notice}</p>}

      {data && data.total === 0 && !filters.search && !filters.city && filters.seller === "" ? (
        <p className="customers-empty">
          {isAdmin
            ? "Nenhum lead ainda. Defina as cidades de cada vendedor em Usuários; a importação da Receita traz as lojas na madrugada seguinte."
            : "Nenhum lead na sua região ainda. Peça ao administrador para cadastrar as cidades que você atende."}
        </p>
      ) : (
        <div className={`customers-layout ${selected ? "with-panel" : ""}`}>
          <section className="customers-table">
            <div className={`customers-row leads-row head ${isAdmin ? "admin" : ""}`}>
              <span>Loja</span><span>Telefone</span>{isAdmin && <span>Vendedor</span>}<span>Abertura</span>
            </div>
            {items.map((l) => (
              <button type="button" key={l.id} onClick={() => { setSelectedId(l.id); setNotice(""); }}
                className={`customers-row leads-row ${isAdmin ? "admin" : ""} ${l.id === selectedId ? "on" : ""}`}>
                <span className="customers-cell-main">
                  <span className="customer-avatar">{initials(l.name)}</span>
                  <span><strong>{l.name}</strong><small>{l.city}/{l.state} · {formatCnpj(l.cnpj)}</small></span>
                </span>
                <span>{l.phone || "—"}</span>
                {isAdmin && <span>{l.seller_name?.split(" ")[0] || "Sem vendedor"}</span>}
                <span>
                  {isNewStore(l.opened_at)
                    ? <span className="cstatus cstatus-active">Nova · {openedText(l.opened_at)}</span>
                    : <small className="muted">{openedText(l.opened_at)}</small>}
                </span>
              </button>
            ))}
            {data && !items.length && <p className="customers-empty">Nenhum lead com esses filtros.</p>}
            <footer className="customers-footer">
              <span className="muted">{data ? `Mostrando ${items.length} de ${data.total.toLocaleString("pt-BR")}` : "Carregando…"}</span>
              {data && items.length < data.total && (
                <button type="button" className="btn" onClick={() => load(items.length)}>Carregar mais</button>
              )}
            </footer>
          </section>

          {selected && (
            <LeadPanel lead={selected} isAdmin={isAdmin} onClose={() => setSelectedId(null)}
              onDiscard={() => setDiscarding({ id: selected.id, name: selected.name, reason: "closed" })}
              onConvert={() => setConverting({
                ...EMPTY_CUSTOMER, name: selected.name, document: formatCnpj(selected.cnpj),
                phone: selected.phone || "", email: selected.email || "", city: selected.city,
                state: selected.state, address: selected.address || "", owner_id: selected.seller_id || "",
                leadId: selected.id,
              })} />
          )}
        </div>
      )}

      {converting && (
        <CustomerFormModal initial={converting} isAdmin={isAdmin} submitUrl={`/leads/${converting.leadId}/convert`}
          onClose={() => setConverting(null)}
          onSaved={() => { drop(converting.leadId); setConverting(null); setNotice("Cliente cadastrado. Ele já aparece em Clientes."); }} />
      )}

      {discarding && (
        <Modal title={`Descartar ${discarding.name}?`} onClose={() => setDiscarding(null)}>
          <form onSubmit={discard} className="form-grid">
            <Field label="Motivo" span={2}>
              <select value={discarding.reason} onChange={(e) => setDiscarding({ ...discarding, reason: e.target.value })}>
                {Object.entries(DISCARD_REASONS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
              </select>
            </Field>
            <div className="span-2"><ErrorBox msg={discarding.error} /></div>
            <div className="actions span-2"><button className="btn danger">Descartar lead</button></div>
          </form>
        </Modal>
      )}
    </div>
  );
}
```

Note: `CustomerFormModal` spreads `initial` into its form and sends the whole form as the body; the extra `leadId` key is ignored by the API (Pydantic drops unknown fields).

- [ ] **Step 5: Menu and route** — in `frontend/src/components/Layout.jsx`, add `LeadsIcon` to the icons import, add after `CUSTOMERS_LINK`:

```jsx
const LEADS_LINK = { to: "/leads", label: "Prospecção", Icon: LeadsIcon };
```

put `LEADS_LINK` right after `CUSTOMERS_LINK` in `ADMIN_LINKS`, and change the sellers' list to:

```jsx
  const links = user?.role === "admin" ? [DASHBOARD_LINK, ...ADMIN_LINKS] : [DASHBOARD_LINK, ORDERS_LINK, CUSTOMERS_LINK, LEADS_LINK, PRODUCTS_LINK];
```

In `frontend/src/App.jsx`, add `import Leads from "./pages/Leads";` with the other page imports and, after the `customers` route:

```jsx
      <Route path="leads" element={<Leads />} />
```

- [ ] **Step 6: CSS** — append to the `prospecção / contatos` block in `styles.css`:

```css
.leads-row { grid-template-columns: minmax(220px, 2fr) minmax(120px, 1fr) 190px; }
.leads-row.admin { grid-template-columns: minmax(220px, 2fr) minmax(120px, 1fr) minmax(90px, 1fr) 190px; }
.customer-panel-actions .btn-primary { flex: 1.3; }
@media (max-width: 860px) {
  .customers-row.leads-row, .customers-row.leads-row.admin { grid-template-columns: minmax(0, 1fr) auto; }
  .customer-panel-actions { flex-wrap: wrap; }
}
```

- [ ] **Step 7: Build**

Run: `npm run build`
Expected: `✓ built in …`, no errors.

- [ ] **Step 8: Manual check** (needs a few leads: run Plano 2's import, or insert two rows into `leads` with `sqlite3`/a Python one-liner, and give the seller the leads' city in Usuários via `PUT /api/users/{id}/cities`):
  1. Seller → menu "Prospecção" → the leads list; "Carregar mais" only when there are more than 50.
  2. Click a lead → panel with CNPJ formatted, "Loja nova" when opened ≤ 2 years, WhatsApp opens `wa.me` with the message text.
  3. "Registrar contato" in the panel works (Task 1 component).
  4. "Virar cliente" → customer modal pre-filled → Salvar → lead leaves the list; notice shown; customer appears in Clientes with the contacts made as lead.
  5. "Descartar" → reason → lead leaves the list.
  6. Admin → sees column Vendedor, "Vendedor: Sem vendedor" filter works.
  7. Narrow the window below 860 px: rows collapse, panel opens full screen with ×.
  8. Seller with no cities → empty-state text.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/LeadPanel.jsx frontend/src/pages/Leads.jsx frontend/src/components/CustomerFormModal.jsx \
        frontend/src/components/icons.jsx frontend/src/components/Layout.jsx frontend/src/App.jsx frontend/src/styles.css
git commit -m "Prospecção screen: ranked leads, lead panel, convert and discard"
```

---

### Task 3: Retornos screen and Painel alert

**Files:**
- Create: `frontend/src/pages/FollowUps.jsx`
- Modify: `frontend/src/components/AlertStrip.jsx`
- Modify: `frontend/src/App.jsx` (route)
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `GET /contacts/due` items `{contact_id, lead_id, customer_id, name, kind, phone, channel, notes, next_action_date, last_contact_at}`; `alerts.follow_ups_due`; `ContactModal`, `CHANNELS`.

- [ ] **Step 1: Create `frontend/src/pages/FollowUps.jsx`**

```jsx
import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { dateBR, initials, localDate, whatsappUrl } from "../format";
import { ErrorBox } from "../components/ui";
import { CHANNELS, ContactModal } from "../components/Contacts";

export default function FollowUps() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [target, setTarget] = useState(null);
  const today = localDate();

  const load = () => api.get("/contacts/due")
    .then((r) => { setRows(r.data); setError(""); })
    .catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Retornos</h1>
          <p className="muted">Contatos que você combinou de retomar até hoje. Registrar o novo contato tira da lista.</p>
        </div>
      </header>
      <ErrorBox msg={error} />
      <section className="customers-table">
        {rows && !rows.length && <p className="customers-empty">Nenhum retorno pendente. 🎉</p>}
        {rows?.map((r) => {
          const wa = whatsappUrl(r.phone);
          return (
            <div key={r.contact_id} className="followup-row">
              <span className="customers-cell-main">
                <span className="customer-avatar">{initials(r.name)}</span>
                <span>
                  <strong>{r.name}</strong>
                  <small>{r.kind === "lead" ? "Lead" : "Cliente"} · último: {CHANNELS[r.channel]}{r.notes ? ` — ${r.notes}` : ""}</small>
                </span>
              </span>
              <span className={r.next_action_date < today ? "followup-late" : "followup-today"}>
                {r.next_action_date < today ? `Atrasado desde ${dateBR(r.next_action_date)}` : "Hoje"}
              </span>
              <span className="followup-actions">
                {wa && <a className="btn" href={wa} target="_blank" rel="noopener noreferrer">WhatsApp</a>}
                <button type="button" className="btn btn-primary"
                  onClick={() => setTarget(r.lead_id ? { lead_id: r.lead_id } : { customer_id: r.customer_id })}>
                  Registrar contato
                </button>
              </span>
            </div>
          );
        })}
      </section>
      {target && <ContactModal target={target} onClose={() => setTarget(null)} onSaved={() => { setTarget(null); load(); }} />}
    </div>
  );
}
```

- [ ] **Step 2: Alert** — in `frontend/src/components/AlertStrip.jsx`, make this the FIRST entry of `items`:

```jsx
    alerts.follow_ups_due > 0 && {
      tone: "info", to: "/follow-ups", cta: "Ver retornos",
      title: plural(alerts.follow_ups_due, "retorno para hoje", "retornos para hoje"),
      text: "Contatos que você combinou de retomar até hoje.",
    },
```

- [ ] **Step 3: Route** — in `frontend/src/App.jsx`, `import FollowUps from "./pages/FollowUps";` and after the `leads` route:

```jsx
      <Route path="follow-ups" element={<FollowUps />} />
```

- [ ] **Step 4: CSS** — append to the `prospecção / contatos` block:

```css
.followup-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 14px; align-items: center; padding: 12px 18px; border-bottom: 1px solid var(--line); background: var(--surface); }
.followup-late { color: var(--danger); font-weight: 600; font-size: 13px; white-space: nowrap; }
.followup-today { color: var(--accent-strong); font-weight: 600; font-size: 13px; }
.followup-actions { display: flex; gap: 8px; }
@media (max-width: 860px) {
  .followup-row { grid-template-columns: minmax(0, 1fr); }
  .followup-actions .btn { flex: 1; text-align: center; }
}
```

- [ ] **Step 5: Build**

Run: `npm run build`
Expected: `✓ built in …`

- [ ] **Step 6: Manual check** — as a seller, register a contact on a lead with "Retornar em" = today (type today's date). Painel shows "1 retorno para hoje" → "Ver retornos" → the row with "Hoje"; "Registrar contato" without a date → the row disappears and the Painel alert goes away. Prospecção header button "Retornos" opens the same screen.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/FollowUps.jsx frontend/src/components/AlertStrip.jsx frontend/src/App.jsx frontend/src/styles.css
git commit -m "Retornos screen and Painel follow-up alert"
```

---

### Task 4: Region cities in Usuários and CNAEs in Configurações

**Files:**
- Modify: `frontend/src/pages/Users.jsx`
- Modify: `frontend/src/pages/Settings.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `GET/PUT /users/{id}/cities` (`[{city, state}]`, 409 detail text), `GET /users/{id}/cities/suggestions` (`[{city, state, taken_by}]`), `GET /users/cities/options`; settings `lead_cnaes`, `last_lead_import_month`, `last_lead_import_at`.

- [ ] **Step 1: Region editor in `Users.jsx`** — add this component above `export default function Users()`:

```jsx
// "Jaraguá do Sul - SC" / "Jaraguá do Sul/SC" -> {city, state}
const parseCity = (text) => {
  const m = text.trim().match(/^(.+?)\s*[-/]\s*([A-Za-z]{2})$/);
  return m ? { city: m[1].trim(), state: m[2].toUpperCase() } : null;
};
const cityKey = (c) => `${normalize(c.city)}|${c.state}`;

function RegionCities({ userId, cities, onChange }) {
  const [options, setOptions] = useState([]);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => { api.get("/users/cities/options").then((r) => setOptions(r.data)); }, []);

  const add = (list) => {
    const seen = new Set(cities.map(cityKey));
    onChange([...cities, ...list.filter((c) => !seen.has(cityKey(c)) && seen.add(cityKey(c)))]);
  };

  function addTyped() {
    const c = parseCity(text);
    if (!c) { setNote("Escreva no formato Cidade - UF (ex.: Jaraguá do Sul - SC)."); return; }
    add([c]);
    setText("");
    setNote("");
  }

  async function suggest() {
    const { data } = await api.get(`/users/${userId}/cities/suggestions`);
    add(data.filter((s) => !s.taken_by).map(({ city, state }) => ({ city, state })));
    const taken = data.filter((s) => s.taken_by);
    setNote(taken.length ? `Não incluídas (já são de outro vendedor): ${taken.map((s) => `${s.city} — ${s.taken_by}`).join("; ")}.` : "");
  }

  return (
    <div className="span-2 region">
      <span className="region-label">Cidades da região (Prospecção)</span>
      <div className="region-chips">
        {cities.map((c) => (
          <button type="button" key={cityKey(c)} className="filter-chip" title="Remover"
            onClick={() => onChange(cities.filter((x) => cityKey(x) !== cityKey(c)))}>{c.city}/{c.state} ×</button>
        ))}
        {!cities.length && <span className="muted">Nenhuma cidade ainda.</span>}
      </div>
      <div className="region-add">
        <input list="city-options" placeholder="Cidade - UF" value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTyped(); } }} />
        <datalist id="city-options">
          {options.map((o) => <option key={`${o.city}|${o.state}`} value={`${o.city} - ${o.state}`} />)}
        </datalist>
        <button type="button" className="btn" onClick={addTyped}>Adicionar</button>
        {userId && <button type="button" className="btn" onClick={suggest}>Sugerir pelas cidades dos clientes</button>}
      </div>
      {note && <p className="muted">{note}</p>}
    </div>
  );
}
```

Add `normalize` to the imports: `import { normalize } from "../format";`.

- [ ] **Step 2: Wire it into the user form** — in `Users()`:

Add state: `const [cities, setCities] = useState(null); // null = not loaded / not a seller`.

Replace the two places that open the form so they also load the cities:

```jsx
  function openForm(u) {
    setError("");
    setForm(u);
    setCities(u.id ? null : []);
    if (u.id && u.role === "seller") api.get(`/users/${u.id}/cities`).then((r) => setCities(r.data));
  }
```

- header button: `onClick={() => openForm({ name: "", email: "", password: "", role: "seller", active: true, annual_goal: "", price_table: "wholesale" })}`
- table row: `onClick={() => openForm({ ...u, password: "" })}`

Replace `save` with:

```jsx
  async function save(e) {
    e.preventDefault();
    setError("");
    const goal = form.annual_goal;
    const body = { ...form, annual_goal: goal === "" || goal == null ? null : Number(goal) };
    try {
      const { data: saved } = form.id ? await api.put(`/users/${form.id}`, body) : await api.post("/users", body);
      setForm({ ...form, id: saved.id }); // a failing region save below must not create the user twice
      if (form.role === "seller" && cities) await api.put(`/users/${saved.id}/cities`, cities);
      setForm(null);
      load();
    } catch (err) { setError(errorMessage(err)); }
  }
```

In the form, after the "Tabela de preço" field, add:

```jsx
            {form.role === "seller" && (cities
              ? <RegionCities userId={form.id} cities={cities} onChange={setCities} />
              : <p className="span-2 muted">Carregando cidades da região…</p>)}
```

and change the `Modal` to `wide` (`<Modal … wide>`) so the region list fits.

- [ ] **Step 3: Configurações** — in `frontend/src/pages/Settings.jsx`, add `lead_cnaes: form.lead_cnaes,` to the `api.put("/settings", {…})` body, and before the `ErrorBox` div of the form:

```jsx
            <Field label="CNAEs da prospecção" span={2}>
              <input placeholder="4781-4/00" value={form.lead_cnaes || ""}
                onChange={(e) => setForm({ ...form, lead_cnaes: e.target.value })} />
            </Field>
            <p className="muted span-2" style={{ marginTop: -8 }}>
              Atividade principal das lojas trazidas da Receita Federal (separe por vírgula). Padrão: 4781-4/00,
              comércio varejista de artigos do vestuário e acessórios.{" "}
              {form.last_lead_import_at
                ? `Última importação: dados de ${new Date(`${form.last_lead_import_month}-01T00:00:00`).toLocaleDateString("pt-BR", { month: "long", year: "numeric" })}, em ${new Date(`${form.last_lead_import_at}Z`).toLocaleDateString("pt-BR")}.`
                : "Ainda não houve importação."}
            </p>
```

Note: `last_lead_import_at` is written by the importer with `datetime.now()` (server local time, not UTC). On the VM the clock is UTC, so `"Z"` is right there; the date may be off by one only between 21:00 and 24:00 locally, which the 03:30 timer never hits.

- [ ] **Step 4: CSS** — append to the `prospecção / contatos` block:

```css
.region { display: flex; flex-direction: column; gap: 8px; }
.region-label { font-size: 13px; font-weight: 600; }
.region-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.region-add { display: flex; gap: 8px; flex-wrap: wrap; }
.region-add input { flex: 1 1 220px; }
```

- [ ] **Step 5: Build**

Run: `npm run build`
Expected: `✓ built in …`

- [ ] **Step 6: Manual check**
  1. Usuários → open a seller → "Cidades da região": type "Jara", pick "Jaraguá do Sul - SC" from the suggestions, Adicionar → chip appears; × removes it.
  2. "Sugerir pelas cidades dos clientes" adds that seller's customer cities; a city owned by another seller is listed in the note and not added.
  3. Salvar → reopen → cities persisted.
  4. Give a second seller a city of the first → Salvar shows "X já é da região de Fulano." in the modal; fix and Salvar again → no duplicate user in the list.
  5. New seller: fill data + one city → Salvar → created with the city.
  6. Admin user form: no region section.
  7. Configurações: CNAE field shows `4781400`; type `4781-4/00, 4642-7/01` → Salvar → shows `4781400,4642701`; type `123` → error message; "Ainda não houve importação." until the first import.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Users.jsx frontend/src/pages/Settings.jsx frontend/src/styles.css
git commit -m "Usuários: seller region cities; Configurações: prospecting CNAEs"
```
