import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { dateBR, orderNumber } from "../format";
import { ErrorBox } from "../components/ui";
import logoFull from "../assets/logo-full.png";

const SIZE_ORDER = ["U", "PP", "P", "M", "G", "GG", "XG"];
const sizeRank = (t) => (SIZE_ORDER.includes(t) ? SIZE_ORDER.indexOf(t) : 99);

// One compact line per product: colors in sequence, each with its size:qty pairs —
// e.g. "Bordô (P:2 M:3 G:1)  •  Marinho (P:1 M:2)" — so many refs fit on a single page.
function colorSequence(lines) {
  const byColor = [...new Map(lines.map((l) => [l.color_id, l])).values()];
  return byColor.map((c) => {
    const sizes = lines
      .filter((l) => l.color_id === c.color_id)
      .sort((a, b) => sizeRank(a.size) - sizeRank(b.size))
      .map((l) => `${l.size}:${l.quantity}`)
      .join(" ");
    return `${c.color_name} (${sizes})`;
  }).join("   •   ");
}

export default function ProductionPrint() {
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

  const totalPieces = o.items.reduce((s, i) => s + i.quantity, 0);

  return (
    <div className="standalone-page">
    <div className="page production-print">
      <div className="actions no-print">
        <button className="btn" onClick={() => nav(-1)}>Voltar</button>
        <button className="btn btn-primary" onClick={() => window.print()}>Imprimir</button>
      </div>
      <ErrorBox msg={error} />

      <div className="pp-header">
        <div className="pp-header-left">
          <img src={logoFull} alt="Di Marcy" className="pp-logo" />
          <span className="pp-order-num">Pedido Nº {orderNumber(o.id)}</span>
          <strong className="pp-customer">{o.customer_name}</strong>
        </div>
        <div className="pp-header-right">
          <span>Pedido: {dateBR(o.date)}</span>
          <strong className="pp-delivery">
            Entrega: {o.delivery_date ? dateBR(o.delivery_date) : "—"}
          </strong>
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
              <td className="num">{lines.reduce((s, l) => s + l.quantity, 0)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr><td colSpan={3}><strong>Total de peças</strong></td><td className="num"><strong>{totalPieces}</strong></td></tr>
        </tfoot>
      </table>

      {o.notes && (
        <div className="pp-notes"><strong>Observações:</strong> {o.notes}</div>
      )}
    </div>
    </div>
  );
}
