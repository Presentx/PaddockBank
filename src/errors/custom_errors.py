"""Os erros das regras do Paddock Bank.

Os códigos seguem o padrão PDK-<ÁREA>-<NNN>, e a tabela completa está
na RFC e no README. Os genéricos de infraestrutura (PDK-GEN-001, 002,
404, 405 e 500) moram em base_error.py; aqui ficam os de sessão
(PDK-GEN-003, 004 e 006) e os de cada área do negócio.

Três famílias de status, e a escolha entre elas é sempre a mesma:

  404  o recurso do CAMINHO não existe — ou existe e é de outra equipe.
       Os dois casos respondem igual de propósito: dizer "existe, mas
       não é seu" já entregaria a existência do recurso (IDOR);
  409  o pedido é bem formado, e o que o impede é o ESTADO de agora:
       um nome já usado, um saldo que não cobre, um pedido já decidido;
  422  o pedido foi lido e entendido, e um VALOR dele não pode ser
       aceito: um CPF que não existe, uma referência a outra equipe.

Nenhuma mensagem repete CPF, CNPJ ou e-mail: é dado pessoal, e a
resposta de erro acaba em log.
"""
from errors import QIException


# ────────────────────────────────────────────────────────────────
# GEN — sessão e acesso
# ────────────────────────────────────────────────────────────────
class ForeignReference(QIException):
    """O corpo aponta para um recurso que existe, mas é de outra equipe.

    422, e não 404: aqui a chave veio no CORPO, como dado, e não no
    caminho, como endereço. O recurso do caminho foi achado e é da
    equipe certa; o valor mandado é que não serve.
    """

    code = "PDK-GEN-003"

    def __init__(self, field) -> None:
        title = "Reference to another team"
        http_status = 422
        description = f"The resource referenced in '{field}' does not belong to this team."
        translation = "O recurso referenciado não pertence a esta equipe."
        super().__init__(title, self.code, http_status, description, translation)


class ForbiddenNotFinance(QIException):
    code = "PDK-GEN-004"

    def __init__(self) -> None:
        title = "Finance role required"
        http_status = 403
        description = "This operation is restricted to the member holding the finance role."
        translation = "Operação restrita ao responsável financeiro."
        super().__init__(title, self.code, http_status, description, translation)


class MissingIdentity(QIException):
    """A requisição não trouxe uma identidade que dê pra usar.

    401, e não 403: 403 diz "sei quem você é, e você não pode"; 401 diz
    "não sei quem você é". Cai aqui o X-Member-Key ausente, fora do
    formato ou que não corresponde a nenhum responsável.
    """

    code = "PDK-GEN-006"

    def __init__(self) -> None:
        title = "Missing identity"
        http_status = 401
        description = "The request has no valid member identity (X-Member-Key) in the session context."
        translation = "Identidade ausente no contexto da sessão."
        super().__init__(title, self.code, http_status, description, translation)


# ────────────────────────────────────────────────────────────────
# TEAM
# ────────────────────────────────────────────────────────────────
class NotFoundTeam(QIException):
    code = "PDK-TEAM-001"

    def __init__(self, team_key) -> None:
        title = "Team not Found"
        http_status = 404
        description = f"Team with key {team_key} was not found."
        translation = f"A equipe com chave {team_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedTeam(QIException):
    code = "PDK-TEAM-002"

    def __init__(self) -> None:
        title = "Team already registered"
        http_status = 409
        description = "There is already a team with this name at this university."
        translation = "Já existe uma equipe com este nome nesta universidade."
        super().__init__(title, self.code, http_status, description, translation)


# ────────────────────────────────────────────────────────────────
# ROLE
# ────────────────────────────────────────────────────────────────
class NotFoundRole(QIException):
    code = "PDK-ROLE-001"

    def __init__(self, role_key) -> None:
        title = "Role not Found"
        http_status = 404
        description = f"Role with key {role_key} was not found."
        translation = f"O cargo com chave {role_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedRoleName(QIException):
    code = "PDK-ROLE-002"

    def __init__(self, name) -> None:
        title = "Role name already in use"
        http_status = 409
        description = f"There is already a role named '{name}' in this team."
        translation = f"Já existe um cargo chamado '{name}' nesta equipe."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidParentRole(QIException):
    """O cargo superior pedido é o próprio cargo, ou um subordinado dele.

    Aceitar criaria um ciclo na árvore: um cargo acima de si mesmo.
    """

    code = "PDK-ROLE-003"

    def __init__(self) -> None:
        title = "Invalid parent role"
        http_status = 409
        description = "The parent role cannot be the role itself or one of its subordinates."
        translation = "O cargo superior não pode ser o próprio cargo nem um subordinado dele."
        super().__init__(title, self.code, http_status, description, translation)


