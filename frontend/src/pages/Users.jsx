import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { Field, ErrorBox, Modal } from "../components/ui";
import { useSort } from "../components/useSort";

export default function Users() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  const load = () => api.get("/users").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);

  async function save(e) {
    e.preventDefault();
    const goal = form.annual_goal;
    const body = { ...form, annual_goal: goal === "" || goal == null ? null : Number(goal) };
    try {
      form.id ? await api.put(`/users/${form.id}`, body) : await api.post("/users", body);
      setForm(null);
      load();
    } catch (err) { setError(errorMessage(err)); }
  }

  const { sorted, sortHeader } = useSort(list, {
    name: (u) => u.name,
    email: (u) => u.email,
    role: (u) => (u.role === "admin" ? "Administrador" : "Vendedor"),
    active: (u) => (u.active ? "Ativo" : "Bloqueado"),
  });

  const f = (k) => ({ value: form[k] || "", onChange: (e) => setForm({ ...form, [k]: e.target.value }) });

  return (
    <div className="page">
      <header className="page-header">
        <h1>Usuários</h1>
        <button className="btn btn-primary" onClick={() => { setError(""); setForm({ name: "", email: "", password: "", role: "seller", active: true, annual_goal: "", price_table: "wholesale" }); }}>Cadastrar usuário</button>
      </header>
      <table className="table">
        <thead>
          <tr>
            {sortHeader("name", "Nome")}
            {sortHeader("email", "E-mail")}
            {sortHeader("role", "Perfil")}
            {sortHeader("active", "Situação")}
          </tr>
        </thead>
        <tbody>
          {sorted.map((u) => (
            <tr key={u.id} className={`clickable ${u.active ? "" : "inactive"}`} onClick={() => { setError(""); setForm({ ...u, password: "" }); }}>
              <td>{u.name}</td><td>{u.email}</td>
              <td>{u.role === "admin" ? "Administrador" : "Vendedor"}</td>
              <td>{u.active ? "Ativo" : "Bloqueado"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {form && (
        <Modal title={form.id ? "Editar usuário" : "Cadastrar usuário"} onClose={() => setForm(null)}>
          <form onSubmit={save} className="form-grid">
            <Field label="Nome" span={2}><input required {...f("name")} /></Field>
            <Field label="E-mail" span={2}><input type="email" required {...f("email")} /></Field>
            <Field label={form.id ? "Nova senha (deixe em branco para manter)" : "Senha"} span={2}>
              <input type="password" minLength={10} required={!form.id} {...f("password")} />
            </Field>
            <Field label="Perfil">
              <select {...f("role")}><option value="seller">Vendedor</option><option value="admin">Administrador</option></select>
            </Field>
            <Field label="Meta anual (R$)">
              <input type="number" min="0" step="0.01" placeholder="Sem meta" {...f("annual_goal")} />
            </Field>
            <Field label="Tabela de preço">
              <select {...f("price_table")}>
                <option value="wholesale">Atacado</option>
                <option value="retail">Varejo</option>
                <option value="both">Atacado e varejo</option>
              </select>
            </Field>
            <label className="check">
              <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} /> Acesso liberado
            </label>
            <div className="span-2"><ErrorBox msg={error} /></div>
            <div className="actions span-2"><button className="btn btn-primary">Salvar usuário</button></div>
          </form>
        </Modal>
      )}
    </div>
  );
}
