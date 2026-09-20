# Di Marcy Pedidos

Aplicativo desktop (Electron + React) que conversa com uma API em Python (FastAPI).
Vários vendedores, em computadores diferentes, acessam o mesmo banco pela internet.

```
[App desktop - React/Electron] --HTTPS--> [API FastAPI na nuvem] --> [PostgreSQL]
```

## Funcionalidades
- Login com usuários (perfis Administrador e Vendedor)
- Clientes: cadastro, busca, edição
- Cores: cartela com tom (hex) de cada cor
- Produtos: referência, preço, coleção, tamanhos e cores disponíveis
- Pedidos: lançamento por grade cor × tamanho, desconto, situação
  (Orçamento → Confirmado → Em produção → Enviado → Entregue / Cancelado), impressão
- Painel: faturamento, peças, ticket médio, orçamentos em aberto, evolução mensal,
  top produtos, top clientes, cores e tamanhos mais vendidos

## Rodar no computador (desenvolvimento)

### 1. API (Python 3.11+)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # Linux/Mac: cp .env.example .env
python seed_data.py             # opcional: cores + referências da coleção Inverno 2027
uvicorn app.main:app --reload
```
Documentação automática da API: http://localhost:8000/docs
Primeiro acesso: `admin@dimarcy.com.br` / `admin123` (troque em Usuários).

### 2. App (Node 20+)
```bash
cd frontend
npm install
npm run app:dev       # abre a janela desktop
# ou: npm run dev     # abre no navegador em http://localhost:5173
```

## Colocar em produção (acesso pela internet)
1. Crie um banco PostgreSQL (Neon, Supabase, Render ou Railway têm plano gratuito).
2. Publique a pasta `backend` num serviço Python (Render, Railway ou uma VPS):
   - comando de início: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - variáveis: `DATABASE_URL`, `SECRET_KEY` (texto longo aleatório), `ADMIN_EMAIL`, `ADMIN_PASSWORD`
3. No `frontend`, crie `.env` com `VITE_API_URL=https://SEU-SERVIDOR/api`.
4. Gere o instalador Windows: `npm run app:dist` → arquivo em `frontend/dist` / `release`.
5. Instale nos computadores dos vendedores.

## Estrutura
```
backend/app
  main.py        inicialização, CORS, arquivos estáticos (/uploads), cria admin no 1º acesso
  models.py      tabelas (users, customers, colors, products, orders, order_items)
  schemas.py     validação de entrada/saída
  security.py    senha (bcrypt) e token JWT
  routers/       auth, users, customers, colors, products, orders, dashboard
frontend/src
  pages/         Login, Dashboard, Orders, OrderForm, OrderDetail, Customers, Products, Colors, Users
  electron/      janela desktop
```

O código (variáveis, funções, comentários, nomes de rotas/colunas) é escrito em inglês;
os textos exibidos para quem usa o sistema (botões, rótulos, mensagens) ficam em português.
Veja [`CLAUDE.md`](./CLAUDE.md) para essa convenção.

## Próximos passos sugeridos
- Migrações com Alembic antes de alterar tabelas em produção
- Exportar pedido em PDF/Excel
- Tabela de preços por cliente (atacado/varejo)
- Estoque e ordem de produção por referência
