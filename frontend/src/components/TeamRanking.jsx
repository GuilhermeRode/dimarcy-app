import { useState } from "react";
import { money, plural } from "../format";
import { Avatar } from "./ui";

// Index i always gets the same color, so a seller keeps their color across components.
export const SELLER_COLORS = ["#5aa2ff", "#86efac", "#fcd34d", "#c4b5fd", "#f9a8d4", "#67e8f9", "#fdba74", "#a5b4fc"];

const METRICS = {
  value: { label: "Faturamento", fmt: money },
  orders: { label: "Pedidos", fmt: (n) => plural(n, "pedido", "pedidos") },
  pieces: { label: "Peças", fmt: (n) => plural(n, "peça", "peças") },
  goal: { label: "% da meta" },
};

// `sellers` = dashboard by_seller (already sorted by revenue).
export default function TeamRanking({ title, sellers, showGoalGap = false }) {
  const [metric, setMetric] = useState("value");
  const hasGoal = sellers.some((s) => s.goal);
  const m = metric === "goal" && !hasGoal ? "value" : metric;
  if (!sellers.length) return null;

  const score = (s) => (m === "goal" ? (s.goal ? (s.value / s.goal) * 100 : -1) : s[m]);
  const rows = sellers.map((s, i) => ({ ...s, color: SELLER_COLORS[i % SELLER_COLORS.length] }))
    .sort((a, b) => score(b) - score(a));
  const best = Math.max(score(rows[0]), 1);
  const teamTotal = sellers.reduce((t, s) => t + s[m === "goal" ? "value" : m], 0);
  const lead = score(rows[0]) > 0
    ? `${rows[0].name.split(" ")[0]} lidera em ${METRICS[m].label.toLowerCase()}`
    : "Sem vendas no período";

  return (
    <section className="team">
      <div className="team-head">
        <div><span>{title}</span><strong>{lead}</strong></div>
        <div className="team-tabs" role="tablist">
          {Object.entries(METRICS).filter(([k]) => k !== "goal" || hasGoal).map(([k, def]) => (
            <button key={k} type="button" role="tab" aria-selected={m === k} className={m === k ? "on" : ""}
              onClick={() => setMetric(k)}>{def.label}</button>
          ))}
        </div>
      </div>
      <div className="team-grid">
        {rows.map((s, i) => (
          <div key={s.id} className="team-card">
            <div className="team-card-head">
              <Avatar url={s.avatar_url} name={s.name} />
              <div><strong>{s.name}</strong><span>{i + 1}º lugar</span></div>
            </div>
            <strong className="team-value">
              {m === "goal" ? (s.goal ? `${Math.round(score(s))}%` : "Sem meta") : METRICS[m].fmt(s[m])}
            </strong>
            <div className="team-bar"><span style={{ width: `${Math.max(0, score(s)) / best * 100}%`, background: s.color }} /></div>
            <span className="team-sub">
              {m === "goal"
                ? (s.goal ? `Meta ${money(s.goal)}` : "Defina em Usuários")
                : `${teamTotal ? Math.round((s[m] / teamTotal) * 100) : 0}% do total da equipe`}
            </span>
            {showGoalGap && s.goal > 0 && (
              <span className="team-sub">
                {s.value >= s.goal ? "Meta do período batida" : `Faltam ${money(s.goal - s.value)} para a meta`}
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
