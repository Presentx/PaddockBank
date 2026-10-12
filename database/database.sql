-- ─────────────────────────────────────────────────────────────
-- Paddock Bank — schema
--
-- Convencoes (as mesmas do base-service):
--   • id SERIAL e interno: so ele aparece em chave estrangeira e
--     nunca sai na API;
--   • *_key CHAR(36) e o UUID que o mundo de fora conhece;
--   • dinheiro e BIGINT em CENTAVOS. Nenhuma coluna de valor e float;
--   • percentual e INTEGER em pontos-base (bps): 100 bps = 1 por cento.
--
-- As restricoes tem NOME de proposito: quando duas requisicoes
-- simultaneas passam pela conferencia do controller e so o banco pega
-- a duplicidade, e pelo nome da restricao violada que o controller
-- escolhe o erro certo (veja BaseController._flush_or_conflict).
-- ─────────────────────────────────────────────────────────────

-- sample_entity: o molde do base-service, como veio na base.
CREATE TABLE sample_entity_status(
    id		                        SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO sample_entity_status (enumerator) VALUES
('created'),
('pending'),
('success'),
('failed');

CREATE TABLE sample_entity(
    id                              SERIAL PRIMARY KEY,
    sample_entity_key               CHAR(36) NOT NULL,
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    sample_entity_data              JSONB NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    birthdate                       DATE NOT NULL,
    counter                         INTEGER NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(sample_entity_key),
    UNIQUE(document_number),
    UNIQUE(email)
);

CREATE TABLE sample_entity_status_event(
    id                              SERIAL PRIMARY KEY,
    sample_entity_id                INTEGER NOT NULL REFERENCES sample_entity(id),
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    event_datetime                  TIMESTAMP NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW())
);

-- Os parametros comerciais moram aqui, e nao no codigo: mudar uma
-- tarifa e um UPDATE, nao um deploy.
CREATE TABLE plan(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    outgoing_fee_bps                INTEGER NOT NULL CHECK (outgoing_fee_bps >= 0),
    min_outgoing_fee                BIGINT NOT NULL CHECK (min_outgoing_fee >= 0),
    handover_fee                    BIGINT NOT NULL CHECK (handover_fee >= 0),
    monthly_price                   BIGINT NOT NULL CHECK (monthly_price >= 0),
    loan_monthly_rate_bps           INTEGER NOT NULL CHECK (loan_monthly_rate_bps >= 0),
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT plan_enumerator_key UNIQUE(enumerator)
);

INSERT INTO plan
(enumerator, outgoing_fee_bps, min_outgoing_fee, handover_fee, monthly_price, loan_monthly_rate_bps) VALUES
('FREE', 100, 10, 4990, 0, 350),
('PRO', 50, 10, 0, 4990, 250);

CREATE TABLE team(
    id                              SERIAL PRIMARY KEY,
    team_key                        CHAR(36) NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    university                      VARCHAR(255) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT team_team_key_key UNIQUE(team_key),
    CONSTRAINT team_name_university_key UNIQUE(name, university)
);

-- Uma conta por equipe (o UNIQUE em team_id).
--
-- Os dois CHECK sao a ultima barreira do saldo: `overdraft` e o valor
-- negativo AUTORIZADO, e so a tarifa de passagem de gestao o aumenta.
-- Como pagamento, tarifa de saida e parcela nunca mexem nele, o saldo
-- so fica negativo pela passagem — mesmo que o controller erre a conta.
CREATE TABLE account(
    id                              SERIAL PRIMARY KEY,
    account_key                     CHAR(36) NOT NULL,
    team_id                         INTEGER NOT NULL REFERENCES team(id),
    plan_id                         INTEGER NOT NULL REFERENCES plan(id),
    pix_key                         CHAR(36) NOT NULL,
    balance                         BIGINT NOT NULL DEFAULT 0,
    overdraft                       BIGINT NOT NULL DEFAULT 0,
    grace_until                     DATE NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT account_account_key_key UNIQUE(account_key),
    CONSTRAINT account_team_id_key UNIQUE(team_id),
    CONSTRAINT account_pix_key_key UNIQUE(pix_key),
    CONSTRAINT account_overdraft_check CHECK (overdraft >= 0),
    CONSTRAINT account_balance_check CHECK (balance >= -overdraft)
);

-- A arvore de cargos: parent_role_id nulo e a raiz.
CREATE TABLE role(
    id                              SERIAL PRIMARY KEY,
    role_key                        CHAR(36) NOT NULL,
    team_id                         INTEGER NOT NULL REFERENCES team(id),
    parent_role_id                  INTEGER REFERENCES role(id),
    name                            VARCHAR(255) NOT NULL,
    is_finance                      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT role_role_key_key UNIQUE(role_key),
    CONSTRAINT role_team_name_key UNIQUE(team_id, name)
);

-- Um cargo financeiro por equipe, e so um. Indice unico PARCIAL: so as
-- linhas com is_finance entram nele, entao os outros cargos da equipe
-- nao disputam a vaga.
CREATE UNIQUE INDEX role_one_finance_per_team ON role (team_id) WHERE is_finance;

