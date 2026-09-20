import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { money, orderNumber } from "../format";
import { Field, ErrorBox, Modal, Swatch } from "../components/ui";
import { EditIcon, PlusIcon } from "../components/icons";

const key = (i) => `${i.color_id}|${i.size}`;
const customerLabel = (c) => `${c.name}${c.city ? ` — ${c.city}/${c.state || ""}` : ""}`;

const EMPTY_CUSTOMER = { name: "", document: "", phone: "", email: "", city: "", state: "", address: "", notes: "", owner_id: "" };
const PAYMENT_METHODS = ["Dinheiro", "Pix", "Boleto"];
const PAYMENT_TERMS = ["À vista", "30/60", "30/60/90", "30/60/90/120", "30/60/90/120/150", "Quinzenal", "A combinar"];

// Color × size grid for a product: the core of placing an order
function QuantityGrid({ product, initial, initialPrice, canEditPrice, onSave, onCancel }) {
  const [qty, setQty] = useState(() => Object.fromEntries(initial.map((i) => [key(i), i.quantity])));
  const [price, setPrice] = useState(initialPrice ?? product.price);

  const totalPieces = Object.values(qty).reduce((s, v) => s + (Number(v) || 0), 0);
  const set = (k, v) => setQty((q) => ({ ...q, [k]: v.replace(/\D/g, "") }));

  function save() {
    const items = [];
    for (const color of product.colors)
      for (const t of product.sizes) {
        const q = Number(qty[`${color.id}|${t}`]) || 0;
        if (q > 0) items.push({
          product_id: product.id, color_id: color.id, size: t, quantity: q,
          unit_price: Number(price) || 0, product_reference: product.reference,
          product_description: product.description, color_name: color.name, color_hex: color.hex,
        });
      }
    onSave(items);
  }

  if (!product.colors.length)
    return <p className="error-message">Este produto não tem cores cadastradas. Vincule cores em Produtos.</p>;

  return (
    <div className="qty-grid">
      <div className="qty-grid-header">
        <div>
          <span className="ref">{product.reference}</span> {product.description}
        </div>
        <label className="qty-grid-price">
          Preço unitário
          {canEditPrice
            ? <input type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)} />
            : <strong>{money(price)}</strong>}
        </label>
      </div>
      <div className="scroll-area">
        <table className="qty-grid-table">
          <thead>
            <tr><th>Cor</th>{product.sizes.map((t) => <th key={t}>{t}</th>)}<th>Total</th></tr>
          </thead>
          <tbody>
            {product.colors.map((c) => {
              const rowTotal = product.sizes.reduce((s, t) => s + (Number(qty[`${c.id}|${t}`]) || 0), 0);
              return (
                <tr key={c.id}>
                  <td className="qty-grid-color"><Swatch hex={c.hex} size={16} /> {c.name}</td>
                  {product.sizes.map((t) => (
                    <td key={t}>
                      <input inputMode="numeric" className="qty-input" value={qty[`${c.id}|${t}`] || ""}
                        onChange={(e) => set(`${c.id}|${t}`, e.target.value)} placeholder="·" aria-label={`${c.name} ${t}`} />
                    </td>
                  ))}
                  <td className="qty-total">{rowTotal || ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="qty-grid-footer">
        <span>{totalPieces} peças · {money(totalPieces * (Number(price) || 0))}</span>
        <div className="actions">
          <button type="button" className="btn" onClick={onCancel}>Cancelar</button>
          <button type="button" className="btn btn-primary" onClick={save}>Salvar grade</button>
        </div>
      </div>
    </div>
  );
}

// Full customer form, used both to create and to edit without leaving the order
function CustomerForm({ customer, onSaved, onClose, isAdmin, sellers }) {
  const [f, setF] = useState(() => (customer ? { ...customer, owner_id: customer.owner_id || "" } : { ...EMPTY_CUSTOMER }));
  const [error, setError] = useState("");
  const editing = Boolean(customer?.id);

  async function save(e) {
    e.preventDefault();
    setError("");
    const body = { ...f, state: f.state ? f.state.toUpperCase() : null, owner_id: f.owner_id ? Number(f.owner_id) : null };
    try {
      const { data } = editing
        ? await api.put(`/customers/${customer.id}`, body)
        : await api.post("/customers", body);
      onSaved(data);
    } catch (err) { setError(errorMessage(err)); }
  }

  const field = (k) => ({ value: f[k] || "", onChange: (e) => setF({ ...f, [k]: e.target.value }) });

  return (
    <Modal title={editing ? `Editar cliente — ${customer.name}` : "Cadastrar cliente"} onClose={onClose} wide>
      <form onSubmit={save} className="form-grid">
        <Field label="Nome / razão social" span={2}><input required autoFocus {...field("name")} /></Field>
        <Field label="CPF/CNPJ" span={2}><input required {...field("document")} /></Field>
        {isAdmin && (
          <Field label="Vendedor responsável" span={2}>
            <select required {...field("owner_id")}>
              <option value="">Selecione o vendedor</option>
              {sellers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
        )}
        <Field label="Telefone"><input {...field("phone")} /></Field>
        <Field label="E-mail"><input type="email" {...field("email")} /></Field>
        <Field label="Cidade / UF" span={2}>
          <div className="city-row">
            <input placeholder="Cidade" {...field("city")} />
            <input placeholder="UF" maxLength={2} className="uf-input" {...field("state")} />
          </div>
        </Field>
        <Field label="Endereço" span={2}><input {...field("address")} /></Field>
        <Field label="Observações do cliente" span={2}><textarea rows={2} {...field("notes")} /></Field>
        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2">
          <button className="btn btn-primary">{editing ? "Salvar alterações" : "Cadastrar cliente"}</button>
        </div>
      </form>
    </Modal>
  );
}

// Searchable customer field: types ahead instead of a giant <select>, since there can be many.
function CustomerSearch({ customers, value, onSelect }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (value && !query) {
      const c = customers.find((x) => x.id === Number(value));
      if (c) setQuery(customerLabel(c));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customers, value]);

  const matches = query
    ? customers.filter((c) => `${c.name} ${c.document || ""}`.toLowerCase().includes(query.toLowerCase())).slice(0, 8)
    : [];

  function pick(c) {
    setQuery(customerLabel(c));
    setOpen(false);
    onSelect(c, customerLabel(c));
  }

  return (
    <div className="customer-search">
      <input placeholder="Buscar cliente por nome ou CNPJ" value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); onSelect(null); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)} />
      {open && query && (
        <ul className="customer-search-list">
          {matches.length ? matches.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => pick(c)}>
                <strong>{c.name}</strong>
                <span className="muted"> {c.document ? `· ${c.document}` : ""} {c.city ? `— ${c.city}/${c.state || ""}` : ""}</span>
              </button>
            </li>
          )) : <li className="customer-search-empty muted">Nenhum cliente encontrado.</li>}
        </ul>
      )}
    </div>
  );
}

