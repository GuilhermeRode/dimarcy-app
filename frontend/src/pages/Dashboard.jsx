import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { compactMoney, CUSTOMER_STATUS, hideable, initials, localDate, money, plural, STATUS } from "../format";
import { ErrorBox } from "../components/ui";
import { ColorList, ColorStrip, pooledColors, ProductThumb, RefColors } from "../components/ColorStrip";
import AlertStrip from "../components/AlertStrip";
import Delta from "../components/Delta";
import PeriodPicker, { defaultPeriod } from "../components/PeriodPicker";
import RevenueHero from "../components/RevenueHero";
import TeamRanking from "../components/TeamRanking";
import usePeriodData from "../components/usePeriodData";


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

// 12 bars, current month dark; hovering a bar previews that month's numbers beside the chart, clicking keeps it there.
function MonthlyBars({ months, hide }) {
  const [picked, setSel] = useState(months.length - 1);
  const [hover, setHover] = useState(null);
  const sel = hover ?? picked;
  const max = Math.max(...months.map((m) => m.value), 1);
  const m = months[sel];
  const prev = months[sel - 1];
  return (
    <div className="month-chart">
      <div className="month-bars" role="group" aria-label="Faturamento por mês" onMouseLeave={() => setHover(null)}>
        {months.map((x, i) => (
          <button key={x.month} type="button" aria-label={`${monthLabel(x.month)}: ${hideable(hide, money)(x.value)}`}
            className={`${i === months.length - 1 ? "current" : ""} ${i === sel ? "on" : ""}`}
            aria-pressed={i === picked} onClick={() => setSel(i)} onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)}
            onBlur={() => setHover(null)}>
            <span style={{ height: x.value > 0 ? `${Math.max(2, (x.value / max) * 100)}%` : 0 }} />
            <small>{MONTHS[Number(x.month.slice(0, 2)) - 1]}</small>
          </button>
        ))}
      </div>
      <div className="month-card">
        <span>{monthLabel(m.month)}{sel === months.length - 1 ? " (parcial)" : ""}</span>
        <strong>{hideable(hide, compactMoney)(m.value)}</strong>
        <small>{plural(m.orders, "pedido", "pedidos")} · {plural(m.pieces, "peça", "peças")}</small>
        {prev && prev.value > 0 && (
          <span className="month-card-delta"><Delta cur={m.value} prev={prev.value} /> vs. {MONTHS[Number(prev.month.slice(0, 2)) - 1]}</span>
        )}
      </div>
    </div>
  );
}

// The stages are an order (quote → delivered), so they take one blue from light to dark instead of six
// unrelated hues; canceled is the gray outside the path. Ramp checked with the dataviz validator (--ordinal).
const STATUS_ORDER = ["quote", "confirmed", "in_production", "shipped", "delivered", "canceled"];
const STATUS_RAMP = { quote: "#7fa8f0", confirmed: "#4a82e8", in_production: "#2257c9", shipped: "#163f8f", delivered: "#0c2140", canceled: "#8b96b3" };
const DONUT_R = 74;
const DONUT_LEN = 2 * Math.PI * DONUT_R;

function StatusDonut({ items, hide }) {
  const brl = hideable(hide, compactMoney);
  const [active, setActive] = useState(null);
  const total = items.reduce((t, s) => t + s.count, 0);
  if (!total) return <p className="muted">Sem pedidos no período.</p>;
  const order = (k) => (STATUS_ORDER.includes(k) ? STATUS_ORDER.indexOf(k) : STATUS_ORDER.length);
  const rows = items.filter((s) => s.count).sort((a, b) => order(a.status) - order(b.status));
  const gap = rows.length > 1 ? 2 : 0; // the surface shows between touching segments
  let offset = 0;
  const arcs = rows.map((s) => {
    const len = (s.count / total) * DONUT_LEN;
    const arc = { ...s, dash: `${Math.max(len - gap, 1)} ${DONUT_LEN}`, offset: -offset };
    offset += len;
    return arc;
  });
  const sel = rows.find((s) => s.status === active);
  return (
    <div className="donut-row" onMouseLeave={() => setActive(null)}>
      <div className="donut">
        <svg viewBox="0 0 184 184" width="184" height="184" role="img"
          aria-label={rows.map((s) => `${STATUS[s.status] || s.status}: ${s.count}`).join(", ")}>
          <g transform="rotate(-90 92 92)">
            {arcs.map((a) => (
              <circle key={a.status} cx="92" cy="92" r={DONUT_R} fill="none" strokeWidth="24"
                stroke={STATUS_RAMP[a.status] || "#8b96b3"} strokeDasharray={a.dash} strokeDashoffset={a.offset}
                opacity={active == null || active === a.status ? 1 : 0.3} onMouseEnter={() => setActive(a.status)} />
            ))}
          </g>
        </svg>
        <div className="donut-center">
          <strong>{sel ? sel.count : total}</strong>
          <span>{sel ? STATUS[sel.status] || sel.status : total === 1 ? "pedido" : "pedidos"}</span>
          <small>{sel ? `${Math.round((sel.count / total) * 100)}% · ${brl(sel.value)}` : "no período"}</small>
        </div>
      </div>
      <ul className="donut-legend">
        {rows.map((s) => (
          <li key={s.status} className={active === s.status ? "on" : ""} onMouseEnter={() => setActive(s.status)}>
            <span className="legend-dot" style={{ background: STATUS_RAMP[s.status] || "#8b96b3" }} />
            <span className="legend-name">{STATUS[s.status] || s.status}</span>
            <strong>{s.count}</strong>
            <small>{brl(s.value)}</small>
          </li>
        ))}
      </ul>
    </div>
  );
}

