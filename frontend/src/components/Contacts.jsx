import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { addDays, dateBR, localDate } from "../format";
import { ErrorBox, Field, Modal } from "./ui";

// Keys match the backend's CONTACT_CHANNELS
export const CHANNELS = { whatsapp: "WhatsApp", call: "Ligação", visit: "Visita", email: "E-mail" };

// created_at is UTC without a zone (SQLite CURRENT_TIMESTAMP); "Z" makes the browser convert it to local time
const contactDate = (iso) => new Date(`${iso}Z`).toLocaleDateString("pt-BR");

// "Aguardar" (the store asked to be called back later) uses it with a title, a preset note and a required date
export function ContactModal({ target, onClose, onSaved, title = "Registrar contato", notes = "", requireDate = false }) {
  const [form, setForm] = useState({ channel: "whatsapp", notes, next_action_date: "" });
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
    <Modal title={title} onClose={onClose}>
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
        <div className="field span-2">
          <span>{requireDate ? "Retornar em" : "Retornar em (opcional)"}</span>
          <div className="contact-next">
            <input type="date" aria-label="Retornar em" required={requireDate} min={today} value={form.next_action_date}
              onChange={(e) => setForm({ ...form, next_action_date: e.target.value })} />
            {[[7, "1 semana"], [15, "15 dias"], [30, "1 mês"]].map(([d, label]) => (
              <button type="button" key={d} className={`btn ${form.next_action_date === addDays(today, d) ? "btn-primary" : ""}`}
                onClick={() => setForm({ ...form, next_action_date: addDays(today, d) })}>{label}</button>
            ))}
          </div>
        </div>
        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2"><button className="btn btn-primary" disabled={busy}>Salvar contato</button></div>
      </form>
    </Modal>
  );
}

export function ContactHistory({ target, onSaved }) {
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
          <small>{contactDate(ct.created_at)} · {CHANNELS[ct.channel] ?? ct.channel} · {ct.user_name}</small>
          {ct.notes && <p>{ct.notes}</p>}
          {ct.next_action_date && <small className="contact-due">Retornar em {dateBR(ct.next_action_date)}</small>}
        </div>
      )) : <p className="customer-panel-empty">Nenhum contato registrado ainda.</p>)}
      {adding && <ContactModal target={target} onClose={() => setAdding(false)}
        onSaved={() => { setAdding(false); load(); onSaved?.(); }} />}
    </div>
  );
}
