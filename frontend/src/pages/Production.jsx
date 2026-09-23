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

export default function Production() {
  const nav = useNavigate();
  const [orders, setOrders] = useState([]);
  const [error, setError] = useState("");
  const [dragOverCol, setDragOverCol] = useState(null);

  const load = () => api.get("/orders").then((r) => { setOrders(r.data); setError(""); }).catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);

  const byColumn = useMemo(() => {
    const map = {};
    for (const col of COLUMNS) map[col.status] = orders.filter((o) => o.status === col.status);
    return map;
  }, [orders]);

  async function changeStatus(id, status) {
    const previous = orders;
    setOrders((list) => list.map((o) => (o.id === id ? { ...o, status } : o))); // optimistic
    try { await api.patch(`/orders/${id}/status`, { status }); }
    catch (e) { setOrders(previous); setError(errorMessage(e)); }
  }

  function onDrop(e, status) {
    e.preventDefault();
    setDragOverCol(null);
    const id = Number(e.dataTransfer.getData("text/plain"));
    const order = orders.find((o) => o.id === id);
    if (id && order && order.status !== status) changeStatus(id, status);
  }

  return (
    <div className="page page-wide">
      <header className="page-header">
        <div>
          <h1>Gestão de produção</h1>
          <p className="muted">Arraste os pedidos entre as colunas conforme avançam. Fica amarelo 2 semanas antes da entrega e vermelho a partir de 1 semana (ou atrasado).</p>
        </div>
      </header>
      <ErrorBox msg={error} />

      <div className="board">
        {COLUMNS.map((col) => {
          const list = byColumn[col.status] || [];
          const groups = groupSorted(list);
          return (
            <div key={col.status} className={`board-column ${dragOverCol === col.status ? "drag-over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragOverCol(col.status); }}
              onDragLeave={() => setDragOverCol((c) => (c === col.status ? null : c))}
              onDrop={(e) => onDrop(e, col.status)}>
              <div className="board-column-header" style={{ borderTopColor: col.color }}>
                <span>{col.label}</span>
                <span className="board-column-count">{list.length}</span>
              </div>
              <div className="board-column-body">
                {!list.length && <p className="muted board-empty">Nenhum pedido aqui.</p>}
                {groups.map((g) => (
                  <div key={g.key} className="board-group">
                    <div className={`board-group-label ${g.key === "overdue" ? "overdue" : ""}`}>{g.label}</div>
                    {g.items.map((o) => {
                      const u = urgency(o.delivery_date, o.status);
                      return (
                        <div key={o.id} className={`ticket ticket-${u}`} draggable
                          onDragStart={(e) => { e.dataTransfer.setData("text/plain", String(o.id)); e.dataTransfer.effectAllowed = "move"; }}
                          onClick={() => nav(`/orders/${o.id}`)}>
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
                    })}
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
