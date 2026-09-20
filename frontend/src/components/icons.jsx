// Minimal line-style icon set (stroke-based, inherits color via currentColor).
const base = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };

export const DashboardIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <line x1="6" y1="20" x2="6" y2="14" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="18" y1="20" x2="18" y2="10" />
  </svg>
);

export const OrdersIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <polyline points="14 3 14 8 19 8" />
    <line x1="8.5" y1="13" x2="15.5" y2="13" />
    <line x1="8.5" y1="17" x2="13" y2="17" />
  </svg>
);

export const CustomersIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <circle cx="12" cy="7.5" r="3.5" />
    <path d="M5 20.5a7 7 0 0 1 14 0" />
  </svg>
);

export const ProductsIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5z" />
    <polyline points="3.5 7.5 12 12 20.5 7.5" />
    <line x1="12" y1="12" x2="12" y2="21" />
  </svg>
);

export const ColorsIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <path d="M12 3a9 9 0 1 0 0 18c1.4 0 2.2-1 1.3-2.1-.4-.5-.3-1.2.3-1.5.6-.3 1.4-.1 1.9.3.9.8 2.3.3 2.4-1C18.2 8.5 15.7 3 12 3z" />
    <circle cx="7.7" cy="10.3" r="1" fill="currentColor" stroke="none" />
    <circle cx="12" cy="7.3" r="1" fill="currentColor" stroke="none" />
    <circle cx="16.3" cy="10.3" r="1" fill="currentColor" stroke="none" />
  </svg>
);

export const UsersAdminIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z" />
    <path d="M9.5 12l1.8 1.8L14.5 10" />
  </svg>
);

export const EyeIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <path d="M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

export const MenuIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 22} height={p.size || 22} {...base} {...p}>
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);

export const PlusIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

export const EditIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <path d="M4 20h4L19.5 8.5a2 2 0 0 0 0-2.8l-1.2-1.2a2 2 0 0 0-2.8 0L4 16z" />
    <line x1="13.5" y1="6.5" x2="17.5" y2="10.5" />
  </svg>
);

export const RevenueIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <polyline points="3 17 9 11 13 15 21 6" />
    <polyline points="14 6 21 6 21 13" />
  </svg>
);

export const ProductionIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <path d="M12 3 3 8l9 5 9-5z" />
    <path d="M3 12l9 5 9-5" />
    <path d="M3 16l9 5 9-5" />
  </svg>
);

export const EyeOffIcon = (p) => (
  <svg viewBox="0 0 24 24" width={p.size || 18} height={p.size || 18} {...base} {...p}>
    <path d="M17.6 17.6A10 10 0 0 1 12 19.5c-7 0-10.5-7.5-10.5-7.5a18 18 0 0 1 4.8-5.6" />
    <path d="M9.6 4.9A9 9 0 0 1 12 4.5c7 0 10.5 7.5 10.5 7.5a18 18 0 0 1-2 2.9" />
    <path d="M9.4 14.6a3 3 0 0 0 4.2-4.2" />
    <line x1="2" y1="2" x2="22" y2="22" />
  </svg>
);
