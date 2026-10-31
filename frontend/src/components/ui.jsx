import { useCallback, useEffect, useState } from "react";
import { PRICE_TABLES, STATUS, normalize } from "../format";
import { fileUrl } from "../api";
import { EyeIcon, EyeOffIcon, WarningIcon } from "./icons";

// Atacado / Varejo tabs of a list; `rows` (each with a price_table) give the count on each tab
export function PriceTableTabs({ value, rows, onChange }) {
  return (
    <div className="tabs-underline" role="group" aria-label="Tipo de venda">
      {Object.entries(PRICE_TABLES).map(([k, label]) => (
        <button key={k} type="button" className={value === k ? "active" : ""} aria-pressed={value === k} onClick={() => onChange(k)}>
          {label} {rows.filter((r) => r.price_table === k).length}
        </button>
      ))}
    </div>
  );
}

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

// A password input with the eye button that shows/hides what was typed
export function PasswordInput(props) {
  const [show, setShow] = useState(false);
  return (
    <div className="password-field">
      <input {...props} type={show ? "text" : "password"} />
      <button type="button" className="password-toggle" onClick={() => setShow((v) => !v)}
        aria-label={show ? "Ocultar senha" : "Mostrar senha"}>
        {show ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  );
}

// A pill-shaped filter menu: "Status: Todos ▾", highlighted while it filters something. options: [[value, label]].
// The real <select> is invisible and covers the whole pill, so a click anywhere on it opens the list.
export function PillSelect({ label, value, options, onChange, className = "" }) {
  return (
    <label className={`pill-select ${value !== "" ? "on" : ""} ${className}`}>
      <span>{label}:</span>
      <strong className="pill-value">{options.find(([v]) => v === value)?.[1]}</strong>
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
        {options.map(([v, text]) => <option key={v} value={v}>{text}</option>)}
      </select>
    </label>
  );
}

// "Cidade:" pill: type part of a name or pick one from our own list (the native <datalist> popup is a dark
// OS-styled box that doesn't match the app). Typing already filters; picking sets the exact city.
const CITY_MENU_MAX = 100;  // Prospecção has 1,000+ cities: show the first ones, typing narrows the rest
// onPick (optional): called when a city is chosen from the list, for screens that search on demand.
export function CityFilter({ value, cities, onChange, onPick }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const typed = normalize(value.trim());
  const matches = cities.filter((c) => normalize(c).includes(typed));
  const items = ["", ...matches.slice(0, CITY_MENU_MAX)];  // "" = Todas
  const pick = (c) => { onChange(c); onPick?.(c); setOpen(false); };
  function onKeyDown(e) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => (i + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length);
    } else if (e.key === "Enter" && open) { e.preventDefault(); pick(items[active] ?? value); }
    else if (e.key === "Escape") setOpen(false);
  }
  return (
    <label className={`pill-select ${value ? "on" : ""}`}>
      <span>Cidade:</span>
      <input className="pill-input" placeholder="Todas" role="combobox" aria-label="Cidade" aria-expanded={open}
        aria-controls="city-menu" autoComplete="off" value={value}
        onFocus={() => { setOpen(true); setActive(0); }} onBlur={() => setOpen(false)} onKeyDown={onKeyDown}
        // typing: the first matching city is highlighted, so Enter picks it (not "Todas")
        onChange={(e) => { onChange(e.target.value); setOpen(true); setActive(e.target.value.trim() ? 1 : 0); }} />
      {open && (
        <ul className="pill-menu" id="city-menu" role="listbox">
          {items.map((c, i) => (
            // mousedown + preventDefault: picks before the input's blur closes the list
            <li key={c || "all"} role="option" aria-selected={i === active} className={i === active ? "active" : ""}
              onMouseDown={(e) => { e.preventDefault(); pick(c); }} onMouseEnter={() => setActive(i)}>
              {c || "Todas"}
            </li>
          ))}
          {!matches.length && <li className="pill-menu-empty">Nenhuma cidade com “{value}”</li>}
          {matches.length > CITY_MENU_MAX && (
            <li className="pill-menu-empty">e mais {matches.length - CITY_MENU_MAX} cidades — digite para filtrar</li>
          )}
        </ul>
      )}
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
