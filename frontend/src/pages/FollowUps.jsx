import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { dateBR, initials, localDate, utcDateBR, whatsappUrl } from "../format";
import { ErrorBox, PillSelect } from "../components/ui";
import { CHANNELS, ContactModal } from "../components/Contacts";

const NEXT_DAYS = 7;   // "Próximos": what's coming up this week
const DONE_DAYS = 30;  // "Concluídos": handled in the last month
const TABS = [["late", "Atrasados"], ["today", "Hoje"], ["next", "Próximos"], ["done", "Concluídos"]];
const KINDS = [["", "Todos"], ["lead", "Leads"], ["customer", "Clientes"]];

export default function FollowUps() {
  const [due, setDue] = useState(null);    // late + today + next NEXT_DAYS days
  const [done, setDone] = useState(null);
  const [error, setError] = useState("");
  const [target, setTarget] = useState(null);
  const [tab, setTab] = useState(null);    // null until loaded: opens on Atrasados when there are any
  const [kind, setKind] = useState("");
  const [seller, setSeller] = useState("");
  const today = localDate();
  const nav = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";  // sees every seller's follow-ups

  const load = () => Promise.all([api.get("/contacts/due", { params: { days: NEXT_DAYS } }),
                                  api.get("/contacts/done", { params: { days: DONE_DAYS } })])
    .then(([d, c]) => {
      setDue(d.data); setDone(c.data); setError("");
      setTab((t) => t || (d.data.some((r) => r.next_action_date < today) ? "late" : "today"));
    })
    .catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);

  const bucket = (r) => (r.next_action_date < today ? "late" : r.next_action_date === today ? "today" : "next");
  const ofKind = (rows) => (rows || []).filter((r) => !kind || r.kind === kind);
  const mine = (rows) => ofKind(rows).filter((r) => !seller || r.user_id === Number(seller));
  const lists = { done: mine(done) };
  for (const [k] of TABS.slice(0, 3)) lists[k] = mine(due).filter((r) => bucket(r) === k);

  // per seller (admin): who is behind, and how often they keep the date they set
  const sellers = new Map();
  const row = (r) => {
    if (!sellers.has(r.user_id)) sellers.set(r.user_id, { id: r.user_id, name: r.user_name, late: 0, today: 0, next: 0, done: 0, onTime: 0 });
    return sellers.get(r.user_id);
  };
  ofKind(due).forEach((r) => { row(r)[bucket(r)] += 1; });
  ofKind(done).forEach((r) => { const s = row(r); s.done += 1; s.onTime += r.on_time ? 1 : 0; });
  // every seller with a follow-up, whatever the Tipo filter: the picked one never vanishes from the pill
  const people = [...new Map([...(due || []), ...(done || [])].map((r) => [String(r.user_id), r.user_name])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1]));
  const summary = [...sellers.values()].sort((a, b) => b.late - a.late || a.name.localeCompare(b.name));

  const rows = tab ? lists[tab] : null;
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Retornos</h1>
          <p className="muted">{isAdmin ? "Retornos combinados por toda a equipe, leads e clientes." : "Contatos que você combinou de retomar, leads e clientes."}
            {" "}Registrar o novo contato tira da lista.</p>
        </div>
        <div className="header-actions">
          <button className="btn" onClick={() => nav("/leads")}>← Prospecção</button>
        </div>
      </header>
      <ErrorBox msg={error} />

      {isAdmin && summary.length > 0 && (
        <table className="table followup-summary">
          <thead>
            <tr><th>Vendedor</th><th>Atrasados</th><th>Hoje</th><th>Próximos {NEXT_DAYS} dias</th>
              <th>Concluídos ({DONE_DAYS} dias)</th><th>No prazo</th></tr>
          </thead>
          <tbody>
            {summary.map((s) => (
              <tr key={s.id} className={String(s.id) === seller ? "active" : ""}>
                <td><button type="button" className="link-btn" title="Ver só os retornos deste vendedor"
                  onClick={() => setSeller(String(s.id) === seller ? "" : String(s.id))}>{s.name}</button></td>
                <td className={s.late ? "followup-late" : ""}>{s.late}</td>
                <td>{s.today}</td>
                <td>{s.next}</td>
                <td>{s.done}</td>
                <td>{s.done ? `${Math.round((s.onTime / s.done) * 100)}%` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <nav className="tabs-underline" aria-label="Situação dos retornos">
        {TABS.map(([k, label]) => (
          <button key={k} type="button" className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {label}{due ? ` (${lists[k].length})` : ""}
          </button>
        ))}
      </nav>

      <section className="filters-bar">
        <div className="filters-row">
          <PillSelect label="Tipo" value={kind} options={KINDS} onChange={setKind} />
          {isAdmin && (
            <PillSelect label="Vendedor" value={seller} onChange={setSeller}
              options={[["", "Todos"], ...people]} />
          )}
        </div>
      </section>

      <section className="customers-table">
        {rows && !rows.length && (
          <p className="customers-empty">{tab === "done" ? `Nenhum retorno concluído nos últimos ${DONE_DAYS} dias.` : "Nenhum retorno aqui. 🎉"}</p>
        )}
        {rows?.map((r) => {
          const wa = whatsappUrl(r.phone);
          return (
            <div key={r.contact_id} className="followup-row">
              <span className="customers-cell-main">
                <span className="customer-avatar">{initials(r.name)}</span>
                <span>
                  <strong>{r.name}</strong>
                  <small>
                    {r.kind === "lead" ? "Lead" : "Cliente"}{isAdmin && ` · ${r.user_name}`}
                    {tab === "done"
                      ? ` · feito por ${r.done_by}: ${CHANNELS[r.channel] ?? r.channel}${r.notes ? ` — ${r.notes}` : ""}`
                      : ` · último${r.set_by !== r.user_name ? ` (por ${r.set_by})` : ""}: ${CHANNELS[r.channel] ?? r.channel}${r.notes ? ` — ${r.notes}` : ""}`}
                  </small>
                </span>
              </span>
              {tab === "done" ? (
                <span className={r.on_time ? "followup-today" : "followup-late"}>
                  {utcDateBR(r.done_at)} · {r.on_time ? "No prazo" : `Atrasado (era ${dateBR(r.next_action_date)})`}
                </span>
              ) : (
                <span className={tab === "late" ? "followup-late" : tab === "today" ? "followup-today" : "muted"}>
                  {tab === "late" ? `Atrasado desde ${dateBR(r.next_action_date)}` : tab === "today" ? "Hoje" : dateBR(r.next_action_date)}
                </span>
              )}
              <span className="followup-actions">
                {tab !== "done" && wa && <a className="btn" href={wa} target="_blank" rel="noopener noreferrer">WhatsApp</a>}
                {tab !== "done" && (
                  <button type="button" className="btn btn-primary"
                    onClick={() => setTarget(r.lead_id ? { lead_id: r.lead_id } : { customer_id: r.customer_id })}>
                    Registrar contato
                  </button>
                )}
              </span>
            </div>
          );
        })}
      </section>
      {target && <ContactModal target={target} onClose={() => setTarget(null)} onSaved={() => { setTarget(null); load(); }} />}
    </div>
  );
}