CREATE TABLE member_status(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT member_status_enumerator_key UNIQUE(enumerator)
);

INSERT INTO member_status (enumerator) VALUES
('ACTIVE'),
('INACTIVE');

-- CPF e e-mail sao unicos POR EQUIPE: a mesma pessoa pode ser
-- responsavel em duas equipes.
CREATE TABLE member(
    id                              SERIAL PRIMARY KEY,
    member_key                      CHAR(36) NOT NULL,
    team_id                         INTEGER NOT NULL REFERENCES team(id),
    role_id                         INTEGER NOT NULL REFERENCES role(id),
    status_id                       INTEGER NOT NULL REFERENCES member_status(id),
    name                            VARCHAR(255) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    phone                           VARCHAR(20) NOT NULL,
    pix_key                         VARCHAR(77) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT member_member_key_key UNIQUE(member_key),
    CONSTRAINT member_team_document_number_key UNIQUE(team_id, document_number),
    CONSTRAINT member_team_email_key UNIQUE(team_id, email)
);

CREATE TABLE supplier(
    id                              SERIAL PRIMARY KEY,
    supplier_key                    CHAR(36) NOT NULL,
    team_id                         INTEGER NOT NULL REFERENCES team(id),
    name                            VARCHAR(255) NOT NULL,
    document_number                 CHAR(18) NOT NULL,
    pix_key                         VARCHAR(77) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT supplier_supplier_key_key UNIQUE(supplier_key),
    CONSTRAINT supplier_team_document_number_key UNIQUE(team_id, document_number)
);

-- `committed` e a soma dos pedidos PENDING e PAID do subsistema.
-- O CHECK committed <= budget e a ultima barreira do teto.
CREATE TABLE subsystem(
    id                              SERIAL PRIMARY KEY,
    subsystem_key                   CHAR(36) NOT NULL,
    team_id                         INTEGER NOT NULL REFERENCES team(id),
    owner_role_id                   INTEGER NOT NULL REFERENCES role(id),
    name                            VARCHAR(255) NOT NULL,
    budget                          BIGINT NOT NULL,
    committed                       BIGINT NOT NULL DEFAULT 0,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT subsystem_subsystem_key_key UNIQUE(subsystem_key),
    CONSTRAINT subsystem_team_name_key UNIQUE(team_id, name),
    CONSTRAINT subsystem_budget_check CHECK (budget >= 0),
    CONSTRAINT subsystem_committed_check CHECK (committed >= 0 AND committed <= budget)
);

-- Os ids desta tabela sao ESCRITOS, e nao gerados, por causa do indice
-- parcial expense_open_invoice la embaixo: o predicado de um indice so
-- aceita constante, entao ele precisa citar os numeros de PENDING e
-- PAID. Escrevendo os ids aqui, o numero deixa de ser sorteio do banco
-- e passa a ser parte do schema.
CREATE TABLE expense_status(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT expense_status_enumerator_key UNIQUE(enumerator)
);

INSERT INTO expense_status (id, enumerator) VALUES
(1, 'PENDING'),
(2, 'PAID'),
(3, 'REJECTED'),
(4, 'CANCELED');

CREATE TABLE expense(
    id                              SERIAL PRIMARY KEY,
    expense_key                     CHAR(36) NOT NULL,
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    subsystem_id                    INTEGER NOT NULL REFERENCES subsystem(id),
    supplier_id                     INTEGER NOT NULL REFERENCES supplier(id),
    requester_member_id             INTEGER NOT NULL REFERENCES member(id),
    approver_member_id              INTEGER REFERENCES member(id),
    status_id                       INTEGER NOT NULL REFERENCES expense_status(id),
    kind                            VARCHAR(50) NOT NULL,
    amount                          BIGINT NOT NULL,
    description                     VARCHAR(255) NOT NULL,
    invoice_number                  VARCHAR(60),
    idempotency_key                 VARCHAR(64) NOT NULL,
    reason                          VARCHAR(255),
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT expense_expense_key_key UNIQUE(expense_key),
    CONSTRAINT expense_requester_idempotency_key UNIQUE(requester_member_id, idempotency_key),
    CONSTRAINT expense_amount_check CHECK (amount > 0),
    CONSTRAINT expense_kind_check CHECK (kind IN ('SUPPLIER_PAYMENT', 'REIMBURSEMENT')),
    CONSTRAINT expense_reimbursement_invoice_check CHECK (kind <> 'REIMBURSEMENT' OR invoice_number IS NOT NULL)
);

-- Uma nota fiscal de um fornecedor so pode estar em UM pedido pendente
-- ou pago. Pedido recusado ou cancelado sai do indice e libera a nota.
CREATE UNIQUE INDEX expense_open_invoice ON expense (supplier_id, invoice_number)
    WHERE invoice_number IS NOT NULL AND status_id IN (1, 2);

