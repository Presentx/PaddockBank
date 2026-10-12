# Paddock Bank — conta e orçamento para equipes de Formula SAE

Time: Gabriel de Castilho Valdo e Rodrigo Rampani Costa

Entrega final do Bootcamp QI Tech 2026. Uma API REST em **Python +
FastAPI**, com banco **PostgreSQL**, rodando em **Docker**, construída
sobre o `bootcamp-base-api` sem alterar a estrutura de camadas dele.

O Paddock Bank dá a uma equipe universitária de Formula SAE o que hoje
vive na conta pessoal do capitão e numa planilha: **conta própria**,
**orçamento por subsistema**, **cadastro de fornecedores** e **linha de
crédito** — sob uma regra única de saída de dinheiro: todo gasto é
**solicitado por um responsável e aprovado pelo responsável
financeiro**.

O desenho completo (problema, alternativas descartadas, modelo de
receita, diagramas e fluxos) está na **RFC**, entregue em PDF. Este
README é o manual do código: como subir, como chamar, e onde cada regra
da RFC mora.

---

## 1. Rodando

Você precisa de **Docker** (para a API e o banco) e de **Python 3.11+**
(só para os testes).

```bash
docker compose up
```

Um comando, sem criar arquivo nenhum antes: as configurações têm valor
padrão no `docker-compose.yml`. Quando aparecer
`Application startup complete`, abra http://localhost:3000:

```json
{"service":"paddock-bank-api","id":"8"}
```

| Serviço | O que é |
|---|---|
| `api` | a API do Paddock Bank |
| `db` | o PostgreSQL 16, com as 16 tabelas de `database/database.sql` |

> **Mexeu no `database/database.sql`?** Ele roda uma vez só, quando o
> banco nasce. Para valer de novo: `docker compose down -v` e
> `docker compose up`.

Porta ocupada? `cp .env.example .env` e troque `API_PORT` / `DB_PORT`.

---

## 2. Um passeio pelas rotas

Toda rota de negócio exige o cabeçalho `INTERNAL-TOKEN`. As rotas com
sessão exigem também o `X-Member-Key` — **quem** está agindo (seção 4).
No Windows, use o **Git Bash** para os `curl`.

Cada resposta devolve chaves que nascem diferentes a cada vez. **Copie
as suas** e troque nos comandos seguintes.

#### 1. Cadastrar a equipe

Um POST cria a equipe, a conta (plano `FREE`, chave PIX própria, 60
dias sem tarifa), o cargo financeiro e o responsável que o ocupa.

```bash
curl -X POST http://localhost:3000/team \
  -H "INTERNAL-TOKEN: default_token" -H "Content-Type: application/json" \
  -d '{
    "name": "EESC-USP Formula SAE",
    "university": "USP São Carlos",
    "finance_role_name": "Diretoria Financeira",
    "treasurer": {
      "name": "Maria da Silva",
      "document_number": "529.982.247-25",
      "email": "maria@exemplo.com.br",
      "phone": "+55 16 99999-0000",
      "pix_key": "maria@exemplo.com.br"
    }
  }'
```

```json
{"team_key":"<TEAM>","account_key":"<ACCOUNT>","pix_key":"<PIX>","finance_role_key":"<FINANCE_ROLE>","member_key":"<MARIA>"}
```

A `member_key` devolvida é a da Maria, a responsável financeira. É ela
que vai no `X-Member-Key` dos próximos comandos.

#### 2. Receber um patrocínio

O dinheiro só entra pela chave PIX da conta. Esta rota não tem sessão:
quem a chama é o arranjo de pagamentos, não um responsável.

```bash
curl -X POST http://localhost:3000/pix/<PIX>/deposit \
  -H "INTERNAL-TOKEN: default_token" -H "Content-Type: application/json" \
  -d '{"amount": 500000, "payer_name": "Patrocinador S.A.", "payer_document": "11.222.333/0001-81",
       "description": "Cota ouro", "idempotency_key": "pix-0001"}'
```

```json
{"transaction_key":"...","balance_after":500000}
```

