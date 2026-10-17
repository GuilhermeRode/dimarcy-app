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
