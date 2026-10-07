# Redesenho das telas Painel, Faturamento e Clientes

**Data:** 2026-10-07
**Referência visual:** `docs/Refatoração de três telas admin/Di Marcy Admin.dc.html` (protótipo com dados fictícios)

## Objetivo

Trazer as três telas para o visual do protótipo, usando só dados reais do app, e tornar
cada tela mais útil para a decisão comercial:

- **Painel:** mostrar de relance o quanto se vendeu, contra o período anterior e contra a meta,
  e apontar o que precisa de ação (clientes em risco, pedidos atrasados, cadastros sem pedido).
- **Faturamento:** comparar vendedores entre si e contra as próprias metas.
- **Clientes:** encontrar oportunidades de venda na carteira (quem parou de comprar, quem nunca comprou)
  e agir direto dali (novo pedido, WhatsApp).

## Fora do escopo

- Menu lateral redesenhado (logo em texto, contadores) — o menu atual fica.
- Etapas de pedido que o app não tem ("Aguardando aprovação", "Pronto p/ envio") — usamos as 6 reais.
- Mapa de calor por dia, contas a receber e maiores pedidos — o protótipo calcula mas não desenha;
  o app não registra pagamentos recebidos.
- Tela do mapa de clientes por cidade (`/customers-by-city`) — continua como está.
- App Electron.

## Decisões

| Tema | Decisão |
|---|---|
| Onde calcular | No servidor. As telas só desenham. Permissão (vendedor vê só o que é seu) continua num lugar só. |
| Metas | Meta **mensal** da empresa (Configurações) e meta **mensal** por vendedor (Usuários). Vazio = sem meta. |
| Meta do período | Calculada na tela: Este mês = mensal; Este ano = mensal × 12; 7 dias = mensal × 7/30; Personalizado = mensal × dias/30. |
| Sem meta cadastrada | Anel de meta e aba "% da meta" não aparecem (nunca "0%"). |
| Período | Botões 7 dias / Este mês / Este ano em destaque + "Personalizado", que mostra os campos de data. |
| Gráficos | Recharts (já instalado) para a linha de 12 meses e a rosca; CSS puro para barras simples. Nenhuma biblioteca nova. |
| Status do cliente | Pela data da última venda: Nunca comprou (nenhuma venda) · Ativo (≤ 60 dias) · Em risco (61–150) · Inativo (> 150). Faixas fixas no código. |
| O que conta como venda | `SALE_STATUSES` (confirmado, em produção, enviado, entregue) — mesma regra do faturamento atual. |
| Pedido atrasado | `delivery_date` < hoje e status `confirmed` ou `in_production`. |
| Clientes por página | 20. |
| Saudação | 00:00–04:59 "Boa noite", 05–11:59 "Bom dia", 12–17:59 "Boa tarde", 18+ "Boa noite" (já corrigido). |

## Dados e API

### Banco

- `app_settings.monthly_goal` — `Numeric(12,2)`, padrão 0 (= sem meta).
- `users.monthly_goal` — `Numeric(12,2)`, nulo (= sem meta).
- Adicionadas no banco existente por `ALTER TABLE` na inicialização, no mesmo padrão de
  `_ensure_user_columns` em `backend/app/main.py`. Nenhum dado é apagado.
- Só admin altera metas: `PUT /api/settings` (já é admin-only) e `PUT /api/users/{id}` (já é admin-only).
  `monthly_goal` entra nos schemas `AppSettingsIn/Out` e `UserIn/UserOut`.

### `GET /api/dashboard` (existente) — campos novos

- `daily_sales`: `[{ "label": "07/10", "start": "2026-10-07", "value": 1234.5 }]`.
  Período de até 31 dias → um ponto por dia; maior → um ponto por semana (segunda a domingo).
- `goals`: `{ "company_monthly": 45000.0 | null, "sellers": { "<seller_id>": 12000.0 } }`.
  Vendedor (não admin) recebe só a própria meta e `company_monthly: null`.
- `by_seller`: cada item ganha `id` e `avatar_url`. Para admin, inclui vendedores ativos sem vendas
  no período (com zeros); vendedores inativos só aparecem se venderam no período.
- `alerts`: `{ "customers_at_risk": n, "customers_never_ordered": n, "late_orders": n, "oldest_late_days": n | null }`.
  Clientes contam a carteira inteira (não dependem do período). Vendedor vê só os seus clientes/pedidos.

A variação contra o período anterior continua como hoje: o Painel chama a rota uma segunda vez
com o período anterior de mesma duração (`previousPeriod` em `Dashboard.jsx`).

### `GET /api/customers/overview` (nova)

Lista completa (sem paginação no servidor — a carteira tem ~525 clientes). Cada item:

```json
{
  "id": 1, "name": "…", "city": "Rio do Sul", "state": "SC", "phone": "…", "document": "…",
  "owner_id": 3, "owner_name": "Marcia", "created_at": "2024-03-01T…",
  "total": 18240.0, "orders": 6, "last_order_date": "2026-09-12", "days_since_last": 25,
  "status": "active | at_risk | inactive | never",
  "colors": ["Preto", "Vinho"],
  "recent_orders": [{ "id": 4812, "date": "2026-09-12", "pieces": 40, "total": 1840.0 }]
}
```

- `total`, `orders`, `last_order_date`, `colors` (até 3, por peças) e `recent_orders` (até 3) consideram só `SALE_STATUSES`.
- Vendedor recebe só clientes com `owner_id` = ele; admin recebe todos.
- Rota declarada antes de `/{cid}` no router de clientes, para não colidir.

## Telas

