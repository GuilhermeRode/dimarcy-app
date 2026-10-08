import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Cell, Pie, PieChart } from "recharts";
import { api } from "../api";
import { useAuth } from "../auth";
import { compactMoney, initials, money, plural, STATUS } from "../format";
import { ErrorBox } from "../components/ui";
import AlertStrip from "../components/AlertStrip";
import Delta from "../components/Delta";
import PeriodPicker, { defaultPeriod } from "../components/PeriodPicker";
import RevenueHero from "../components/RevenueHero";
import TeamRanking from "../components/TeamRanking";
import usePeriodData from "../components/usePeriodData";

const EXCLUDE_MAP = import.meta.env.VITE_EXCLUDE_MAP === "1";

const STATUS_COLORS = {
  quote: "#8b96b3", confirmed: "#2f6fed", in_production: "#b8862f",
  shipped: "#0d95ac", delivered: "#0c2140", canceled: "#c0392b",
};

function greeting(h = new Date().getHours()) {
  if (h < 5) return "Boa noite"; // after midnight it's still night, not morning
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

function todayLabel() {
  const s = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const Empty = () => <p className="muted">Sem vendas no período.</p>;

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const monthLabel = (mmYY) => `${MONTHS[Number(mmYY.slice(0, 2)) - 1]}/${mmYY.slice(3)}`; // "10/26" -> "out/26"

// 12 bars, current month dark; clicking a bar shows that month's numbers beside the chart.
function MonthlyBars({ months }) {
  const [sel, setSel] = useState(months.length - 1);
  const max = Math.max(...months.map((m) => m.value), 1);
  const m = months[sel];
  const prev = months[sel - 1];
  return (
    <div className="month-chart">
      <div className="month-bars" role="group" aria-label="Faturamento por mês">
        {months.map((x, i) => (
          <button key={x.month} type="button" title={`${monthLabel(x.month)}: ${money(x.value)}`}
            className={`${i === months.length - 1 ? "current" : ""} ${i === sel ? "on" : ""}`}
            aria-pressed={i === sel} onClick={() => setSel(i)}>
            <span style={{ height: `${Math.max(2, (x.value / max) * 100)}%` }} />
            <small>{MONTHS[Number(x.month.slice(0, 2)) - 1]}</small>
          </button>
        ))}
      </div>
      <div className="month-card">
        <span>{monthLabel(m.month)}{sel === months.length - 1 ? " (parcial)" : ""}</span>
        <strong>{compactMoney(m.value)}</strong>
        <small>{plural(m.orders, "pedido", "pedidos")} · {plural(m.pieces, "peça", "peças")}</small>
        {prev && prev.value > 0 && (
          <span className="month-card-delta"><Delta cur={m.value} prev={prev.value} /> vs. {MONTHS[Number(prev.month.slice(0, 2)) - 1]}</span>
        )}
      </div>
    </div>
  );
}

function StatusDonut({ items }) {
  const [active, setActive] = useState(null);
  const total = items.reduce((t, s) => t + s.count, 0);
  const sel = active == null ? null : items[active];
  if (!total) return <p className="muted">Sem pedidos no período.</p>;
  return (
    <div className="donut-row" onMouseLeave={() => setActive(null)}>
      <div className="donut">
        <PieChart width={184} height={184}>
          <Pie data={items} dataKey="count" nameKey="status" innerRadius={62} outerRadius={90} paddingAngle={2}
            onMouseEnter={(_, i) => setActive(i)} isAnimationActive={false}>
            {items.map((s, i) => (
              <Cell key={s.status} fill={STATUS_COLORS[s.status] || "#8b96b3"} opacity={active == null || active === i ? 1 : 0.25} />
            ))}
          </Pie>
        </PieChart>
        <div className="donut-center">
          <strong>{sel ? sel.count : total}</strong>
          <span>{sel ? STATUS[sel.status] : "pedidos no período"}</span>
          {sel && <small>{Math.round((sel.count / total) * 100)}% do total</small>}
        </div>
      </div>
      <ul className="donut-legend">
        {items.map((s, i) => (
          <li key={s.status} className={active === i ? "on" : ""} onMouseEnter={() => setActive(i)}>
            <span className="legend-dot" style={{ background: STATUS_COLORS[s.status] || "#8b96b3" }} />
            <span className="legend-name">{STATUS[s.status] || s.status}</span>
            <span className="legend-qty">{s.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Bars({ items, label, value, detail }) {
  if (!items.length) return <Empty />;
  const max = Math.max(...items.map(value), 1);
  return (
    <ul className="hbars">
      {items.map((i, k) => (
        <li key={k}>
          <div><span>{label(i)}</span><strong>{detail(i)}</strong></div>
          <span className="hbar"><span style={{ width: `${(value(i) / max) * 100}%` }} /></span>
        </li>
      ))}
    </ul>
  );
}

// With dozens of colors a strip or donut turns into slivers: rank the top ones and pool the rest.
const TOP_COLORS = 8;
function ColorRanking({ colors, totalPieces }) {
  if (!colors.length || !totalPieces) return <Empty />;
  const top = colors.slice(0, TOP_COLORS); // the API sends every color, already ranked by pieces
  const others = totalPieces - top.reduce((t, c) => t + c.pieces, 0);
  const rows = others > 0 ? [...top, { name: "Outras cores", hex: null, pieces: others }] : top;
  const max = Math.max(...rows.map((c) => c.pieces), 1);
  return (
    <ul className="color-ranking">
      {rows.map((c) => (
        <li key={c.name} className={c.hex ? "" : "others"}>
          <span className="swatch" style={{ background: c.hex || "var(--line)", width: 12, height: 12 }} />
          <span className="color-name">{c.name}</span>
          <span className="hbar"><span style={{ width: `${(c.pieces / max) * 100}%`, background: c.hex || "var(--muted)" }} /></span>
          <strong>{Math.round((c.pieces / totalPieces) * 100)}%</strong>
        </li>
      ))}
    </ul>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const nav = useNavigate();
  const isAdmin = user?.role === "admin";
  const [period, setPeriod] = useState(defaultPeriod);
  const { data: d, error } = usePeriodData(period);
  const [topCities, setTopCities] = useState([]);

  useEffect(() => {
    if (!isAdmin || EXCLUDE_MAP) return;
    api.get("/customers").then((r) => {
      const counts = new Map();
      for (const c of r.data) {
        if (!c.city) continue;
        const key = `${c.city.trim()}/${(c.state || "").trim().toUpperCase()}`;
        counts.set(key, (counts.get(key) || 0) + 1);
      }
      setTopCities([...counts.entries()].map(([name, count]) => ({ name, count }))
        .sort((a, b) => b.count - a.count).slice(0, 5));
    });
  }, [isAdmin]);

  const sizeMax = d ? Math.max(...d.by_size.map((s) => s.pieces), 1) : 1;
  const kpis = d && [
    ["Pedidos fechados", d.kpis.orders, d.previous_kpis.orders, (v) => v.toLocaleString("pt-BR")],
    ["Peças vendidas", d.kpis.pieces, d.previous_kpis.pieces, (v) => v.toLocaleString("pt-BR")],
    ["Ticket médio", d.kpis.average_ticket, d.previous_kpis.average_ticket, money],
  ];

  return (
    <div className="page">
      <header className="dashboard-header">
        <div>
          <p className="dashboard-date muted">{todayLabel()}</p>
          <h1>{greeting()}, {user?.name?.split(" ")[0] || "vendedor"}</h1>
        </div>
        <PeriodPicker value={period} onChange={setPeriod} />
      </header>
      <ErrorBox msg={error} />
      {d && (
        <>
          <section className="hero-row">
            <RevenueHero title="Faturamento no período" revenue={d.kpis.revenue} prevRevenue={d.previous_kpis.revenue}
              series={d.sales_series} goal={d.goal} onClick={isAdmin ? () => nav("/revenue") : undefined} />
            <div className="kpi-stack">
              {kpis.map(([label, cur, prev, fmt]) => (
                <div key={label}>
                  <span>{label}</span><strong>{fmt(cur)}</strong><Delta cur={cur} prev={prev} />
                </div>
              ))}
            </div>
          </section>

          <AlertStrip alerts={d.alerts} />

          <section className="dash-row">
            <div className="panel dash-wide">
              <h3>Faturamento nos últimos 12 meses</h3>
              <MonthlyBars months={d.monthly_sales} />
            </div>
            <div className="panel">
              <div className="panel-header"><h3>Situação dos pedidos</h3></div>
              <StatusDonut items={d.by_status} />
            </div>
          </section>

          {isAdmin && <TeamRanking title="Equipe comercial no período" sellers={d.by_seller} />}

          <section className="dash-grid-3">
            <div className="panel">
              <h3>Cores mais vendidas</h3>
              <ColorRanking colors={d.by_color} totalPieces={d.kpis.pieces} />
            </div>
            <div className="panel">
              <div className="panel-header"><h3>Peças por tamanho</h3><span className="muted">{plural(d.kpis.pieces, "peça", "peças")}</span></div>
              {d.by_size.length ? (
                <div className="vbars">
                  {d.by_size.map((s) => (
                    <div key={s.size}>
                      <small>{Math.round((s.pieces / Math.max(d.kpis.pieces, 1)) * 100)}%</small>
                      <span className={s.pieces === sizeMax ? "top" : ""} style={{ height: `${(s.pieces / sizeMax) * 78}%` }} />
                      <strong>{s.size}</strong>
                    </div>
                  ))}
                </div>
              ) : <Empty />}
            </div>
            <div className="panel">
              <h3>Produtos mais vendidos</h3>
              <Bars items={d.top_products.slice(0, 5)} label={(i) => `${i.reference} · ${i.description}`}
                value={(i) => i.pieces} detail={(i) => `${i.pieces} pç`} />
            </div>
          </section>

          <section className="dash-grid-2">
            <div className="panel">
              <div className="panel-header">
                <h3>Melhores clientes</h3>
                <button type="button" className="link-btn" onClick={() => nav("/customers?sort=total")}>Ver todos →</button>
              </div>
              {d.top_customers.length ? (
                <ol className="top-customers">
                  {d.top_customers.slice(0, 5).map((c, i) => (
                    <li key={i}>
                      <span className="rank">{i + 1}</span>
                      <span className="customer-avatar">{initials(c.name)}</span>
                      <span className="grow"><strong>{c.name}</strong><small>{plural(c.orders, "pedido", "pedidos")}</small></span>
                      <strong>{compactMoney(c.value)}</strong>
                    </li>
                  ))}
                </ol>
              ) : <Empty />}
            </div>
            {!EXCLUDE_MAP && isAdmin && topCities.length > 0 && (
              <div className="panel">
                <div className="panel-header">
                  <h3>Clientes por cidade</h3>
                  <button type="button" className="link-btn" onClick={() => nav("/customers-by-city")}>Ver mapa →</button>
                </div>
                <Bars items={topCities} label={(i) => i.name} value={(i) => i.count} detail={(i) => i.count} />
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
