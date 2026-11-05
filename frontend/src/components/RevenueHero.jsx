import { useState } from "react";
import { hideable, money } from "../format";
import Delta from "./Delta";
import { EyeIcon, EyeOffIcon } from "./icons";

// The eye that masks every value on a screen; each visit starts with them hidden.
export function HideToggle({ hide, onToggle }) {
  const label = hide ? "Mostrar valores" : "Ocultar valores";
  function toggle(e) {
    e.stopPropagation();  // the Painel's card itself opens Faturamento
    onToggle();
  }
  return (
    <button type="button" className="hero-eye" aria-pressed={hide} onClick={toggle} aria-label={label} title={label}>
      {hide ? <EyeOffIcon size={16} /> : <EyeIcon size={16} />}
    </button>
  );
}

// goal/goalValue: the annual goal vs. the goal year's sales, whatever the period shown.
export default function RevenueHero({ title, revenue, prevRevenue, series, goal, goalValue, onClick, hide, onToggleHide }) {
  const [hover, setHover] = useState(null);
  const amount = hideable(hide, money);
  const max = Math.max(...series.map((p) => p.value), 1);
  const active = hover ?? series.length - 1;
  const point = series[active];
  const pct = goal ? Math.round((goalValue / goal) * 100) : null;
  return (
    <div className={`hero ${onClick ? "hero-clickable" : ""}`} onClick={onClick}>
      <div className="hero-main">
        <span className="hero-label">
          {title}
          <HideToggle hide={hide} onToggle={onToggleHide} />
        </span>
        <strong className="hero-value">{amount(revenue)}</strong>
        {prevRevenue > 0 && <span className="hero-delta"><Delta cur={revenue} prev={prevRevenue} /> vs. período anterior</span>}
        {point && <span className="hero-point">{point.label}: {amount(point.value)}</span>}
        <div className="spark" onMouseLeave={() => setHover(null)}>
          {series.map((p, i) => (
            <span key={p.start} className={i === active ? "on" : ""} title={`${p.label}: ${amount(p.value)}`}
              style={{ height: `${Math.max(4, (p.value / max) * 100)}%` }} onMouseEnter={() => setHover(i)} />
          ))}
        </div>
      </div>
      {pct != null && (
        <div className="hero-goal">
          <div className="goal-ring" style={{ "--pct": Math.min(pct, 100) }}>
            <div><strong>{pct}%</strong><span>da meta</span></div>
          </div>
          <span>Meta anual · {amount(goalValue)} de {amount(goal)}</span>
        </div>
      )}
    </div>
  );
}
