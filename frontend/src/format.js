export const money = (v) =>
  Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const dateBR = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString("pt-BR") : "");

export const orderNumber = (id) => String(id).padStart(5, "0");

export const STATUS = {
  quote: "Orçamento",
  confirmed: "Confirmado",
  in_production: "Em produção",
  shipped: "Enviado",
  delivered: "Entregue",
  canceled: "Cancelado",
};

export const DEFAULT_SIZES = ["U", "P", "M", "G", "GG"];
