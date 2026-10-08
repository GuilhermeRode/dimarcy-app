import { useState } from "react";
import { money } from "../format";
import Delta from "./Delta";

export default function RevenueHero({ title, revenue, prevRevenue, series, goal, onClick }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(...series.map((p) => p.value), 1);
  const active = hover ?? series.length - 1;
  const point = series[active];
  const pct = goal ? Math.round((revenue / goal) * 100) : null;
  return (
    <div className={`hero ${onClick ? "hero-clickable" : ""}`} onClick={onClick}>
      <div className="hero-main">
        <span className="hero-label">{title}</span>
        <strong className="hero-value">{money(revenue)}</strong>
        {prevRevenue > 0 && <span className="hero-delta"><Delta cur={revenue} prev={prevRevenue} /> vs. período anterior</span>}
        {point && <span className="hero-point">{point.label}: {money(point.value)}</span>}
        <div className="spark" onMouseLeave={() => setHover(null)}>
          {series.map((p, i) => (
            <span key={p.start} className={i === active ? "on" : ""} title={`${p.label}: ${money(p.value)}`}
              style={{ height: `${Math.max(4, (p.value / max) * 100)}%` }} onMouseEnter={() => setHover(i)} />
          ))}
        </div>
      </div>
      {pct != null && (
        <div className="hero-goal">
          <div className="goal-ring" style={{ "--pct": Math.min(pct, 100) }}>
            <div><strong>{pct}%</strong><span>da meta</span></div>
          </div>
          <span>Meta do período · {money(goal)}</span>
        </div>
      )}
    </div>
  );
}
