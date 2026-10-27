import { useState } from "react";
import { api, errorMessage, fileUrl } from "../api";
import { useAuth } from "../auth";
import { LEAD_SIZES, dateBR, formatCnpj, initials, money, whatsappUrl } from "../format";
import { ContactHistory } from "./Contacts";

export const isNewStore = (openedAt) =>
  !!openedAt && (Date.now() - new Date(`${openedAt}T00:00:00`)) / 86400000 <= 730; // opened within 2 years

export default function LeadPanel({ lead, isAdmin, sellers = [], catalogUrl, onClose, onConvert, onDiscard, onReleased, onContacted, onNoAnswer }) {
  const [releasing, setReleasing] = useState(false);
  const [releaseTo, setReleaseTo] = useState("");  // only for a lead whose city has no seller
  const [releaseError, setReleaseError] = useState("");
  const [waOpened, setWaOpened] = useState(false);
  const [history, setHistory] = useState(0);  // bumped to reload the contact list
  async function contactDone() {
    setReleaseError("");
    try {
      await api.post("/contacts", { lead_id: lead.id, channel: "whatsapp" });
      setWaOpened(false);
      setHistory((n) => n + 1);
      onContacted?.();
    } catch (e) { setReleaseError(errorMessage(e)); }
  }
  async function noAnswer() {
    setReleaseError("");
    try {
      const { data } = await api.post(`/leads/${lead.id}/no-answer`);
      setWaOpened(false);
      setHistory((n) => n + 1);
      onNoAnswer?.(data);
    } catch (e) { setReleaseError(errorMessage(e)); }
  }
  async function release() {
    setReleasing(true);
    try {
      const { data } = await api.post("/leads/release", { ids: [lead.id], seller_id: releaseTo ? Number(releaseTo) : null });
      onReleased?.(data);
    } catch (e) { setReleaseError(errorMessage(e)); }
    setReleasing(false);
  }
  const releasable = isAdmin && lead.status === "pending";
  const { user } = useAuth();
  const firstName = (user?.name || "").split(" ")[0];
  const wa = whatsappUrl(lead.phone, `Olá, tudo bem? Sou ${firstName} da Di Marcy. Gostaria de apresentar nossa `
    + `coleção para a ${lead.name}. Posso te enviar o catálogo?`);
  const waCatalog = catalogUrl && whatsappUrl(lead.phone, `Olá, tudo bem? Sou ${firstName} da Di Marcy. `
    + `Segue o nosso catálogo: ${fileUrl(catalogUrl)}\nQualquer dúvida estou à disposição!`);
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
      {/* two columns, so a narrow (notebook) panel never leaves a button squeezed or stranded:
          contact pairs first, then the decision — Liberar across, Cadastrar cliente | Descartar under it */}
      <div className="customer-panel-actions lead-actions lead-contact">
        {wa
          ? <a className="btn" href={wa} target="_blank" rel="noopener noreferrer" onClick={() => setWaOpened(true)}>WhatsApp</a>
          : <button type="button" className="btn" disabled title="Telefone não cadastrado ou inválido">WhatsApp</button>}
        {waCatalog && <a className="btn" href={waCatalog} target="_blank" rel="noopener noreferrer" onClick={() => setWaOpened(true)}>Enviar catálogo</a>}
        {wa && <button type="button" className="btn" onClick={noAnswer} title="Agenda nova tentativa em 7 dias; na 3ª a loja é descartada">Não respondeu</button>}
        {waOpened && <button type="button" className="btn btn-primary" onClick={contactDone}>Contato feito</button>}
      </div>
      {isAdmin && lead.status === "pending" && !lead.seller_id && (
        // no seller has this city: pick one, and the city joins their region
        <label className="lead-release-to">
          <span>Liberar para</span>
          <select value={releaseTo} onChange={(e) => setReleaseTo(e.target.value)}>
            <option value="">Escolha o vendedor…</option>
            {sellers.map((s) => <option key={s.id} value={s.id}>{s.role === "admin" ? `${s.name} (admin)` : s.name}</option>)}
          </select>
          <small className="muted">{lead.city}/{lead.state} ainda não é de nenhum vendedor: ela entra na região de quem você escolher.</small>
        </label>
      )}
      <div className="customer-panel-actions lead-actions">
        {releasable && (
          <button type="button" className="btn btn-primary lead-action-wide" disabled={releasing || (!lead.seller_id && !releaseTo)} onClick={release}>
            {lead.seller_id ? `Liberar para ${lead.seller_name.split(" ")[0]}` : "Liberar"}
          </button>
        )}
        {/* one blue button at a time: while Liberar is there, it is the main action */}
        <button type="button" className={`btn ${releasable ? "" : "btn-primary"}`} onClick={onConvert}>Cadastrar cliente</button>
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
      <ContactHistory key={history} target={{ lead_id: lead.id }} onSaved={onContacted} />
    </aside>
  );
}
