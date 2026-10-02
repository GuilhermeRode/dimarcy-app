import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import logoFull from "../assets/logo-full.png";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: password });
      setDone(true);
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

        <div className="login-card">
          <h1 className="login-title">Redefinir senha</h1>
          {!token ? (
            <>
              <p className="login-sub">Link inválido. Peça um novo link na tela de login.</p>
              <Link className="btn btn-block" to="/login">Voltar para o login</Link>
            </>
          ) : done ? (
            <>
              <p className="login-sub">Senha redefinida com sucesso.</p>
              <Link className="btn btn-primary btn-block" to="/login">Entrar</Link>
            </>
          ) : (
            <form onSubmit={submit}>
              <p className="login-sub">Escolha sua nova senha.</p>
              <label className="field">
                <span>Nova senha</span>
                <input type="password" minLength={10} autoComplete="new-password" value={password}
                  onChange={(e) => setPassword(e.target.value)} autoFocus required />
              </label>
              {error && <div className="error-message">{error}</div>}
              <button className="btn btn-primary btn-block" disabled={loading}>
                {loading ? "Salvando..." : "Redefinir senha"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