class FinanceRoleOnlyByHandover(QIException):
    """Tentaram pôr ou tirar alguém do cargo financeiro fora da passagem de gestão.

    O cargo financeiro é o titular da conta, e a troca de titular tem
    rota própria (POST /team/{team_key}/handover), com registro e
    tarifa. Deixar o PATCH do responsável fazer a mesma coisa abriria
    uma segunda porta, sem registro nenhum.
    """

    code = "PDK-ROLE-004"

    def __init__(self) -> None:
        title = "Finance role changes only by handover"
        http_status = 409
        description = "The finance role can only be assigned or left through the management handover."
        translation = "O cargo financeiro só é alterado pela passagem de gestão."
        super().__init__(title, self.code, http_status, description, translation)


# ────────────────────────────────────────────────────────────────
# MEMB
# ────────────────────────────────────────────────────────────────
class NotFoundMember(QIException):
    code = "PDK-MEMB-001"

    def __init__(self, member_key) -> None:
        title = "Member not Found"
        http_status = 404
        description = f"Member with key {member_key} was not found."
        translation = f"O responsável com chave {member_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidCpf(QIException):
    """O CPF tem a máscara certa e não existe.

    422, e não 400: o formato já foi cobrado pelo schema, que responde
    400. Aqui a API leu, entendeu, e os dígitos verificadores é que não
    batem (veja src/utils/document_number.py).
    """

    code = "PDK-MEMB-002"

    def __init__(self) -> None:
        title = "Invalid CPF"
        http_status = 422
        description = "The document number is not a valid CPF."
        translation = "O CPF informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedMemberDocument(QIException):
    code = "PDK-MEMB-003"

    def __init__(self) -> None:
        title = "CPF already registered in the team"
        http_status = 409
        description = "There is already a member with this document number in this team."
        translation = "Já existe um responsável com este CPF nesta equipe."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedMemberEmail(QIException):
    code = "PDK-MEMB-004"

    def __init__(self) -> None:
        title = "Email already registered in the team"
        http_status = 409
        description = "There is already a member with this email in this team."
        translation = "Já existe um responsável com este e-mail nesta equipe."
        super().__init__(title, self.code, http_status, description, translation)


class InactiveMember(QIException):
    code = "PDK-MEMB-005"

    def __init__(self, member_key) -> None:
        title = "Inactive member"
        http_status = 422
        description = f"Member {member_key} is inactive."
        translation = "O responsável está inativo."
        super().__init__(title, self.code, http_status, description, translation)


class FinanceMemberCannotBeDeactivated(QIException):
    code = "PDK-MEMB-006"

    def __init__(self) -> None:
        title = "Finance member cannot be deactivated"
        http_status = 409
        description = "The member holding the finance role cannot be deactivated. Hand the role over first."
        translation = "O responsável financeiro não pode ser desativado. Faça antes a passagem de gestão."
        super().__init__(title, self.code, http_status, description, translation)


class MemberAlreadyFinance(QIException):
    code = "PDK-MEMB-007"

    def __init__(self, member_key) -> None:
        title = "Member already holds the finance role"
        http_status = 409
        description = f"Member {member_key} already holds the finance role."
        translation = "O responsável já ocupa o cargo financeiro."
        super().__init__(title, self.code, http_status, description, translation)


# ────────────────────────────────────────────────────────────────
# SUPP
# ────────────────────────────────────────────────────────────────
class NotFoundSupplier(QIException):
    code = "PDK-SUPP-001"

    def __init__(self, supplier_key) -> None:
        title = "Supplier not Found"
        http_status = 404
        description = f"Supplier with key {supplier_key} was not found."
        translation = f"O fornecedor com chave {supplier_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidCnpj(QIException):
    code = "PDK-SUPP-002"

    def __init__(self) -> None:
        title = "Invalid CNPJ"
        http_status = 422
        description = "The document number is not a valid CNPJ."
        translation = "O CNPJ informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedSupplierDocument(QIException):
    code = "PDK-SUPP-003"

    def __init__(self) -> None:
        title = "CNPJ already registered in the team"
        http_status = 409
        description = "There is already a supplier with this document number in this team."
        translation = "Já existe um fornecedor com este CNPJ nesta equipe."
        super().__init__(title, self.code, http_status, description, translation)