Valores sempre em **centavos inteiros**: `500000` é R$ 5.000,00. Rode o
mesmo comando de novo: a resposta é a mesma, com **200** em vez de 201,
e o saldo não muda — é a `idempotency_key` trabalhando.

#### 3. Montar o orçamento e cadastrar um fornecedor

```bash
curl -X POST http://localhost:3000/team/<TEAM>/subsystem \
  -H "INTERNAL-TOKEN: default_token" -H "X-Member-Key: <MARIA>" -H "Content-Type: application/json" \
  -d '{"name": "Powertrain", "budget": 100000, "owner_role_key": "<FINANCE_ROLE>"}'

curl -X POST http://localhost:3000/team/<TEAM>/supplier \
  -H "INTERNAL-TOKEN: default_token" -H "X-Member-Key: <MARIA>" -H "Content-Type: application/json" \
  -d '{"name": "Usinagem Interlagos Ltda", "document_number": "11.222.333/0001-81", "pix_key": "11.222.333/0001-81"}'
```

#### 4. Solicitar um gasto

```bash
curl -X POST http://localhost:3000/expense \
  -H "INTERNAL-TOKEN: default_token" -H "X-Member-Key: <MARIA>" -H "Content-Type: application/json" \
  -d '{"subsystem_key": "<SUBSYSTEM>", "supplier_key": "<SUPPLIER>", "kind": "SUPPLIER_PAYMENT",
       "amount": 15000, "description": "Jogo de pastilhas de freio", "idempotency_key": "pedido-0001"}'
```

```json
{"expense_key":"<EXPENSE>","status":"PENDING"}
```

O pedido nasce `PENDING` e **já reserva** os R$ 150,00 no subsistema
(`GET /team/<TEAM>/subsystems` mostra `committed: 15000`). O dinheiro
ainda não saiu da conta. Um pedido acima do que resta do teto responde
**409** `PDK-SUBS-004`.

#### 5. Aprovar — e pagar

```bash
curl -X PUT http://localhost:3000/expense/<EXPENSE>/approve \
  -H "INTERNAL-TOKEN: default_token" -H "X-Member-Key: <MARIA>"
```

```json
{"expense_key":"<EXPENSE>","status":"PAID","fee":0,"balance_after":485000}
```

`fee: 0` porque a conta está na carência. Depois dela, a tarifa de
saída (1,0% no `FREE`, mínimo de R$ 0,10) sai como uma linha `FEE`
própria no extrato. Aprovar de novo responde **409** `PDK-EXP-002`: um
pedido é pago uma vez só.

#### 6. O extrato

```bash
curl http://localhost:3000/account/<ACCOUNT>/statement \
  -H "INTERNAL-TOKEN: default_token" -H "X-Member-Key: <MARIA>"
```

Da linha mais nova para a mais antiga, cada uma com o `amount` com
sinal e o `balance_after`. A soma dos `amount` é sempre o saldo da
conta.

#### 7. Sem identidade, e a identidade errada

Tire o `X-Member-Key` do comando 6: **401** `PDK-GEN-006`. Cadastre
outra equipe e use a `member_key` dela para ler a conta da primeira:
**404** `PDK-ACCT-001` — a mesma resposta de uma conta que não existe.

---

## 3. Todas as rotas

