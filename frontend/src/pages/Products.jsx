import { useEffect, useState } from "react";
import { api, errorMessage, fileUrl } from "../api";
import { money, DEFAULT_SIZES } from "../format";
import { Field, ErrorBox, Modal, Swatch, EmptyState } from "../components/ui";

const EMPTY = { reference: "", description: "", collection: "", price: "", sizes: DEFAULT_SIZES, color_ids: [], active: true, image_url: null };

export default function Products() {
  const [list, setList] = useState([]);
  const [colors, setColors] = useState([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [error, setError] = useState("");
  const [newSize, setNewSize] = useState("");
  const [uploading, setUploading] = useState(false);

  const load = () => api.get("/products", { params: { search } }).then((r) => setList(r.data));
  useEffect(() => { api.get("/colors").then((r) => setColors(r.data)); }, []);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [search]);

  function open(p) {
    setError("");
    setImageFile(null);
    setForm(p ? { ...p, color_ids: p.colors.map((c) => c.id) } : EMPTY);
  }

  const toggle = (field, v) =>
    setForm((f) => ({ ...f, [field]: f[field].includes(v) ? f[field].filter((x) => x !== v) : [...f[field], v] }));

  async function save(e) {
    e.preventDefault();
    setError("");
    setUploading(true);
    const body = { ...form, price: Number(form.price) || 0 };
    try {
      const { data } = form.id ? await api.put(`/products/${form.id}`, body) : await api.post("/products", body);
      if (imageFile) {
        const fd = new FormData();
        fd.append("file", imageFile);
        await api.post(`/products/${data.id}/image`, fd);
      }
      setForm(null);
      setImageFile(null);
      load();
    } catch (err) { setError(errorMessage(err)); } finally { setUploading(false); }
  }

  async function remove() {
    if (!confirm(`Excluir ${form.reference}?`)) return;
    try { await api.delete(`/products/${form.id}`); setForm(null); load(); }
    catch (err) { setError(errorMessage(err)); }
  }

  const sizeOptions = [...new Set([...DEFAULT_SIZES, "XG", ...(form?.sizes || [])])];
  const previewUrl = imageFile ? URL.createObjectURL(imageFile) : fileUrl(form?.image_url);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Produtos</h1>
        <button className="btn btn-primary" onClick={() => open(null)}>Cadastrar produto</button>
      </header>
      <div className="filter-bar">
        <input placeholder="Buscar por referência, nome ou coleção" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      {!list.length ? <EmptyState text="Nenhum produto cadastrado." /> : (
        <table className="table">
          <thead><tr><th></th><th>Ref.</th><th>Descrição</th><th>Coleção</th><th>Tamanhos</th><th>Cores</th><th className="num">Preço</th></tr></thead>
          <tbody>
            {list.map((p) => (
              <tr key={p.id} className={`clickable ${p.active ? "" : "inactive"}`} onClick={() => open(p)}>
                <td>
                  {p.image_url
                    ? <img className="product-thumb" src={fileUrl(p.image_url)} alt="" />
                    : <span className="product-thumb product-thumb-empty" aria-hidden="true">🧶</span>}
                </td>
                <td className="ref">{p.reference}</td>
                <td>{p.description}{!p.active && <span className="tag">inativo</span>}</td>
                <td>{p.collection}</td>
                <td>{p.sizes.join(" ")}</td>
                <td><span className="swatches">{p.colors.map((c) => <Swatch key={c.id} hex={c.hex} />)}</span></td>
                <td className="num">{money(p.price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {form && (
        <Modal title={form.id ? `Editar ${form.reference}` : "Cadastrar produto"} onClose={() => setForm(null)} wide>
          <form onSubmit={save} className="form-grid">
            <div className="field span-2">
              <span>Foto do produto</span>
              <div className="product-image-field">
                {previewUrl
                  ? <img className="product-image-preview" src={previewUrl} alt="Pré-visualização" />
                  : <div className="product-image-preview product-image-empty" aria-hidden="true">🧶</div>}
                <div className="product-image-actions">
                  <label className="btn btn-light">
                    Escolher arquivo
                    <input type="file" accept="image/*" hidden
                      onChange={(e) => setImageFile(e.target.files?.[0] || null)} />
                  </label>
                  {(imageFile || form.image_url) && (
                    <button type="button" className="btn btn-light danger" onClick={async () => {
                      setImageFile(null);
                      if (form.id && form.image_url) {
                        try { await api.delete(`/products/${form.id}/image`); } catch (err) { setError(errorMessage(err)); }
                      }
                      setForm((f) => ({ ...f, image_url: null }));
                    }}>
                      Remover foto
                    </button>
                  )}
                </div>
              </div>
            </div>

            <Field label="Referência"><input required value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></Field>
            <Field label="Preço (R$)"><input type="number" step="0.01" min="0" required value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} /></Field>
            <Field label="Descrição" span={2}><input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
            <Field label="Coleção" span={2}><input value={form.collection || ""} onChange={(e) => setForm({ ...form, collection: e.target.value })} placeholder="Ex.: Inverno 2027" /></Field>

            <div className="field span-2">
              <span>Tamanhos</span>
              <div className="chips">
                {sizeOptions.map((t) => (
                  <button type="button" key={t} className={`chip ${form.sizes.includes(t) ? "on" : ""}`} onClick={() => toggle("sizes", t)}>{t}</button>
                ))}
                <input className="chip-input" placeholder="Outro" value={newSize} maxLength={5}
                  onChange={(e) => setNewSize(e.target.value.toUpperCase())}
                  onKeyDown={(e) => { if (e.key === "Enter" && newSize) { e.preventDefault(); if (!form.sizes.includes(newSize)) toggle("sizes", newSize); setNewSize(""); } }} />
              </div>
            </div>

            <div className="field span-2">
              <span>Cores disponíveis</span>
              {colors.length ? (
                <div className="chips">
                  {colors.map((c) => (
                    <button type="button" key={c.id} className={`chip ${form.color_ids.includes(c.id) ? "on" : ""}`} onClick={() => toggle("color_ids", c.id)}>
                      <Swatch hex={c.hex} /> {c.name}
                    </button>
                  ))}
                </div>
              ) : <p className="muted">Cadastre as cores primeiro na tela Cores.</p>}
            </div>

            <label className="check span-2">
              <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
              Disponível para venda
            </label>
            <div className="span-2"><ErrorBox msg={error} /></div>
            <div className="actions span-2">
              {form.id && <button type="button" className="btn danger" onClick={remove}>Excluir</button>}
              <button className="btn btn-primary" disabled={uploading}>{uploading ? "Salvando..." : "Salvar produto"}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
