import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { dateBR, money, orderNumber, STATUS } from "../format";
import { ErrorBox, Status, EmptyState } from "../components/ui";

const OPEN_STATUSES = ["quote", "confirmed", "in_production", "shipped"];
const PAGE_SIZE = 20;

function daysUntil(dateStr) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = new Date(`${dateStr}T00:00:00`);
  return Math.round((d - today) / 86400000);
}

export default function Orders() {
  const nav = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [orders, setOrders] = useState([]);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.get("/orders")
      .then((r) => { setOrders(r.data); setError(""); })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoaded(true));
  }, []);

  const counts = useMemo(() => {
    const c = {};
    for (const o of orders) c[o.status] = (c[o.status] || 0) + 1;
    return c;
  }, [orders]);

  const filtered = useMemo(() => {
    const t = search.toLowerCase();
    return orders
      .filter((o) => !status || o.status === status)
      .filter((o) => !t || o.customer_name.toLowerCase().includes(t) || orderNumber(o.id).includes(t));
  }, [orders, search, status]);

  useEffect(() => { setPage(1); }, [search, status]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const kpis = useMemo(() => {
    const open = orders.filter((o) => OPEN_STATUSES.includes(o.status));
    const upcoming = open.filter((o) => o.delivery_date && daysUntil(o.delivery_date) >= 0 && daysUntil(o.delivery_date) <= 15);
    return {
      openCount: open.length,
      openValue: open.reduce((s, o) => s + o.total, 0),
      openPieces: open.reduce((s, o) => s + o.pieces, 0),
      upcomingCount: upcoming.length,
    };
  }, [orders]);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Pedidos</h1>
        <button className="btn btn-primary" onClick={() => nav("/orders/new")}>Novo pedido</button>
      </header>

      <section className="orders-kpis">
        <div className="kpi">
          <div className="kpi-header"><span>Em aberto</span><span className="kpi-icon icon-indigo" aria-hidden="true">📋</span></div>
          <strong>{kpis.openCount}</strong>
          <span>pedidos ativos</span>
        </div>
        <div className="kpi">
          <div className="kpi-header"><span>Valor em aberto</span><span className="kpi-icon" aria-hidden="true">💰</span></div>
          <strong>{money(kpis.openValue)}</strong>
          <span>soma dos pedidos ativos</span>
        </div>
        <div className="kpi">
          <div className="kpi-header"><span>Peças</span><span className="kpi-icon icon-teal" aria-hidden="true">📦</span></div>
          <strong>{kpis.openPieces}</strong>
          <span>a produzir</span>
        </div>
        <div className="kpi">
          <div className="kpi-header"><span>Entrega próxima</span><span className="kpi-icon icon-gold" aria-hidden="true">📅</span></div>
          <strong>{kpis.upcomingCount}</strong>
          <span>nos próximos 15 dias</span>
        </div>
      </section>

      <div className="filter-bar">
        <input placeholder="Buscar por cliente ou número" value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="period-chips">
          <button type="button" className={`period-chip ${!status ? "on" : ""}`} onClick={() => setStatus("")}>
            Todas {orders.length}
          </button>
          {Object.entries(STATUS).map(([k, v]) => (
            <button key={k} type="button" className={`period-chip ${status === k ? "on" : ""}`} onClick={() => setStatus(k)}>
              {v} {counts[k] || 0}
            </button>
          ))}
        </div>
      </div>

      <ErrorBox msg={error} />
      {loaded && !filtered.length ? (
        <EmptyState text="Nenhum pedido encontrado."
          action={<button className="btn" onClick={() => nav("/orders/new")}>Lançar o primeiro pedido</button>} />
      ) : (
        <>
          <table className="table table-orders">
            <thead>
              <tr>
                <th>{isAdmin ? "Nº" : "Data"}</th><th>Cliente</th><th>Entrega</th><th className="num">Peças</th>
                <th className="num">Total</th><th>Situação</th><th></th>
              </tr>
            </thead>
            <tbody>
              {pageItems.map((o) => (
                <tr key={o.id}>
                  <td>
                    {isAdmin ? (
                      <span className="cell-stack">
                        <span className="ref">{orderNumber(o.id)}</span>
                        <span className="cell-sub">{dateBR(o.date)}</span>
                      </span>
                    ) : <span className="ref">{dateBR(o.date)}</span>}
                  </td>
                  <td>
                    <span className="cell-stack">
                      <span>{o.customer_name}</span>
                      {isAdmin && <span className="cell-sub">{o.seller_name}</span>}
                    </span>
                  </td>
                  <td>{o.delivery_date ? dateBR(o.delivery_date) : "—"}</td>
                  <td className="num">{o.pieces}</td>
                  <td className="num">{money(o.total)}</td>
                  <td><Status s={o.status} /></td>
                  <td>
                    <div className="actions actions-end">
                      {isAdmin && (
                        <button className="btn btn-light" onClick={() => nav(`/orders/${o.id}/production-print`)}>Imprimir</button>
                      )}
                      <button className="btn btn-light" onClick={() => nav(`/orders/${o.id}`)}>Abrir</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="table-footer">
            <span className="muted">Mostrando {pageItems.length} de {filtered.length} pedidos</span>
            {totalPages > 1 && (
              <div className="actions">
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
                  <button key={n} className={`btn btn-light ${n === page ? "btn-primary" : ""}`} onClick={() => setPage(n)}>
                    {n}
                  </button>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
