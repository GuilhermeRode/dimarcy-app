# Hospedagem Pública do Backend (Electron + Mobile) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tirar o backend do PC local e colocá-lo numa VM gratuita "sempre ligada" na internet, com HTTPS, para que o app Electron e o app mobile funcionem para vendedores de qualquer lugar, sem custo mensal.

**Architecture:** VM na Oracle Cloud Always Free rodando o FastAPI existente como serviço systemd, atrás de um reverse proxy Caddy que fornece HTTPS automático via Let's Encrypt. SQLite permanece como banco (disco persistente da VM). Electron e Capacitor passam a apontar para essa URL pública em vez do IP da rede local.

**Tech Stack:** Oracle Linux 9 (aarch64), systemd, Caddy 2, Python 3.11 (venv), FastAPI/uvicorn (já existentes), Capacitor/Android, Electron/electron-builder.

**Spec:** `docs/superpowers/specs/2026-09-20-hospedagem-publica-design.md`

## Notas de execução (divergências do plano original)

Duas coisas saíram diferentes do previsto durante a execução — documentado aqui para referência futura:

1. **Sistema operacional real: Oracle Linux 9, não Ubuntu 22.04.** A instância criada no console veio como Oracle Linux (usuário padrão `opc`, não `ubuntu`; gerenciador de pacotes `dnf`, não `apt`; firewall `firewalld`, não `ufw`). Todos os comandos abaixo já refletem isso. Python 3.9 vem por padrão no OL9, mas `python-multipart==0.0.31` exige 3.10+ — foi instalado Python 3.11 via `dnf` à parte.
2. **Domínio público real: `https://144-22-219-124.sslip.io`, não `pedidos.dimarcy.com.br`.** O domínio `dimarcy.com.br` tem DNS gerenciado pelo Cloudflare (não pelo painel Turbo Cloud/cPanel), e o usuário não tem acesso a essa conta Cloudflare — quem criou o site não repassou esse acesso. A Task 2 original foi substituída por essa alternativa gratuita e instantânea (não depende de propagação nem de acesso de terceiros). Quando o acesso ao Cloudflare for resolvido (via a própria empresa que criou o site), trocar é só reconfigurar o Caddyfile e o `VITE_API_URL` para o subdomínio real — nada mais muda.

## Global Constraints

- Custo mensal de hospedagem: **R$ 0** (tier "always free", não trial).
- Servidor deve ficar disponível 24h, sem "sleep"/cold-start.
- Banco de dados continua **SQLite** — não migrar para Postgres.
- HTTPS obrigatório em toda comunicação com a API.
- O domínio `dimarcy.com.br` (site institucional) não pode ser alterado.
- Segredos (`SECRET_KEY`, credenciais SMTP, senha do admin) nunca entram no Git — só no `.env` do servidor.
- Acesso SSH à VM só por chave, nunca por senha.

## Review Focus

- **DNS ainda não propagado** — não se aplica mais (sslip.io resolve na hora), mas volta a valer se/quando migrar para o subdomínio real.
- **Firewall em duas camadas na Oracle Cloud** (Security List da rede virtual + firewall do próprio SO) — liberar só uma camada é o erro mais comum. Confirmado nas duas camadas (Task 1 e Task 6).
- **systemd não habilitado para iniciar no boot** → confirmado com `systemctl is-enabled` (Task 4) = `enabled`.
- **Múltiplos processos uvicorn escrevendo no mesmo arquivo SQLite** causaria erro "database is locked". Serviço configurado sem `--workers` (1 único processo).
- **E-mail do Gmail sendo sinalizado como spam** a partir de um IP de datacenter — ainda pendente de checar na Task 9 (validação final).

---

## Task 1: Criar a VM Oracle Cloud Always Free — ✅ concluído

**Resultado real:** instância Oracle Linux 9 (aarch64, Ampere), IP público `144.22.219.124`, usuário SSH `opc`, chave privada em `C:\Users\guilh\OneDrive\Desktop\keys\ssh-key-2026-09-21.key`. VCN e sub-rede pública criadas via "Start VCN Wizard → Create VCN with Internet Connectivity" (o caminho de criar a rede inline durante a criação da instância não liberava IP público). Portas 80/443 liberadas na Security List.

