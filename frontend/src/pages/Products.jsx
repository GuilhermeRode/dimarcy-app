import { useEffect, useState } from "react";
import { api, errorMessage, fileUrl, screenCache } from "../api";
import { useAuth } from "../auth";
import { money, tablePrice, DEFAULT_SIZES, normalize, sortSizes } from "../format";
import { Field, ErrorBox, Modal, Swatch, EmptyState, PhotoZoom, useConfirm } from "../components/ui";
import { useSort } from "../components/useSort";

// The image file in a drag-and-drop, or null (e.g. a dragged link or text)
// (Windows sometimes gives a dragged .jpg no type, so the extension counts too; the server checks the real bytes)
const isImage = (f) => f.type.startsWith("image/") || /\.(jpe?g|jfif|png|webp|gif)$/i.test(f.name);
const droppedImage = (e) => [...(e.dataTransfer?.files || [])].find(isImage) || null;

const EMPTY = { reference: "", description: "", collection: "", price: "", sizes: DEFAULT_SIZES, color_ids: [], seller_ids: [], active: true, image_url: null };

// Admins manage the catalog; sellers only browse the products enabled for them (the API filters and blocks writes).
export default function Products() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [confirmDialog, ask] = useConfirm();
  const [list, setList] = useState(() => screenCache.get("products") || []);
  const [colors, setColors] = useState([]);
  const [sellers, setSellers] = useState([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [error, setError] = useState("");
  const [newSize, setNewSize] = useState("");
  const [colorSearch, setColorSearch] = useState("");
  const [colorKind, setColorKind] = useState("all"); // all | solid | combo
  const [newColor, setNewColor] = useState(null); // { name, hex, hex2 } while creating a color from the product form
  const [uploading, setUploading] = useState(false);
  const [zoom, setZoom] = useState(null); // { src, caption } of the photo shown enlarged
  const [dropTarget, setDropTarget] = useState(null); // product id (or "form") a photo is being dragged over
  const [sendingId, setSendingId] = useState(null); // product whose dropped photo is uploading
  const [listError, setListError] = useState("");
  // the price columns: admins see the registered price; a seller sees the table(s) they sell with
  const [pricing, setPricing] = useState({ tables: ["wholesale"], markup: 0 });

  const load = () => api.get("/products", { params: { search } }).then((r) => {
    setList(r.data);
    if (!search) screenCache.set("products", r.data); // only the unfiltered list is worth showing on return
  });
  useEffect(() => {
    if (!isAdmin) {  // the edit form's options aren't needed: sellers never open it
      api.get("/settings").then((r) => setPricing({ tables: r.data.price_tables, markup: r.data.retail_markup_percent }));
      return;
    }
    api.get("/colors").then((r) => setColors(r.data));
    api.get("/users").then((r) => setSellers(r.data));  // sellers and admins: an admin may be the only one enabled
  }, [isAdmin]);
  // A photo dropped outside a drop area would make the browser (and the desktop app) navigate to the file
  useEffect(() => {
    const block = (e) => e.preventDefault();
    window.addEventListener("dragover", block);
    window.addEventListener("drop", block);
    return () => { window.removeEventListener("dragover", block); window.removeEventListener("drop", block); };
  }, []);
  useEffect(() => { const t = setTimeout(load, search ? 250 : 0); return () => clearTimeout(t); }, [search]);

  function open(p) {
    setError("");
    setImageFile(null);
    setColorSearch("");
    setNewColor(null);
    setNewSize("");
    setForm(p ? { ...p, color_ids: p.colors.map((c) => c.id), seller_ids: p.seller_ids || [] } : EMPTY);
  }

  const toggle = (field, v) =>
    setForm((f) => ({ ...f, [field]: f[field].includes(v) ? f[field].filter((x) => x !== v) : [...f[field], v] }));

  function addSize() {
    if (newSize && !form.sizes.includes(newSize)) setForm((f) => ({ ...f, sizes: [...f.sizes, newSize] }));
    setNewSize("");
  }

  async function createColor() {
    if (!newColor?.name.trim()) return;
    try {
      const { data } = await api.post("/colors", { ...newColor, name: newColor.name.trim() });
      setColors((cs) => [...cs, data].sort((a, b) => a.name.localeCompare(b.name)));
      setForm((f) => ({ ...f, color_ids: [...f.color_ids, data.id] }));
      setNewColor(null);
      setColorSearch("");
    } catch (err) { setError(errorMessage(err)); }
  }

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

  // Dropping a photo on a row in the list uploads it straight away (replacing the current one)
  async function dropOnRow(e, p) {
    e.preventDefault();
    setDropTarget(null);
    const file = droppedImage(e);
    if (!file) return setListError("Solte um arquivo de imagem (JPEG, PNG ou WEBP).");
    setListError("");
    setSendingId(p.id);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post(`/products/${p.id}/image`, fd);
      await load();
    } catch (err) { setListError(`${p.reference}: ${errorMessage(err)}`); } finally { setSendingId(null); }
  }

  const dragProps = (target, onDrop) => ({
    onDragOver: (e) => { e.preventDefault(); if (dropTarget !== target) setDropTarget(target); },
    onDragLeave: (e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDropTarget(null); },
    onDrop,
  });

  async function remove() {
    if (!(await ask({ title: `Excluir ${form.reference} · ${form.description}?`, message: "O produto e a foto dele serão removidos.", confirmLabel: "Excluir", danger: true }))) return;
    try { await api.delete(`/products/${form.id}`); setForm(null); load(); }
    catch (err) { setError(errorMessage(err)); }
  }

  const { sorted, sortHeader } = useSort(list, {
    reference: (p) => p.reference,
    description: (p) => p.description,
    collection: (p) => p.collection,
    sizes: (p) => p.sizes.length,
    colors: (p) => p.colors.length,
    price: (p) => p.price,
  });

  const pickedColors = colors.filter((c) => form?.color_ids.includes(c.id));
  // solid colors first, then two-tone combos
  const shownColors = colors
    .filter((c) => colorKind === "all" || (colorKind === "combo") === !!c.hex2)
    .filter((c) => normalize(c.name).includes(normalize(colorSearch)))
    .sort((a, b) => !!a.hex2 - !!b.hex2);
  const sizeOptions = sortSizes(new Set([...DEFAULT_SIZES, "XG", ...(form?.sizes || [])]));
  // the small version for the preview box; the full-size photo for zoom
  const fileBlob = imageFile ? URL.createObjectURL(imageFile) : null;
  const previewUrl = fileBlob || fileUrl(form?.thumb_url);
  const fullUrl = fileBlob || fileUrl(form?.image_url);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Produtos</h1>
        <div className="header-search-group">
          <input className="header-search" placeholder="Buscar por referência, nome ou coleção" value={search} onChange={(e) => setSearch(e.target.value)} />
          {isAdmin && <button className="btn btn-primary" onClick={() => open(null)}>Cadastrar produto</button>}
        </div>
      </header>
      {isAdmin && list.length > 0 && <p className="muted drop-hint">Dica: arraste uma foto do computador para cima de um produto para adicioná-la.</p>}
      <ErrorBox msg={listError} />
      {!list.length ? <EmptyState text="Nenhum produto cadastrado." /> : (
        <table className="table table-products">
          <thead>
            <tr>
              <th></th>
              {sortHeader("reference", "Ref.")}
              {sortHeader("description", "Descrição")}
              {sortHeader("collection", "Coleção")}
              {sortHeader("sizes", "Tamanhos")}
              {sortHeader("colors", "Cores")}
              {pricing.tables.length === 1
                ? sortHeader("price", "Preço", "num")
                : pricing.tables.map((t) => <th key={t} className="num">{t === "retail" ? "Varejo" : "Atacado"}</th>)}
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <tr key={p.id} className={`${isAdmin ? "clickable" : ""} ${p.active ? "" : "inactive"} ${dropTarget === p.id ? "drop-over" : ""}`}
                {...(isAdmin && { onClick: () => open(p), ...dragProps(p.id, (e) => dropOnRow(e, p)) })}>
                <td>
                  {sendingId === p.id
                    ? <span className="product-thumb product-thumb-empty" aria-label="Enviando foto">⏳</span>
                    : p.image_url
                    ? <img className="product-thumb zoomable" src={fileUrl(p.thumb_url)} alt={`Ampliar foto ${p.reference}`} loading="lazy"
                        onClick={(e) => { e.stopPropagation(); setZoom({ src: fileUrl(p.image_url), caption: `${p.reference} · ${p.description}` }); }} />
                    : <span className="product-thumb product-thumb-empty" aria-hidden="true">🧶</span>}
                </td>
                <td className="ref">{p.reference}</td>
                <td>{p.description}{!p.active && <span className="tag">inativo</span>}
                  {p.seller_ids?.length > 0 && <span className="tag" title="Disponível só para alguns vendedores">exclusivo</span>}</td>
                <td>{p.collection}</td>
                <td>{p.sizes.join(" ")}</td>
                <td><span className="swatches">{p.colors.map((c) => <Swatch key={c.id} hex={c.hex} hex2={c.hex2} />)}</span></td>
                {pricing.tables.map((t) => <td key={t} className="num">{money(tablePrice(p.price, t, pricing.markup))}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {form && (
        <Modal title={form.id ? `Editar ${form.reference}` : "Cadastrar produto"} onClose={() => setForm(null)} wide>
          <form onSubmit={save} className="product-form">
            <div className="product-form-top">
              <div className={`product-image-field ${dropTarget === "form" ? "drop-over" : ""}`}
                {...dragProps("form", (e) => {
                  e.preventDefault();
                  setDropTarget(null);
                  const file = droppedImage(e);
                  if (file) setImageFile(file); else setError("Solte um arquivo de imagem (JPEG, PNG ou WEBP).");
                })}>
                {previewUrl
                  ? <img className="product-image-preview zoomable" src={previewUrl} alt="Pré-visualização (clique para ampliar)"
                      onClick={() => setZoom({ src: fullUrl, caption: form.reference ? `${form.reference} · ${form.description}` : "" })} />
                  : <div className="product-image-preview product-image-empty" aria-hidden="true">🧶</div>}
                <div className="product-image-actions">
                  <label className="btn btn-light">
                    {previewUrl ? "Trocar foto" : "Escolher foto"}
                    <input type="file" accept="image/*,.jpg,.jpeg,.jfif,.png,.webp" hidden
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
                      Remover
                    </button>
                  )}
                  <small className="muted">ou arraste a foto para cá</small>
                </div>
              </div>

              <div className="form-grid">
                <Field label="Referência"><input required value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></Field>
                <Field label="Preço (R$)"><input type="number" step="0.01" min="0" required value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} /></Field>
                <Field label="Descrição" span={2}><input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
                <Field label="Coleção" span={2}><input value={form.collection || ""} onChange={(e) => setForm({ ...form, collection: e.target.value })} placeholder="Ex.: Inverno 2027" /></Field>
              </div>
            </div>

            <section className="form-section">
              <h3>Tamanhos <small className="muted">{form.sizes.length ? sortSizes(form.sizes).join(" · ") : "nenhum marcado"}</small></h3>
              <div className="chips">
                {sizeOptions.map((t) => (
                  <button type="button" key={t} className={`chip ${form.sizes.includes(t) ? "on" : ""}`} onClick={() => toggle("sizes", t)}>{t}</button>
                ))}
                <input className="chip-input" placeholder="Novo" value={newSize} maxLength={5} aria-label="Novo tamanho"
                  onChange={(e) => setNewSize(e.target.value.toUpperCase().trim())}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addSize(); } }} />
                <button type="button" className="chip" onClick={addSize} disabled={!newSize}>+ Adicionar tamanho</button>
              </div>
            </section>

            <section className="form-section">
              <h3>Cores <small className="muted">{form.color_ids.length ? `${form.color_ids.length} selecionada${form.color_ids.length > 1 ? "s" : ""}` : "nenhuma selecionada"}</small></h3>
              {pickedColors.length > 0 && (
                <div className="chips">
                  {pickedColors.map((c) => (
                    <span key={c.id} className="chip on">
                      <Swatch hex={c.hex} hex2={c.hex2} size={16} /> {c.name}
                      <button type="button" className="chip-remove" aria-label={`Remover ${c.name}`} onClick={() => toggle("color_ids", c.id)}>×</button>
                    </span>
                  ))}
                </div>
              )}
              <div className="color-picker">
                <div className="color-picker-bar">
                  <div className="segmented">
                    {[["all", "Todas"], ["solid", "Lisas"], ["combo", "Combinações"]].map(([k, label]) => (
                      <button type="button" key={k} className={colorKind === k ? "on" : ""} onClick={() => setColorKind(k)}>{label}</button>
                    ))}
                  </div>
                  <input type="search" placeholder="Buscar cor pelo nome ou código" value={colorSearch} onChange={(e) => setColorSearch(e.target.value)} />
                  {shownColors.length > 0 && (
                    <button type="button" className="btn btn-light" onClick={() => setForm((f) => ({ ...f, color_ids: [...new Set([...f.color_ids, ...shownColors.map((c) => c.id)])] }))}>
                      Marcar todas
                    </button>
                  )}
                  {form.color_ids.length > 0 && <button type="button" className="btn btn-light" onClick={() => setForm((f) => ({ ...f, color_ids: [] }))}>Limpar</button>}
                </div>
                <div className="color-options">
                  {shownColors.map((c) => {
                    const on = form.color_ids.includes(c.id);
                    return (
                      <button type="button" key={c.id} className={`color-option ${on ? "on" : ""}`} aria-pressed={on} onClick={() => toggle("color_ids", c.id)}>
                        <Swatch hex={c.hex} hex2={c.hex2} size={22} />
                        <span>{c.name}</span>
                        {on && <span className="color-option-check" aria-hidden="true">✓</span>}
                      </button>
                    );
                  })}
                  {!shownColors.length && <p className="muted">{colors.length ? "Nenhuma cor encontrada." : "Nenhuma cor cadastrada ainda."}</p>}
                </div>
                {newColor ? (
                  <div className="color-new">
                    <input type="color" value={newColor.hex} onChange={(e) => setNewColor({ ...newColor, hex: e.target.value })} aria-label="Cor" />
                    {newColor.hex2 != null && <input type="color" value={newColor.hex2} onChange={(e) => setNewColor({ ...newColor, hex2: e.target.value })} aria-label="Segunda cor" />}
                    <input placeholder="Nome da cor (ex.: 09 Bordô)" value={newColor.name} autoFocus
                      onChange={(e) => setNewColor({ ...newColor, name: e.target.value })}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); createColor(); } if (e.key === "Escape") setNewColor(null); }} />
                    <label className="check"><input type="checkbox" checked={newColor.hex2 != null}
                      onChange={(e) => setNewColor({ ...newColor, hex2: e.target.checked ? "#ffffff" : null })} /> Bicolor</label>
                    <button type="button" className="btn btn-primary" onClick={createColor} disabled={!newColor.name.trim()}>Criar e marcar</button>
                    <button type="button" className="btn btn-light" onClick={() => setNewColor(null)}>Cancelar</button>
                  </div>
                ) : (
                  <button type="button" className="btn btn-light color-new-btn" onClick={() => setNewColor({ name: colorSearch.trim(), hex: "#cccccc", hex2: null })}>
                    + Nova cor{colorSearch.trim() && ` “${colorSearch.trim()}”`}
                  </button>
                )}
              </div>
            </section>

            {sellers.length > 0 && (
              <details className="form-section" open={form.seller_ids.length > 0}>
                <summary>
                  <h3>Disponível para <small className="muted">
                    {form.seller_ids.length ? `${form.seller_ids.length} vendedor${form.seller_ids.length > 1 ? "es" : ""}` : "todos os vendedores"}
                  </small></h3>
                </summary>
                <div className="chips">
                  {/* inactive users only if already picked, so they can still be unchecked */}
                  {sellers.filter((u) => u.active || form.seller_ids.includes(u.id)).map((u) => (
                    <button type="button" key={u.id} className={`chip ${form.seller_ids.includes(u.id) ? "on" : ""}`}
                      onClick={() => toggle("seller_ids", u.id)}>{u.name}{u.role === "admin" && " (admin)"}{!u.active && " (inativo)"}</button>
                  ))}
                </div>
                <small className="muted">
                  {form.seller_ids.length ? "Só quem está marcado pode vender este produto." : "Nenhum marcado: todos podem vender."}
                </small>
              </details>
            )}

            <ErrorBox msg={error} />
            <div className="actions product-form-footer">
              <label className="check">
                <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
                Disponível para venda
              </label>
              {form.id && <button type="button" className="btn danger" onClick={remove}>Excluir</button>}
              <button className="btn btn-primary" disabled={uploading}>{uploading ? "Salvando..." : "Salvar produto"}</button>
            </div>
          </form>
        </Modal>
      )}

      {zoom && <PhotoZoom {...zoom} onClose={() => setZoom(null)} />}
      {confirmDialog}
    </div>
  );
}
