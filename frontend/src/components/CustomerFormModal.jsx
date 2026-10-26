import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api";
import { Field, ErrorBox, Modal, useConfirm } from "./ui";
import { customerFieldError, maskDocument, maskPhone, maskStateRegistration, stateRegistrationHint } from "../format";

export const EMPTY_CUSTOMER = { name: "", document: "", state_registration: "", phone: "", email: "", city: "", state: "", address: "", notes: "", owner_id: "" };

// Pre-fills the customer form from the CNPJ (Receita Federal) once its 14th digit is typed: only empty fields,
// never what was already typed. Purely a help: it never blocks typing or saving, and a failure is a quiet note.
const CNPJ_FILLS = ["name", "address", "city", "state", "phone", "email"];
const onlyDigits = (s) => (s || "").replace(/\D/g, "");
export function useCnpjAutofill(document, initialDocument, setForm) {
  const [note, setNote] = useState(null); // { tone: "" | "warn", text }
  const last = useRef(onlyDigits(initialDocument)); // an existing customer's own CNPJ isn't looked up again
  useEffect(() => {
    const d = onlyDigits(document);
    if (d.length !== 14) { setNote(null); return; }
    if (d === last.current) return;
    last.current = d;
    let alive = true;
    setNote({ tone: "", text: "Buscando dados do CNPJ…" });
    api.get(`/customers/cnpj/${d}`).then(({ data }) => {
      if (!alive) return;
      setForm((f) => {
        const out = { ...f };
        for (const k of CNPJ_FILLS) if (!String(f[k] || "").trim() && data[k]) out[k] = data[k];
        return out;
      });
      setNote(data.status && data.status !== "ATIVA"
        ? { tone: "warn", text: `Atenção: este CNPJ está com situação ${data.status} na Receita Federal.` }
        : { tone: "", text: "Dados preenchidos pela Receita Federal. Confira antes de salvar." });
    }).catch((err) => {
      if (!alive) return;
      setNote({ tone: "", text: err.response?.status === 404
        ? "CNPJ não encontrado na Receita Federal. Preencha os dados manualmente."
        : "Não foi possível buscar os dados agora. Preencha os dados manualmente." });
    });
    return () => { alive = false; };
  }, [document]);
  return note;
}

export const CnpjNote = ({ note }) => (note ? <small className={`field-note ${note.tone}`} role="status">{note.text}</small> : null);

// Inscrição estadual: a number, or the "Isento" box for customers exempt from it (stored as "ISENTO")
// formatted with the customer's UF mask (re-applied when the UF changes)
export function StateRegistrationField({ value, uf, onChange, required = true }) {
  const exempt = value === "ISENTO";
  return (
    <Field label="Inscrição estadual">
      <div className="field-row">
        <input required={required && !exempt} inputMode="numeric" disabled={exempt}
          value={exempt ? "" : maskStateRegistration(value, uf)}
          placeholder={exempt ? "Isento" : stateRegistrationHint(uf) || "Número da IE"}
          onChange={(e) => onChange(maskStateRegistration(e.target.value, uf))} />
        <label className="check"><input type="checkbox" checked={exempt} onChange={(e) => onChange(e.target.checked ? "ISENTO" : "")} /> Isento</label>
      </div>
    </Field>
  );
}

export default function CustomerFormModal({ initial, isAdmin, onClose, onSaved, onConflict, submitUrl = "/customers" }) {
  const [confirmDialog, ask] = useConfirm();
  const [form, setForm] = useState({ ...initial, owner_id: initial.owner_id || "" });
  const [sellers, setSellers] = useState([]);
  const cnpjNote = useCnpjAutofill(form.document, initial.document, setForm);
  const [error, setError] = useState("");

  useEffect(() => { if (isAdmin) api.get("/users").then((r) => setSellers(r.data)); }, [isAdmin]);

  async function save(e) {
    e.preventDefault();
    setError("");
    const invalid = customerFieldError(form, initial);
    if (invalid) return setError(invalid);
    const body = { ...form, state: form.state ? form.state.toUpperCase() : null, owner_id: form.owner_id ? Number(form.owner_id) : null };
    try {
      form.id ? await api.put(`/customers/${form.id}`, body) : await api.post(submitUrl, body);
      onSaved();
    } catch (err) {
      if (onConflict && err.response?.status === 409) onConflict(); else setError(errorMessage(err));
    }
  }

  async function remove() {
    if (!(await ask({ title: `Excluir ${form.name}?`, message: "O cliente será removido do cadastro.", confirmLabel: "Excluir", danger: true }))) return;
    try { await api.delete(`/customers/${form.id}`); onSaved(); }
    catch (err) { setError(errorMessage(err)); }
  }

  const f = (k) => ({ value: form[k] || "", onChange: (e) => setForm({ ...form, [k]: e.target.value }) });
  // An admin editing an existing customer may save with blanks (the API accepts it, see CustomerDraft);
  // registering, and every seller save, keep all fields required.
  const required = !(isAdmin && form.id);

  return (
    <>
    <Modal title={form.id ? "Editar cliente" : "Cadastrar cliente"} onClose={onClose} wide>
      <form onSubmit={save} className="form-grid">
        {!required && (
          <p className="field-note span-2">Como administrador, você pode salvar mesmo com campos em branco. Só o nome é obrigatório.</p>
        )}
        <Field label="Nome / razão social" span={2}><input required {...f("name")} /></Field>
        <Field label="CPF/CNPJ"><input required={required} inputMode="numeric" placeholder="000.000.000-00 ou 00.000.000/0000-00" {...f("document")}
          onChange={(e) => setForm({ ...form, document: maskDocument(e.target.value) })} /><CnpjNote note={cnpjNote} /></Field>
        <StateRegistrationField value={form.state_registration} uf={form.state} required={required}
          onChange={(v) => setForm({ ...form, state_registration: v })} />
        {isAdmin && (
          <Field label="Vendedor responsável" span={2}>
            <select required={required} {...f("owner_id")}>
              <option value="">{required ? "Selecione o vendedor" : "Sem vendedor"}</option>
              {sellers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
        )}
        <Field label="Telefone"><input required={required} type="tel" inputMode="tel" autoComplete="tel" placeholder="(00) 00000-0000" {...f("phone")}
          onChange={(e) => setForm({ ...form, phone: maskPhone(e.target.value) })} /></Field>
        <Field label="E-mail"><input required={required} type="email" placeholder="nome@empresa.com.br" {...f("email")} /></Field>
        <Field label="Cidade / UF" span={2}>
          <div className="city-row">
            <input required={required} placeholder="Cidade" {...f("city")} />
            <input required={required} placeholder="UF" minLength={2} maxLength={2} className="uf-input" {...f("state")} />
          </div>
        </Field>
        <Field label="Endereço" span={2}><input required={required} {...f("address")} /></Field>
        <Field label="Observações (opcional)" span={2}><textarea rows={3} {...f("notes")} /></Field>
        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2">
          {form.id && <button type="button" className="btn danger" onClick={remove}>Excluir</button>}
          <button className="btn btn-primary">Salvar cliente</button>
        </div>
      </form>
    </Modal>
    {confirmDialog}
    </>
  );
}