-- O request_id e o X-Request-ID da requisicao que causou a linha. O
-- base-service aceita ate 64 caracteres vindos de fora (veja
-- src/utils/request_context.py), e por isso a coluna e VARCHAR(64).
CREATE TABLE expense_status_event(
    id                              SERIAL PRIMARY KEY,
    expense_id                      INTEGER NOT NULL REFERENCES expense(id),
    status_id                       INTEGER NOT NULL REFERENCES expense_status(id),
    member_id                       INTEGER NOT NULL REFERENCES member(id),
    request_id                      VARCHAR(64) NOT NULL,
    event_datetime                  TIMESTAMP NOT NULL
);

CREATE TABLE loan(
    id                              SERIAL PRIMARY KEY,
    loan_key                        CHAR(36) NOT NULL,
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    requester_member_id             INTEGER NOT NULL REFERENCES member(id),
    status                          VARCHAR(20) NOT NULL,
    principal                       BIGINT NOT NULL,
    monthly_rate_bps                INTEGER NOT NULL,
    installments                    INTEGER NOT NULL,
    installment_amount              BIGINT NOT NULL,
    purpose                         VARCHAR(255) NOT NULL,
    idempotency_key                 VARCHAR(64) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT loan_loan_key_key UNIQUE(loan_key),
    CONSTRAINT loan_account_idempotency_key UNIQUE(account_id, idempotency_key),
    CONSTRAINT loan_status_check CHECK (status IN ('ACTIVE', 'LATE', 'PAID')),
    CONSTRAINT loan_principal_check CHECK (principal > 0),
    CONSTRAINT loan_installments_check CHECK (installments BETWEEN 1 AND 12)
);

CREATE TABLE transaction_type(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT transaction_type_enumerator_key UNIQUE(enumerator)
);

INSERT INTO transaction_type (enumerator) VALUES
('DEPOSIT'),
('SUPPLIER_PAYMENT'),
('REIMBURSEMENT'),
('FEE'),
('HANDOVER_FEE'),
('LOAN_DISBURSEMENT'),
('LOAN_INSTALLMENT');

-- O extrato. Append-only: nenhuma linha daqui e alterada ou apagada.
-- `amount` tem sinal (credito positivo, debito negativo) e
-- `balance_after` e o saldo da conta logo depois da linha: a soma dos
-- amounts de uma conta e sempre o saldo dela.
CREATE TABLE transaction(
    id                              SERIAL PRIMARY KEY,
    transaction_key                 CHAR(36) NOT NULL,
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    type_id                         INTEGER NOT NULL REFERENCES transaction_type(id),
    expense_id                      INTEGER REFERENCES expense(id),
    loan_id                         INTEGER REFERENCES loan(id),
    subsystem_id                    INTEGER REFERENCES subsystem(id),
    amount                          BIGINT NOT NULL,
    balance_after                   BIGINT NOT NULL,
    counterparty_name               VARCHAR(255),
    counterparty_document           VARCHAR(18),
    description                     VARCHAR(255),
    idempotency_key                 VARCHAR(64),
    request_id                      VARCHAR(64) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT transaction_transaction_key_key UNIQUE(transaction_key),
    CONSTRAINT transaction_account_idempotency_key UNIQUE(account_id, idempotency_key),
    CONSTRAINT transaction_amount_check CHECK (amount <> 0)
);

CREATE INDEX transaction_account_id_idx ON transaction (account_id, id);

CREATE TABLE loan_installment(
    id                              SERIAL PRIMARY KEY,
    loan_id                         INTEGER NOT NULL REFERENCES loan(id),
    number                          INTEGER NOT NULL,
    due_date                        DATE NOT NULL,
    amount                          BIGINT NOT NULL,
    status                          VARCHAR(20) NOT NULL,
    transaction_id                  INTEGER REFERENCES transaction(id),
    paid_at                         TIMESTAMP,
    CONSTRAINT loan_installment_loan_number_key UNIQUE(loan_id, number),
    CONSTRAINT loan_installment_status_check CHECK (status IN ('PENDING', 'PAID', 'LATE')),
    CONSTRAINT loan_installment_amount_check CHECK (amount > 0)
);

CREATE INDEX loan_installment_due_idx ON loan_installment (due_date) WHERE status <> 'PAID';

CREATE TABLE handover(
    id                              SERIAL PRIMARY KEY,
    handover_key                    CHAR(36) NOT NULL,
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    outgoing_member_id              INTEGER NOT NULL REFERENCES member(id),
    incoming_member_id              INTEGER NOT NULL REFERENCES member(id),
    fee                             BIGINT NOT NULL,
    transaction_id                  INTEGER REFERENCES transaction(id),
    idempotency_key                 VARCHAR(64) NOT NULL,
    request_id                      VARCHAR(64) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    CONSTRAINT handover_handover_key_key UNIQUE(handover_key),
    CONSTRAINT handover_account_idempotency_key UNIQUE(account_id, idempotency_key),
    CONSTRAINT handover_fee_check CHECK (fee >= 0)
);
