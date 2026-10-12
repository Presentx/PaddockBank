CPF_LENGTH = 11

CHECK_DIGIT_POSITIONS = [9, 10]


def is_valid_cpf(document_number: str) -> bool:
    """Diz se um CPF existe de verdade — não se ele tem a cara certa.

    O schema em src/schemas/post_sample_entity.json já cobrou o formato:
    três pontos, um hífen, onze dígitos. Isto aqui é outra pergunta, e a
    diferença entre as duas é a lição deste arquivo.

    Os dois últimos dígitos de um CPF não são escolhidos: eles são o
    RESULTADO de uma conta feita sobre os nove primeiros. Por isso um
    número pode ter o formato perfeito e não existir — "111.222.333-44"
    passa no schema e não passa aqui.

    É o mesmo motivo pelo qual a resposta dessa recusa é 422 e não 400:
    não é que a API não conseguiu ler o pedido; ela leu, entendeu, e o
    valor não pode existir.

    A conta, para cada um dos dois dígitos: multiplica cada dígito
    anterior por um peso que decresce, soma tudo, tira o resto da divisão
    por 11. Resto menor que 2 vira dígito 0; nos outros casos, o dígito é
    11 menos o resto.
    """
    digits = []
    for character in document_number:
        if character.isdigit():
            digits.append(int(character))

    if len(digits) != CPF_LENGTH:
        return False

    # Um CPF de dígitos todos iguais ("111.111.111-11") passa na conta
    # dos dígitos verificadores e mesmo assim não vale. São onze números
    # conhecidos, e a Receita não emite nenhum deles.
    all_digits_are_equal = True
    for digit in digits:
        if digit != digits[0]:
            all_digits_are_equal = False
            break

    if all_digits_are_equal:
        return False

    for position in CHECK_DIGIT_POSITIONS:
        total = 0
        first_weight = position + 1

        for index in range(position):
            total = total + digits[index] * (first_weight - index)

        remainder = total % 11

        if remainder < 2:
            expected_digit = 0
        else:
            expected_digit = 11 - remainder

        if digits[position] != expected_digit:
            return False

    return True


CNPJ_LENGTH = 14

# Os pesos da conta do CNPJ, lidos da direita pra esquerda: 2, 3, ... 9,
# e de novo 2, 3, ... Diferente do CPF, o peso nao so decresce: ele da a
# volta depois do 9.
CNPJ_FIRST_WEIGHTS = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
CNPJ_SECOND_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def is_valid_cnpj(document_number: str) -> bool:
    """Diz se um CNPJ existe de verdade — a mesma pergunta do is_valid_cpf.

    O schema (src/schemas/post_supplier.json) ja cobrou a mascara
    00.000.000/0000-00. Aqui se confere o que a mascara nao sabe: os
    dois ultimos digitos sao o RESULTADO de uma conta sobre os doze
    primeiros. Mascara certa com digitos errados e 422, nao 400.

    Isto NAO consulta a Receita Federal: um CNPJ que passa aqui pode nao
    estar ativo, ou nem ter sido emitido. Essa consulta esta fora do
    escopo — seria um connector, e a decisao sobre o que fazer com a
    resposta dele seria do controller.
    """
    digits = []
    for character in document_number:
        if character.isdigit():
            digits.append(int(character))

    if len(digits) != CNPJ_LENGTH:
        return False

    # Mesma armadilha do CPF: digitos todos iguais passam na conta e nao
    # sao um CNPJ.
    all_digits_are_equal = True
    for digit in digits:
        if digit != digits[0]:
            all_digits_are_equal = False
            break

    if all_digits_are_equal:
        return False

    for weights in [CNPJ_FIRST_WEIGHTS, CNPJ_SECOND_WEIGHTS]:
        total = 0

        for index in range(len(weights)):
            total = total + digits[index] * weights[index]

        remainder = total % 11

        if remainder < 2:
            expected_digit = 0
        else:
            expected_digit = 11 - remainder

        if digits[len(weights)] != expected_digit:
            return False

    return True
