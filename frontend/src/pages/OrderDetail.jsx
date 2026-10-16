import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { dateBR, money, orderNumber, STATUS } from "../format";
import { ErrorBox, Status, Swatch, useConfirm } from "../components/ui";
import { EntryStatus, PayModal } from "./Finance";

export default function OrderDetail() {
  const [confirmDialog, ask] = useConfirm();
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [o, setO] = useState(null);
  const [error, setError] = useState("");
  const [installments, setInstallments] = useState(null);
  const [paying, setPaying] = useState(null);
  const [generating, setGenerating] = useState(false);

  // Admin only: sellers can open this screen too and must not see the order's receivables.
  function loadInstallments() {
    if (!isAdmin) return;
    api.get("/finance/entries", { params: { order_id: id, status: "all" } })
      .then((r) => setInstallments(r.data)).catch((e) => setError(errorMessage(e)));
  }
  useEffect(loadInstallments, [id]);

  async function generate() {
    setGenerating(true);
    try { await api.post(`/finance/orders/${id}/generate`); loadInstallments(); }
    catch (e) { setError(errorMessage(e)); } finally { setGenerating(false); }
  }

  useEffect(() => { api.get(`/orders/${id}`).then((r) => setO(r.data)).catch((e) => setError(errorMessage(e))); }, [id]);

  const groups = useMemo(() => {
    const g = {};
    for (const i of o?.items || []) (g[i.product_id] ||= []).push(i);
    return Object.values(g);
  }, [o]);

  async function changeStatus(status) {
    try { setO((await api.patch(`/orders/${id}/status`, { status })).data); loadInstallments(); }
    catch (e) { setError(errorMessage(e)); }
  }

  async function remove() {
    if (!(await ask({ title: "Excluir este pedido?", message: "Esta ação não pode ser desfeita.", confirmLabel: "Excluir", danger: true }))) return;
    try { await api.delete(`/orders/${id}`); nav("/orders"); }
    catch (e) { setError(errorMessage(e)); }
  }

  if (!o) return <div className="page"><ErrorBox msg={error} /></div>;

  const list = installments || [];
  const paidTotal = list.filter((x) => x.paid_at).reduce((s, x) => s + x.amount, 0);
  const canGenerate = installments !== null && o.status === "delivered" && !list.some((x) => !x.paid_at) && o.total - paidTotal > 0.005;

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
          ) : (
            <>
              <Status s={o.status} />
              <button className="btn" onClick={() => nav(`/orders/${id}/client-print`)}>Imprimir p/ cliente</button>
            </>
          )}
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
          {o.price_table === "retail" && <div className="info-item"><span>Tabela de preço</span><strong>Varejo</strong></div>}
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
                    <td><Swatch hex={c.color_hex} hex2={c.color_hex2} /> {c.color_name}</td>
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

      {isAdmin && (list.length > 0 || canGenerate) && (
        <section className="panel">
          <div className="panel-header">
            <h3>Parcelas</h3>
            {canGenerate && <button className="btn btn-primary" disabled={generating} onClick={generate}>Gerar parcelas</button>}
          </div>
          {list.length > 0 && (
            <table className="table table-compact">
              <thead><tr><th>Parcela</th><th>Vencimento</th><th className="num">Valor</th><th>Situação</th><th></th></tr></thead>
              <tbody>
                {list.map((x) => (
                  <tr key={x.id}>
                    <td>{x.installments ? `${x.installment}/${x.installments}` : x.description}</td>
                    <td>{dateBR(x.due_date)}</td>
                    <td className="num">{money(x.amount)}</td>
                    <td><EntryStatus entry={x} /></td>
                    <td>{x.paid_at
                      ? <span className="muted">pago em {dateBR(x.paid_at)}</span>
                      : <button className="btn btn-light" onClick={() => setPaying(x)}>Dar baixa</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      <section className="panel order-summary">
        <div>{o.notes && <><h3>Observações</h3><p className="notes-text">{o.notes}</p></>}</div>
        <div className="totals">
          <div><span>Peças</span><strong>{o.pieces}</strong></div>
          <div><span>Subtotal</span><strong>{money(o.gross)}</strong></div>
          <div><span>Desconto</span><strong>{money(o.discount)}</strong></div>
          <div className="grand-total"><span>Total</span><strong>{money(o.total)}</strong></div>
        </div>
      </section>
      {confirmDialog}
      {paying && <PayModal entry={paying} onClose={() => setPaying(null)} onDone={() => { setPaying(null); loadInstallments(); }} />}
    </div>
  );
}
