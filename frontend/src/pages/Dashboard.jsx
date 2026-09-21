import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { money, STATUS } from "../format";
import { ErrorBox, Swatch } from "../components/ui";

const today = () => new Date().toISOString().slice(0, 10);
const addDays = (base, days) => {
  const d = new Date(`${base}T00:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};
const startOfMonth = () => {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
};
const startOfYear = () => `${new Date().getFullYear()}-01-01`;

const PRESETS = [
  { key: "7d", label: "7 dias", start: () => addDays(today(), -6) },
  { key: "month", label: "Este mês", start: startOfMonth },
  { key: "year", label: "Este ano", start: startOfYear },
];

const STATUS_COLORS = {
  quote: "#8b96b3", confirmed: "#2f6fed", in_production: "#b8862f",
  shipped: "#0d95ac", delivered: "#1c7a52", canceled: "#9a5b12",
};

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

function previousPeriod(start, end) {
  const s = new Date(`${start}T00:00:00`);
  const e = new Date(`${end}T00:00:00`);
  const days = Math.round((e - s) / 86400000) + 1;
  const prevEnd = new Date(s);
  prevEnd.setDate(prevEnd.getDate() - 1);
  const prevStart = new Date(prevEnd);
  prevStart.setDate(prevStart.getDate() - days + 1);
  return { start: prevStart.toISOString().slice(0, 10), end: prevEnd.toISOString().slice(0, 10) };
}

function Delta({ cur, prev }) {
  if (!prev) return null;
  const pct = ((cur - prev) / prev) * 100;
  if (!isFinite(pct) || Math.abs(pct) < 0.5) return <span className="kpi-delta neutral">= período anterior</span>;
  const pos = pct >= 0;
  return (
    <span className={`kpi-delta ${pos ? "pos" : "neg"}`}>
      {pos ? "▲" : "▼"} {Math.abs(pct).toFixed(0)}%
    </span>
  );
}

function Ranking({ items, label, detail }) {
  const max = Math.max(...items.map((i) => i.value), 1);
  if (!items.length) return <p className="muted">Sem vendas no período.</p>;
  return (
    <ol className="ranking">
      {items.map((i, k) => (
        <li key={k}>
          <div className="ranking-row">
            <span className="ranking-left">
              <span className={`ranking-rank ${k === 0 ? "gold" : ""}`}>{k + 1}</span>
              <span className="ranking-name">{label(i)}</span>
            </span>
            <span className="ranking-value">{money(i.value)}</span>
          </div>
          <div className="ranking-bar"><span style={{ width: `${(i.value / max) * 100}%` }} /></div>
          <div className="ranking-detail">{detail(i)}</div>
        </li>
      ))}
    </ol>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const nav = useNavigate();
  const isAdmin = user?.role === "admin";
  const [activePreset, setActivePreset] = useState("year");
  const [start, setStart] = useState(startOfYear());
  const [end, setEnd] = useState(today());
  const [d, setD] = useState(null);
  const [dPrev, setDPrev] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const prev = previousPeriod(start, end);
    Promise.all([
      api.get("/dashboard", { params: { start, end } }),
      api.get("/dashboard", { params: prev }),
    ])
      .then(([r1, r2]) => { setD(r1.data); setDPrev(r2.data); setError(""); })
      .catch((e) => setError(errorMessage(e)));
  }, [start, end]);

  function applyPreset(p) {
    setActivePreset(p.key);
    setStart(p.start());
    setEnd(today());
  }

  return (
    <div className="page">
      <header className="dashboard-header">
        <div>
          <h1>{greeting()}, {user?.name?.split(" ")[0] || "vendedor"} 👋</h1>
          <p className="dashboard-greeting muted">Aqui está o resumo das vendas da Di Marcy no período.</p>
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
            <div className={`kpi kpi-highlight ${isAdmin ? "kpi-clickable" : ""}`}
              onClick={isAdmin ? () => nav("/revenue") : undefined}>
              <div className="kpi-header">
                <span>Faturamento</span>
                <span className="kpi-icon" aria-hidden="true">💰</span>
              </div>
              <strong>{money(d.kpis.revenue)}</strong>
              <Delta cur={d.kpis.revenue} prev={dPrev?.kpis.revenue} />
            </div>
            <div className="kpis-secondary">
              <div className={`kpi ${isAdmin ? "kpi-clickable" : ""}`} onClick={isAdmin ? () => nav("/orders") : undefined}>
                <div className="kpi-header"><span>Pedidos fechados</span><span className="kpi-icon icon-teal" aria-hidden="true">🧾</span></div>
                <strong>{d.kpis.orders}</strong>
                <Delta cur={d.kpis.orders} prev={dPrev?.kpis.orders} />
              </div>
              <div className="kpi">
                <div className="kpi-header"><span>Peças vendidas</span><span className="kpi-icon icon-indigo" aria-hidden="true">📦</span></div>
                <strong>{d.kpis.pieces}</strong>
                <Delta cur={d.kpis.pieces} prev={dPrev?.kpis.pieces} />
              </div>
              <div className="kpi">
                <div className="kpi-header"><span>Ticket médio</span><span className="kpi-icon icon-gold" aria-hidden="true">🎫</span></div>
                <strong>{money(d.kpis.average_ticket)}</strong>
                <Delta cur={d.kpis.average_ticket} prev={dPrev?.kpis.average_ticket} />
              </div>
            </div>
          </section>

          <section className="dashboard-grid">
            <div className="panel panel-wide">
              <h3>Faturamento nos últimos 12 meses</h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={d.monthly_sales} margin={{ left: 10 }}>
                  <defs>
                    <linearGradient id="barColor" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2f6fed" />
                      <stop offset="100%" stopColor="#1f5296" />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke="#e3e8f2" />
                  <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis tickLine={false} axisLine={false} fontSize={12}
                    tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)} />
                  <Tooltip cursor={{ fill: "rgba(47, 111, 237, 0.08)", radius: 6 }}
                    formatter={(v, n) => (n === "value" ? [money(v), "Faturamento"] : [v, "Peças"])} />
                  <Bar dataKey="value" fill="url(#barColor)" radius={[4, 4, 0, 0]} maxBarSize={34} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="panel panel-fill">
              <h3>Situação dos pedidos</h3>
              <div className="panel-fill-body">
                {d.by_status.length ? (
                  <div className="donut-row">
                    <ResponsiveContainer width={168} height={168}>
                      <PieChart>
                        <Pie data={d.by_status} dataKey="count" nameKey="status" innerRadius={50} outerRadius={80} paddingAngle={2}>
                          {d.by_status.map((s) => <Cell key={s.status} fill={STATUS_COLORS[s.status] || "#8b96b3"} />)}
                        </Pie>
                        <Tooltip formatter={(v, n, p) => [`${v} pedido(s)`, STATUS[p.payload.status]]} />
                      </PieChart>
                    </ResponsiveContainer>
                    <ul className="donut-legend">
                      {d.by_status.map((s) => (
                        <li key={s.status}>
                          <span className="legend-dot" style={{ background: STATUS_COLORS[s.status] || "#8b96b3" }} />
                          <span className="legend-name">{STATUS[s.status] || s.status}</span>
                          <span className="legend-qty">{s.count}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : <p className="muted">Sem pedidos no período.</p>}
              </div>
            </div>

            <div className="panel">
              <h3>Cores mais vendidas</h3>
              {d.by_color.length ? (
                <div className="donut-row">
                  <ResponsiveContainer width={110} height={110}>
                    <PieChart>
                      <Pie data={d.by_color} dataKey="pieces" nameKey="name" innerRadius={32} outerRadius={50} paddingAngle={2}>
                        {d.by_color.map((c) => <Cell key={c.name} fill={c.hex} stroke="rgba(0,0,0,.1)" />)}
                      </Pie>
                      <Tooltip formatter={(v, n, p) => [`${v} peças`, p.payload.name]} />
                    </PieChart>
                  </ResponsiveContainer>
                  <ul className="donut-legend">
                    {d.by_color.slice(0, 6).map((c) => (
                      <li key={c.name}>
                        <Swatch hex={c.hex} size={10} />
                        <span className="legend-name">{c.name}</span>
                        <span className="legend-qty">{c.pieces}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : <p className="muted">Sem vendas no período.</p>}
            </div>

            <div className="panel">
              <h3>Produtos mais vendidos</h3>
              <Ranking items={d.top_products} label={(i) => `${i.reference} · ${i.description}`}
                detail={(i) => `${i.pieces} peças`} />
            </div>

            <div className="panel">
              <h3>Melhores clientes</h3>
              <Ranking items={d.top_customers} label={(i) => i.name}
                detail={(i) => `${i.orders} pedidos · ${i.pieces} peças`} />
            </div>

            <div className="panel">
              <h3>Peças por tamanho</h3>
              {d.by_size.length ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={d.by_size} margin={{ left: 10 }}>
                    <defs>
                      <linearGradient id="barColorSizes" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#2f6fed" />
                        <stop offset="100%" stopColor="#1f5296" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke="#e3e8f2" />
                    <XAxis dataKey="size" tickLine={false} axisLine={false} fontSize={12} />
                    <YAxis tickLine={false} axisLine={false} fontSize={12} allowDecimals={false} />
                    <Tooltip cursor={{ fill: "rgba(47, 111, 237, 0.08)", radius: 6 }}
                      formatter={(v) => [`${v} peças`, ""]} labelFormatter={(l) => `Tamanho ${l}`} />
                    <Bar dataKey="pieces" fill="url(#barColorSizes)" radius={[4, 4, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <p className="muted">Sem vendas no período.</p>}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
