import { NavLink } from "react-router-dom";

const TABS = [["/revenue", "Vendas"], ["/revenue/receivables", "Contas a receber"], ["/revenue/payables", "Contas a pagar"]];

export default function RevenueTabs() {
  return (
    <nav className="segmented revenue-tabs" aria-label="Seções do faturamento">
      {TABS.map(([to, label]) => <NavLink key={to} to={to} end>{label}</NavLink>)}
    </nav>
  );
}
