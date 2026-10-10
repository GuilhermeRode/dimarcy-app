import { useCallback, useEffect, useState } from "react";
import { STATUS } from "../format";
import { fileUrl } from "../api";
import { WarningIcon } from "./icons";

// A product photo shown full screen; click anywhere, × or Esc closes it. Renders above modals.
export function PhotoZoom({ src, caption, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="photo-zoom" role="dialog" aria-label="Foto ampliada" onClick={onClose}>
      <button className="photo-zoom-close" aria-label="Fechar">×</button>
      <img src={src} alt={caption || ""} />
      {caption && <p>{caption}</p>}
    </div>
  );
}

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

// In-app replacement for window.confirm(): clear title, explanation and labelled buttons
export function ConfirmDialog({ title, message, confirmLabel = "Confirmar", cancelLabel = "Cancelar", danger, onConfirm, onCancel }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="modal confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
        <div className={`confirm-icon ${danger ? "danger" : ""}`} aria-hidden="true"><WarningIcon size={26} strokeWidth={2.2} /></div>
        <h2 id="confirm-title">{title}</h2>
        {message && <p className="muted">{message}</p>}
        <div className="confirm-actions">
          <button type="button" className="btn btn-light" onClick={onCancel} autoFocus>{cancelLabel}</button>
          <button type="button" className={`btn ${danger ? "btn-danger" : "btn-primary"}`} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}

// const [confirmDialog, ask] = useConfirm();  if (!(await ask({ title, ... }))) return;  ...  render {confirmDialog}
export function useConfirm() {
  const [pending, setPending] = useState(null); // { options, resolve }
  const ask = useCallback((options) => new Promise((resolve) => setPending({ options, resolve })), []);
  const close = (answer) => { pending.resolve(answer); setPending(null); };
  const dialog = pending && <ConfirmDialog {...pending.options} onConfirm={() => close(true)} onCancel={() => close(false)} />;
  return [dialog, ask];
}

export const Status = ({ s }) => <span className={`status st-${s}`}>{STATUS[s] || s}</span>;

// Two-color combos (e.g. 09/37) show as a dot split diagonally in both tones
export const swatchBg = (hex, hex2) => (hex2 ? `linear-gradient(135deg, ${hex} 50%, ${hex2} 50%)` : hex);

export const Swatch = ({ hex, hex2, size = 14 }) => (
  <span className="swatch" style={{ background: swatchBg(hex, hex2), width: size, height: size }} />
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
