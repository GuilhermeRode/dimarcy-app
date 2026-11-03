import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { dateBR, orderNumber, sortSizes } from "../format";
import { ErrorBox } from "../components/ui";
import logoFull from "../assets/logo-full.png";

// One compact line per product: colors in sequence, each with its size:qty pairs —
// e.g. "Bordô (P:2 M:3 G:1)  •  Marinho (P:1 M:2)" — so many refs fit on a single page.
function colorSequence(lines) {
  const byColor = [...new Map(lines.map((l) => [l.color_id, l])).values()];
  const order = sortSizes(new Set(lines.map((l) => l.size)));
  return byColor.map((c) => {
    const sizes = lines
      .filter((l) => l.color_id === c.color_id)
      .sort((a, b) => order.indexOf(a.size) - order.indexOf(b.size))
      .map((l) => `${l.size}:${l.quantity}`)
      .join(" ");
    return `${c.color_name} (${sizes})`;
  }).join("   •   ");
}

const unique = (xs) => [...new Set(xs.filter(Boolean))];

// Turns one or more orders into the sheet's fields. Several orders become one sheet: header
// fields list every order, items are summed per product × color × size.
function mergeOrders(orders) {
  const items = {};
  for (const o of orders) {
    for (const i of o.items) {
      const k = `${i.product_id}|${i.color_id}|${i.size}`;
      items[k] = { ...i, quantity: (items[k]?.quantity || 0) + i.quantity };
    }
  }
  const deliveries = orders.map((o) => o.delivery_date).filter(Boolean).sort();
  const several = orders.length > 1;
  return {
    customer: unique(orders.map((o) => o.customer_name)).join("  •  "),
    number: orders.map((o) => orderNumber(o.id)).join("  •  "),
    seller: unique(orders.map((o) => o.seller_name)).join("  •  "),
    ordered: unique(orders.map((o) => dateBR(o.date))).join("  •  "),
    delivery: deliveries.length ? dateBR(deliveries[0]) : "A definir",
    items: Object.values(items),
    notes: orders.filter((o) => o.notes).map((o) => (several ? `${orderNumber(o.id)}: ${o.notes}` : o.notes)).join("\n"),
    several,
  };
}

// /orders/:id/production-print prints one order; /orders/production-print?ids=1,2,3 prints
// several orders grouped on one sheet.
export default function ProductionPrint() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const ids = id || params.get("ids") || "";
  const [orders, setOrders] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all(ids.split(",").filter(Boolean).map((i) => api.get(`/orders/${i}`).then((r) => r.data)))
      .then(setOrders).catch((e) => setError(errorMessage(e)));
  }, [ids]);

  const s = useMemo(() => orders && mergeOrders(orders), [orders]);
  const groups = useMemo(() => {
    const g = {};
    for (const i of s?.items || []) (g[i.product_id] ||= []).push(i);
    return Object.values(g);
  }, [s]);

  if (!s) return <div className="standalone-page"><div className="page"><ErrorBox msg={error} /></div></div>;

  const totalPieces = s.items.reduce((t, i) => t + i.quantity, 0);

  return (
    <div className="standalone-page">
    <div className="page production-print">
      <div className="actions no-print">
        <button className="btn" onClick={() => nav(-1)}>Voltar</button>
        <button className="btn btn-primary" onClick={() => window.print()}>Imprimir</button>
      </div>
      <ErrorBox msg={error} />

      <div className="pp-header">
        <div className="pp-header-logo">
          <img src={logoFull} alt="Di Marcy" className="pp-logo" />
        </div>
        <div className={`pp-header-grid ${s.several ? "pp-several" : ""}`}>
          <div className="pp-field pp-field-cliente">
            <span className="pp-field-label">Cliente</span>
            <strong className="pp-field-value">{s.customer}</strong>
          </div>
          <div className="pp-field pp-field-ordem">
            <span className="pp-field-label">Ordem de produção</span>
            <strong className="pp-field-value">{s.number}</strong>
          </div>
          <div className="pp-field pp-field-vendedor">
            <span className="pp-field-label">Vendedor</span>
            <strong className="pp-field-value">{s.seller}</strong>
          </div>
          <div className="pp-field pp-field-pedido-em">
            <span className="pp-field-label">Pedido em</span>
            <strong className="pp-field-value">{s.ordered}</strong>
          </div>
          <div className="pp-field pp-field-entrega">
            <span className="pp-field-label">{s.several ? "Entrega mais próxima" : "Entrega"}</span>
            <strong className="pp-field-value">{s.delivery}</strong>
          </div>
        </div>
      </div>

      <table className="pp-table">
        <thead>
          <tr><th>Ref.</th><th>Descrição</th><th>Cores × tamanhos</th><th className="num">Peças</th></tr>
        </thead>
        <tbody>
          {groups.map((lines) => (
            <tr key={lines[0].product_id}>
              <td className="pp-ref">{lines[0].product_reference}</td>
              <td>{lines[0].product_description}</td>
              <td className="pp-colors">{colorSequence(lines)}</td>
              <td className="num">{lines.reduce((t, l) => t + l.quantity, 0)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr><td colSpan={3}><strong>Total de peças</strong></td><td className="num"><strong>{totalPieces}</strong></td></tr>
        </tfoot>
      </table>

      <div className="pp-notes-box">
        <span className="pp-field-label">Observações</span>
        {s.notes ? <p className="pp-notes-text">{s.notes}</p> : (
          <>
            <div className="pp-notes-line" />
            <div className="pp-notes-line" />
          </>
        )}
      </div>
    </div>
    </div>
  );
}
