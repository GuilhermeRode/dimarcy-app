# Di Marcy Pedidos — guia para o Claude Code

## Idioma do código

- **Código em inglês por padrão**: variáveis, funções, classes, nomes de arquivo, comentários,
  nomes de rotas de API, nomes de tabelas/colunas do banco e classes CSS devem ser escritos
  em inglês (`customer`, `order`, `payment_method`, `.panel`, `.btn-primary`, etc.).
- **Texto visível para quem usa o app fica em português (pt-BR)**: rótulos, botões, mensagens
  de erro, placeholders, cabeçalhos de tabela e qualquer string exibida na tela continuam em
  português, porque o público (vendedores e administração da Di Marcy) fala português.
- Dados de exemplo/negócio (nomes de cor como "Bordô", descrições de produto como "Blusão de
  tricot xadrez") também ficam em português — são conteúdo do negócio, não código.

**Por quê**: mantém o código legível e consistente com convenções comuns de programação,
sem comprometer a experiência de quem usa o sistema no dia a dia.

## Estrutura

- `backend/app` — FastAPI + SQLAlchemy (SQLite em desenvolvimento, Postgres em produção).
  Tabelas: `users`, `customers`, `colors`, `products`, `orders`, `order_items`.
- `frontend/src` — React + Vite, empacotado como app desktop via Electron.
  Rotas do app: `/orders`, `/customers`, `/products`, `/colors`, `/users`.
- Uploads de imagem de produto ficam em `backend/uploads/products` e são servidos em `/uploads/...`.

## Ao adicionar campos/telas novas

- Siga a convenção acima: nome do campo em inglês no banco/schema/API, rótulo em português no formulário.
- Ao mudar o schema do banco (SQLite local), prefira migrar em vez de apagar `dimarcy.db`
  quando já houver dados reais cadastrados.
