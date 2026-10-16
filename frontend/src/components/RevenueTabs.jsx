import { NavLink } from "react-router-dom";

const TABS = [["/revenue", "Vendas"], ["/revenue/receivables", "Contas a receber"], ["/revenue/payables", "Contas a pagar"]];

export default function RevenueTabs() {
  return (
    <nav className="tabs-underline" aria-label="Seções do faturamento">
      {TABS.map(([to, label]) => <NavLink key={to} to={to} end>{label}</NavLink>)}
    </nav>
  );
}

// Shared header of the three Faturamento tabs: breadcrumb, tab title, then tabs (left) and the tab's actions (right)
export function RevenueHeader({ title, children }) {
  return (
    <header className="revenue-header">
      <span className="breadcrumb">Faturamento</span>
      <h1>{title}</h1>
      <div className="revenue-toolbar">
        <RevenueTabs />
        <div className="header-actions">{children}</div>
      </div>
    </header>
  );
}
