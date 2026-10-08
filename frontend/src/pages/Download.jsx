import { useEffect, useState } from "react";
import logoIcon from "../assets/logo-icon.png";
import logoWordmark from "../assets/logo-wordmark.png";

// Built and published by .github/workflows/desktop.yml; "latest" always serves the newest installer.
const REPO = "GuilhermeRode/dimarcy-app";
const INSTALLER = "Di-Marcy-Pedidos-Setup.exe";
const INSTALLER_URL = `https://github.com/${REPO}/releases/latest/download/${INSTALLER}`;

const WindowsLogo = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="currentColor">
    <path d="M3 5.5 10.5 4.4v7.1H3zM11.5 4.3 21 3v8.5h-9.5zM3 12.5h7.5v7.1L3 18.5zM11.5 12.5H21V21l-9.5-1.3z" />
  </svg>
);

const FEATURES = [
  ["Sempre atualizado", "O app abre a versão mais nova do sistema. Melhorias chegam sozinhas, sem reinstalar."],
  ["Atalho na área de trabalho", "Um clique para abrir, numa janela própria, sem abas do navegador no caminho."],
  ["Mesmo acesso", "Entre com o mesmo e-mail e senha. Pedidos e clientes são os mesmos do navegador."],
];

// Release details (version, date, size) from the public GitHub API; the page works without them.
function useLatestRelease() {
  const [info, setInfo] = useState(null);
  useEffect(() => {
    fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
      .then((r) => (r.ok ? r.json() : null))
      .then((rel) => {
        const asset = rel?.assets?.find((a) => a.name === INSTALLER);
        if (!asset) return;
        setInfo({
          date: new Date(rel.published_at).toLocaleDateString("pt-BR"),
          size: `${Math.round(asset.size / 1e6)} MB`,
        });
      })
      .catch(() => {});
  }, []);
  return info;
}

// Unlisted page at /download (no menu links to it): the desktop installer for Windows.
export default function Download() {
  const release = useLatestRelease();
  return (
    <div className="dl">
      <header className="dl-hero">
        <div className="dl-hero-inner">
          <div className="dl-copy">
            <img src={logoWordmark} alt="Di Marcy" className="dl-wordmark" />
            <h1>Di Marcy Pedidos no seu computador</h1>
            <p>O sistema de pedidos da Di Marcy num app para Windows: abra direto da área de trabalho e trabalhe numa janela só dele.</p>
            <a className="dl-button" href={INSTALLER_URL}><WindowsLogo /> Baixar para Windows</a>
            <small className="dl-meta">
              Windows 10 ou 11{release ? ` · ${release.size} · atualizado em ${release.date}` : ""}
            </small>
          </div>

          <div className="dl-mock" aria-hidden="true">
            <div className="dl-mock-bar"><i /><i /><i /><span>Di Marcy Pedidos</span></div>
            <div className="dl-mock-body">
              <div className="dl-mock-side"><img src={logoIcon} alt="" /><b /><b /><b /><b /><b /></div>
              <div className="dl-mock-main">
                <div className="dl-mock-hero"><b /><em /><div className="dl-mock-spark">{[40, 65, 35, 80, 55, 90, 70].map((h, i) => <s key={i} style={{ height: `${h}%` }} />)}</div></div>
                <div className="dl-mock-cards"><span /><span /><span /></div>
                <div className="dl-mock-rows"><p /><p /><p /></div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="dl-content">
        <section className="dl-features">
          {FEATURES.map(([title, text]) => (
            <article key={title}><h2>{title}</h2><p>{text}</p></article>
          ))}
        </section>

        <section className="dl-steps">
          <h2>Como instalar</h2>
          <ol>
            <li><span><b>Baixe</b> o instalador pelo botão acima.</span></li>
            <li><span><b>Abra</b> o arquivo baixado e siga as telas de instalação.</span></li>
            <li><span><b>Entre</b> com o mesmo e-mail e senha que você já usa.</span></li>
          </ol>
          <div className="dl-note">
            <strong>Apareceu “O Windows protegeu o computador”?</strong>
            <span>É normal para apps novos. Clique em <b>Mais informações</b> e depois em <b>Executar assim mesmo</b>.</span>
          </div>
        </section>

        <footer className="dl-footer">
          <a href="/">Prefiro usar no navegador</a>
        </footer>
      </main>
    </div>
  );
}
