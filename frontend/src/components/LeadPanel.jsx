import { useAuth } from "../auth";
import { dateBR, formatCnpj, initials, whatsappUrl } from "../format";
import { ContactHistory } from "./Contacts";

export const isNewStore = (openedAt) =>
  !!openedAt && (Date.now() - new Date(`${openedAt}T00:00:00`)) / 86400000 <= 730; // backend NEW_STORE_DAYS

export default function LeadPanel({ lead, isAdmin, onClose, onConvert, onDiscard }) {
  const { user } = useAuth();
  const firstName = (user?.name || "").split(" ")[0];
  const wa = whatsappUrl(lead.phone, `Olá, tudo bem? Sou ${firstName} da Di Marcy. Gostaria de apresentar nossa `
    + `coleção para a ${lead.name}. Posso te enviar o catálogo?`);
  return (
    <aside className="customer-panel" aria-label={`Lead ${lead.name}`}>
      <button type="button" className="customer-panel-close" onClick={onClose} aria-label="Fechar">×</button>
      <div className="customer-panel-head">
        <span className="customer-avatar lg">{initials(lead.name)}</span>
        <div>
          <strong>{lead.name}</strong>
          <span className="muted">{[`${lead.city}/${lead.state}`, lead.phone].filter(Boolean).join(" · ")}</span>
          {isNewStore(lead.opened_at) && <span className="cstatus cstatus-active">Loja nova</span>}
        </div>
      </div>
      <div className="customer-panel-actions">
        {wa
          ? <a className="btn" href={wa} target="_blank" rel="noopener noreferrer">WhatsApp</a>
          : <button type="button" className="btn" disabled title="Telefone não cadastrado ou inválido">WhatsApp</button>}
        <button type="button" className="btn btn-primary" onClick={onConvert}>Virar cliente</button>
        <button type="button" className="btn" onClick={onDiscard}>Descartar</button>
      </div>
      <dl className="customer-panel-info">
        <dt>CNPJ</dt><dd>{formatCnpj(lead.cnpj)}</dd>
        <dt>Aberta em</dt><dd>{lead.opened_at ? dateBR(lead.opened_at) : "—"}</dd>
        <dt>E-mail</dt><dd>{lead.email || "—"}</dd>
        <dt>Endereço</dt><dd>{lead.address || "—"}</dd>
        {isAdmin && <><dt>Vendedor</dt><dd>{lead.seller_name || "Sem vendedor"}</dd></>}
      </dl>
      <ContactHistory target={{ lead_id: lead.id }} />
    </aside>
  );
}
