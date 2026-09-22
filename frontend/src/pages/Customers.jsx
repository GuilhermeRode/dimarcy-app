import { useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { dateBR } from "../format";
import { Field, ErrorBox, Modal, EmptyState } from "../components/ui";

const EMPTY = { name: "", document: "", phone: "", email: "", city: "", state: "", address: "", notes: "", owner_id: "" };
const OPEN_STATUSES = ["quote", "confirmed", "in_production", "shipped"];

const AVATAR_PALETTE = [
  { bg: "#dfe9fc", fg: "#1d54c9" },
  { bg: "#eef0fd", fg: "#4338ca" },
  { bg: "#fbf0e0", fg: "#9a5b12" },
  { bg: "#dff2f5", fg: "#0d6d80" },
  { bg: "#e0f1ea", fg: "#1c7a52" },
  { bg: "#eceff5", fg: "#4b5875" },
];

function initials(name) {
  const words = name.trim().split(/\s+/);
  return words.length > 1 ? (words[0][0] + words[1][0]).toUpperCase() : words[0].slice(0, 2).toUpperCase();
}

export default function Customers() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [list, setList] = useState([]);
  const [orders, setOrders] = useState([]);
  const [sellers, setSellers] = useState([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  const load = () => api.get("/customers", { params: { search } })
    .then((r) => { setList(r.data); setError(""); })
    .catch((err) => setError(errorMessage(err)));
  useEffect(() => { if (isAdmin) api.get("/users").then((r) => setSellers(r.data)); }, [isAdmin]);
  useEffect(() => { api.get("/orders").then((r) => setOrders(r.data)); }, []);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [search]);

  const stats = useMemo(() => {
    const m = new Map();
    for (const o of orders) {
      const s = m.get(o.customer_id) || { count: 0, open: 0, last: null };
      s.count += 1;
      if (OPEN_STATUSES.includes(o.status)) s.open += 1;
      if (!s.last || o.date > s.last) s.last = o.date;
      m.set(o.customer_id, s);
    }
    return m;
  }, [orders]);

  const { withOrders, withoutOrders, openTotal } = useMemo(() => {
    const withO = [], withoutO = [];
    let openTotal = 0;
    for (const c of list) {
      const s = stats.get(c.id);
      if (s?.count) { withO.push(c); openTotal += s.open; } else withoutO.push(c);
    }
    withO.sort((a, b) => (stats.get(b.id).last || "").localeCompare(stats.get(a.id).last || ""));
    return { withOrders: withO, withoutOrders: withoutO, openTotal };
  }, [list, stats]);

  async function save(e) {
    e.preventDefault();
    setError("");
    const body = { ...form, state: form.state ? form.state.toUpperCase() : null, owner_id: form.owner_id ? Number(form.owner_id) : null };
    try {
      form.id ? await api.put(`/customers/${form.id}`, body) : await api.post("/customers", body);
      setForm(null);
      load();
    } catch (err) { setError(errorMessage(err)); }
  }

  async function remove() {
    if (!confirm(`Excluir ${form.name}?`)) return;
    try { await api.delete(`/customers/${form.id}`); setForm(null); load(); }
    catch (err) { setError(errorMessage(err)); }
  }

  const f = (k) => ({ value: form[k] || "", onChange: (e) => setForm({ ...form, [k]: e.target.value }) });

  function openEdit(c) { setError(""); setForm({ ...c, owner_id: c.owner_id || "" }); }

  function Row({ c }) {
    const s = stats.get(c.id);
    const pal = AVATAR_PALETTE[c.id % AVATAR_PALETTE.length];
    return (
      <div className="customer-row" onClick={() => openEdit(c)}>
        <span className="customer-avatar" style={{ background: pal.bg, color: pal.fg }}>{initials(c.name)}</span>
        <span className="customer-row-main">
          <span className="customer-row-name">{c.name}</span>
          <span className="cell-sub">{c.city}{c.state ? `/${c.state}` : ""}</span>
        </span>
        <span className="customer-row-status">
          {!s ? (
            <span className="muted">Nunca comprou</span>
          ) : s.open ? (
            <span className="customer-status-open">{s.open} em aberto · último {dateBR(s.last)}</span>
          ) : (
            <span className="muted">Última compra {dateBR(s.last)}</span>
          )}
        </span>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Clientes</h1>
        <div className="actions">
          <input className="header-search" placeholder="Buscar cliente" value={search} onChange={(e) => setSearch(e.target.value)} />
          <button className="btn btn-primary" onClick={() => { setError(""); setForm(EMPTY); }}>Cadastrar cliente</button>
        </div>
      </header>

      <ErrorBox msg={error} />
      {!list.length ? <EmptyState text="Nenhum cliente encontrado." /> : (
        <>
          {withOrders.length > 0 && (
            <section className="customer-group">
              <div className="customer-group-header">
                <span><span className="customer-group-dot dot-accent" />COM PEDIDOS <span className="tag">{withOrders.length}</span></span>
                <span className="muted">{openTotal} em aberto</span>
              </div>
              <div className="customer-list">
                {withOrders.map((c) => <Row key={c.id} c={c} />)}
              </div>
            </section>
          )}

          {withoutOrders.length > 0 && (
            <section className="customer-group">
              <div className="customer-group-header">
                <span><span className="customer-group-dot dot-muted" />SEM PEDIDOS <span className="tag">{withoutOrders.length}</span></span>
                <span className="muted">oportunidades de primeiro pedido</span>
              </div>
              <div className="customer-list">
                {withoutOrders.map((c) => <Row key={c.id} c={c} />)}
              </div>
            </section>
          )}
        </>
      )}

      {form && (
        <Modal title={form.id ? "Editar cliente" : "Cadastrar cliente"} onClose={() => setForm(null)} wide>
          <form onSubmit={save} className="form-grid">
            <Field label="Nome / razão social" span={2}><input required {...f("name")} /></Field>
            <Field label="CPF/CNPJ" span={2}><input required {...f("document")} /></Field>
            {isAdmin && (
              <Field label="Vendedor responsável" span={2}>
                <select required {...f("owner_id")}>
                  <option value="">Selecione o vendedor</option>
                  {sellers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </Field>
            )}
            <Field label="Telefone"><input {...f("phone")} /></Field>
            <Field label="E-mail"><input type="email" {...f("email")} /></Field>
            <Field label="Cidade / UF" span={2}>
              <div className="city-row">
                <input placeholder="Cidade" {...f("city")} />
                <input placeholder="UF" maxLength={2} className="uf-input" {...f("state")} />
              </div>
            </Field>
            <Field label="Endereço" span={2}><input {...f("address")} /></Field>
            <Field label="Observações" span={2}><textarea rows={3} {...f("notes")} /></Field>
            <div className="span-2"><ErrorBox msg={error} /></div>
            <div className="actions span-2">
              {form.id && <button type="button" className="btn danger" onClick={remove}>Excluir</button>}
              <button className="btn btn-primary">Salvar cliente</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
