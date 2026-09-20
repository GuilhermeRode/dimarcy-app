import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { errorMessage } from "../api";
import { EyeIcon, EyeOffIcon } from "../components/icons";
import logoFull from "../assets/logo-full.png";

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      nav("/");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login">
      <div className="login-box">
        <div className="login-hero">
          <img src={logoFull} alt="Di Marcy" className="login-hero-logo" />
        </div>

        <form className="login-card" onSubmit={submit}>
          <h1 className="login-title">Entrar</h1>
          <p className="login-sub">Use seu e-mail e senha para acessar o painel.</p>
          <label className="field">
            <span>E-mail</span>
            <input type="email" placeholder="seu@email.com" value={email}
              onChange={(e) => setEmail(e.target.value)} autoFocus required />
          </label>
          <label className="field">
            <span>Senha</span>
            <div className="password-field">
              <input type={showPassword ? "text" : "password"} placeholder="••••••••"
                value={password} onChange={(e) => setPassword(e.target.value)} required />
              <button type="button" className="password-toggle" onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}>
                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </div>
          </label>
          {error && <div className="error-message">{error}</div>}
          <button className="btn btn-primary btn-block" disabled={loading}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
