import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api",
});

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && !err.config.url.includes("/auth/login")) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.hash = "#/login";
      window.location.reload();
    }
    return Promise.reject(err);
  }
);

// Last response of each list screen, so going back to a screen shows it at once while it refreshes.
// Cleared on logout: another user may sign in on the same device.
export const screenCache = new Map();

// Uploaded files (e.g. product images) are served from the API's root, outside the "/api" prefix.
export const fileUrl = (path) =>
  path ? `${api.defaults.baseURL.replace(/\/api\/?$/, "")}${path}` : null;

export const errorMessage = (e) => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    // our own pt-BR validators surface as "Value error, <message>"
    const msg = d[0]?.msg;
    return typeof msg === "string" && msg.startsWith("Value error, ") ? msg.slice(13) : "Confira os campos preenchidos.";
  }
  return e?.response ? "Não foi possível concluir a operação." : "Sem conexão com o servidor.";
};
