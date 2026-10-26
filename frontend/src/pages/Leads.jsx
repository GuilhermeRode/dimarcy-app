import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { LEAD_SIZES, dateBR, formatCnpj, initials } from "../format";
import { CityFilter, ErrorBox, Field, Modal, PillSelect } from "../components/ui";
import LeadPanel, { isNewStore } from "../components/LeadPanel";
import CustomerFormModal, { EMPTY_CUSTOMER } from "../components/CustomerFormModal";

const PAGE_SIZE = 50;
// Keys match the backend's DISCARD_REASONS
const DISCARD_REASONS = { closed: "Loja fechou", not_target: "Não é o nosso público", competitor: "Já compra de concorrente",
  not_recommended: "Não recomendada", no_answer: "Não respondeu (3 tentativas)", other: "Outro" };
const AUTO_REASONS = ["not_recommended", "no_answer"];  // set by the admin's queue / the "Não respondeu" button

// Where the seller left off: the latest contact's follow-up date, or how long ago it was
function contactText(lead) {
  if (lead.next_action_date) return `Retorno ${dateBR(lead.next_action_date)}`;
  if (!lead.last_contact_at) return "";
  const days = Math.floor((Date.now() - new Date(`${lead.last_contact_at}Z`)) / 86400000);
  return days < 1 ? "Contatado hoje" : `Contatado há ${days} ${days === 1 ? "dia" : "dias"}`;
}

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
  const [filters, setFilters] = useState({ search: "", city: "", seller: "", tab: "pending" });
  const [searchText, setSearchText] = useState("");
  const [cityText, setCityText] = useState("");
  // Searching is explicit: Enter, the magnifier or "Pesquisar" apply what was typed; picking a city applies it.
  const search = (city = cityText) => setFilters((f) => ({ ...f, search: searchText.trim(), city: city.trim() }));
  const [data, setData] = useState(null); // {items, total, cities}
  const [allCities, setAllCities] = useState([]);
  const [sellers, setSellers] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [converting, setConverting] = useState(null);
  const [discarding, setDiscarding] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [checked, setChecked] = useState(new Set());
  const [busy, setBusy] = useState(false);
  const [releaseTo, setReleaseTo] = useState("");  // "" = each lead's city seller
  const [importCfg, setImportCfg] = useState(null);
  const pending = isAdmin && filters.tab === "pending";
  const week = pending && data?.week;  // only when a seller is picked
  const suggested = week ? Math.max(week.quota - week.released, 0) : 0;

  const [statusError, setStatusError] = useState(false);
  const loadStatus = () => api.get("/settings")
    .then((r) => { setImportCfg(r.data); setStatusError(false); return r.data; })
    .catch(() => { setStatusError(true); return null; });
  useEffect(() => { if (isAdmin) loadStatus(); }, [isAdmin]);

  // While an import runs, poll every 15 s; when it finishes, reload the list so new pending leads show up.
  const importing = !!importCfg?.lead_import_started_at;
  useEffect(() => {
    if (!importing) return;
    const timer = setInterval(async () => {
      const cfg = await loadStatus();
      if (cfg && !cfg.lead_import_started_at) load(0);
    }, 15000);
    return () => clearInterval(timer);
  }, [importing]);

  async function importNow() {
    try {
      await api.post("/settings/lead-import");
      await loadStatus();
      setNotice("Importando…");
    } catch (e) { setNotice(errorMessage(e)); }
  }

  // Server timestamps are naive UTC, so append "Z" before parsing to display them in local time.
  const utc = (v) => new Date(`${v}Z`);
  const hhmm = (v) => utc(v).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  function importStatus() {
    if (importCfg.lead_import_started_at) return `Importando desde ${hhmm(importCfg.lead_import_started_at)}…`;
    const [y, m] = (importCfg.last_lead_import_month || "").split("-");
    if (!y) return "Ainda não houve importação.";
    return `Última importação: dados de ${m}/${y} (${utc(importCfg.last_lead_import_at).toLocaleDateString("pt-BR")})`;
  }

  const [catalogUrl, setCatalogUrl] = useState(null);
  useEffect(() => { api.get("/settings").then((r) => setCatalogUrl(r.data.catalog_url)).catch(() => {}); }, []);

  useEffect(() => {
    if (isAdmin) api.get("/users").then((r) => setSellers(r.data.filter((u) => u.role === "seller" && u.active)));
  }, [isAdmin]);

  async function load(offset = 0) {
    const params = { limit: PAGE_SIZE, offset, search: filters.search, city: filters.city };
    if (isAdmin) params.status = filters.tab;
    if (isAdmin && filters.seller !== "") params.seller_id = filters.seller;
    try {
      const { data: d } = await api.get("/leads", { params });
      setData((prev) => (offset && prev ? { ...d, items: [...prev.items, ...d.items] } : d));
      if (!filters.city) setAllCities(d.cities); // keep the full list while a city is picked
      setError("");
    } catch (e) { setError(errorMessage(e)); }
  }
  useEffect(() => { setSelectedId(null); setChecked(new Set()); load(0); }, [filters]);

  const items = data?.items || [];
  const selected = items.find((l) => l.id === selectedId);
  const drop = (id) => {
    setData((d) => ({ ...d, items: d.items.filter((l) => l.id !== id), total: d.total - 1 }));
    setSelectedId(null);
  };

  // sellerId: who gets the leads whose city has no seller yet (their city joins that seller's region)
  async function release(ids, sellerId = "") {
    if (busy || !ids.length) return;
    setBusy(true);
    try {
      const { data: r } = await api.post("/leads/release", { ids, seller_id: sellerId ? Number(sellerId) : null });
      afterRelease(ids, r);
    } catch (e) { setError(errorMessage(e)); }
    setBusy(false);
  }
  function afterRelease(ids, r) {
    const gone = new Set(ids);
    const others = Object.entries(r.skipped_other_seller || {});
    setChecked(new Set());
    setSelectedId(null);
    // skipped rows stay pending on the server, so reload instead of dropping them locally
    if (r.skipped_no_seller > 0 || others.length) load(0);
    else setData((d) => ({ ...d, items: d.items.filter((l) => !gone.has(l.id)), total: d.total - ids.length }));
    setNotice([
      `${r.released} ${r.released === 1 ? "loja liberada" : "lojas liberadas"}.`,
      r.cities_added?.length && `Cidade${r.cities_added.length > 1 ? "s" : ""} adicionada${r.cities_added.length > 1 ? "s" : ""} ao vendedor: ${r.cities_added.join(", ")}.`,
      others.length && `Não liberadas por serem de outro vendedor: ${others.map(([n, k]) => `${k} de ${n}`).join(", ")}.`,
      r.skipped_no_seller > 0 && `${r.skipped_no_seller} sem vendedor — escolha para quem liberar ou cadastre a cidade em Usuários.`,
    ].filter(Boolean).join(" "));
  }
  async function selectSuggested() {
    // only PAGE_SIZE rows are loaded: fetch the rest of the suggestion first (in pages of up to 200)
    let rows = items;
    try {
      while (rows.length < Math.min(suggested, data.total)) {
        const { data: d } = await api.get("/leads", { params: {
          status: "pending", seller_id: filters.seller, search: filters.search, city: filters.city,
          offset: rows.length, limit: Math.min(suggested - rows.length, 200) } });
        if (!d.items.length) break;
        rows = [...rows, ...d.items];
      }
    } catch (e) { setError(errorMessage(e)); return; }
    setData((d) => ({ ...d, items: rows }));
    setChecked(new Set(rows.slice(0, suggested).map((l) => l.id)));
  }
  async function refreshContact(id) {
    try {
      const { data: [ct] } = await api.get(`/contacts?lead_id=${id}`);  // newest first
      setData((d) => ({ ...d, items: d.items.map((l) => (l.id === id
        ? { ...l, last_contact_at: ct?.created_at ?? null, next_action_date: ct?.next_action_date ?? null } : l)) }));
    } catch { /* the list is only a hint; the panel already shows the contact */ }
  }
  const toggle = (id) => setChecked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

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
      if (discarding.ids) {  // "Não recomendar" on the checked rows
        const { data: r } = await api.post("/leads/discard", { ids: discarding.ids, reason: discarding.reason });
        const gone = new Set(discarding.ids);
        setData((d) => ({ ...d, items: d.items.filter((l) => !gone.has(l.id)), total: d.total - gone.size }));
        setChecked(new Set());
        setSelectedId(null);
        setDiscarding(null);
        setNotice(`${r.discarded} ${r.discarded === 1 ? "loja tirada" : "lojas tiradas"} da fila. Elas não voltam nas próximas importações.`);
        return;
      }
      await api.post(`/leads/${discarding.id}/discard`, { reason: discarding.reason });
      drop(discarding.id);
      setDiscarding(null);
      setNotice("Lead descartado. Ele não volta nas próximas importações.");
    } catch (err) {
      if (err.response?.status === 409) alreadyHandled(discarding.id);
      else setDiscarding({ ...discarding, busy: false, error: errorMessage(err) });
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Prospecção</h1>
          <p className="muted">Lojas de roupa da sua região que ainda não compram da Di Marcy.</p>
          {isAdmin && statusError && !importCfg && <p className="muted import-status">Não foi possível carregar o status da importação.</p>}
          {isAdmin && importCfg && (
            <p className="muted import-status">
              {importStatus()}
              {importCfg.lead_import_error && !importCfg.lead_import_started_at && (
                <span style={{ color: "var(--danger)" }}> · Última tentativa falhou: {importCfg.lead_import_error}</span>
              )}
              {statusError && <span> · Não foi possível carregar o status da importação.</span>}
            </p>
          )}
        </div>
        <div className="header-actions">
          {isAdmin && <button className="btn" onClick={importNow} disabled={!!importCfg?.lead_import_started_at}>Atualizar agora</button>}
          <button className="btn" onClick={() => nav("/follow-ups")}>Retornos</button>
        </div>
      </header>

      {isAdmin && (
        <nav className="tabs-underline" aria-label="Status dos leads">
          {[["pending", "Aguardando liberação"], ["new", "Liberados"]].map(([k, label]) => (
            <button key={k} type="button" className={filters.tab === k ? "active" : ""}
              onClick={() => { setNotice(""); setFilters({ ...filters, tab: k }); }}>{label}</button>
          ))}
        </nav>
      )}

      <section className="filters-bar">
        <form className="filters-row" onSubmit={(e) => { e.preventDefault(); search(); }}>
          <div className="search-box">
            <button type="submit" className="search-box-icon" aria-label="Pesquisar" title="Pesquisar" />
            <input className="filters-search" placeholder="Buscar por nome, cidade ou CNPJ" aria-label="Buscar por nome, cidade ou CNPJ"
              value={searchText} onChange={(e) => setSearchText(e.target.value)} />
          </div>
          <CityFilter value={cityText} cities={allCities} onChange={setCityText} onPick={search} />
          {isAdmin && (
            <PillSelect label="Vendedor" value={filters.seller} onChange={(v) => setFilters({ ...filters, seller: v })}
              options={[["", "Todos"], ["0", "Sem vendedor"], ...sellers.map((s) => [String(s.id), s.name])]} />
          )}
          <button type="submit" className="btn btn-primary btn-search">Pesquisar</button>
        </form>
      </section>

      <ErrorBox msg={error} />
      {notice && <p className="muted">{notice}</p>}

      {data && data.total === 0 && !filters.search && !filters.city && filters.seller === "" ? (
        <p className="customers-empty">
          {pending
            ? "Nenhuma loja aguardando liberação. Clique em Atualizar agora ou aguarde a importação da madrugada."
            : isAdmin
            ? "Nenhum lead ainda. Defina as cidades de cada vendedor em Usuários; a importação da Receita traz as lojas na madrugada seguinte."
            : "Nenhum lead disponível na sua região agora. Se você ainda não tem cidades cadastradas, peça ao administrador."}
        </p>
      ) : (
        <div className={`customers-layout ${selected ? "with-panel" : ""}`}>
          <section className="customers-table">
            <div className={`customers-row leads-row head ${isAdmin ? "admin" : ""} ${pending ? "picking" : ""}`}>
              <span>Loja</span><span>Telefone</span>{isAdmin && <span>Vendedor</span>}<span>Abertura</span>
            </div>
            {pending && (
              <div className="leads-toolbar">
                {week ? (
                  <>
                    <span className="muted">
                      Esta semana: {week.released} de {week.quota} liberados para {sellers.find((s) => String(s.id) === filters.seller)?.name.split(" ")[0]}
                    </span>
                    <button type="button" className="btn" disabled={!suggested}
                      onClick={selectSuggested}>
                      Selecionar os {suggested} sugeridos
                    </button>
                  </>
                ) : (
                  <button type="button" className="btn" onClick={() => setChecked(new Set(items.slice(0, 20).map((l) => l.id)))}>Selecionar os 20 primeiros</button>
                )}
                <button type="button" className="btn" onClick={() => setChecked(new Set())}>Limpar seleção</button>
                <button type="button" className="btn danger" disabled={!checked.size || busy}
                  onClick={() => setDiscarding({ ids: [...checked], name: `${checked.size} ${checked.size === 1 ? "loja" : "lojas"}`, reason: "not_recommended" })}>
                  Não recomendar ({checked.size})
                </button>
                <PillSelect label="Liberar para" value={releaseTo} onChange={setReleaseTo} className="pill-release"
                  options={[["", "Vendedor da cidade"], ...sellers.map((s) => [String(s.id), s.name])]} />
                <button type="button" className="btn btn-primary" disabled={!checked.size || busy}
                  title={releaseTo ? "Lojas de cidades sem vendedor vão para este vendedor, e a cidade entra na região dele" : undefined}
                  onClick={() => release([...checked], releaseTo)}>Liberar ({checked.size})</button>
              </div>
            )}
            {items.map((l) => (
              <div key={l.id} className={pending ? `lead-pick ${l.id === selectedId ? "on" : ""}` : undefined}
                style={pending ? undefined : { display: "contents" }}>
              {pending && <input type="checkbox" checked={checked.has(l.id)} onChange={() => toggle(l.id)} aria-label={`Selecionar ${l.name}`} />}
              <button type="button" onClick={() => { setSelectedId(l.id); setNotice(""); }}
                className={`customers-row leads-row ${isAdmin ? "admin" : ""} ${l.id === selectedId ? "on" : ""}`}>
                <span className="customers-cell-main">
                  <span className="customer-avatar">{initials(l.name)}</span>
                  <span><strong>{l.name}</strong><small>{l.city}/{l.state} · {formatCnpj(l.cnpj)} · {LEAD_SIZES[l.size] || "—"}{l.in_debt ? " · dívida ativa" : ""}</small>
                    {contactText(l) && <small className="contact-due">{contactText(l)}</small>}</span>
                </span>
                <span>{l.phone || "—"}</span>
                {isAdmin && <span>{l.seller_name?.split(" ")[0] || "Sem vendedor"}</span>}
                <span>
                  {isNewStore(l.opened_at)
                    ? <span className="cstatus cstatus-active">Nova · {openedText(l.opened_at)}</span>
                    : <small className="muted">{openedText(l.opened_at)}</small>}
                </span>
              </button>
              </div>
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
            <LeadPanel key={selected.id} lead={selected} isAdmin={isAdmin} sellers={sellers} onClose={() => setSelectedId(null)}
              onReleased={(r) => afterRelease([selected.id], r)}
              onContacted={() => refreshContact(selected.id)}
              catalogUrl={catalogUrl}
              onNoAnswer={(r) => {
                if (r.discarded) { drop(selected.id); setNotice("3 tentativas sem resposta: a loja foi descartada."); }
                else { refreshContact(selected.id); setNotice(`Tentativa ${r.tries} de 3 registrada. Retorno em ${dateBR(r.retry_on)}.`); }
              }}
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
        <Modal title={discarding.ids ? `Não recomendar ${discarding.name}?` : `Descartar ${discarding.name}?`} onClose={() => setDiscarding(null)}>
          <form onSubmit={discard} className="form-grid">
            <Field label="Motivo" span={2}>
              <select value={discarding.reason} onChange={(e) => setDiscarding({ ...discarding, reason: e.target.value })}>
                {Object.entries(DISCARD_REASONS).filter(([k]) => !AUTO_REASONS.includes(k) || (discarding.ids && k === "not_recommended"))
                  .map(([k, label]) => <option key={k} value={k}>{label}</option>)}
              </select>
            </Field>
            <div className="span-2"><ErrorBox msg={discarding.error} /></div>
            <div className="actions span-2"><button className="btn danger" disabled={discarding.busy}>{discarding.ids ? "Tirar da fila" : "Descartar lead"}</button></div>
          </form>
        </Modal>
      )}
    </div>
  );
}