**Verificação:** `ssh -i ".../ssh-key-2026-09-21.key" opc@144.22.219.124` conecta sem senha. ✅

---

## Task 2: Apontar DNS — ⚠️ adiado (bloqueado por acesso a terceiro)

DNS de `dimarcy.com.br` é gerenciado via Cloudflare, sem acesso do usuário. Substituído por `144-22-219-124.sslip.io` (ver "Notas de execução" acima). Task original fica registrada aqui para quando o acesso ao Cloudflare for resolvido:

- [ ] Conseguir acesso à conta Cloudflare de `dimarcy.com.br` (pedir para quem criou o site) ou pedir para eles adicionarem: registro **A**, nome `pedidos`, valor `144.22.219.124`.
- [ ] Quando propagado (`nslookup pedidos.dimarcy.com.br` retornar o IP), atualizar o Caddyfile (Task 5) e `VITE_API_URL` (Task 7) para usar o subdomínio em vez do sslip.io.

---

## Task 3: Preparar o servidor e subir o código do backend — ✅ concluído

**Files:** código copiado para `/opt/dimarcy/backend` na VM (não versionado no repo).

- [x] **Passo 1:** `sudo dnf install -y python3 python3-pip git rsync` — depois `sudo dnf install -y python3.11 python3.11-pip` (necessário pelo `python-multipart==0.0.31`, ver Notas de execução).
- [x] **Passo 2:** Como `rsync` não estava disponível no Git Bash local, o código foi copiado via `tar` sobre SSH:
  ```bash
  cd backend
  tar czf - --exclude='.venv' --exclude='__pycache__' --exclude='*.db-journal' --exclude='.env' . | \
    ssh -i "chave.key" opc@144.22.219.124 "mkdir -p /opt/dimarcy/backend && tar xzf - -C /opt/dimarcy/backend"
  ```
- [x] **Passo 3:** `python3.11 -m venv .venv && ./.venv/bin/pip install -r requirements.txt` — instalado com sucesso, incluindo `python-multipart==0.0.31` e `PyJWT==2.13.0` (mesmas versões do fix de segurança).
- [x] **Passo 4:** `dimarcy.db` real copiado via `scp`.

**Verificação:** `uvicorn` manual respondeu `{"ok":true}`. ✅

---

## Task 4: `.env` de produção e serviço systemd — ✅ concluído

- [x] **Passo 1:** `.env` local copiado via `scp` (preserva as credenciais SMTP/admin sem digitá-las em nenhum comando), depois `SECRET_KEY` trocado por um valor novo gerado direto no servidor (diferente do `.env` local), `chmod 600`.
- [x] **Passo 2-3:** Serviço systemd criado com `User=opc` (não `ubuntu`), sem flag `--workers` (evita "database is locked" no SQLite), `enable` + `start`.

**Verificação:**
- `systemctl status dimarcy-backend` → `active (running)` ✅
- `systemctl is-enabled dimarcy-backend` → `enabled` ✅
- `curl http://127.0.0.1:8000/api/health` → `{"ok":true}` ✅

---

## Task 5: Caddy + HTTPS automático — ✅ concluído

- [x] **Passo 1:** Instalado via COPR (repositório Fedora/RHEL, não o repo apt do Ubuntu):
  ```bash
  sudo dnf install -y 'dnf-command(copr)'
  sudo dnf copr enable -y @caddy/caddy
  sudo dnf install -y caddy
  ```
- [x] **Passo 2:** Caddyfile configurado para `144-22-219-124.sslip.io` (em vez do subdomínio — ver Notas de execução):
  ```
  144-22-219-124.sslip.io {
      reverse_proxy 127.0.0.1:8000
  }
  ```
  `sudo systemctl enable caddy && sudo systemctl restart caddy`

