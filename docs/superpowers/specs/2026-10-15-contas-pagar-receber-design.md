# Contas a pagar e a receber

**Data:** 2026-10-15

## Objetivo

Controlar dentro do app o dinheiro que entra e sai, no lugar da planilha de contas a pagar:

- **A receber:** parcelas geradas automaticamente dos pedidos entregues, com baixa manual
  (conferida com o que o banco/contabilidade informa).
- **A pagar:** despesas da empresa lançadas à mão, com repetição mensal.

Só o administrador acessa. Vendedores não veem nada disso.

## Fora do escopo

- Gerar boleto e emitir NF-e — continuam no sistema atual da empresa. Pode virar outra etapa,
  usando as parcelas daqui como base.
- Importar extrato / arquivo de retorno do banco — a baixa é manual.
- Fluxo de caixa com gráfico, aviso de vencidas no Painel, exportar para Excel, anexar comprovantes.
- Categorias editáveis pela tela (começam como lista fixa no código).
- Gerar parcelas em massa para pedidos entregues antes desta funcionalidade (ver "Pedidos antigos").

## Decisões

| Tema | Decisão |
|---|---|
| Armazenamento | Uma tabela `financial_entries` para os dois lados, com `kind` = `receivable` / `payable`. |
| Quando nasce o a receber | Quando o pedido vira **Entregue**, por qualquer caminho (troca de status, edição, criação já entregue). |
| Data-base dos prazos | O dia em que o pedido foi marcado como entregue (`clock.today_br()`). |
| Valor das parcelas | Total do pedido (com desconto) ÷ nº de parcelas, arredondado; a diferença de centavos vai para a 1ª. |
| Duplicidade | Pedido que já tem parcelas nunca gera outras (cobre sair de Entregue e voltar). |
| Pedido cancelado | Parcelas em aberto daquele pedido são removidas; as pagas ficam. |
| Pedido editado após entregue | Parcelas não mudam sozinhas; o admin ajusta à mão. |
| Situação | Calculada, não gravada: **Paga** (`paid_at` preenchido), **Vencida** (aberta e `due_date` < hoje), **Em aberto**. |
| Repetição (a pagar) | "Repetir mensalmente por N meses" (1–60) cria N lançamentos independentes. |
| Onde fica na tela | Abas dentro de Faturamento: Vendas (atual) · Contas a receber · Contas a pagar. |

### Prazo do pedido → parcelas (dias após a entrega)

| `payment_terms` | Dias |
|---|---|
| À vista | 0 (1 parcela, vence no dia da entrega) |
| 30/60, 30/60/90, 30/60/90/120, 30/60/90/120/150 | os números do texto |
| Quinzenal | 15, 30, 45 … 150 (10 parcelas) |
| Qualquer outro texto | 0 (1 parcela; o admin ajusta) |

Função pura `installment_days(payment_terms) -> list[int]`, fácil de testar.

## Dados

Nova tabela `financial_entries` (criada pelo `create_all`; nenhuma coluna nova em tabelas existentes):

| Coluna | Tipo | Uso |
|---|---|---|
| `id` | int PK | |
| `kind` | `String(10)`, indexado | `receivable` / `payable` |
| `description` | `String(200)` | "Pedido 00123 — parcela 2/3", "Aluguel (3/12)" |
| `amount` | `Numeric(12,2)` | valor previsto |
| `due_date` | `Date`, indexado | vencimento |
| `paid_at` | `Date` nulo | data da baixa; nulo = em aberto |
| `paid_amount` | `Numeric(12,2)` nulo | valor efetivamente pago (juros/desconto) |
| `payment_method` | `String(40)` nulo | no a receber, copiado do pedido |
| `notes` | `Text` nulo | |
| `order_id` | FK `orders.id` nulo, indexado | a receber de pedido |
| `customer_id` | FK `customers.id` nulo | a receber (de pedido ou avulso) |
| `supplier` | `String(160)` nulo | a pagar, texto livre |
| `category` | `String(40)` nulo | a pagar, uma de `PAYABLE_CATEGORIES` |
| `installment`, `installments` | int nulos | "2 de 3" |
| `created_at` | `DateTime` | |

`PAYABLE_CATEGORIES = ["Matéria-prima", "Aluguel", "Salários", "Impostos", "Energia", "Manutenção", "Outros"]`
(valores em português por serem conteúdo do negócio).

## Backend

Novo `app/finance.py` com a lógica (sem FastAPI), e `app/routers/finance.py` com as rotas.
Tudo sob `require_admin`.

**Lógica (`app/finance.py`):**
- `installment_days(terms)` — tabela acima.
- `split_amount(total, n)` — divide em centavos; resto na 1ª parcela.
- `create_order_installments(db, order, today)` — se o pedido já tem lançamentos, não faz nada;
  senão cria um `receivable` por parcela.
