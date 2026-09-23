import { useEffect, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api, errorMessage } from "../api";
import { money } from "../format";
import { ErrorBox, Swatch } from "../components/ui";

const PIE_COLORS = ["#2f6fed", "#4338ca", "#b8862f", "#0d95ac", "#1c7a52", "#5c6c8a"];

function topWithOthers(list, n = 6) {
  const top = list.slice(0, n);
  const rest = list.slice(n).reduce((s, i) => s + i.value, 0);
  return rest > 0 ? [...top, { name: "Outros", value: rest }] : top;
}

function RevenueDonut({ data }) {
  const items = topWithOthers(data);
  return (
    <div className="donut-row">
      <ResponsiveContainer width={150} height={150}>
        <PieChart>
          <Pie data={items} dataKey="value" nameKey="name" innerRadius={42} outerRadius={68} paddingAngle={2}>
            {items.map((it, i) => <Cell key={it.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
          </Pie>
          <Tooltip formatter={(v) => money(v)} />
        </PieChart>
      </ResponsiveContainer>
      <ul className="donut-legend">
        {items.map((it, i) => (
          <li key={it.name}>
            <Swatch hex={PIE_COLORS[i % PIE_COLORS.length]} size={10} />
            <span className="legend-name">{it.name}</span>
            <span className="legend-qty">{money(it.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const today = () => new Date().toISOString().slice(0, 10);
const startOfYear = () => `${new Date().getFullYear()}-01-01`;
const startOfMonth = () => {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
};
const addDays = (base, days) => {
  const d = new Date(`${base}T00:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

const PRESETS = [
  { key: "7d", label: "7 dias", start: () => addDays(today(), -6) },
  { key: "month", label: "Este mês", start: startOfMonth },
  { key: "year", label: "Este ano", start: startOfYear },
];

export default function Revenue() {
  const [activePreset, setActivePreset] = useState("year");
  const [start, setStart] = useState(startOfYear());
  const [end, setEnd] = useState(today());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/dashboard", { params: { start, end } })
      .then((r) => { setD(r.data); setError(""); })
      .catch((e) => setError(errorMessage(e)));
  }, [start, end]);

  function applyPreset(p) {
    setActivePreset(p.key);
    setStart(p.start());
    setEnd(today());
  }

  const sellers = d?.by_seller || [];
  const cities = d?.by_city || [];
  const totals = sellers.reduce((a, s) => ({
    orders: a.orders + s.orders, pieces: a.pieces + s.pieces, value: a.value + s.value,
  }), { orders: 0, pieces: 0, value: 0 });

  return (
    <div className="page">
      <header className="dashboard-header">
        <div>
          <h1>Faturamento</h1>
          <p className="dashboard-greeting muted">Desempenho de vendas por vendedor no período.</p>
        </div>
        <div className="period-block">
          <div className="period-chips">
            {PRESETS.map((p) => (
              <button key={p.key} type="button" className={`period-chip ${activePreset === p.key ? "on" : ""}`}
                onClick={() => applyPreset(p)}>{p.label}</button>
            ))}
          </div>
          <div className="period-filter">
            <input type="date" value={start} aria-label="Início"
              onChange={(e) => { setActivePreset(""); setStart(e.target.value); }} />
            <span>até</span>
            <input type="date" value={end} aria-label="Fim"
              onChange={(e) => { setActivePreset(""); setEnd(e.target.value); }} />
          </div>
        </div>
      </header>
      <ErrorBox msg={error} />

      {d && (
        <>
          <section className="kpis">
            <div className="kpi kpi-highlight">
              <div className="kpi-header"><span>Faturamento total</span><span className="kpi-icon" aria-hidden="true">💰</span></div>
              <strong>{money(totals.value)}</strong>
            </div>
            <div className="kpis-secondary">
              <div className="kpi">
                <div className="kpi-header"><span>Vendedores ativos</span><span className="kpi-icon icon-teal" aria-hidden="true">🧑‍💼</span></div>
                <strong>{sellers.length}</strong>
              </div>
              <div className="kpi">
                <div className="kpi-header"><span>Pedidos</span><span className="kpi-icon icon-indigo" aria-hidden="true">🧾</span></div>
                <strong>{totals.orders}</strong>
              </div>
              <div className="kpi">
                <div className="kpi-header"><span>Peças</span><span className="kpi-icon icon-gold" aria-hidden="true">📦</span></div>
                <strong>{totals.pieces}</strong>
              </div>
            </div>
          </section>

          <div className="revenue-charts">
            <section className="panel">
              <h3>Por vendedor</h3>
              {sellers.length ? <RevenueDonut data={sellers} /> : <p className="muted">Sem vendas no período.</p>}
            </section>

            <section className="panel">
              <h3>Por cidade</h3>
              {cities.length ? <RevenueDonut data={cities} /> : <p className="muted">Sem vendas no período.</p>}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