export default function OrderForm() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [customers, setCustomers] = useState([]);
  const [sellers, setSellers] = useState([]);
  const [products, setProducts] = useState([]);
  const [header, setHeader] = useState({
    customer_id: "", date: new Date().toISOString().slice(0, 10), delivery_date: "",
    status: "confirmed", payment_method: "", payment_terms: "", discount: 0, notes: "",
  });
  const [customerKey, setCustomerKey] = useState(0); // forces CustomerSearch to resync its label after a save
  const [items, setItems] = useState([]);
  const [productModal, setProductModal] = useState(false);
  const [modalSearch, setModalSearch] = useState("");
  const [editing, setEditing] = useState(null); // product open in the quantity grid, inside the modal
  const [customerModal, setCustomerModal] = useState(null); // null | "new" | {customer}
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const hasUnsavedChanges = !saved && (Boolean(header.customer_id) || items.length > 0);

  // Warn before closing the window/app with an unsaved order in progress.
  useEffect(() => {
    function handler(e) {
      if (!hasUnsavedChanges) return;
      e.preventDefault();
      e.returnValue = "";
    }
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsavedChanges]);

  function goBack() {
    if (hasUnsavedChanges && !confirm("Deseja realmente sair? O pedido não será salvo.")) return;
    nav(-1);
  }

  useEffect(() => {
    api.get("/customers").then((r) => setCustomers(r.data));
    api.get("/products", { params: { active_only: true } }).then((r) => setProducts(r.data));
    if (isAdmin) api.get("/users").then((r) => setSellers(r.data));
    if (id) api.get(`/orders/${id}`).then(({ data }) => {
      setHeader({
        customer_id: data.customer_id, date: data.date, delivery_date: data.delivery_date || "",
        status: data.status, payment_method: data.payment_method || "",
        payment_terms: data.payment_terms || "", discount: data.discount, notes: data.notes || "",
      });
      setItems(data.items);
    });
  }, [id]);

  const groups = useMemo(() => {
    const g = {};
    for (const i of items) (g[i.product_id] ||= []).push(i);
    return g;
  }, [items]);

  const gross = items.reduce((s, i) => s + i.quantity * i.unit_price, 0);
  const pieces = items.reduce((s, i) => s + i.quantity, 0);
  const total = gross - (Number(header.discount) || 0);

  const selectedCustomer = customers.find((c) => c.id === Number(header.customer_id));

  const filteredProducts = modalSearch
    ? products.filter((p) => `${p.reference} ${p.description}`.toLowerCase().includes(modalSearch.toLowerCase()))
    : products;

  function openNewProductModal() {
    setEditing(null);
    setModalSearch("");
    setProductModal(true);
  }

  async function openExistingGrid(pid) {
    const p = products.find((x) => x.id === pid) || (await api.get(`/products/${pid}`)).data;
    setEditing(p);
    setProductModal(true);
  }

  function closeProductModal() {
    setProductModal(false);
    setEditing(null);
    setModalSearch("");
  }

  function saveGrid(newItems) {
    setItems((cur) => [...cur.filter((i) => i.product_id !== editing.id), ...newItems]);
    closeProductModal();
  }

  async function save() {
    setError("");
    if (!header.customer_id) return setError("Escolha o cliente.");
    if (!header.delivery_date) return setError("Informe a data de entrega.");
    if (!header.payment_method) return setError("Selecione a forma de pagamento.");
    if (!header.payment_terms) return setError("Selecione o prazo de pagamento.");
    if (!items.length) return setError("Adicione ao menos um produto.");
    setSaving(true);
    const body = {
      ...header, customer_id: Number(header.customer_id), discount: Number(header.discount) || 0,
      items: items.map(({ product_id, color_id, size, quantity, unit_price }) =>
        ({ product_id, color_id, size, quantity, unit_price })),
    };
    try {
      const { data } = id ? await api.put(`/orders/${id}`, body) : await api.post("/orders", body);
      setSaved(true);
      // Sellers don't have access to the order detail screen — send them back to their dashboard.
      nav(isAdmin ? `/orders/${data.id}` : "/");
    } catch (e) { setError(errorMessage(e)); setSaving(false); }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>{id ? `Editar pedido ${orderNumber(id)}` : "Novo pedido"}</h1>
      </header>

      <section className="panel form-grid form-order">
        <Field label="Cliente" span={2}>
          <div className="customer-row">
            <CustomerSearch key={customerKey} customers={customers} value={header.customer_id}
              onSelect={(c) => setHeader((h) => ({ ...h, customer_id: c ? c.id : "" }))} />
            <button type="button" className="btn icon-btn" title="Cadastrar novo cliente" onClick={() => setCustomerModal("new")}>
              <PlusIcon />
            </button>
            {selectedCustomer && (
              <button type="button" className="btn icon-btn" title="Editar dados do cliente" onClick={() => setCustomerModal(selectedCustomer)}>
                <EditIcon />
              </button>
            )}
          </div>
        </Field>
        <Field label="Data do pedido"><input type="date" value={header.date} onChange={(e) => setHeader({ ...header, date: e.target.value })} /></Field>

        <Field label="Data de entrega">
          <input type="date" required value={header.delivery_date} onChange={(e) => setHeader({ ...header, delivery_date: e.target.value })} />
        </Field>
        <Field label="Forma de pagamento">
          <select required value={header.payment_method} onChange={(e) => setHeader({ ...header, payment_method: e.target.value })}>
            <option value="">Selecione</option>
            {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </Field>
        <Field label="Prazo / condição de pagamento">
          <select required value={header.payment_terms} onChange={(e) => setHeader({ ...header, payment_terms: e.target.value })}>
            <option value="">Selecione</option>
            {PAYMENT_TERMS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Produtos</h3>
          <button type="button" className="btn btn-primary" onClick={openNewProductModal}>+ Adicionar produto</button>
        </div>

        {!Object.keys(groups).length && <p className="muted">Nenhum produto adicionado ainda.</p>}

        {Object.entries(groups).map(([pid, lines]) => {
          const sizes = [...new Set(lines.map((l) => l.size))];
          const colors = [...new Map(lines.map((l) => [l.color_id, l])).values()];
          const q = (c, t) => lines.find((l) => l.color_id === c && l.size === t)?.quantity;
          const subtotal = lines.reduce((s, l) => s + l.quantity * l.unit_price, 0);
          return (
            <div key={pid} className="item-group">
              <div className="item-group-header">
                <div><span className="ref">{lines[0].product_reference}</span> {lines[0].product_description}
                  <span className="muted"> · {money(lines[0].unit_price)} un.</span></div>
                <div className="actions">
                  <button type="button" className="btn btn-light" onClick={() => openExistingGrid(Number(pid))}>Editar grade</button>
                  <button type="button" className="btn btn-light danger"
                    onClick={() => setItems((a) => a.filter((i) => i.product_id !== Number(pid)))}>Remover</button>
                </div>
              </div>
              <table className="table table-compact">
                <thead><tr><th>Cor</th>{sizes.map((t) => <th key={t} className="num">{t}</th>)}</tr></thead>
                <tbody>
                  {colors.map((c) => (
                    <tr key={c.color_id}>
                      <td><Swatch hex={c.color_hex} /> {c.color_name}</td>
                      {sizes.map((t) => <td key={t} className="num">{q(c.color_id, t) || "–"}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="item-group-subtotal">{lines.reduce((s, l) => s + l.quantity, 0)} peças · {money(subtotal)}</div>
            </div>
          );
        })}
      </section>

      <section className="panel order-summary">
        <Field label="Observações">
          <textarea rows={3} value={header.notes} onChange={(e) => setHeader({ ...header, notes: e.target.value })}
            placeholder="Detalhes de envio, combinações extras..." />
        </Field>
        <div className="totals">
          <div><span>Peças</span><strong>{pieces}</strong></div>
          <div><span>Subtotal</span><strong>{money(gross)}</strong></div>
          <div>
            <span>Desconto (R$)</span>
            <input type="number" min="0" step="0.01" value={header.discount} onChange={(e) => setHeader({ ...header, discount: e.target.value })} />
          </div>
          <div className="grand-total"><span>Total</span><strong>{money(total)}</strong></div>
        </div>
      </section>

      <ErrorBox msg={error} />
      <div className="actions actions-end">
        <button className="btn" onClick={goBack}>Voltar</button>
        <button className="btn btn-primary" disabled={saving} onClick={save}>
          {saving ? "Salvando..." : id ? "Salvar alterações" : "Salvar pedido"}
        </button>
      </div>

      {productModal && (
        <Modal title={editing ? `Grade — ${editing.reference} · ${editing.description}` : "Adicionar produto ao pedido"}
          onClose={closeProductModal} wide>
          {!editing ? (
            <>
              <input placeholder="Buscar por referência ou descrição" value={modalSearch}
                onChange={(e) => setModalSearch(e.target.value)} autoFocus />
              <div className="product-grid">
                {filteredProducts.length ? filteredProducts.map((p) => {
                  const added = Boolean(groups[p.id]);
                  return (
                    <button key={p.id} type="button" className={`product-card ${added ? "added" : ""}`}
                      onClick={() => setEditing(p)}>
                      <div className="product-card-header">
                        <span className="ref">{p.reference}</span>
                        <span className="product-card-price">{money(p.price)}</span>
                      </div>
                      <div className="product-card-desc">{p.description}</div>
                      <div className="product-card-footer">
                        <span className="product-card-colors">
                          {p.colors.slice(0, 6).map((c) => <Swatch key={c.id} hex={c.hex} size={13} />)}
                        </span>
                        {added ? <span className="tag">no pedido</span> : p.collection ? <span className="muted">{p.collection}</span> : null}
                      </div>
                    </button>
                  );
                }) : <p className="muted">Nenhum produto encontrado.</p>}
              </div>
            </>
          ) : (
            <>
              <button type="button" className="modal-back" onClick={() => setEditing(null)}>← Escolher outro produto</button>
              <QuantityGrid product={editing} initial={groups[editing.id] || []}
                initialPrice={groups[editing.id]?.[0]?.unit_price} canEditPrice={isAdmin}
                onSave={saveGrid} onCancel={closeProductModal} />
            </>
          )}
        </Modal>
      )}

      {customerModal && (
        <CustomerForm customer={customerModal === "new" ? null : customerModal}
          isAdmin={isAdmin} sellers={sellers}
          onClose={() => setCustomerModal(null)}
          onSaved={(c) => {
            setCustomers((l) => [...l.filter((x) => x.id !== c.id), c].sort((a, b) => a.name.localeCompare(b.name)));
            setHeader((x) => ({ ...x, customer_id: c.id }));
            setCustomerKey((k) => k + 1);
            setCustomerModal(null);
          }} />
      )}
    </div>
  );
}
