import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, errorMessage } from "../api";
import { money } from "../format";
import { ErrorBox } from "../components/ui";

function RankedBarChart({ data, height }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20 }}>
        <defs>
          <linearGradient id="barColorRevenue" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#1f5296" />
            <stop offset="100%" stopColor="#2f6fed" />
          </linearGradient>
        </defs>
        <CartesianGrid horizontal={false} stroke="#e3e8f2" />
        <XAxis type="number" tickLine={false} axisLine={false} fontSize={12}
          tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)} />
        <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} fontSize={12} width={130} />
        <Tooltip cursor={{ fill: "rgba(47, 111, 237, 0.08)" }} formatter={(v) => [money(v), "Faturamento"]} />
        <Bar dataKey="value" fill="url(#barColorRevenue)" radius={[0, 4, 4, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
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
              {sellers.length ? (
                <RankedBarChart data={sellers} height={Math.max(160, sellers.length * 40)} />
              ) : <p className="muted">Sem vendas no período.</p>}
            </section>

            <section className="panel">
              <h3>Por cidade</h3>
              {cities.length ? (
                <RankedBarChart data={cities} height={Math.max(160, cities.length * 40)} />
              ) : <p className="muted">Sem vendas no período.</p>}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
