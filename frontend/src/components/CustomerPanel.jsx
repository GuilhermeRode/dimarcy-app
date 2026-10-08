import { useNavigate } from "react-router-dom";
import { CUSTOMER_STATUS, compactMoney, dateBR, initials, money, orderNumber, whatsappUrl } from "../format";

export default function CustomerPanel({ customer: c, isAdmin, onClose, onEdit }) {
  const nav = useNavigate();
  const st = CUSTOMER_STATUS[c.status];
  const wa = whatsappUrl(c.phone);
  const since = c.created_at
    ? new Date(c.created_at).toLocaleDateString("pt-BR", { month: "short", year: "numeric" }) : "—";
  const stats = [
    ["Total comprado", c.total ? money(c.total) : "—"],
    ["Pedidos", String(c.orders)],
    ["Ticket médio", c.orders ? compactMoney(c.total / c.orders) : "—"],
    ["Cliente desde", since],
  ];
  return (
    <aside className="customer-panel" aria-label={`Cliente ${c.name}`}>
      <button type="button" className="customer-panel-close" onClick={onClose} aria-label="Fechar">×</button>
      <div className="customer-panel-head">
        <span className="customer-avatar lg">{initials(c.name)}</span>
        <div>
          <strong>{c.name}</strong>
          <span className="muted">{[c.city && `${c.city}${c.state ? `/${c.state}` : ""}`, c.phone].filter(Boolean).join(" · ")}</span>
          <span className={`cstatus cstatus-${st.tone}`}>{st.label}</span>
        </div>
      </div>
      <div className="customer-panel-actions">
        <button type="button" className="btn btn-primary" onClick={() => nav(`/orders/new?customer=${c.id}`)}>Novo pedido</button>
        {wa
          ? <a className="btn" href={wa} target="_blank" rel="noopener noreferrer">WhatsApp</a>
          : <button type="button" className="btn" disabled title="Telefone não cadastrado ou inválido">WhatsApp</button>}
        <button type="button" className="btn" onClick={onEdit}>Editar</button>
      </div>
      <div className="customer-panel-stats">
        {stats.map(([l, v]) => <div key={l}><span>{l}</span><strong>{v}</strong></div>)}
      </div>
      <dl className="customer-panel-info">
        {isAdmin && <><dt>Vendedor</dt><dd>{c.owner_name || "Sem vendedor"}</dd></>}
        <dt>Cores mais compradas</dt><dd>{c.colors.slice(0, 3).join(", ") || "—"}</dd>
      </dl>
      <div>
        <h3>Últimos pedidos</h3>
        {c.recent_orders.length ? c.recent_orders.map((o) => (
          <button type="button" key={o.id} className="customer-panel-order" onClick={() => nav(`/orders/${o.id}`)}>
            <span><strong>#{orderNumber(o.id)}</strong><small>{dateBR(o.date)} · {o.pieces} peças</small></span>
            <strong>{money(o.total)}</strong>
          </button>
        )) : <p className="customer-panel-empty">Ainda sem compras. Bom momento para um primeiro contato.</p>}
      </div>
    </aside>
  );
}
