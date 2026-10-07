import { useNavigate } from "react-router-dom";
import { plural } from "../format";

export default function AlertStrip({ alerts }) {
  const nav = useNavigate();
  const items = [
    alerts.customers_at_risk > 0 && {
      tone: "warn", to: "/customers?status=at_risk", cta: "Ver lista",
      title: `${plural(alerts.customers_at_risk, "cliente", "clientes")} em risco`,
      text: "Compravam e estão entre 61 e 150 dias sem comprar.",
    },
    alerts.late_orders > 0 && {
      tone: "danger", to: "/orders?late=1", cta: "Ver pedidos",
      title: plural(alerts.late_orders, "pedido atrasado", "pedidos atrasados"),
      text: `O mais antigo está ${plural(alerts.oldest_late_days, "dia", "dias")} além da data de entrega.`,
    },
    alerts.customers_never_ordered > 0 && {
      tone: "info", to: "/customers?status=never_ordered", cta: "Ver cadastros",
      title: plural(alerts.customers_never_ordered, "cadastro sem compra", "cadastros sem compra"),
      text: "Oportunidade de primeira venda para a equipe comercial.",
    },
  ].filter(Boolean);
  if (!items.length) return null;
  return (
    <section className="alerts">
      {items.map((a) => (
        <div key={a.to} className={`alert alert-${a.tone}`}>
          <span className="alert-dot" aria-hidden="true" />
          <div>
            <strong>{a.title}</strong>
            <p>{a.text}</p>
            <button type="button" className="link-btn" onClick={() => nav(a.to)}>{a.cta} →</button>
          </div>
        </div>
      ))}
    </section>
  );
}
