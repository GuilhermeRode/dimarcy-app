import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { dateBR, localDate, money, STATUS } from "../format";
import { ErrorBox, Swatch } from "../components/ui";
import logoFull from "../assets/logo-full.png";

export default function ClientPrint() {
  const { id } = useParams();
  const nav = useNavigate();
  const [o, setO] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { api.get(`/orders/${id}`).then((r) => setO(r.data)).catch((e) => setError(errorMessage(e))); }, [id]);

  const groups = useMemo(() => {
    const g = {};
    for (const i of o?.items || []) (g[i.product_id] ||= []).push(i);
    return Object.values(g);
  }, [o]);

  if (!o) return <div className="standalone-page"><div className="page"><ErrorBox msg={error} /></div></div>;

  return (
    <div className="standalone-page">
    <div className="page">
      <div className="actions no-print">
        <button className="btn" onClick={() => nav(-1)}>Voltar</button>
        <button className="btn btn-primary" onClick={() => window.print()}>Imprimir</button>
      </div>
      <ErrorBox msg={error} />

      {/* No order number on the customer's copy — it's an internal reference. */}
      <header className="cp-header">
        <div className="cp-brand">
          <img src={logoFull} alt="Di Marcy" className="cp-logo" />
          <small>pedidos@dimarcy.com.br</small>
        </div>
        <div className="cp-doc">
          <span className="cp-title">Resumo do pedido</span>
          <span className={`status st-${o.status}`}>{STATUS[o.status] || o.status}</span>
          <small>Emitido em {dateBR(localDate())}</small>
        </div>
      </header>
      <p className="cp-greeting">Obrigado pela sua compra! Confira abaixo os detalhes do seu pedido.</p>

      <section className="cp-card">
        <div className="cp-customer">
          <span>Cliente</span>
          <strong>{o.customer_name}</strong>
          {o.customer_city && <small>{o.customer_city}{o.customer_state ? `/${o.customer_state}` : ""}</small>}
        </div>
        <dl className="cp-facts">
          <div><dt>Data do pedido</dt><dd>{dateBR(o.date)}</dd></div>
          <div><dt>Previsão de entrega</dt><dd>{o.delivery_date ? dateBR(o.delivery_date) : "A definir"}</dd></div>
          <div><dt>Pagamento</dt><dd>{[o.payment_method, o.payment_terms].filter(Boolean).join(" · ") || "—"}</dd></div>
          <div><dt>Vendedor</dt><dd>{o.seller_name}</dd></div>
        </dl>
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

      <div className="print-thanks">
        <p>Agradecemos a sua compra e a confiança na Di Marcy!</p>
        <p className="muted">Qualquer dúvida sobre este pedido, estamos à disposição.</p>
      </div>
    </div>
    </div>
  );
}
