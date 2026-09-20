import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import {
  ColorsIcon, CustomersIcon, DashboardIcon, MenuIcon, OrdersIcon, ProductionIcon,
  ProductsIcon, RevenueIcon, UsersAdminIcon,
} from "./icons";
import logoIcon from "../assets/logo-icon.png";

const DASHBOARD_LINK = { to: "/", label: "Painel", end: true, Icon: DashboardIcon };
const ADMIN_LINKS = [
  { to: "/orders", label: "Pedidos", Icon: OrdersIcon },
  { to: "/production", label: "Produção", Icon: ProductionIcon },
  { to: "/revenue", label: "Faturamento", Icon: RevenueIcon },
  { to: "/customers", label: "Clientes", Icon: CustomersIcon },
  { to: "/products", label: "Produtos", Icon: ProductsIcon },
  { to: "/colors", label: "Cores", Icon: ColorsIcon },
  { to: "/users", label: "Usuários", Icon: UsersAdminIcon },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  // Sellers only see the dashboard (scoped to their own orders) and "Novo pedido"; admins see everything.
  const links = user?.role === "admin" ? [DASHBOARD_LINK, ...ADMIN_LINKS] : [DASHBOARD_LINK];
  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="shell">
      {menuOpen && <div className="sidebar-backdrop" onClick={closeMenu} />}
      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="brand">
          <img src={logoIcon} alt="" className="brand-icon" />
          <span className="brand-text">
            <span className="brand-name">Di Marcy</span>
            <span className="brand-sub">Pedidos</span>
          </span>
        </div>
        <button className="btn btn-new" onClick={() => { closeMenu(); nav("/orders/new"); }}>+ Novo pedido</button>
        <nav>
          {links.map(({ to, label, end, Icon }) => (
            <NavLink key={to} to={to} end={end} className="nav-link" onClick={closeMenu}>
              <Icon />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-name">{user?.name}</div>
          <button className="logout-link" onClick={logout}>Sair</button>
        </div>
      </aside>
      <main className="content">
        <div className="mobile-topbar">
          <button className="mobile-menu-btn" onClick={() => setMenuOpen(true)} aria-label="Abrir menu">
            <MenuIcon />
          </button>
          <img src={logoIcon} alt="" className="mobile-topbar-icon" />
          <span className="mobile-topbar-name">Di Marcy</span>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
