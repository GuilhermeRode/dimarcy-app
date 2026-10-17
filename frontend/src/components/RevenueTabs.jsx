import { NavLink } from "react-router-dom";

const TABS = [["/revenue", "Vendas"], ["/revenue/receivables", "Contas a receber"], ["/revenue/payables", "Contas a pagar"]];

export default function RevenueTabs() {
  return (
    <nav className="tabs-underline" aria-label="Seções do faturamento">
      {TABS.map(([to, label]) => <NavLink key={to} to={to} end>{label}</NavLink>)}
    </nav>
  );
}

// Shared header of the three Faturamento tabs, same pattern as every page (title + subtitle | actions), tabs below
export function RevenueHeader({ subtitle, children }) {
  return (
    <>
      <header className="page-header">
        <div>
          <h1>Faturamento</h1>
          <p className="muted">{subtitle}</p>
        </div>
        <div className="header-actions">{children}</div>
      </header>
      <RevenueTabs />
    </>
  );
}
