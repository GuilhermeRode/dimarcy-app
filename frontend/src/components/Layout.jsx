import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import {
  ColorsIcon, CustomersIcon, DashboardIcon, FollowUpsIcon, LeadsIcon, MenuIcon, OrdersIcon, ProductionIcon,
  ProductsIcon, RevenueIcon, SettingsIcon, UsersAdminIcon,
} from "./icons";
import { Avatar } from "./ui";
import UpdateBanner from "./UpdateBanner";
import DailyAlert, { useDailyAlert } from "./DailyAlert";
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
  { to: "/settings", label: "Configurações", Icon: SettingsIcon },
];

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
  const badges = counts ? {
    "/follow-ups": counts.follow_ups_due > 0 && { n: counts.follow_ups_due, tone: counts.follow_ups_late ? "late" : "today",
      title: counts.follow_ups_late ? `${counts.follow_ups_late} atrasado(s)` : "Retornos para hoje" },
    "/leads": counts.new_leads > 0 && { n: counts.new_leads, tone: "new", title: "Novas oportunidades, ainda sem contato" },
  } : {};
  useEffect(() => {  // on every screen change, and every 5 min so an idle app still sees leads handed out meanwhile
    const load = () => api.get("/dashboard/badges").then((r) => setCounts(r.data)).catch(() => {});
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [pathname]);
  const daily = useDailyAlert(user?.id, counts);
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
        {daily.visible && (
          <DailyAlert name={user?.name} counts={counts} onClose={daily.close} onGo={(to) => { daily.close(); nav(to); }} />
        )}
      </main>
    </div>
  );
}