| Método e rota | O que faz | Quem pode |
|---|---|---|
| `GET /` | diz qual serviço é este | aberta |
| `GET /health_check` | diz se a API está de pé (`204`) | aberta |
| `POST /team` | cadastra equipe, conta, cargo financeiro e responsável | sem sessão |
| `GET /team/{team_key}` | a equipe, a conta e o responsável financeiro | responsável |
| `POST /team/{team_key}/handover` | passagem de gestão | financeiro |
| `POST /team/{team_key}/role` | cria um cargo | financeiro |
| `PATCH /role/{role_key}` | renomeia ou reposiciona um cargo | financeiro |
| `GET /team/{team_key}/roles` | lista os cargos | responsável |
| `POST /team/{team_key}/member` | cadastra um responsável | financeiro |
| `PATCH /member/{member_key}` | altera contato, cargo ou situação | financeiro |
| `GET /member/{member_key}` | um responsável | responsável |
| `GET /team/{team_key}/members` | lista (filtro `role_key`) | responsável |
| `POST /team/{team_key}/supplier` | cadastra um fornecedor (CNPJ) | responsável |
| `GET /team/{team_key}/suppliers` | lista os fornecedores | responsável |
| `POST /team/{team_key}/subsystem` | cria um subsistema | financeiro |
| `PATCH /subsystem/{subsystem_key}` | altera nome, teto ou cargo | financeiro |
| `GET /team/{team_key}/subsystems` | lista com teto, comprometido e disponível | responsável |
| `GET /account/{account_key}` | saldo, plano, titular, limite de crédito | responsável |
| `PATCH /account/{account_key}` | troca o plano (`FREE` / `PRO`) | financeiro |
| `POST /pix/{pix_key}/deposit` | credita uma entrada | sem sessão |
| `GET /account/{account_key}/statement` | extrato (filtro `subsystem_key`) | responsável |
| `POST /expense` | solicita um gasto e reserva o orçamento | responsável |
| `GET /expense/{expense_key}` | o pedido e o histórico de status | responsável |
| `GET /team/{team_key}/expenses` | lista (filtro `status`, repetível) | responsável |
| `PUT /expense/{expense_key}/approve` | `PENDING → PAID`: debita e paga | financeiro |
| `PUT /expense/{expense_key}/reject` | `PENDING → REJECTED`: libera a reserva | financeiro |
| `PUT /expense/{expense_key}/cancel` | `PENDING → CANCELED`: libera a reserva | só o solicitante |
| `POST /account/{account_key}/loan` | contrata crédito | financeiro |
| `GET /loan/{loan_key}` | o crédito e as parcelas | responsável |
| `POST /loan-installments/charge-due` | cobra as parcelas vencidas (agendador) | sem sessão |

"Responsável" é qualquer responsável **ativo da equipe dona do
recurso**. As listas aceitam `?limit=` (padrão 10, teto 100) e `?page=`
(padrão 0) e devolvem `data`, `limit`, `page` e `is_last_page`.
Parâmetro com nome desconhecido é recusado com 400.

Rotas idempotentes: `POST /pix/.../deposit`, `POST /expense`,
`POST /account/.../loan` e `POST /team/.../handover` recebem uma
`idempotency_key`; a repetição devolve o resultado original com `200`.
`POST /team`, `/member` e `/supplier` são protegidas pelo `UNIQUE`
natural (a repetição responde `409`). A cobrança de parcelas ignora
parcela já paga.

---

## 4. Identidade e acesso

Esta API **não autentica o usuário final** — isso é do gateway. O
gateway confere quem é a pessoa e repassa a `member_key` dela em
`X-Member-Key`, junto com o `INTERNAL-TOKEN`. É o token que torna o
cabeçalho confiável.

O ator de toda operação sai desse cabeçalho e **nunca do corpo**:
nenhum schema aceita um campo "quem solicita" ou "quem aprova".

| Situação | Resposta |
|---|---|
| sem `INTERNAL-TOKEN` | `403` `PDK-GEN-002` |
| sem `X-Member-Key`, fora do formato ou de ninguém | `401` `PDK-GEN-006` |
| responsável inativo | `422` `PDK-MEMB-005` |
| rota do financeiro, e quem chama não é | `403` `PDK-GEN-004` |
| recurso **do caminho** é de outra equipe | `404` do próprio recurso |
| chave **do corpo** aponta para outra equipe | `422` `PDK-GEN-003` |

O 404 para recurso de outra equipe é deliberado: responder "existe, mas
não é seu" já revelaria a existência (IDOR). Onde isso mora no código:
`src/middlewares/member_identity.py` põe a identidade no contexto;
`BaseController._get_actor`, `_require_finance` e `_require_same_team`
conferem.

---

## 5. As regras do dinheiro

Os parâmetros que mudam por plano moram na tabela `plan` (um `UPDATE`
troca uma tarifa, sem deploy):

