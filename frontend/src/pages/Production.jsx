import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { dateBR } from "../format";
import { ErrorBox, Avatar } from "../components/ui";

const today = () => new Date().toISOString().slice(0, 10);
const diffDays = (a, b) => Math.round((new Date(`${a}T00:00:00`) - new Date(`${b}T00:00:00`)) / 86400000);

const COLUMNS = [
  { status: "confirmed", label: "Confirmado", color: "#2f6fed" },
  { status: "in_production", label: "Em produção", color: "#b8862f" },
  { status: "shipped", label: "Enviado", color: "#0d95ac" },
  { status: "delivered", label: "Entregue", color: "#1c7a52" },
];

// How urgent a ticket is, based on how close (or overdue) its delivery date is:
// 2+ weeks away = neutral, 1–2 weeks = amber, under a week (or overdue) = red.
function urgency(deliveryDate, status) {
  if (!deliveryDate || status === "delivered") return "none";
  const days = diffDays(deliveryDate, today());
  if (days < 7) return "red";
  if (days < 14) return "amber";
  return "none";
}

// Buckets tickets within a column by how close the delivery date is, for extra organization.
function bucketOf(deliveryDate) {
  if (!deliveryDate) return "none";
  const days = diffDays(deliveryDate, today());
  if (days < 0) return "overdue";
  if (days < 7) return "week";
  if (days < 14) return "twoWeeks";
  return "later";
}
const BUCKET_ORDER = ["overdue", "week", "twoWeeks", "later", "none"];
const BUCKET_LABEL = {
  overdue: "Atrasados", week: "Esta semana", twoWeeks: "Próximas 2 semanas",
  later: "Mais adiante", none: "Sem data de entrega",
};

function groupSorted(orders) {
  const buckets = {};
  for (const o of orders) (buckets[bucketOf(o.delivery_date)] ||= []).push(o);
  for (const k in buckets) buckets[k].sort((a, b) => (a.delivery_date || "9999").localeCompare(b.delivery_date || "9999"));
  return BUCKET_ORDER.map((k) => ({ key: k, label: BUCKET_LABEL[k], items: buckets[k] || [] })).filter((g) => g.items.length);
}

// Drag payload: "order:12" or "batch:3"
const dragged = (e) => {
  const [kind, id] = e.dataTransfer.getData("text/plain").split(":");
  return { kind, id: Number(id) };
};

function Ticket({ o, onOpen }) {
  const u = urgency(o.delivery_date, o.status);
  return (
    <div className={`ticket ticket-${u}`} draggable
      onDragStart={(e) => { e.stopPropagation(); e.dataTransfer.setData("text/plain", `order:${o.id}`); e.dataTransfer.effectAllowed = "move"; }}
      onClick={() => onOpen(o.id)}>
      <div className="ticket-top">
        <div className="ticket-customer-block">
          <span className="ticket-customer">{o.customer_name}</span>
          {o.customer_city && (
            <span className="ticket-city">{o.customer_city}{o.customer_state ? `/${o.customer_state}` : ""}</span>
          )}
        </div>
        <Avatar url={o.seller_avatar_url} name={o.seller_name} size="sm" />
      </div>
      <div className="ticket-delivery-row">
        <span className="ticket-delivery">
          {o.delivery_date ? dateBR(o.delivery_date) : "Sem data de entrega"}
        </span>
        <span className="ticket-pieces">{o.pieces} peças</span>
      </div>
    </div>
  );
}

