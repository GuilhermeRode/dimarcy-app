import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { Field, ErrorBox, Modal, Swatch, EmptyState } from "../components/ui";

// Picks readable text (light or dark) for a given background color.
function textOn(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.65 ? "#16233d" : "#ffffff";
}

export default function Colors() {
  const [list, setList] = useState([]);
  const [products, setProducts] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  const load = () => api.get("/colors").then((r) => setList(r.data));
  useEffect(() => { load(); api.get("/products").then((r) => setProducts(r.data)); }, []);

  const usageCount = (colorId) => products.filter((p) => p.colors.some((c) => c.id === colorId)).length;

  async function save(e) {
    e.preventDefault();
    try {
      form.id ? await api.put(`/colors/${form.id}`, form) : await api.post("/colors", form);
      setForm(null);
      load();
    } catch (err) { setError(errorMessage(err)); }
  }

  async function remove() {
    if (!confirm(`Excluir a cor ${form.name}?`)) return;
    try { await api.delete(`/colors/${form.id}`); setForm(null); load(); }
    catch (err) { setError(errorMessage(err)); }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Cores</h1>
        <button className="btn btn-primary" onClick={() => { setError(""); setForm({ name: "", hex: "#cccccc" }); }}>Cadastrar cor</button>
      </header>
      {!list.length ? <EmptyState text="Nenhuma cor cadastrada ainda." /> : (
        <div className="color-grid">
          {list.map((c) => {
            const uses = usageCount(c.id);
            const fg = textOn(c.hex);
            return (
              <button key={c.id} className="color-card" style={{ background: c.hex, color: fg }}
                onClick={() => { setError(""); setForm(c); }}>
                <span className="color-card-name">{c.name}</span>
                <span className="color-card-hex" style={{ color: fg, opacity: .8 }}>{c.hex.toUpperCase()}</span>
                <span className="color-card-usage" style={{ color: fg, opacity: .8 }}>
                  {uses ? `${uses} produto${uses > 1 ? "s" : ""}` : "Não usada em produtos"}
                </span>
              </button>
            );
          })}
        </div>
      )}
      {form && (
        <Modal title={form.id ? "Editar cor" : "Cadastrar cor"} onClose={() => setForm(null)}>
          <form onSubmit={save} className="form-grid">
            <Field label="Nome" span={2}><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Tom" span={2}>
              <div className="field-row">
                <input type="color" value={form.hex} onChange={(e) => setForm({ ...form, hex: e.target.value })} />
                <Swatch hex={form.hex} size={28} />
                <span className="muted">{form.hex.toUpperCase()}</span>
              </div>
            </Field>
            <div className="span-2"><ErrorBox msg={error} /></div>
            <div className="actions span-2">
              {form.id && <button type="button" className="btn danger" onClick={remove}>Excluir</button>}
              <button className="btn btn-primary">Salvar cor</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
