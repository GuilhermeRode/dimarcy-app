import { useEffect } from "react";
import { STATUS } from "../format";
import { fileUrl } from "../api";

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
