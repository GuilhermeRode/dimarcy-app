import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { Field, ErrorBox, Modal, EmptyState } from "../components/ui";

const EMPTY = { name: "", document: "", phone: "", email: "", city: "", state: "", address: "", notes: "", owner_id: "" };

export default function Customers() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [list, setList] = useState([]);
  const [sellers, setSellers] = useState([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  const load = () => api.get("/customers", { params: { search } })
    .then((r) => { setList(r.data); setError(""); })
    .catch((err) => setError(errorMessage(err)));
  useEffect(() => { if (isAdmin) api.get("/users").then((r) => setSellers(r.data)); }, [isAdmin]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [search]);

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

  return (
    <div className="page">
      <header className="page-header">
        <h1>Clientes</h1>
        <button className="btn btn-primary" onClick={() => { setError(""); setForm(EMPTY); }}>Cadastrar cliente</button>
      </header>
      <div className="filter-bar">
        <input placeholder="Buscar por nome, cidade ou CPF/CNPJ" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <ErrorBox msg={error} />
      {!list.length ? <EmptyState text="Nenhum cliente encontrado." /> : (
        <table className="table">
          <thead><tr><th>Nome</th><th>CPF/CNPJ</th><th>Cidade</th><th>Telefone</th>{isAdmin && <th>Vendedor</th>}</tr></thead>
          <tbody>
            {list.map((c) => (
              <tr key={c.id} className="clickable" onClick={() => { setError(""); setForm({ ...c, owner_id: c.owner_id || "" }); }}>
                <td>{c.name}</td><td>{c.document}</td>
                <td>{c.city}{c.state ? `/${c.state}` : ""}</td><td>{c.phone}</td>
                {isAdmin && <td>{c.owner_name || <span className="muted">Não vinculado</span>}</td>}
              </tr>
            ))}
          </tbody>
        </table>
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
