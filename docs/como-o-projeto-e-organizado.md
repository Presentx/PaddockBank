# Como o projeto é organizado

> Se você ainda não rodou o projeto, comece pelo
> [`README.md`](../README.md): ele sobe a API, faz as primeiras
> requisições e lista as rotas. Este texto é o passo seguinte.

O Paddock Bank foi construído sobre o `bootcamp-base-api` **sem alterar
a estrutura de camadas dele**. As dez pastas de `src/` são as mesmas, e
cada uma continua com um trabalho só. Este texto mostra o caminho de
uma requisição por elas, o que cada pasta pode e não pode fazer, e onde
se mexe para cada tipo de mudança.

---

## 1. O caminho de uma requisição

Este é o `PUT /expense/{expense_key}/approve`, a rota que paga um gasto:

```
  requisição chega
        ↓
  src/middlewares/     cinco camadas, de fora para dentro:
        ↓              identificador da requisição (X-Request-ID) → log
        ↓              de entrada → INTERNAL-TOKEN (sem ele, para aqui:
        ↓              403) → identidade (X-Member-Key, só guarda) →
        ↓              sessão de banco. A ordem está comentada em
        ↓              src/app.py
        ↓
  src/resources/       que endereço é esse? quem cuida dele?
        ↓              (nas rotas com corpo, src/schemas/ confere o JSON
        ↓               antes da 1ª linha rodar. Torto, para aqui: 400)
        ↓
  src/controllers/     QUEM está agindo? pode fazer isso? É aqui que
        ↓              moram a regra, a ordem das travas e o commit
        ↓
  src/repositories/    a conversa com o banco — só aqui existe consulta,
        ↓              e só aqui existe SELECT ... FOR UPDATE
        ↓
  src/models/          as tabelas, descritas em Python
        ↓
      banco
        ↓
  src/dtos/            traduz o objeto do banco no JSON da resposta
        ↓
  resposta sai
```

Quando o código chega no **controller**, o JSON já foi conferido.
Quando chega no **repository**, a decisão já foi tomada. Cada camada
confia no trabalho da anterior.

---

## 2. O que cada pasta pode e não pode

| Pasta | Pode | Não pode |
|---|---|---|
| `resources/` | receber a requisição, conferir o schema, chamar **um** controller, escolher o status de sucesso | saber SQL, decidir regra, saber quem está agindo |
| `schemas/` | dizer qual JSON é aceito na entrada, e recusar o que não é | falar com banco, decidir regra |
| `controllers/` | identificar o ator, decidir o que pode, travar o que lê pra decidir, salvar (`commit`) | escrever consulta, saber que existe HTTP |
| `repositories/` | buscar, travar, criar e atualizar no banco | decidir se aquilo era permitido |
| `models/` | descrever as tabelas em Python | ter regra dentro |
| `dtos/` | transformar o objeto do banco no dicionário da resposta | buscar no banco, decidir regra |
| `errors/` | definir cada erro: código, mensagem e status HTTP | ter regra de negócio dentro |
| `middlewares/` | fazer algo em **toda** requisição | conhecer uma rota específica, consultar o banco |
| `connectors/` | chamar um serviço de fora | decidir regra, falar com o nosso banco |
| `utils/` | ferramenta de uso geral: logger, request id, identidade, CPF/CNPJ, schema, paginação | virar o depósito do que não se sabe onde pôr |

Um teste rápido para saber se uma linha está na pasta certa: **nenhum
`raise` mora em `resources/`**, e **nenhum `with_for_update` mora fora
de `repositories/`**:

```bash
grep -rn "raise" src/resources/
grep -rln "with_for_update" src/
```

O primeiro não volta nada; o segundo só volta arquivos de
`repositories/`.

`connectors/` está vazio de propósito: a liquidação PIX, o DICT e a
Receita Federal estão fora do escopo da entrega, então nada chama
serviço de fora. O `rest_connector.py` do base-service fica como o
ponto de partida de um connector futuro.

---

## 3. As três coisas que o `BaseController` passou a saber

O `BaseController` do base-service entregava a sessão de banco e o log.
Três regras do Paddock Bank valem para mais de um controller, e moram
nele em vez de serem copiadas:

**Quem está agindo.** O middleware `member_identity` não recusa
ninguém: ele só guarda o `X-Member-Key` no contexto (o mesmo mecanismo
`contextvars` do `request_id`). Quem confere é o controller:

- `_get_actor()` — acha o responsável; sem identidade, 401; inativo, 422;
- `_require_finance(actor)` — 403 se ele não ocupa o cargo financeiro;
- `_require_same_team(actor, team_id, campo)` — 422 quando uma chave
  **do corpo** aponta para outra equipe.

Recurso **do caminho** que é de outra equipe é conferido em cada
controller, junto com o "não existe", para que os dois respondam o
mesmo 404.

