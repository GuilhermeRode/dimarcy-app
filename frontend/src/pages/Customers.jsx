import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { CUSTOMER_STATUS, compactMoney, initials, normalize } from "../format";
import { ErrorBox } from "../components/ui";
import CustomerPanel from "../components/CustomerPanel";
import CustomerFormModal, { EMPTY_CUSTOMER } from "../components/CustomerFormModal";

const PAGE_SIZE = 20;
const SORTS = {
  total: { label: "Total comprado", fn: (a, b) => b.total - a.total },
  orders: { label: "Nº de pedidos", fn: (a, b) => b.orders - a.orders },
  recent: { label: "Compra mais recente", fn: (a, b) => (b.last_order_date || "").localeCompare(a.last_order_date || "") },
  name: { label: "Nome A–Z", fn: (a, b) => a.name.localeCompare(b.name, "pt-BR") },
};
const uniqSorted = (list) => [...new Set(list.filter(Boolean))].sort((a, b) => a.localeCompare(b, "pt-BR"));

export default function Customers() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState(null);
  const [params, setParams] = useSearchParams();

  const load = () => api.get("/customers/overview")
    .then((r) => { setRows(r.data); setError(""); })
    .catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);

  const options = useMemo(() => {
    const sellers = new Map(rows.filter((r) => r.owner_id).map((r) => [String(r.owner_id), r.owner_name]));
    return {
      states: uniqSorted(rows.map((r) => r.state)),
      sellers: [...sellers.entries()].sort((a, b) => a[1].localeCompare(b[1], "pt-BR")),
    };
  }, [rows]);

  // URL values are untrusted: anything outside the known lists is ignored.
  const f = useMemo(() => {
    const get = (k) => params.get(k) || "";
    const seller = get("seller");
    return {
      q: get("q"),
      status: Object.hasOwn(CUSTOMER_STATUS, get("status")) ? get("status") : "",
      state: get("state"),
      city: get("city"),
      seller: isAdmin && (seller === "none" || options.sellers.some(([id]) => id === seller)) ? seller : "",
      sort: Object.hasOwn(SORTS, get("sort")) ? get("sort") : "total",
      page: Math.max(1, parseInt(get("page"), 10) || 1),
    };
  }, [params, isAdmin, options]);

  function setFilter(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (key === "state") next.delete("city");
    if (key !== "page") next.delete("page");
    setParams(next, { replace: true });
  }

  const cities = useMemo(() => uniqSorted(rows.filter((r) => !f.state || r.state === f.state).map((r) => r.city)), [rows, f.state]);

  const visible = useMemo(() => {
    const text = normalize(f.q.trim());
    const digits = f.q.replace(/\D/g, "");
    return rows.filter((r) =>
      (!f.status || r.status === f.status)
      && (!f.state || r.state === f.state)
      && (!f.city || r.city === f.city)
      && (!f.seller || (f.seller === "none" ? !r.owner_id : String(r.owner_id) === f.seller))
      && (!text || normalize(`${r.name} ${r.city || ""}`).includes(text)
        || (digits.length >= 3 && (r.document || "").replace(/\D/g, "").includes(digits)))
    ).sort(SORTS[f.sort].fn);
  }, [rows, f]);

  const pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const page = Math.min(f.page, pages);
  const pageRows = visible.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const selected = rows.find((r) => r.id === selectedId);

  const chips = [
    f.q && ["q", `Busca: ${f.q}`],
    f.status && ["status", `Status: ${CUSTOMER_STATUS[f.status].label}`],
    f.state && ["state", `Estado: ${f.state}`],
    f.city && ["city", `Cidade: ${f.city}`],
    f.seller && ["seller", `Vendedor: ${f.seller === "none" ? "Sem vendedor" : options.sellers.find(([id]) => id === f.seller)[1]}`],
  ].filter(Boolean);

  async function openEdit(id) {
    try { setForm((await api.get(`/customers/${id}`)).data); }
    catch (e) { setError(errorMessage(e)); }
  }

  // A pill-shaped menu: "Status: Todos ▾". Highlighted while it filters something.
  const select = (label, key, value, opts, extraClass = "") => (
    <label className={`pill-select ${value ? "on" : ""} ${extraClass}`}>
      <span>{label}:</span>
      <select value={value} onChange={(e) => setFilter(key, e.target.value)}>{opts}</select>
    </label>
  );

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Clientes</h1>
          <p className="muted">Acompanhe a carteira e encontre oportunidades de venda.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setForm(EMPTY_CUSTOMER)}>+ Cadastrar cliente</button>
      </header>

      <section className="filters-bar">
        <div className="filters-row">
          <input className="filters-search" placeholder="Nome, cidade ou CPF/CNPJ"
            value={f.q} onChange={(e) => setFilter("q", e.target.value)} />
          {select("Status", "status", f.status, <>
            <option value="">Todos</option>
            {Object.entries(CUSTOMER_STATUS).map(([k, s]) => <option key={k} value={k}>{s.label}</option>)}
          </>)}
          {select("Estado", "state", f.state, <>
            <option value="">Todos</option>{options.states.map((s) => <option key={s}>{s}</option>)}
          </>)}
          {select("Cidade", "city", f.city, <>
            <option value="">Todas</option>{cities.map((c) => <option key={c}>{c}</option>)}
          </>)}
          {isAdmin && select("Vendedor", "seller", f.seller, <>
            <option value="">Todos</option><option value="none">Sem vendedor</option>
            {options.sellers.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </>)}
          {select("Ordenar", "sort", f.sort === "total" ? "" : f.sort,
            Object.entries(SORTS).map(([k, s]) => <option key={k} value={k === "total" ? "" : k}>{s.label}</option>),
            "pill-sort")}
        </div>
        {chips.length > 0 && (
          <div className="filters-chips">
            <span className="muted">Filtros ativos</span>
            {chips.map(([key, label]) => (
              <button type="button" key={key} className="filter-chip" onClick={() => setFilter(key, "")}>{label} ×</button>
            ))}
            <button type="button" className="link-btn" onClick={() => setParams({}, { replace: true })}>Limpar tudo</button>
          </div>
        )}
      </section>

      <ErrorBox msg={error} />

      <div className={`customers-layout ${selected ? "with-panel" : ""}`}>
        <section className="customers-table">
          <div className={`customers-row head ${isAdmin ? "admin" : ""}`}>
            <span>Cliente</span>{isAdmin && <span>Vendedor</span>}<span className="num">Total</span><span className="num">Pedidos</span><span>Status</span>
          </div>
          {pageRows.map((r) => (
            <button type="button" key={r.id} onClick={() => setSelectedId(r.id)}
              className={`customers-row ${isAdmin ? "admin" : ""} ${r.id === selectedId ? "on" : ""}`}>
              <span className="customers-cell-main">
                <span className="customer-avatar">{initials(r.name)}</span>
                <span><strong>{r.name}</strong><small>{r.city ? `${r.city}${r.state ? `/${r.state}` : ""}` : "—"}</small></span>
              </span>
              {isAdmin && <span>{r.owner_name?.split(" ")[0] || "—"}</span>}
              <span className="num">{r.total ? compactMoney(r.total) : "—"}</span>
              <span className="num">{r.orders}</span>
              <span><span className={`cstatus cstatus-${CUSTOMER_STATUS[r.status].tone}`}>{CUSTOMER_STATUS[r.status].label}</span></span>
            </button>
          ))}
          {!pageRows.length && <p className="customers-empty">Nenhum cliente com esses filtros.</p>}
          <footer className="customers-footer">
            <span className="muted">
              Mostrando {visible.length ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(visible.length, page * PAGE_SIZE)}` : "0"} de {visible.length}
            </span>
            <div className="pager">
              <button type="button" className="btn" disabled={page === 1} onClick={() => setFilter("page", String(page - 1))}>‹ Anterior</button>
              <span>{page} / {pages}</span>
              <button type="button" className="btn" disabled={page === pages} onClick={() => setFilter("page", String(page + 1))}>Próxima ›</button>
            </div>
          </footer>
        </section>

        {selected && (
          <CustomerPanel customer={selected} isAdmin={isAdmin}
            onClose={() => setSelectedId(null)} onEdit={() => openEdit(selected.id)} />
        )}
      </div>

      {form && (
        <CustomerFormModal initial={form} isAdmin={isAdmin} onClose={() => setForm(null)}
          onSaved={() => { setForm(null); setSelectedId(null); load(); }} />
      )}
    </div>
  );
}
