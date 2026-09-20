import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const Ctx = createContext(null);

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme === "dark" ? "dark" : "light";
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const u = localStorage.getItem("user");
    return u ? JSON.parse(u) : null;
  });

  useEffect(() => { applyTheme(user?.theme); }, [user?.theme]);

  async function login(email, password) {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("user", JSON.stringify(data.user));
    setUser(data.user);
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  }

  function updateUser(next) {
    localStorage.setItem("user", JSON.stringify(next));
    setUser(next);
  }

  return <Ctx.Provider value={{ user, login, logout, updateUser }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
