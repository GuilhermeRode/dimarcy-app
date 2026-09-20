import { STATUS } from "../format";
import { fileUrl } from "../api";

export function Modal({ title, onClose, children, wide }) {
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-label={title}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="btn-x" onClick={onClose} aria-label="Fechar">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export const Status = ({ s }) => <span className={`status st-${s}`}>{STATUS[s] || s}</span>;

export const Swatch = ({ hex, size = 14 }) => (
  <span className="swatch" style={{ background: hex, width: size, height: size }} />
);

export function Avatar({ url, name, size = "sm" }) {
  const initial = (name || "?").trim().charAt(0).toUpperCase();
  const cls = `avatar-${size}`;
  return url
    ? <img src={fileUrl(url)} alt="" className={`avatar ${cls}`} />
    : <span className={`avatar-placeholder ${cls}`}>{initial}</span>;
}

export function Field({ label, children, span }) {
  return (
    <label className={`field ${span ? "span-" + span : ""}`}>
      <span>{label}</span>
      {children}
    </label>
  );
}

export const ErrorBox = ({ msg }) => (msg ? <div className="error-message">{msg}</div> : null);

export function EmptyState({ text, action }) {
  return (
    <div className="empty-state">
      <p>{text}</p>
      {action}
    </div>
  );
}
