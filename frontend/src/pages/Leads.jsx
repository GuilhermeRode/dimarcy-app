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
    if (isAdmin) api.get("/users").then((r) => setSellers(r.data.filter((u) => u.role === "seller" && u.active)));
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
  useEffect(() => { setSelectedId(null); load(0); }, [filters]);

  const items = data?.items || [];
  const selected = items.find((l) => l.id === selectedId);
  const drop = (id) => {
    setData((d) => ({ ...d, items: d.items.filter((l) => l.id !== id), total: d.total - 1 }));
    setSelectedId(null);
  };

  function alreadyHandled(id) {
    drop(id);
    setDiscarding(null);
    setConverting(null);
    setNotice("Este lead já tinha sido tratado por outra pessoa.");
  }

  async function discard(e) {
    e.preventDefault();
    if (discarding.busy) return;
    setDiscarding({ ...discarding, busy: true, error: "" });
    try {
      await api.post(`/leads/${discarding.id}/discard`, { reason: discarding.reason });
      drop(discarding.id);
      setDiscarding(null);
      setNotice("Lead descartado. Ele não volta nas próximas importações.");
    } catch (err) {
      if (err.response?.status === 409) alreadyHandled(discarding.id);
      else setDiscarding({ ...discarding, busy: false, error: errorMessage(err) });
    }
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
            : "Nenhum lead disponível na sua região agora. Se você ainda não tem cidades cadastradas, peça ao administrador."}
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
          onClose={() => setConverting(null)} onConflict={() => alreadyHandled(converting.leadId)}
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
            <div className="actions span-2"><button className="btn danger" disabled={discarding.busy}>Descartar lead</button></div>
          </form>
        </Modal>
      )}
    </div>
  );
}
