import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { dateBR, money, orderNumber, STATUS } from "../format";
import { ErrorBox, Status, Swatch } from "../components/ui";

export default function OrderDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [o, setO] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { api.get(`/orders/${id}`).then((r) => setO(r.data)).catch((e) => setError(errorMessage(e))); }, [id]);

  const groups = useMemo(() => {
    const g = {};
    for (const i of o?.items || []) (g[i.product_id] ||= []).push(i);
    return Object.values(g);
  }, [o]);

  async function changeStatus(status) {
    try { setO((await api.patch(`/orders/${id}/status`, { status })).data); }
    catch (e) { setError(errorMessage(e)); }
  }

  async function remove() {
    if (!confirm("Excluir este pedido? Esta ação não pode ser desfeita.")) return;
    try { await api.delete(`/orders/${id}`); nav("/orders"); }
    catch (e) { setError(errorMessage(e)); }
  }

  if (!o) return <div className="page"><ErrorBox msg={error} /></div>;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Pedido {orderNumber(o.id)}</h1>
          <p className="muted">{o.customer_name} · {dateBR(o.date)} · vendedor {o.seller_name}</p>
        </div>
        <div className="actions">
          {isAdmin ? (
            <>
              <select value={o.status} onChange={(e) => changeStatus(e.target.value)} aria-label="Situação">
                {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <button className="btn" onClick={() => nav(`/orders/${id}/client-print`)}>Imprimir p/ cliente</button>
              <button className="btn" onClick={() => nav(`/orders/${id}/production-print`)}>Imprimir produção</button>
              <button className="btn" onClick={() => nav(`/orders/${id}/edit`)}>Editar</button>
              <button className="btn danger" onClick={remove}>Excluir</button>
            </>
          ) : <Status s={o.status} />}
        </div>
      </header>
      <ErrorBox msg={error} />
      <section className="panel">
        <div className="order-info">
          <div className="info-item"><span>Situação</span><Status s={o.status} /></div>
          <div className="info-item"><span>Data do pedido</span><strong>{dateBR(o.date)}</strong></div>
          <div className="info-item"><span>Data de entrega</span><strong>{o.delivery_date ? dateBR(o.delivery_date) : "Não definida"}</strong></div>
          <div className="info-item"><span>Forma de pagamento</span><strong>{o.payment_method || "—"}</strong></div>
          <div className="info-item"><span>Prazo / condição</span><strong>{o.payment_terms || "—"}</strong></div>
        </div>
      </section>

      {groups.map((lines) => {
        const sizes = [...new Set(lines.map((l) => l.size))];
        const colors = [...new Map(lines.map((l) => [l.color_id, l])).values()];
        const q = (c, t) => lines.find((l) => l.color_id === c && l.size === t)?.quantity;
        return (
          <section key={lines[0].product_id} className="panel item-group">
            <div className="item-group-header">
              <div><span className="ref">{lines[0].product_reference}</span> {lines[0].product_description}</div>
              <span className="muted">{money(lines[0].unit_price)} un.</span>
            </div>
            <table className="table table-compact">
              <thead><tr><th>Cor</th>{sizes.map((t) => <th key={t} className="num">{t}</th>)}<th className="num">Total</th></tr></thead>
              <tbody>
                {colors.map((c) => (
                  <tr key={c.color_id}>
                    <td><Swatch hex={c.color_hex} /> {c.color_name}</td>
                    {sizes.map((t) => <td key={t} className="num">{q(c.color_id, t) || "–"}</td>)}
                    <td className="num">{lines.filter((l) => l.color_id === c.color_id).reduce((s, l) => s + l.quantity, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="item-group-subtotal">{money(lines.reduce((s, l) => s + l.subtotal, 0))}</div>
          </section>
        );
      })}

      <section className="panel order-summary">
        <div>{o.notes && <><h3>Observações</h3><p className="notes-text">{o.notes}</p></>}</div>
        <div className="totals">
          <div><span>Peças</span><strong>{o.pieces}</strong></div>
          <div><span>Subtotal</span><strong>{money(o.gross)}</strong></div>
          <div><span>Desconto</span><strong>{money(o.discount)}</strong></div>
          <div className="grand-total"><span>Total</span><strong>{money(o.total)}</strong></div>
        </div>
      </section>
    </div>
  );
}
