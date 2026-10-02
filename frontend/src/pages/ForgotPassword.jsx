import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import logoFull from "../assets/logo-full.png";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
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
          <h1 className="login-title">Esqueci minha senha</h1>
          {sent ? (
            <>
              <p className="login-sub">Se esse e-mail existir, enviamos um link para redefinir a senha.
                Confira sua caixa de entrada.</p>
              <Link className="btn btn-block" to="/login">Voltar para o login</Link>
            </>
          ) : (
            <form onSubmit={submit}>
              <p className="login-sub">Informe seu e-mail de acesso e enviaremos um link para redefinir a senha.</p>
              <label className="field">
                <span>E-mail</span>
                <input type="email" name="email" autoComplete="username" placeholder="seu@email.com" value={email}
                  onChange={(e) => setEmail(e.target.value)} autoFocus required />
              </label>
              {error && <div className="error-message">{error}</div>}
              <button className="btn btn-primary btn-block" disabled={loading}>
                {loading ? "Enviando..." : "Enviar link"}
              </button>
              <Link className="btn btn-block" to="/login">Voltar para o login</Link>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
