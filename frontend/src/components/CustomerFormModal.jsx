import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { Field, ErrorBox, Modal } from "./ui";

export const EMPTY_CUSTOMER = { name: "", document: "", phone: "", email: "", city: "", state: "", address: "", notes: "", owner_id: "" };

export default function CustomerFormModal({ initial, isAdmin, onClose, onSaved }) {
  const [form, setForm] = useState({ ...initial, owner_id: initial.owner_id || "" });
  const [sellers, setSellers] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => { if (isAdmin) api.get("/users").then((r) => setSellers(r.data)); }, [isAdmin]);

  async function save(e) {
    e.preventDefault();
    setError("");
    const body = { ...form, state: form.state ? form.state.toUpperCase() : null, owner_id: form.owner_id ? Number(form.owner_id) : null };
    try {
      form.id ? await api.put(`/customers/${form.id}`, body) : await api.post("/customers", body);
      onSaved();
    } catch (err) { setError(errorMessage(err)); }
  }

  async function remove() {
    if (!confirm(`Excluir ${form.name}?`)) return;
    try { await api.delete(`/customers/${form.id}`); onSaved(); }
    catch (err) { setError(errorMessage(err)); }
  }

  const f = (k) => ({ value: form[k] || "", onChange: (e) => setForm({ ...form, [k]: e.target.value }) });

  return (
    <Modal title={form.id ? "Editar cliente" : "Cadastrar cliente"} onClose={onClose} wide>
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
  );
}