export default function Production() {
  const nav = useNavigate();
  const [orders, setOrders] = useState([]);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [dragOverCol, setDragOverCol] = useState(null);
  const [dragOverBatch, setDragOverBatch] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set()); // batches start collapsed: that's what saves room
  const [newName, setNewName] = useState(null); // null = the "Novo lote" form is closed
  const [renaming, setRenaming] = useState(null); // { id, name } while a batch's name is being edited

  const load = () => Promise.all([api.get("/orders"), api.get("/batches")])
    .then(([o, b]) => { setOrders(o.data); setBatches(b.data); setError(""); })
    .catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);
  // Updates are optimistic; when the server refuses one, show why and reload the real board
  const fail = (e) => { setError(errorMessage(e)); load(); };

  const byColumn = useMemo(() => {
    const map = {};
    for (const col of COLUMNS) map[col.status] = orders.filter((o) => o.status === col.status);
    return map;
  }, [orders]);

  const open = (id) => nav(`/orders/${id}`, { state: { back: { to: "/production", label: "Produção" } } });

  async function changeStatus(o, status) {
    // moved on its own out of its batch's column, it leaves the batch (the server does the same)
    const stays = batches.some((b) => b.id === o.batch_id && b.status === status);
    setOrders((list) => list.map((x) => (x.id === o.id ? { ...x, status, batch_id: stays ? x.batch_id : null } : x)));
    try { await api.patch(`/orders/${o.id}/status`, { status }); } catch (e) { fail(e); }
  }

  async function setBatch(o, batch) {
    setOrders((list) => list.map((x) => (x.id === o.id
      ? { ...x, batch_id: batch?.id ?? null, batch_name: batch?.name ?? null, status: batch?.status ?? x.status } : x)));
    try { await api.put(`/orders/${o.id}/batch`, { batch_id: batch?.id ?? null }); } catch (e) { fail(e); }
  }

  async function moveBatch(b, status) {
    setBatches((list) => list.map((x) => (x.id === b.id ? { ...x, status } : x)));
    setOrders((list) => list.map((o) => (o.batch_id === b.id ? { ...o, status } : o)));
    try { await api.patch(`/batches/${b.id}`, { status }); } catch (e) { fail(e); }
  }

  async function createBatch(e) {
    e.preventDefault();
    try {
      const { data } = await api.post("/batches", { name: newName.trim() });
      setBatches((list) => [...list, data]);
      setExpanded((s) => new Set(s).add(data.id)); // open, ready to receive tickets
      setNewName(null);
    } catch (err) { setError(errorMessage(err)); }
  }

  async function rename(e) {
    e.preventDefault();
    if (!renaming) return; // Enter already saved; this is the blur of the input going away
    const { id, name } = renaming;
    setRenaming(null);
    if (!name.trim() || name.trim() === batches.find((x) => x.id === id)?.name) return;
    setBatches((list) => list.map((x) => (x.id === id ? { ...x, name: name.trim() } : x)));
    setOrders((list) => list.map((o) => (o.batch_id === id ? { ...o, batch_name: name.trim() } : o)));
    try { await api.patch(`/batches/${id}`, { name: name.trim() }); } catch (err) { fail(err); }
  }

  async function ungroup(b) {
    setBatches((list) => list.filter((x) => x.id !== b.id));
    setOrders((list) => list.map((o) => (o.batch_id === b.id ? { ...o, batch_id: null, batch_name: null } : o)));
    try { await api.delete(`/batches/${b.id}`); } catch (e) { fail(e); }
  }

  const toggle = (id) => setExpanded((s) => {
    const next = new Set(s);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  function onDropColumn(e, status) {
    e.preventDefault();
    setDragOverCol(null);
    const { kind, id } = dragged(e);
    if (kind === "batch") {
      const b = batches.find((x) => x.id === id);
      if (b && b.status !== status) moveBatch(b, status);
      return;
    }
    const o = orders.find((x) => x.id === id);
    if (!o) return;
    if (o.status !== status) changeStatus(o, status);
    else if (o.batch_id) setBatch(o, null); // dropped loose in its own column: just leaves the batch
  }

  function onDropBatch(e, b) {
    e.preventDefault();
    e.stopPropagation(); // the column underneath must not handle it too
    setDragOverBatch(null);
    setDragOverCol(null);
    const { kind, id } = dragged(e);
    const o = kind === "order" && orders.find((x) => x.id === id);
    if (o && o.batch_id !== b.id) setBatch(o, b);
  }

  return (
    <div className="page page-wide">
      <header className="page-header">
        <div>
          <h1>Gestão de produção</h1>
          <p className="muted">Arraste os pedidos entre colunas ou para um lote. Amarelo: entrega em 2 semanas · vermelho: em 1 semana ou atrasado.</p>
        </div>
        {newName === null ? (
          <button className="btn btn-primary" onClick={() => setNewName("")}>Novo lote</button>
        ) : (
          <form className="batch-form" onSubmit={createBatch}>
            <input autoFocus placeholder="Nome do lote" maxLength={80} value={newName} onChange={(e) => setNewName(e.target.value)} />
            <button className="btn btn-primary" disabled={!newName.trim()}>Criar</button>
            <button type="button" className="btn" onClick={() => setNewName(null)}>Cancelar</button>
          </form>
        )}
      </header>
      <ErrorBox msg={error} />

      <div className="board">
        {COLUMNS.map((col) => {
          const list = byColumn[col.status] || [];
          const colBatches = batches.filter((b) => b.status === col.status)
            .map((b) => ({ ...b, items: list.filter((o) => o.batch_id === b.id) }));
          const inBatch = new Set(colBatches.flatMap((b) => b.items.map((o) => o.id)));
          const groups = groupSorted(list.filter((o) => !inBatch.has(o.id)));
          return (
            <div key={col.status} className={`board-column ${dragOverCol === col.status ? "drag-over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragOverCol(col.status); }}
              onDragLeave={() => setDragOverCol((c) => (c === col.status ? null : c))}
              onDrop={(e) => onDropColumn(e, col.status)}>
              <div className="board-column-header" style={{ borderTopColor: col.color }}>
                <span>{col.label}</span>
                <span className="board-column-count">{list.length}</span>
              </div>
              <div className="board-column-body">
                {!list.length && !colBatches.length && <p className="muted board-empty">Nenhum pedido aqui.</p>}
                {colBatches.map((b) => {
                  const isOpen = expanded.has(b.id);
                  return (
                    <div key={b.id} className={`batch ${dragOverBatch === b.id ? "drag-over" : ""}`} draggable={renaming?.id !== b.id}
                      onDragStart={(e) => { e.dataTransfer.setData("text/plain", `batch:${b.id}`); e.dataTransfer.effectAllowed = "move"; }}
                      onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragOverBatch(b.id); setDragOverCol(null); }}
                      onDragLeave={() => setDragOverBatch((x) => (x === b.id ? null : x))}
                      onDrop={(e) => onDropBatch(e, b)}>
                      {renaming?.id === b.id ? (
                        <form className="batch-rename" onSubmit={rename}>
                          <input autoFocus aria-label="Nome do lote" maxLength={80} value={renaming.name}
                            onChange={(e) => setRenaming({ id: b.id, name: e.target.value })}
                            onKeyDown={(e) => { if (e.key === "Escape") setRenaming(null); }} onBlur={rename} />
                        </form>
                      ) : (
                        <button type="button" className="batch-head" aria-expanded={isOpen} onClick={() => toggle(b.id)}>
                          <span className="batch-caret" aria-hidden="true">{isOpen ? "▾" : "▸"}</span>
                          <span className="batch-name">{b.name}</span>
                          <span className="batch-meta">
                            {b.items.length} {b.items.length === 1 ? "pedido" : "pedidos"} · {b.items.reduce((s, o) => s + o.pieces, 0)} peças
                          </span>
                        </button>
                      )}
                      {isOpen && (
                        <div className="batch-body">
                          {b.items.map((o) => <Ticket key={o.id} o={o} onOpen={open} />)}
                          {!b.items.length && <p className="muted board-empty">Arraste pedidos para cá.</p>}
                        </div>
                      )}
                      <div className="batch-actions">
                        <button type="button" className="link-btn" disabled={!b.items.length}
                          onClick={() => nav(`/orders/production-print?ids=${b.items.map((o) => o.id).join(",")}`)}>
                          Imprimir
                        </button>
                        <button type="button" className="link-btn" onClick={() => setRenaming({ id: b.id, name: b.name })}>Renomear</button>
                        <button type="button" className="link-btn" onClick={() => ungroup(b)}>Desfazer</button>
                      </div>
                    </div>
                  );
                })}
                {groups.map((g) => (
                  <div key={g.key} className="board-group">
                    <div className={`board-group-label ${g.key === "overdue" ? "overdue" : ""}`}>{g.label}</div>
                    {g.items.map((o) => <Ticket key={o.id} o={o} onOpen={open} />)}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
