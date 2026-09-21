import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import {
  ColorsIcon, CustomersIcon, DashboardIcon, MenuIcon, OrdersIcon, ProductionIcon,
  ProductsIcon, RevenueIcon, UsersAdminIcon,
} from "./icons";
import { Avatar } from "./ui";
import logoIcon from "../assets/logo-icon.png";

const DASHBOARD_LINK = { to: "/", label: "Painel", end: true, Icon: DashboardIcon };
const ORDERS_LINK = { to: "/orders", label: "Pedidos", Icon: OrdersIcon };
const CUSTOMERS_LINK = { to: "/customers", label: "Clientes", Icon: CustomersIcon };
const ADMIN_LINKS = [
  ORDERS_LINK,
  { to: "/production", label: "Produção", Icon: ProductionIcon },
  { to: "/revenue", label: "Faturamento", Icon: RevenueIcon },
  CUSTOMERS_LINK,
  { to: "/products", label: "Produtos", Icon: ProductsIcon },
  { to: "/colors", label: "Cores", Icon: ColorsIcon },
  { to: "/users", label: "Usuários", Icon: UsersAdminIcon },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  // Sellers see the dashboard (scoped to their own orders), "Novo pedido", and their own orders/customers; admins see everything.
  const links = user?.role === "admin" ? [DASHBOARD_LINK, ...ADMIN_LINKS] : [DASHBOARD_LINK, ORDERS_LINK, CUSTOMERS_LINK];
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
          <img src={logoIcon} alt="" className="mobile-topbar-icon" />
          <span className="mobile-topbar-name">Di Marcy</span>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