# ────────────────────────────────────────────────────────────────
# SUBS
# ────────────────────────────────────────────────────────────────
class NotFoundSubsystem(QIException):
    code = "PDK-SUBS-001"

    def __init__(self, subsystem_key) -> None:
        title = "Subsystem not Found"
        http_status = 404
        description = f"Subsystem with key {subsystem_key} was not found."
        translation = f"O subsistema com chave {subsystem_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedSubsystemName(QIException):
    code = "PDK-SUBS-002"

    def __init__(self, name) -> None:
        title = "Subsystem name already in use"
        http_status = 409
        description = f"There is already a subsystem named '{name}' in this team."
        translation = f"Já existe um subsistema chamado '{name}' nesta equipe."
        super().__init__(title, self.code, http_status, description, translation)


class BudgetBelowCommitted(QIException):
    code = "PDK-SUBS-003"

    def __init__(self, budget, committed) -> None:
        title = "Budget below committed amount"
        http_status = 409
        description = f"The budget ({budget}) cannot be lower than the committed amount ({committed})."
        translation = "O teto não pode ser inferior ao valor já comprometido do subsistema."
        super().__init__(title, self.code, http_status, description, translation)


class BudgetExceeded(QIException):
    """O pedido não cabe no que resta do orçamento do subsistema.

    409, e não 422: o mesmo pedido seria aceito num subsistema com
    folga. O que impede é o estado de agora — o que já está
    comprometido.
    """

    code = "PDK-SUBS-004"

    def __init__(self, amount, available) -> None:
        title = "Subsystem budget exceeded"
        http_status = 409
        description = f"The amount ({amount}) exceeds the available budget of the subsystem ({available})."
        translation = "O pedido excede o valor disponível do subsistema."
        super().__init__(title, self.code, http_status, description, translation)


# ────────────────────────────────────────────────────────────────
# ACCT
# ────────────────────────────────────────────────────────────────
class NotFoundAccount(QIException):
    code = "PDK-ACCT-001"

    def __init__(self, account_key) -> None:
        title = "Account not Found"
        http_status = 404
        description = f"Account with key {account_key} was not found."
        translation = f"A conta com chave {account_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class InsufficientBalance(QIException):
    code = "PDK-ACCT-002"

    def __init__(self, required) -> None:
        title = "Insufficient balance"
        http_status = 409
        description = f"The account balance does not cover the amount plus the fee ({required})."
        translation = "Saldo insuficiente para o valor e a tarifa."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundPixKey(QIException):
    code = "PDK-ACCT-003"

    def __init__(self, pix_key) -> None:
        title = "PIX key not Found"
        http_status = 404
        description = f"There is no account with the PIX key {pix_key}."
        translation = "Chave PIX inexistente."
        super().__init__(title, self.code, http_status, description, translation)


# ────────────────────────────────────────────────────────────────
# EXP
# ────────────────────────────────────────────────────────────────
class NotFoundExpense(QIException):
    code = "PDK-EXP-001"

    def __init__(self, expense_key) -> None:
        title = "Expense not Found"
        http_status = 404
        description = f"Expense with key {expense_key} was not found."
        translation = f"O pedido com chave {expense_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class ExpenseNotPending(QIException):
    """O pedido já foi decidido: pago, recusado ou cancelado.

    É este erro que impede o pagamento em duplicidade: a segunda
    aprovação do mesmo pedido encontra PAID e para aqui.
    """

    code = "PDK-EXP-002"

    def __init__(self, current_status, target_status) -> None:
        title = "Expense is not pending"
        http_status = 409
        description = f"Expense with status {current_status} cannot change to {target_status}."
        translation = f"O pedido está {current_status} e não pode passar para {target_status}."
        super().__init__(title, self.code, http_status, description, translation)


class InvoiceAlreadyPaid(QIException):
    code = "PDK-EXP-003"

    def __init__(self, invoice_number) -> None:
        title = "Invoice already paid"
        http_status = 409
        description = f"The invoice {invoice_number} of this supplier has already been paid."
        translation = "Esta nota fiscal já foi paga a este fornecedor."
        super().__init__(title, self.code, http_status, description, translation)


class CancelOnlyByRequester(QIException):
    code = "PDK-EXP-004"

    def __init__(self) -> None:
        title = "Cancel restricted to the requester"
        http_status = 403
        description = "Only the member who requested the expense can cancel it."
        translation = "Só quem solicitou o pedido pode cancelá-lo."
        super().__init__(title, self.code, http_status, description, translation)