Visual do protótipo (fonte, cores, cards escuros `#0c2140`, cantos arredondados), implementado
com classes em `frontend/src/styles.css`, reaproveitando as existentes (`.page`, `.kpi`, `.card`,
`.tag`, `.muted` …) e respeitando o tema escuro atual. Textos em pt-BR, código em inglês.

### Componentes compartilhados

- `PeriodPicker` — botões de período + "Personalizado" com os campos de data. Usado em Painel e Faturamento.
- `TeamRanking` — bloco escuro "Fulano lidera em …" com abas Faturamento / Pedidos / Peças / % da meta
  e um card por vendedor. Usado em Painel e Faturamento (no Faturamento mostra também meta do período e quanto falta).
- Esses componentes ficam em `frontend/src/components/`.

### Painel (`/`, todos os usuários)

1. Cabeçalho: data por extenso, saudação + primeiro nome, `PeriodPicker`.
2. Card escuro: faturamento do período, variação vs. anterior (verde/vermelho), mini-gráfico de `daily_sales`
   com valor ao passar o mouse; anel "% da meta" à direita se houver meta. Admin: clique leva a `/revenue`.
   Coluna branca: Pedidos fechados, Peças vendidas, Ticket médio, cada um com variação.
3. Alertas (só os com contagem > 0; faixa some se todos forem 0):
   - clientes em risco → `/customers?status=at_risk`
   - pedidos atrasados → `/production` (admin) ou `/orders` (vendedor)
   - cadastros sem pedido → `/customers?status=never`
4. Linha de 12 meses (Recharts, tooltip) + rosca "Situação dos pedidos" com as 6 situações reais;
   passar o mouse numa situação destaca a fatia e mostra número e % no centro.
5. `TeamRanking` — só admin.
6. Cores mais vendidas (faixa com as cores reais + legenda %), Peças por tamanho (barras, maior destacada),
   Produtos mais vendidos (barras finas).
7. Melhores clientes (top 5, "Ver todos" → `/customers?sort=total`) e Clientes por cidade
   (admin, com "Ver mapa"; oculto no build Android, como hoje).
8. Card sem dados: "Sem vendas no período."

### Faturamento (`/revenue`, só admin)

1. Cabeçalho "Faturamento" + `PeriodPicker`.
2. Card escuro: faturamento total + variação; Pedidos, Peças, Ticket médio; barra de participação por
   vendedor (uma cor cada) com legenda "Nome 36%".
3. `TeamRanking` com meta do período e quanto falta por vendedor.
4. Por cidade: 5 cidades com mais faturamento + "Outras", com valor e barra.

### Clientes (`/customers`, todos os usuários)

1. Cabeçalho "Clientes" + subtítulo + "+ Cadastrar cliente" (formulário atual).
2. Filtros: busca (nome, cidade, CPF/CNPJ; ignora acento e maiúscula), Status, Estado, Cidade (do estado
   escolhido), Vendedor (só admin), Cor comprada, Ordenar (Total comprado / Nº de pedidos /
   Compra mais recente / Nome A–Z). Etiquetas removíveis dos filtros ativos + "Limpar tudo".
   Filtros na URL (`?status=&state=&city=&seller=&color=&sort=&q=&page=`).
3. Tabela: Cliente (iniciais, nome, cidade/UF), Vendedor (só admin), Total, Pedidos, Status colorido.
   20 por página, "Mostrando 1–20 de N", paginação. Vazio: "Nenhum cliente com esses filtros."
4. Painel lateral do cliente clicado: iniciais, nome, cidade · telefone, status; botões
   **Novo pedido** (`/orders/new?customer=<id>`), **WhatsApp** (`https://wa.me/55<dígitos>`,
   desabilitado sem telefone) e **Editar** (formulário atual, com Excluir); totais (total comprado, pedidos,
   ticket médio, cliente desde); vendedor e cores mais compradas; 3 últimos pedidos clicáveis
   (→ `/orders/<id>`) ou "Ainda sem pedidos. Bom momento para um primeiro contato."
5. Celular: tabela vira lista de cartões; o painel abre em tela cheia com botão de fechar.

### Formulário de pedido

`OrderForm` lê `?customer=<id>` em `/orders/new` e já seleciona o cliente.

## Erros e casos de borda

- Falha ao carregar: mensagem "Não foi possível carregar os dados." no lugar do conteúdo.
- Período anterior com faturamento 0: variação não é exibida (evita "+∞%").
- Cliente sem telefone: botão WhatsApp desabilitado.
- `?customer=` inválido ou de outro vendedor: formulário abre sem cliente escolhido.
- Valores sempre formatados em R$ pt-BR com o `money` de `format.js`.

## Testes

- `backend/test_dashboard.py`, no estilo de `test_security.py` (banco SQLite temporário):
  status do cliente nas fronteiras (60/61, 150/151 dias, sem venda; orçamento e cancelado não contam),
  pedido atrasado (sim para confirmado/em produção vencido; não para enviado/entregue/cancelado),
  `daily_sales` diário vs. semanal, vendedor não recebe clientes, pedidos nem metas de outro vendedor.
- `backend/test_security.py` continua passando.
- Frontend: `npm run build` sem erro e conferência manual das três telas com admin e com vendedor,
  no desktop e na largura de celular.

## Ordem sugerida de implementação

1. Banco + API (metas, `/dashboard` novos campos, `/customers/overview`) com testes.
2. Campos de meta em Configurações e Usuários.
3. Componentes compartilhados (`PeriodPicker`, `TeamRanking`).
4. Clientes (inclui `?customer=` no `OrderForm`).
5. Painel.
6. Faturamento.
