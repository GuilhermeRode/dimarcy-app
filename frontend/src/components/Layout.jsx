import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import {
  ColorsIcon, CustomersIcon, DashboardIcon, FollowUpsIcon, LeadsIcon, MenuIcon, OrdersIcon, ProductionIcon,
  ProductsIcon, RegionsIcon, RevenueIcon, SettingsIcon, UsersAdminIcon,
} from "./icons";
import { Avatar } from "./ui";
import UpdateBanner from "./UpdateBanner";
import logoFull from "../assets/logo-full.png";

const DASHBOARD_LINK = { to: "/", label: "Painel", end: true, Icon: DashboardIcon };
const ORDERS_LINK = { to: "/orders", label: "Pedidos", Icon: OrdersIcon };
const CUSTOMERS_LINK = { to: "/customers", label: "Clientes", Icon: CustomersIcon };
const FOLLOW_UPS_LINK = { to: "/follow-ups", label: "Retornos", Icon: FollowUpsIcon };
const LEADS_LINK = { to: "/leads", label: "Prospecção", Icon: LeadsIcon };
const SELLER_LEADS_LINK = { ...LEADS_LINK, label: "Oportunidades" };  // sellers: the stores to visit, not the admin's whole queue
const PRODUCTS_LINK = { to: "/products", label: "Produtos", Icon: ProductsIcon };
const ADMIN_LINKS = [
  ORDERS_LINK,
  { to: "/production", label: "Produção", Icon: ProductionIcon },
  { to: "/revenue", label: "Faturamento", Icon: RevenueIcon },
  CUSTOMERS_LINK,
  LEADS_LINK,
  FOLLOW_UPS_LINK,
  PRODUCTS_LINK,
  { to: "/colors", label: "Cores", Icon: ColorsIcon },
  { to: "/users", label: "Usuários", Icon: UsersAdminIcon },
  { to: "/regions", label: "Regiões", Icon: RegionsIcon },
  { to: "/settings", label: "Configurações", Icon: SettingsIcon },
];

const BellIcon = () => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
  </svg>
);