class InvoiceAlreadyPending(QIException):
    code = "PDK-EXP-005"

    def __init__(self, invoice_number) -> None:
        title = "Invoice already in a pending expense"
        http_status = 409
        description = f"The invoice {invoice_number} of this supplier is already in an expense pending approval."
        translation = "Esta nota fiscal já está em um pedido pendente de aprovação."
        super().__init__(title, self.code, http_status, description, translation)


# ────────────────────────────────────────────────────────────────
# CRD
# ────────────────────────────────────────────────────────────────
class NotFoundLoan(QIException):
    code = "PDK-CRD-001"

    def __init__(self, loan_key) -> None:
        title = "Loan not Found"
        http_status = 404
        description = f"Loan with key {loan_key} was not found."
        translation = f"O crédito com chave {loan_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class CreditLimitExceeded(QIException):
    code = "PDK-CRD-002"

    def __init__(self, amount, available_limit) -> None:
        title = "Credit limit exceeded"
        http_status = 409
        description = f"The amount ({amount}) exceeds the available credit limit ({available_limit})."
        translation = "O valor pedido está acima do limite de crédito disponível."
        super().__init__(title, self.code, http_status, description, translation)


class LateInstallmentBlocksLoan(QIException):
    code = "PDK-CRD-003"

    def __init__(self) -> None:
        title = "Late installment blocks new loans"
        http_status = 409
        description = "The account has a late installment, and cannot take a new loan until it is paid."
        translation = "Há parcela em atraso: quite-a antes de contratar novo crédito."
        super().__init__(title, self.code, http_status, description, translation)

# ────────────────────────────────────────────────────────────────
# sample_entity — o molde do base-service, com os códigos originais
# ────────────────────────────────────────────────────────────────
class NotFoundSampleEntity(QIException):
    code = "QIT001001"

    def __init__(self, sample_entity_key) -> None:
        title = "Entity not Found"
        http_status = 404
        description = f"Entity with key {sample_entity_key} was not found."
        translation = f"A entidade com chave {sample_entity_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class SampleEntityFinalStatus(QIException):
    code = "QIT001002"

    def __init__(self, old_status, new_status) -> None:
        title = "Entity cannot change status"
        http_status = 409
        description = f"Entity with status {old_status} cannot update to {new_status}."
        translation = "Essa entidade não pode ser atualizada."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidDocumentNumber(QIException):
    """O CPF tem o formato certo e não existe.

    422, e não 400, de propósito: 400 quer dizer "não consegui ler o seu
    pedido". Aqui a API leu, entendeu, e o valor é que não pode existir —
    os dois últimos dígitos não batem com a conta. A diferença está
    explicada em src/utils/document_number.py.
    """

    code = "QIT001003"

    def __init__(self, document_number) -> None:
        title = "Invalid Document Number"
        http_status = 422
        description = f"The document number {document_number} is not a valid CPF."
        translation = "O CPF informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedDocumentNumber(QIException):
    """Já existe um cadastro com este CPF.

    409 Conflict: o pedido está correto em si, e o que impede é o que já
    está no banco. É a mesma família do SampleEntityFinalStatus aqui em
    cima — conflito com o que já existe, não erro de quem pediu.
    """

    code = "QIT001004"

    def __init__(self, document_number) -> None:
        title = "Document Number already registered"
        http_status = 409
        description = f"There is already an entity with the document number {document_number}."
        translation = "Já existe um cadastro com este CPF."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedEmail(QIException):
    code = "QIT001005"

    def __init__(self, email) -> None:
        title = "Email already registered"
        http_status = 409
        description = f"There is already an entity with the email {email}."
        translation = "Já existe um cadastro com este e-mail."
        super().__init__(title, self.code, http_status, description, translation)


class UnderageSampleEntity(QIException):
    code = "QIT001006"

    def __init__(self, age, minimum_age) -> None:
        title = "Entity is underage"
        http_status = 422
        description = f"The entity is {age} years old, and the minimum is {minimum_age}."
        translation = f"É preciso ter pelo menos {minimum_age} anos."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidBirthdate(QIException):
    """A data tem o formato certo e não existe no calendário.

    Existe porque o `pattern` do schema sabe contar dígitos, não dias:
    "2025-02-30" e "9999-99-99" passam pelo regex e morrem no
    `date.fromisoformat`. Sem esta classe, esse ValueError virava 500 —
    a API culpando a si mesma por um erro de quem chamou.
    """

    code = "QIT001007"

    def __init__(self, birthdate) -> None:
        title = "Invalid Birthdate"
        http_status = 422
        description = f"The birthdate {birthdate} is not a real date."
        translation = "A data de nascimento informada não existe."
        super().__init__(title, self.code, http_status, description, translation)