**Verificação:** `curl -v https://144-22-219-124.sslip.io/api/health` do PC local → `HTTP/1.1 200 OK`, `{"ok":true}`, certificado TLS válido (Let's Encrypt emitido automaticamente). ✅

---

## Task 6: Firewall e hardening do SSH — ✅ concluído

- [x] **Passo 1 (firewalld, não ufw):**
  ```bash
  sudo firewall-cmd --permanent --add-service=http
  sudo firewall-cmd --permanent --add-service=https
  sudo firewall-cmd --reload
  ```
- [x] **Passo 2:** `PasswordAuthentication no` em `/etc/ssh/sshd_config`, `systemctl restart sshd`.

**Verificação:**
- `firewall-cmd --list-all` → serviços `dhcpv6-client http https ssh` ✅
- Acesso SSH por chave confirmado funcionando **depois** do hardening (sem lockout) ✅

---

## Task 7: Electron → API pública — ✅ concluído

- [x] **Passo 1:** `frontend/.env` → `VITE_API_URL=https://144-22-219-124.sslip.io/api`
- [x] **Passo 2:** `npm run app:dist` → gerado `frontend/dist/Di Marcy Pedidos Setup 1.0.0.exe` (174 MB), confirmado que a nova URL está embutida no bundle JS.
- [x] **Passo 3:** `frontend/.env.example` atualizado como referência.

- [ ] **Verificação pendente (só o usuário pode fazer):** instalar o novo instalador numa máquina fora da rede Wi-Fi de casa e confirmar login.

---

## Task 8: Capacitor — modo produção — ✅ concluído

- [x] **Passo 1:** `frontend/capacitor.config.dev.ts` criado, preservando o `server.url` do live-reload local.
- [x] **Passo 2:** `frontend/capacitor.config.ts` reescrito sem bloco `server` (modo produção).
- [x] **Passo 3:** Scripts `cap:sync:dev` e `cap:sync:prod` adicionados ao `package.json`.
- [x] **Passo 4:** `npm run build && npx cap sync android` — confirmado que `android/app/src/main/assets/capacitor.config.json` não tem mais bloco `server`, e o bundle sincronizado tem a URL pública embutida.

- [ ] **Passo 5 (pendente — só o usuário, precisa do Android Studio):** gerar o APK (`npx cap open android` → Build → Build APK(s)).
- [ ] **Verificação pendente:** instalar o APK, desligar o Wi-Fi, confirmar login só no 4G/5G.

---

## Task 9: Validação fim a fim fora da rede local — pendente

- [ ] **Passo 1:** Login fora da rede local (mobile e Electron).
- [ ] **Passo 2:** Criar um pedido de teste.
- [ ] **Passo 3:** Marcar como entregue, checar e-mail (inbox **e spam**) em `di_marcy@hotmail.com`.
- [ ] **Passo 4:** Apagar os dados de teste.
- [ ] **Passo 5:** `sudo reboot` na VM, esperar ~1 min, `curl https://144-22-219-124.sslip.io/api/health` deve voltar sozinho (confirma `systemctl enable`), dados reais intactos.

---

## Task 10 (adicional, fora do escopo original): acesso via navegador (iPhone) — ✅ concluído

Extensão pedida depois da Task 9 ser planejada: como não existe app nativo iOS possível sem Mac/Xcode, o frontend passou a ser servido também como site simples, para acesso via Safari/Chrome de qualquer navegador.

- [x] Build do frontend (`frontend/dist/`, o mesmo já usado no Electron/Capacitor) copiado para `/opt/dimarcy/frontend-dist` na VM.
- [x] Caddyfile atualizado para diferenciar por caminho na mesma URL:
  ```
  144-22-219-124.sslip.io {
      handle /api/* {
          reverse_proxy 127.0.0.1:8000
      }
      handle /uploads/* {
          reverse_proxy 127.0.0.1:8000
      }
      handle {
          root * /opt/dimarcy/frontend-dist
          try_files {path} /index.html
          file_server
      }
  }
  ```
  (`/uploads/*` também precisa ir para o backend — é onde ficam as fotos de produtos/avatares, servidas pelo FastAPI fora do prefixo `/api`.)

**Verificação:** `curl https://144-22-219-124.sslip.io/api/health` → `{"ok":true}`; `curl https://144-22-219-124.sslip.io/` → HTML do app; asset JS → HTTP 200. ✅ (Teste visual real no Safari do iPhone: pendente, só o usuário pode confirmar.)

**Nota:** essa cópia do frontend na VM é estática — se o código do frontend mudar no futuro, é preciso repetir esse `tar`/copy manualmente (não há deploy automático configurado, por decisão de escopo do plano original).