| | `FREE` | `PRO` |
|---|---|---|
| Mensalidade | R$ 0 | R$ 49,90 |
| Tarifa por saída | 1,0%, mínimo R$ 0,10 | 0,5%, mínimo R$ 0,10 |
| Tarifa de passagem de gestão | R$ 49,90 | isenta |
| Juros do crédito | 3,5% a.m. | 2,5% a.m. |

Os que valem para todos estão em `src/constants.py`: carência de **60
dias** sem tarifa; limite de crédito de **50% do saldo médio diário de
90 dias**, menos o saldo devedor.

- **Dinheiro é inteiro.** Centavos em `BIGINT`, percentuais em
  pontos-base (`350` = 3,5%). Nenhum valor vira `float`; a parcela da
  tabela Price é calculada em `Decimal` e arredondada uma vez.
- **Tarifa de saída**: `max(valor × alíquota, mínimo)`, arredondada ao
  centavo mais próximo. É uma linha `FEE` do extrato, separada do
  pagamento.
- **Saldo não negativo**: pagamento, tarifa de saída e parcela só saem
  com saldo. A única exceção é a **tarifa de passagem de gestão**,
  cobrada mesmo sem saldo: o descoberto fica em `account.overdraft`, é
  compensado pelas entradas seguintes e, enquanto durar, a conta não
  paga pedidos.
- **Limite de crédito**: média do saldo de fechamento dos últimos 90
  dias (hoje incluso), calculada sobre o extrato. Dinheiro que chegou
  hoje pesa um dia em noventa. O saldo devedor é a soma das parcelas em
  aberto. Parcela em atraso bloqueia nova contratação.
- **Crédito**: 1 a 12 parcelas iguais (tabela Price), a primeira um mês
  depois. A taxa é copiada do plano na contratação.

### Concorrência: a ordem das travas

Toda decisão sobre dinheiro é tomada com a linha consultada travada
(`SELECT ... FOR UPDATE`) e gravada na mesma transação. Todas as rotas
travam na **mesma ordem — pedido ou parcela, subsistema, conta** —, o
que impede o deadlock:

| Operação | Trava |
|---|---|
| solicitar gasto | subsistema |
| aprovar | pedido → conta |
| recusar / cancelar | pedido → subsistema |
| cobrar parcela | parcela → conta |
| depósito, crédito, passagem, troca de plano | conta |

Por baixo, o banco repete as regras como última barreira:
`CHECK (committed <= budget)`, `CHECK (balance >= -overdraft)`, o índice
único parcial da nota fiscal e os `UNIQUE` das chaves de idempotência.
Quando só o banco pega um conflito (duas requisições passaram juntas
pela conferência), o controller traduz a restrição violada no mesmo
`409` — veja `BaseController._flush_or_conflict`.

### Rastreabilidade

O `X-Request-ID` (recebido ou gerado pelo base-service) aparece em toda
linha de log e é **gravado** em cada linha do extrato, em cada evento
do histórico de um pedido e em cada passagem de gestão. De um
lançamento se chega à requisição que o causou:

```bash
docker compose logs api | grep <request_id>
```

---

## 6. Rodando os testes

Os testes rodam **na sua máquina**, contra a API de pé no Docker, e
falam com ela só por HTTP — nenhum importa nada de `src/`.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

```
============================= 114 passed in 12s ==============================
```

| Arquivo | Testes | O que cobre |
|---|---|---|
| `test_healthcheck.py` | 8 | raiz, health check, 403/404/405, `X-Request-ID`, acentos |
| `team/test_team.py` | 8 | cadastro atômico, duplicidade, CPF, 401, IDOR |
| `role/test_role.py` | 11 | árvore de cargos, ciclo, acesso, paginação |
| `member/test_member.py` | 13 | cadastro, cargo financeiro só por passagem, inativo |
| `supplier/test_supplier.py` | 5 | CNPJ, duplicidade por equipe |
| `subsystem/test_subsystem.py` | 8 | teto, teto abaixo do comprometido |
| `account/test_account.py` | 11 | depósito idempotente (inclusive simultâneo), extrato |
| `expense/test_expense_create.py` | 12 | reserva, teto sob pedidos simultâneos, nota fiscal |
| `expense/test_expense_decision.py` | 16 | tarifa, saldo, pagamento único, recusa, cancelamento |
| `loan/test_loan.py` | 12 | limite, tabela Price, cobrança, atraso |
| `handover/test_handover.py` | 10 | troca de titular, tarifa sem saldo, repetição |

