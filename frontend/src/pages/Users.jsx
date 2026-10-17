import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api";
import { Field, ErrorBox, Modal } from "../components/ui";
import { useSort } from "../components/useSort";
import { normalize } from "../format";

// "Jaraguá do Sul - SC" / "Jaraguá do Sul/SC" -> {city, state}
const parseCity = (text) => {
  const m = text.trim().match(/^(.+?)\s*[-/]\s*([A-Za-z]{2})$/);
  return m ? { city: m[1].trim(), state: m[2].toUpperCase() } : null;
};
const cityKey = (c) => `${normalize(c.city)}|${c.state}`;

function RegionCities({ userId, cities, onChange }) {
  const [options, setOptions] = useState([]);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => { api.get("/users/cities/options").then((r) => setOptions(r.data)); }, []);

  const add = (list) => {
    const seen = new Set(cities.map(cityKey));
    onChange([...cities, ...list.filter((c) => !seen.has(cityKey(c)) && seen.add(cityKey(c)))]);
  };

  function addTyped() {
    const c = parseCity(text);
    if (!c) { setNote("Escreva no formato Cidade - UF (ex.: Jaraguá do Sul - SC)."); return; }
    add([c]);
    setText("");
    setNote("");
  }

  async function suggest() {
    const { data } = await api.get(`/users/${userId}/cities/suggestions`);
    add(data.filter((s) => !s.taken_by).map(({ city, state }) => ({ city, state })));
    const taken = data.filter((s) => s.taken_by);
    setNote(taken.length ? `Não incluídas (já são de outro vendedor): ${taken.map((s) => `${s.city} — ${s.taken_by}`).join("; ")}.` : "");
  }

  return (
    <div className="span-2 region">
      <span className="region-label">Cidades da região (Prospecção)</span>
      <div className="region-chips">
        {cities.map((c) => (
          <button type="button" key={cityKey(c)} className="filter-chip" title="Remover"
            onClick={() => onChange(cities.filter((x) => cityKey(x) !== cityKey(c)))}>{c.city}/{c.state} ×</button>
        ))}
        {!cities.length && <span className="muted">Nenhuma cidade ainda.</span>}
      </div>
      <div className="region-add">
        <input list="city-options" aria-label="Cidade - UF" placeholder="Cidade - UF" value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTyped(); } }} />
        <datalist id="city-options">
          {options.map((o) => <option key={`${o.city}|${o.state}`} value={`${o.city} - ${o.state}`} />)}
        </datalist>
        <button type="button" className="btn" onClick={addTyped}>Adicionar</button>
        {userId && <button type="button" className="btn" onClick={suggest}>Sugerir pelas cidades dos clientes</button>}
      </div>
      {note && <p className="muted">{note}</p>}
    </div>
  );
}

export default function Users() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [cities, setCities] = useState(null); // null = not loaded / not a seller

  const openId = useRef(null); // which user the form shows, to drop late region responses of another one

  const load = () => api.get("/users").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);

  function openForm(u) {
    setError("");
    setForm(u);
    openId.current = u.id ?? "new";
    setCities(u.id ? null : []);
    if (u.id) {
      api.get(`/users/${u.id}/cities`)
        .then((r) => { if (openId.current === u.id) setCities(r.data); })
        .catch((e) => { if (openId.current === u.id) setError(errorMessage(e)); });
    }
  }

  async function save(e) {
    e.preventDefault();
    if (form.role === "seller" && cities === null) { setError("Não foi possível carregar as cidades da região. Feche e abra o usuário de novo."); return; }
    setError("");
    const goal = form.annual_goal;
    const body = { ...form, annual_goal: goal === "" || goal == null ? null : Number(goal) };
    try {
      const { data: saved } = form.id ? await api.put(`/users/${form.id}`, body) : await api.post("/users", body);
      setForm({ ...form, id: saved.id }); // a failing region save below must not create the user twice
      load();
      if (form.role === "seller" && cities) await api.put(`/users/${saved.id}/cities`, cities);
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
        <button className="btn btn-primary" onClick={() => openForm({ name: "", email: "", password: "", role: "seller", active: true, annual_goal: "", price_table: "wholesale" })}>Cadastrar usuário</button>
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
            <tr key={u.id} className={`clickable ${u.active ? "" : "inactive"}`} onClick={() => openForm({ ...u, password: "" })}>
              <td>{u.name}</td><td>{u.email}</td>
              <td>{u.role === "admin" ? "Administrador" : "Vendedor"}</td>
              <td>{u.active ? "Ativo" : "Bloqueado"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {form && (
        <Modal title={form.id ? "Editar usuário" : "Cadastrar usuário"} onClose={() => setForm(null)} wide>
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
            {form.role === "seller" && (cities
              ? <RegionCities userId={form.id} cities={cities} onChange={setCities} />
              : <p className="span-2 muted">Carregando cidades da região…</p>)}
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