Middleware não consulta banco nem conhece rota — e três rotas não têm
sessão (o cadastro da equipe, o depósito e a cobrança de parcelas). Por
isso a decisão "esta rota exige identidade?" é do controller: quem não
chama `_get_actor()` não exige.

**Como o saldo muda.** `_register_movement()` é o único lugar do
projeto que escreve em `account.balance` — e ele sempre grava a linha
do extrato junto. É por isso que a soma do extrato é o saldo: não
existe caminho que mexa num sem mexer no outro.

**Quanto crédito a conta tem.** `_available_credit_limit()` é usado na
consulta da conta e na contratação do crédito.

---

## 4. Travas: onde, por quê, e em que ordem

Toda regra de dinheiro aqui é uma **leitura seguida de uma gravação**
("o saldo cobre? então debita"), e o perigo mora entre as duas: outra
requisição lê o mesmo valor no intervalo. A saída é travar a linha
ANTES de ler:

- o **repository** oferece o `..._for_update` (com `populate_existing`,
  para que o objeto já lido seja regravado com o valor de depois da
  espera);
- o **controller** decide quais linhas travar e em que ordem, e só dá
  `commit` depois de gravar tudo — a trava vale enquanto a transação
  estiver aberta.

A ordem é uma só no projeto inteiro: **pedido ou parcela → subsistema →
conta**. Nenhum método pega a conta e depois pede o pedido. É isso que
impede o deadlock.

As docstrings contam cada caso onde ele acontece:
`ExpenseController.create` (o teto), `ExpenseController.approve` (o
saldo e o pagamento único), `AccountController.deposit` e
`HandoverController.create` (a idempotência sob a trava) e
`LoanController.charge_due` (uma transação por parcela).

**E o `commit`?** Continua sendo do controller, e continua sendo a
última linha antes do `return`. O middleware de sessão cuida do ciclo
de vida (desfaz se explodiu, fecha sempre); o controller decide o
conteúdo. Uma recusa (`raise`) antes do `commit` não deixa nada
gravado — e solta as travas.

---

## 5. Onde eu mexo quando quero...

| Quero... | Mexo em | Na ordem |
|---|---|---|
| **aceitar um campo novo** na entrada | o `.json` da rota em `src/schemas/` | se vai para o banco, também `database/database.sql` e `src/models/` |
| **mudar o que a resposta devolve** | o DTO da entidade em `src/dtos/` | o envelope da listagem é do resource (`utils/pagination.py`) |
| **criar uma rota nova** | o resource da entidade | registrar em `src/app.py`; método novo no controller se a regra for nova |
| **mudar uma regra** | o controller da entidade | erro novo em `src/errors/custom_errors.py`, com código `PDK-` livre |
| **mudar uma tarifa ou os juros** | a linha do plano na tabela `plan` | nenhum arquivo de código |
| **mudar a carência ou o limite de crédito** | `src/constants.py` | — |
| **consultar o banco de outro jeito** | o repository da entidade | o controller chama o método novo |
| **criar uma tabela** | `database/database.sql` | depois `src/models/` e o `__init__.py` da pasta, na ordem das dependências |
| **exigir (ou não) o cargo financeiro** | a primeira linha do método do controller | `_get_actor()` e `_require_finance()` |

Três armadilhas herdadas do base-service, que continuam valendo:

- **A ordem do `src/models/__init__.py` importa.** Cada model importa
  de dentro do próprio pacote; entidade nova entra **depois** daquelas
  a que ela aponta.
- **O `database/database.sql` roda uma vez só**, quando o banco nasce.
  Mudou o schema: `docker compose down -v` e `docker compose up`.
- **Restrição nova no banco tem nome.** O `_flush_or_conflict` traduz a
  violação em erro pelo **nome** da restrição; uma restrição sem nome
  conhecido sobe como 500.

---

## 6. Schemas e DTOs: o que entra e o que sai

O `schemas/` cuida do que **entra**; o `dtos/` cuida do que **sai**.

- Os schemas são arquivos **JSON Schema**, conferidos pelo
  `@SchemaHandler.validate(...)` (corpo) e pelo
  `@SchemaHandler.validate_query_params(...)` (query string) antes de a
  rota rodar. Todos têm `additionalProperties: false`: campo a mais é
  400 — inclusive um campo que tente dizer quem está agindo.
- O dinheiro entra como `integer` (centavos), com mínimo e teto.
  Fração, texto e negativo morrem no schema.
- O schema cobra o **formato** (a máscara do CPF e do CNPJ); a
  **validade** (os dígitos verificadores) é do controller, e responde
  422 em vez de 400.
- Os DTOs trocam todo `id` interno por `_key`: nenhum número gerado
  pelo banco sai numa resposta.