Sete desses testes disparam requisições **simultâneas** (com threads)
para provar as garantias de concorrência da RFC: dez pedidos disputando
o resto de um orçamento, oito aprovações do mesmo pedido, seis
pagamentos disputando o saldo, oito cópias do mesmo depósito e da mesma
passagem de gestão.

Duas honestidades sobre os testes:

- **A carência dura 60 dias**, e um teste de caixa-preta não tem como
  esperar. `DbUtils.expire_grace()` empurra o `grace_until` da conta
  para ontem, direto no banco. É a única vez em que um teste monta
  cenário fora da API, e o porquê está em `tests/utils/db_utils.py`.
- **Os testes da cobrança de parcelas zeram o banco**
  (`DbUtils.rollback()`), porque a cobrança varre o banco inteiro e
  responde quantas parcelas cobrou.

---

## 7. Onde cada coisa mora

A estrutura de pastas é a do base-service, sem alteração:

```
src/
  app.py           ← rotas, middlewares e tratamento de erro
  resources/       ← recebe o HTTP e devolve a resposta
  schemas/         ← o formato do que entra (JSON Schema)
  controllers/     ← as regras de negócio — e as travas
  repositories/    ← as consultas; todo FOR UPDATE está aqui
  models/          ← as 16 tabelas, descritas em Python
  dtos/            ← o JSON que sai
  errors/          ← os erros, cada um com o seu código PDK-
  middlewares/     ← o que vale para toda requisição
  connectors/      ← vazio de propósito: nada chama serviço de fora
  utils/           ← logger, request id, identidade, CPF/CNPJ, paginação
database/
  database.sql     ← o schema, em SQL puro
tests/             ← os testes de integração
```

Os acréscimos ao base-service, todos previstos na RFC:

| Acréscimo | Onde |
|---|---|
| middleware de identidade da sessão | `src/middlewares/member_identity.py` + `src/utils/member_identity.py` |
| validação de CNPJ, ao lado da de CPF | `src/utils/document_number.py` |
| rota acionada por agendador externo | `POST /loan-installments/charge-due` |
| `request_id` gravado nos lançamentos | `BaseController.__init__` e os repositories |

O mapa detalhado das camadas está em
[`docs/como-o-projeto-e-organizado.md`](docs/como-o-projeto-e-organizado.md).

---

## 8. Os códigos de erro

Todo erro responde no formato do base-service:

```json
{
  "title": "Subsystem budget exceeded",
  "description": "The amount (20001) exceeds the available budget of the subsystem (20000).",
  "translation": "O pedido excede o valor disponível do subsistema.",
  "code": "PDK-SUBS-004"
}
```

