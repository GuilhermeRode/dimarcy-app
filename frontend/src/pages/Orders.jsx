import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { dateBR, money, orderNumber, STATUS } from "../format";
import { ErrorBox, Status, EmptyState } from "../components/ui";

export default function Orders() {
  const nav = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [orders, setOrders] = useState([]);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.get("/orders", { params: { status } })
      .then((r) => setOrders(r.data))
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoaded(true));
  }, [status]);

  const filtered = useMemo(() => {
    const t = search.toLowerCase();
    return orders.filter((o) => !t || o.customer_name.toLowerCase().includes(t) || orderNumber(o.id).includes(t));
  }, [orders, search]);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Pedidos</h1>
        <button className="btn btn-primary" onClick={() => nav("/orders/new")}>Novo pedido</button>
      </header>
      <div className="filter-bar">
        <input placeholder="Buscar por cliente ou número" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todas as situações</option>
          {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <ErrorBox msg={error} />
      {loaded && !filtered.length ? (
        <EmptyState text="Nenhum pedido encontrado."
          action={<button className="btn" onClick={() => nav("/orders/new")}>Lançar o primeiro pedido</button>} />
      ) : (
        <table className="table">
          <thead>
            <tr><th>Nº</th><th>Data</th><th>Entrega</th><th>Cliente</th>{isAdmin && <th>Vendedor</th>}<th className="num">Peças</th><th className="num">Total</th><th>Situação</th></tr>
          </thead>
          <tbody>
            {filtered.map((o) => (
              <tr key={o.id} className="clickable" onClick={() => nav(`/orders/${o.id}`)}>
                <td className="ref">{orderNumber(o.id)}</td>
                <td>{dateBR(o.date)}</td>
                <td>{o.delivery_date ? dateBR(o.delivery_date) : "—"}</td>
                <td>{o.customer_name}</td>
                {isAdmin && <td>{o.seller_name}</td>}
                <td className="num">{o.pieces}</td>
                <td className="num">{money(o.total)}</td>
                <td><Status s={o.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