function DailyAlert({ name, counts, onClose, onLater, onGo }) {
  const now = new Date();
  const hour = now.getHours();
  const hello = hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
  const day = now.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  const late = counts.follow_ups_late, todayDue = counts.follow_ups_due - late;
  const rows = [
    late > 0 && { tone: "late", n: late, label: late === 1 ? "retorno atrasado" : "retornos atrasados",
      hint: "Já passou do dia combinado", to: "/follow-ups" },
    todayDue > 0 && { tone: "today", n: todayDue, label: todayDue === 1 ? "retorno para hoje" : "retornos para hoje",
      hint: "Contatos combinados para hoje", to: "/follow-ups" },
    counts.new_leads > 0 && { tone: "new", n: counts.new_leads, label: counts.new_leads === 1 ? "nova oportunidade" : "novas oportunidades",
      hint: "Chegaram para você, ainda sem contato", to: "/leads" },
  ].filter(Boolean);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onLater()}>
      <div className="modal daily-alert" role="dialog" aria-labelledby="daily-alert-title">
        <button className="btn-x daily-alert-x" onClick={onClose} aria-label="Fechar">×</button>
        <div className="daily-alert-head">
          <span className="daily-alert-bell"><BellIcon /></span>
          <h2 id="daily-alert-title">{hello}, {(name || "").split(" ")[0]}!</h2>
          <p>{day.charAt(0).toUpperCase() + day.slice(1)}<br />Veja o que está esperando por você</p>
        </div>
        <div className="daily-alert-list">
          {rows.map((r) => (
            <button key={r.tone} type="button" className={`daily-alert-row daily-${r.tone}`} onClick={() => onGo(r.to)}>
              <span className="daily-alert-count">{r.n}</span>
              <span className="daily-alert-text"><strong>{r.label}</strong><small>{r.hint}</small></span>
              <span className="daily-alert-go" aria-hidden="true">›</span>
            </button>
          ))}
        </div>
        <button type="button" className="btn daily-alert-later" onClick={onLater}>Mais tarde</button>
      </div>
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  // Prospecção can be admin-only for now (Configurações); the API refuses it to sellers too.
  const [leadsForSellers, setLeadsForSellers] = useState(false);
  useEffect(() => {
    if (user?.role !== "admin") api.get("/settings").then((r) => setLeadsForSellers(!!r.data.leads_for_sellers)).catch(() => {});
  }, [user?.role]);
  // menu badges (Retornos: due today or late, red when any is late; Prospecção: new stores), refreshed on every screen change
  const { pathname } = useLocation();
  const [counts, setCounts] = useState(null);
  const badge = counts ? counts.new_leads + counts.follow_ups_due : 0;  // anything pending: the day's pop-up
  const badges = counts ? {
    "/follow-ups": counts.follow_ups_due > 0 && { n: counts.follow_ups_due, tone: counts.follow_ups_late ? "late" : "today",
      title: counts.follow_ups_late ? `${counts.follow_ups_late} atrasado(s)` : "Retornos para hoje" },
    "/leads": counts.new_leads > 0 && { n: counts.new_leads, tone: "new", title: "Novas oportunidades, ainda sem contato" },
  } : {};
  useEffect(() => {
    api.get("/dashboard/badges").then((r) => setCounts(r.data)).catch(() => {});
  }, [pathname]);
  // the day's pop-up when something is pending: × or a row hides it until tomorrow, "Mais tarde" for 2 hours
  const hideKey = `daily-alert-until-${user?.id}`;
  const [dailyClosed, setDailyClosed] = useState(() => { try { return Date.now() < Number(localStorage.getItem(hideKey)); } catch { return false; } });
  const hideDaily = (until) => { try { localStorage.setItem(hideKey, String(until)); } catch { /* private mode: shows again next time */ } setDailyClosed(true); };
  const closeDaily = () => { const t = new Date(); t.setHours(24, 0, 0, 0); hideDaily(t.getTime()); };
  const laterDaily = () => hideDaily(Date.now() + 2 * 60 * 60 * 1000);
  useEffect(() => {  // after "Mais tarde", come back once the 2 hours are over (app left open)
    if (!dailyClosed) return;
    const id = setInterval(() => { try { if (Date.now() >= Number(localStorage.getItem(hideKey))) setDailyClosed(false); } catch { /* keep hidden */ } }, 60000);
    return () => clearInterval(id);
  }, [dailyClosed, hideKey]);
  // Sellers see the dashboard (scoped to their own orders), "Novo pedido", their own orders/customers, prospecting and their products (read-only); admins see everything.
  const links = user?.role === "admin" ? [DASHBOARD_LINK, ...ADMIN_LINKS]
    : [DASHBOARD_LINK, ORDERS_LINK, CUSTOMERS_LINK, ...(leadsForSellers ? [SELLER_LEADS_LINK] : []), FOLLOW_UPS_LINK, PRODUCTS_LINK];
  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="shell">
      {menuOpen && <div className="sidebar-backdrop" onClick={closeMenu} />}
      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="brand">
          <img src={logoFull} alt="Di Marcy" className="brand-logo" />
        </div>
        <button className="btn btn-new" onClick={() => { closeMenu(); nav("/orders/new"); }}>+ Novo pedido</button>
        <nav>
          {links.map(({ to, label, end, Icon }) => (
            <NavLink key={to} to={to} end={end} className="nav-link" onClick={closeMenu}>
              <Icon />
              {label}
              {badges[to] && <span className={`nav-badge nav-badge-${badges[to].tone}`} title={badges[to].title}>{badges[to].n}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="sidebar-user" onClick={() => { closeMenu(); nav("/profile"); }}>
            <Avatar url={user?.avatar_url} name={user?.name} size="sm" />
            <span>
              <span className="user-name">{user?.name}</span>
              <span className="user-role">Meu perfil</span>
            </span>
          </button>
          <button className="logout-link" onClick={logout}>Sair</button>
        </div>
      </aside>
      <main className="content">
        <div className="mobile-topbar">
          <button className="mobile-menu-btn" onClick={() => setMenuOpen(true)} aria-label="Abrir menu">
            <MenuIcon />
          </button>
          <img src={logoFull} alt="Di Marcy" className="mobile-topbar-logo" />
        </div>
        <Outlet />
        <UpdateBanner />
        {!dailyClosed && badge > 0 && (
          <DailyAlert name={user?.name} counts={counts} onClose={closeDaily} onLater={laterDaily}
            onGo={(to) => { closeDaily(); nav(to); }} />
        )}
      </main>
    </div>
  );
}