const pct = (part, whole) => `${Math.round((part / Math.max(whole, 1)) * 100)}%`;
const daysSince = (iso, today) => Math.round((Date.parse(today) - Date.parse(iso)) / 86400000);

// Best customers of the period, each with its city, when it last bought and whether it is still active
function TopCustomers({ customers, revenue, overview, hide }) {
  if (!customers.length) return <Empty />;
  const today = localDate();
  return (
    <div className="top-customers">
      <ol className="ranking">
        {customers.map((c, i) => {
          const o = overview.get(c.id);
          const last = o?.last_order_date ? daysSince(o.last_order_date, today) : null;
          const where = o?.city ? `${o.city}${o.state ? `/${o.state}` : ""}` : null;
          return (
            <li key={c.id}>
              <span className="rank">{i + 1}</span>
              <span className="customer-avatar">{initials(c.name)}</span>
              <span className="grow">
                <span className="rank-line"><span className="rank-title">{c.name}</span><strong>{hideable(hide, compactMoney)(c.value)}</strong></span>
                <span className="rank-line">
                  <small className="rank-sub">
                    {[where, last == null ? null : last === 0 ? "comprou hoje" : `último pedido há ${last} d`].filter(Boolean).join(" · ")}
                  </small>
                  <small>{pct(c.value, revenue)}</small>
                </span>
              </span>
              {o && <span className={`cstatus cstatus-${CUSTOMER_STATUS[o.status].tone}`}>{CUSTOMER_STATUS[o.status].label}</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

// The "Retornos pendentes" card: the headline count, a strip of its mix and the counts.
// `parts` are [cssKey, label, count]; the head goes to the screen where they're worked.
function ContactSide({ title, total, caption, parts, to, nav }) {
  const all = parts.reduce((t, [, , n]) => t + n, 0);
  return (
    <div className="follow-side">
      <button type="button" className="follow-head" onClick={() => nav(to)}>
        <span>{title}</span>
        <strong>{total}</strong>
        <small>{caption}</small>
      </button>
      <div className="follow-strip" role="img" aria-label={parts.map(([, label, n]) => `${n} ${label}`).join(", ")}>
        {all > 0 && parts.map(([k, , n]) => n > 0 && <span key={k} className={`fu-${k}`} style={{ flexGrow: n }} />)}
      </div>
      <ul className="follow-counts">
        {parts.map(([k, label, n]) => (
          <li key={k} className={n ? "" : "zero"}><i className={`fu-${k}`} aria-hidden="true" /><strong>{n}</strong> {label}</li>
        ))}
      </ul>
    </div>
  );
}

// Leads with a call-back due (the Retornos screen), by urgency; for an admin, also the stores being worked (not Pendentes)
function ContactsCard({ leads, firstContact, nav }) {
  return (
    <div className="follow-card">
      <ContactSide title="Leads" total={leads.overdue + leads.today} caption="retornos para fazer" to="/follow-ups" nav={nav}
        parts={[["late", "atrasados", leads.overdue], ["today", "para hoje", leads.today], ["week", "nos próximos 7 dias", leads.week]]} />
      {firstContact && (
        <ContactSide title="Prospecção" total={firstContact.contacted + firstContact.new} caption="lojas em andamento" to="/leads" nav={nav}
          parts={[["today", "em primeiro contato", firstContact.contacted], ...(firstContact.new ? [["week", "liberados", firstContact.new]] : [])]} />
      )}
    </div>
  );
}

// One ranked row per item: position, an optional picture, a title with its measure, a sub-line with
// a detail, and a bar for the measure in the colors sold. `measure` drives the bar, the rest is text.
function Ranking({ rows }) {
  if (!rows.length) return <Empty />;
  const max = Math.max(...rows.map((r) => r.measure), 1);
  return (
    <ol className="ranking">
      {rows.map((r, i) => (
        <li key={r.key}>
          <span className="rank">{i + 1}</span>
          {r.lead}
          <span className="grow">
            <span className="rank-line"><span className="rank-title">{r.title}</span><strong>{r.value}</strong></span>
            <span className="rank-line"><small className="rank-sub">{r.sub}</small><small>{r.detail}</small></span>
            <RefColors colors={r.colors} total={r.measure} style={{ width: `${(r.measure / max) * 100}%` }} />
          </span>
        </li>
      ))}
    </ol>
  );
}

// The mix of the period as one strip in the real fabric colors, then the ranking. With dozens of
// colors the strip turns into slivers, so the top ones are ranked and the rest pooled.
const TOP_COLORS = 8;
function ColorRanking({ colors, totalPieces }) {
  if (!colors.length || !totalPieces) return <Empty />;
  const rows = pooledColors(colors, totalPieces, TOP_COLORS); // the API sends every color, already ranked by pieces
  return (
    <div className="color-mix">
      <ColorStrip colors={rows} total={totalPieces} />
      <ColorList colors={rows} total={totalPieces} />
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const nav = useNavigate();
  const isAdmin = user?.role === "admin";
  const [period, setPeriod] = useState(defaultPeriod);
  const { data: d, error } = usePeriodData(period);
  // The customer base (not the period): city, last order and status of the best customers
  const [overview, setOverview] = useState([]);
  useEffect(() => { api.get("/customers/overview").then((r) => setOverview(r.data)).catch(() => {}); }, []);
  const byId = new Map(overview.map((c) => [c.id, c]));

  const [hide, setHide] = useState(true);  // the eye: every Painel visit starts with the values hidden
  const sizeMax = d ? Math.max(...d.by_size.map((s) => s.pieces), 1) : 1;
  const kpis = d && [
    ["Pedidos fechados", d.kpis.orders, d.previous_kpis.orders, (v) => v.toLocaleString("pt-BR")],
    ["Peças vendidas", d.kpis.pieces, d.previous_kpis.pieces, (v) => v.toLocaleString("pt-BR")],
    ["Ticket médio", d.kpis.average_ticket, d.previous_kpis.average_ticket, hideable(hide, money)],
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
              series={d.sales_series} goal={d.goal} goalValue={d.goal_value} onClick={isAdmin ? () => nav("/revenue") : undefined}
              hide={hide} onToggleHide={() => setHide(!hide)} />
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
              <MonthlyBars months={d.monthly_sales} hide={hide} />
            </div>
            <div className="panel">
              <div className="panel-header"><h3>Situação dos pedidos</h3></div>
              <StatusDonut items={d.by_status} hide={hide} />
            </div>
          </section>

          {isAdmin && <TeamRanking title="Equipe comercial no período" sellers={d.by_seller} hide={hide} />}

          <section className="dash-grid-3">
            <div className="panel">
              <h3>Cores mais vendidas</h3>
              <ColorRanking colors={d.by_color} totalPieces={d.kpis.pieces} />
            </div>
            <div className="panel">
              <div className="panel-header"><h3>Peças por tamanho</h3><span className="muted">{plural(d.kpis.pieces, "peça", "peças")}</span></div>
              {d.by_size.length ? (
                <div className="size-bars">
                  {d.by_size.map((s) => (
                    <div key={s.size} className={s.pieces === sizeMax ? "top" : ""} title={plural(s.pieces, "peça", "peças")}>
                      <span style={{ height: `${(s.pieces / sizeMax) * 100}%` }}>
                        <b>{Math.round((s.pieces / Math.max(d.kpis.pieces, 1)) * 100)}%</b>
                      </span>
                      <strong>{s.size}</strong>
                    </div>
                  ))}
                </div>
              ) : <Empty />}
            </div>
            <div className="panel">
              <div className="panel-header">
                <h3>Referências mais vendidas</h3>
                {d.top_products.length > 0 && (
                  <button type="button" className="link-btn" onClick={() => nav("/top-products", { state: { period } })}>Ver todas →</button>
                )}
              </div>
              <Ranking rows={d.top_products.slice(0, 3).map((p) => ({
                key: p.reference, lead: <ProductThumb url={p.thumb_url} />, measure: p.pieces, colors: p.colors,
                title: <span className="ref">{p.reference}</span>, value: `${p.pieces.toLocaleString("pt-BR")} pç`,
                sub: p.description, detail: hideable(hide, compactMoney)(p.value),
              }))} />
            </div>
          </section>

          <section className="dash-grid-2">
            <div className="panel">
              <div className="panel-header">
                <h3>Melhores clientes</h3>
                <button type="button" className="link-btn" onClick={() => nav("/customers?sort=total")}>Ver todos →</button>
              </div>
              <TopCustomers customers={d.top_customers.slice(0, 5)} revenue={d.kpis.revenue} overview={byId} hide={hide} />
            </div>
            <div className="panel">
              <div className="panel-header">
                <h3>Retornos pendentes</h3>
                <button type="button" className="link-btn" onClick={() => nav("/follow-ups")}>Ver retornos →</button>
              </div>
              <ContactsCard leads={d.lead_follow_ups} firstContact={d.first_contact} nav={nav} />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