| Código | HTTP | Situação |
|---|---|---|
| `PDK-GEN-001` | 400 | corpo ou parâmetro fora do formato |
| `PDK-GEN-002` | 403 | `INTERNAL-TOKEN` ausente ou inválido |
| `PDK-GEN-003` | 422 | referência no corpo a recurso de outra equipe |
| `PDK-GEN-004` | 403 | operação restrita ao responsável financeiro |
| `PDK-GEN-006` | 401 | identidade ausente no contexto da sessão |
| `PDK-GEN-404` | 404 | rota inexistente |
| `PDK-GEN-405` | 405 | método não aceito pela rota |
| `PDK-GEN-500` | 500 | erro inesperado |
| `PDK-TEAM-001` | 404 | equipe inexistente |
| `PDK-TEAM-002` | 409 | equipe já cadastrada com o mesmo nome e universidade |
| `PDK-ROLE-001` | 404 | cargo inexistente |
| `PDK-ROLE-002` | 409 | nome de cargo já utilizado na equipe |
| `PDK-ROLE-003` | 409 | cargo superior inválido (o próprio ou um subordinado) |
| `PDK-ROLE-004` | 409 | cargo financeiro alterável apenas pela passagem de gestão |
| `PDK-MEMB-001` | 404 | responsável inexistente |
| `PDK-MEMB-002` | 422 | CPF inválido |
| `PDK-MEMB-003` | 409 | CPF já cadastrado na equipe |
| `PDK-MEMB-004` | 409 | e-mail já cadastrado na equipe |
| `PDK-MEMB-005` | 422 | responsável inativo |
| `PDK-MEMB-006` | 409 | responsável financeiro não pode ser desativado |
| `PDK-MEMB-007` | 409 | responsável já ocupa o cargo financeiro |
| `PDK-SUPP-001` | 404 | fornecedor inexistente |
| `PDK-SUPP-002` | 422 | CNPJ inválido |
| `PDK-SUPP-003` | 409 | CNPJ já cadastrado na equipe |
| `PDK-SUBS-001` | 404 | subsistema inexistente |
| `PDK-SUBS-002` | 409 | nome de subsistema já utilizado na equipe |
| `PDK-SUBS-003` | 409 | teto inferior ao valor comprometido |
| `PDK-SUBS-004` | 409 | pedido excede o valor disponível do subsistema |
| `PDK-ACCT-001` | 404 | conta inexistente |
| `PDK-ACCT-002` | 409 | saldo insuficiente para o valor e a tarifa |
| `PDK-ACCT-003` | 404 | chave PIX inexistente |
| `PDK-EXP-001` | 404 | pedido inexistente |
| `PDK-EXP-002` | 409 | pedido fora do status `PENDING` |
| `PDK-EXP-003` | 409 | nota fiscal já paga com o fornecedor |
| `PDK-EXP-004` | 403 | cancelamento restrito ao solicitante |
| `PDK-EXP-005` | 409 | nota fiscal vinculada a pedido pendente de aprovação |
| `PDK-CRD-001` | 404 | crédito inexistente |
| `PDK-CRD-002` | 409 | valor acima do limite disponível |
| `PDK-CRD-003` | 409 | parcela em atraso impede nova contratação |

Não repita um código: a checagem `error_verification`, em
`src/errors/base_error.py`, derruba a API no start se dois erros usarem
o mesmo. Nenhuma mensagem de erro repete CPF, CNPJ ou e-mail.

---

## 9. Onde o código precisou decidir além da RFC

A RFC é o contrato; estes são os pontos em que ela não descia ao
detalhe, e o que o código fez:

- **Erros de infraestrutura.** A RFC cataloga os erros de negócio. Rota
  inexistente, método não aceito e erro inesperado ganharam
  `PDK-GEN-404`, `PDK-GEN-405` e `PDK-GEN-500`, no mesmo padrão.
- **`request_id` com 64 caracteres.** O diagrama diz `char(36)`, mas o
  base-service aceita um `X-Request-ID` recebido de até 64. As colunas
  são `VARCHAR(64)`, para que um identificador válido nunca vire 500.
- **Taxa em pontos-base.** O crédito devolve `monthly_rate_bps` (350 =
  3,5%), e não um `monthly_rate` fracionário: nenhum número da API
  viaja como float. As parcelas vêm em `installment_list`, porque
  `installments` já é a quantidade.
- **Ids escritos em `expense_status`.** O índice único parcial da nota
  fiscal precisa citar os status `PENDING` e `PAID` por número; por isso
  os ids dessa tabela são escritos no `INSERT`, e não gerados.
- **Saldo médio com o dia de hoje.** A janela de 90 dias inclui hoje, e
  o saldo de um dia é o de fechamento.
- **Responsável inativo** recebe `422 PDK-MEMB-005` em qualquer rota
  com sessão, não só nas duas em que a RFC o destaca.
- **A recusa exige `reason`**, para que o histórico diga por quê.
- **Fora do escopo, como na RFC:** autenticação do usuário final,
  liquidação PIX e DICT, consulta de CNPJ na Receita, cobrança da
  mensalidade Pro, o agendador em si, renegociação de crédito, exclusões
  e encerramento de conta.

---

## 10. A licença

**MIT**, herdada do projeto base — o arquivo `LICENSE` acompanha o
código.