- `cancel_order_installments(db, order)` — remove os em aberto do pedido.
- `add_months(d, n)` — mantém o dia, limitado ao fim do mês (31/01 + 1 → 28/02).

**Ganchos nos pedidos (`routers/orders.py`):** onde hoje já existe `became_delivered`
(criação, edição e `PATCH /status`) chama `create_order_installments`; quando o status passa a
`canceled`, chama `cancel_order_installments`. Na criação, se já nasce `delivered`, também gera.

**Rotas (`/api/finance`):**

| Método e caminho | O que faz |
|---|---|
| `GET /entries?kind=&status=open\|overdue\|paid\|all&start=&end=&search=&category=&order_id=` | lista; período filtra por vencimento; `search` busca em descrição, cliente e fornecedor |
| `GET /summary?kind=` | cartões: vencido (valor, qtd), vence em 7 dias, em aberto, pago no mês corrente |
| `POST /entries` | lança manualmente (`kind`, campos, `repeat_months` opcional, padrão 1) |
| `PUT /entries/{id}` | edita descrição, valor, vencimento, forma, observações, fornecedor, categoria |
| `POST /entries/{id}/pay` | baixa: `paid_at` (padrão hoje), `paid_amount` (> 0, padrão o valor), `payment_method` |
| `POST /entries/{id}/unpay` | desfaz a baixa |
| `POST /entries/{id}/split` | `amount` (0 < x < valor) e `due_date` → reduz a original e cria uma nova com o restante dos campos copiados; só para lançamentos em aberto |
| `DELETE /entries/{id}` | exclui |
| `POST /orders/{order_id}/generate` | gera as parcelas de um pedido entregue que ainda não tem nenhuma (ver "Pedidos antigos"); usa hoje como data-base |

Validações: `amount` > 0 e finito; `category` deve estar na lista; `kind` só os dois valores;
`repeat_months` entre 1 e 60. Mensagens de erro em português.

### Pedidos antigos

Pedidos já entregues antes desta funcionalidade não ganham parcelas automaticamente (a maioria
já foi paga). No detalhe do pedido entregue sem parcelas aparece o botão **"Gerar parcelas"**,
que usa a regra normal com o dia de hoje como data-base; o admin ajusta vencimentos se precisar.

## Frontend

- **Faturamento** ganha abas no topo: `Vendas` (`/revenue`, tela atual), `Contas a receber`
  (`/revenue/receivables`), `Contas a pagar` (`/revenue/payables`). Rotas admin-only como hoje.
- **Uma página `Finance.jsx`** atende as duas abas, recebendo `kind`. Diferenças por `kind`:
  colunas (Cliente/Pedido × Fornecedor/Categoria), filtro de categoria e botão "Lançar conta" só
  no a pagar, rótulo "Recebido no mês" × "Pago no mês".
- **Cartões de resumo** (Vencido · Vence em 7 dias · Em aberto · Recebido/Pago no mês); clicar
  aplica o filtro correspondente.
- **Filtros:** situação (padrão Em aberto), período de vencimento, busca.
- **Tabela:** Vencimento · Cliente/Fornecedor · Pedido/Categoria · Parcela · Valor · Situação ·
  botão "Dar baixa" (ou data de pagamento, se paga). Vencidas destacadas.
- **Modal de baixa:** data (hoje), valor recebido/pago (o da parcela), forma de pagamento.
- **Modal de edição** (clicar na linha): campos editáveis + Desmembrar, Desfazer baixa, Excluir
  (com confirmação via `useConfirm`, como nas outras telas).
- **Modal "Lançar conta":** descrição, fornecedor, categoria, valor, 1º vencimento, forma,
  observações, "Repetir mensalmente por [N] meses".
- **Detalhe do pedido:** bloco "Parcelas" com a lista do pedido, situação e "Dar baixa";
  "Gerar parcelas" quando entregue e sem nenhuma.

## Testes

`backend/test_finance.py`, no estilo dos `test_*.py` atuais (SQLite temporário, `TestClient`):

- `installment_days` para cada prazo, incluindo Quinzenal = 10 e texto desconhecido = 1.
- `split_amount`: 100,00 ÷ 3 = 33,34 / 33,33 / 33,33; soma sempre igual ao total.
- Pedido marcado entregue gera parcelas com valores e vencimentos certos; marcar de novo não duplica.
- Pedido criado já como entregue gera parcelas.
- Cancelar remove as abertas e mantém as pagas.
- Baixa, desfazer baixa, desmembrar (soma preservada; não desmembra paga).
- Repetição mensal: 12 lançamentos; 31/01 → 28/02 (ou 29/02).
- Filtros de situação (aberta/vencida/paga) e resumo.
- Vendedor recebe 403 em todas as rotas `/api/finance`.
