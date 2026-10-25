import { useState } from "react";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { LEAD_SIZES, dateBR, formatCnpj, initials, money, whatsappUrl } from "../format";
import { ContactHistory } from "./Contacts";

export const isNewStore = (openedAt) =>
  !!openedAt && (Date.now() - new Date(`${openedAt}T00:00:00`)) / 86400000 <= 730; // opened within 2 years

export default function LeadPanel({ lead, isAdmin, onClose, onConvert, onDiscard, onReleased }) {
  const [releasing, setReleasing] = useState(false);
  const [releaseError, setReleaseError] = useState("");
  async function release() {
    setReleasing(true);
    try {
      const { data } = await api.post("/leads/release", { ids: [lead.id] });
      onReleased?.(data);
    } catch (e) { setReleaseError(errorMessage(e)); }
    setReleasing(false);
  }
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
          {lead.in_debt && <span className="cstatus cstatus-risk">Dívida ativa</span>}
        </div>
      </div>
      <div className="customer-panel-actions">
        {wa
          ? <a className="btn" href={wa} target="_blank" rel="noopener noreferrer">WhatsApp</a>
          : <button type="button" className="btn" disabled title="Telefone não cadastrado ou inválido">WhatsApp</button>}
        {isAdmin && lead.status === "pending" && (
          <button type="button" className="btn btn-primary" disabled={releasing} onClick={release}>Liberar</button>
        )}
        <button type="button" className="btn btn-primary" onClick={onConvert}>Virar cliente</button>
        <button type="button" className="btn" onClick={onDiscard}>Descartar</button>
      </div>
      {releaseError && <p className="muted" style={{ color: "var(--danger)" }}>{releaseError}</p>}
      <dl className="customer-panel-info">
        <dt>CNPJ</dt><dd>{formatCnpj(lead.cnpj)}</dd>
        <dt>Aberta em</dt><dd>{lead.opened_at ? dateBR(lead.opened_at) : "—"}</dd>
        <dt>Porte</dt><dd>{LEAD_SIZES[lead.size] || "—"}</dd>
        <dt>Capital social</dt><dd>{lead.capital != null ? money(lead.capital) : "—"}</dd>
        <dt>Dívida ativa (União)</dt>
        <dd>{lead.in_debt == null ? "Não verificado" : lead.in_debt ? "Tem dívida em cobrança" : "Nenhuma em cobrança"}</dd>
        <dt>E-mail</dt><dd>{lead.email || "—"}</dd>
        <dt>Endereço</dt><dd>{lead.address || "—"}</dd>
        {isAdmin && <><dt>Vendedor</dt><dd>{lead.seller_name || "Sem vendedor"}</dd></>}
      </dl>
      <ContactHistory target={{ lead_id: lead.id }} />
    </aside>
  );
}
